"""Visible, normal browser operations only. No injected stealth, DOM removal or private APIs."""
import re
import time
from dataclasses import dataclass,field
from urllib.parse import urlsplit
from .config import DEFAULTS

HOME='https://creator.xiaohongshu.com/'
PUBLISH=HOME+'publish/publish?source=official&target=image'

class PublishError(RuntimeError):
    def __init__(self,code,message): self.code=code;super().__init__(message)

@dataclass
class Baseline:
    verified: bool=False
    ids: set[str]=field(default_factory=set)


def norm(text): return re.sub(r'\s+',' ',text.replace('\xa0',' ')).strip()

def visible_one(root,selectors):
    for css in selectors:
        candidates=[x for x in root.locator(css).all() if x.is_visible()]
        if len(candidates)==1: return candidates[0]
    return None

class BrowserAdapter:
 def __init__(self,context,selectors=None,timeout=45):
    self.context=context;self.selectors=selectors or DEFAULTS;self.timeout=timeout
    self.page=context.new_page();self.submits=0
 def navigate(self,page,url):
    if urlsplit(url).hostname!='creator.xiaohongshu.com': raise PublishError('HOST_DENIED','只操作小红书官方创作者平台')
    response=page.goto(url,wait_until='domcontentloaded',timeout=30000)
    if response and response.status>=400: raise PublishError('PLATFORM_HTTP_DENIED','创作者平台返回访问错误，已停止')
    page.wait_for_timeout(1000);self.guard(page)
 def guard(self,page=None):
    page=page or self.page
    if 'login' in urlsplit(page.url).path.lower(): raise PublishError('LOGIN_REQUIRED','登录已失效，请先手动登录')
    text=page.locator('body').inner_text(timeout=5000)
    if any(x in text for x in ['请完成安全验证','访问频繁','操作频繁','异常访问','安全验证']):
        raise PublishError('PLATFORM_VERIFICATION','遇到平台验证或风控，已暂停；请自行检查官方页面，不自动处理验证码')
    for css in ['.login-modal','.login-container','.captcha-container']:
        if any(x.is_visible() for x in page.locator(css).all()):
            raise PublishError('LOGIN_OR_VERIFICATION','需要手动登录或验证，已停止自动操作')
 def _header_names(self,page):
    # Read only rendered DOM in the top-right account area. No private API/state.
    return page.locator('body').evaluate(r"""body => {
      const names = new Set();
      for (const el of body.querySelectorAll('span,a,p,div')) {
        if (el.children.length) continue;
        const r=el.getBoundingClientRect();
        const style=getComputedStyle(el);
        if (r.width<=0 || r.height<=0 || r.top<0 || r.bottom>85 || r.left<innerWidth*.65 || style.visibility==='hidden' || style.display==='none' || style.opacity==='0') continue;
        const text=(el.innerText||'').replace(/\s+/g,' ').trim();
        if (text && text.length<=80 && !['登录','注册','消息','帮助','反馈','退出登录'].includes(text)) names.add(text);
      }
      return [...names];
    }""")
 def current_account(self,page=None):
    page=page or self.page;self.guard(page)
    names=self._header_names(page)
    if len(names)==1: return names[0]
    found=set()
    for css in self.selectors['account']:
        for el in page.locator(css).all():
            if el.is_visible():
                name=norm(el.inner_text(timeout=2000))
                if name and len(name)<=80 and name not in {'登录','注册'}: found.add(name)
    return next(iter(found)) if len(found)==1 else None
 def verify_account(self,expected,timeout=15):
    deadline=time.monotonic()+timeout
    observed=None
    while True:
        observed=self.current_account()
        if observed==norm(expected): return
        if time.monotonic()>=deadline: break
        self.page.wait_for_timeout(250)
    if observed:
        raise PublishError('ACCOUNT_MISMATCH','页面识别到的账号与绑定账号不同，尚未提交；请核对右上角账号')
    raise PublishError('ACCOUNT_NAME_UNREADABLE','已打开官方页面，但15秒内未能唯一识别账号名称；请保留页面以适配，尚未提交')
 def open(self): self.navigate(self.page,HOME)
 def _manager(self):
    page=self.context.new_page()
    try:
        self.navigate(page,HOME)
        link=None
        for label in ['笔记管理','内容管理','作品管理']:
            matches=page.get_by_text(label,exact=True)
            for el in matches.all():
                if el.is_visible(): link=el;break
            if link: break
        if not link: return page,False
        link.click(timeout=5000);page.wait_for_timeout(1500);self.guard(page)
        return page,True
    except Exception:
        page.close();raise
 def _records(self,page):
    for css in self.selectors['cards']:
        cards=[x for x in page.locator(css).all() if x.is_visible()]
        if not cards: continue
        records=[]
        for card in cards[:30]:
            title_el=visible_one(card,self.selectors['card_title']);status_el=visible_one(card,self.selectors['card_status'])
            title=norm(title_el.inner_text()) if title_el else None
            status=norm(status_el.inner_text()) if status_el else None
            note_id=card.get_attribute('data-note-id')
            if not note_id:
                for a in card.locator('a[href]').all():
                    href=a.get_attribute('href') or ''
                    match=re.search(r'(?:/explore/|/discovery/item/)([a-f0-9]{24})(?:[/?#]|$)',href,re.I)
                    if match: note_id=match[1].lower();break
            if note_id and re.fullmatch(r'[a-f0-9]{24}',note_id,re.I) and title:
                records.append({'id':note_id.lower(),'title':title,'status':status})
        return records,True if records else False
    text=page.locator('body').inner_text()
    return [],any(x in text for x in ['暂无笔记','还没有发布笔记','暂无作品'])
 def baseline(self):
    page,found=self._manager()
    try:
        if not found: return Baseline()
        records,verified=self._records(page)
        return Baseline(verified,{x['id'] for x in records})
    finally: page.close()
 def _editor(self,key):
    el=visible_one(self.page,self.selectors[key])
    if not el: raise PublishError('UI_CHANGED_'+key.upper(),'未找到唯一可见的'+key+'控件，请适配页面选择器；尚未提交')
    return el
 def upload_files(self,files):
    deadline=time.monotonic()+min(self.timeout,15)
    paths=[str(p) for p in files]
    while True:
        self.guard()
        # The visible button selects its actual input, even when old/hidden inputs coexist.
        buttons=[x for x in self.page.get_by_text('上传图片',exact=True).all() if x.is_visible()]
        if len(buttons)==1:
            try:
                with self.page.expect_file_chooser(timeout=5000) as event:
                    buttons[0].click(timeout=5000)
                chooser=event.value
                if len(files)>1 and not chooser.is_multiple():
                    raise PublishError('UPLOAD_MULTIPLE_UNSUPPORTED','当前图片选择框不支持多图，本次未上传或提交')
                accept=(chooser.element.get_attribute('accept') or '').lower()
                if accept and not any(t in accept for t in ['image','.png','.jpg','.jpeg','.webp','*/*']):
                    raise PublishError('UPLOAD_WRONG_TYPE','按钮对应的文件框不接受图片，本次未上传或提交')
                chooser.set_files(paths)
                return
            except PublishError: raise
            except Exception:
                raise PublishError('UPLOAD_CHOOSER_NOT_OPENED','点击上传图片后未取得文件选择事件，请保留页面检查；尚未提交') from None
        # Older layouts expose a unique image input without a visible upload button.
        for css in ['input[type="file"][accept*="image"]','input[type="file"][accept*=".png"]','input[type="file"][accept*=".jpg"]',*self.selectors['upload']]:
            matches=self.page.locator(css)
            if matches.count()!=1: continue
            candidate=matches.first
            accept=(candidate.get_attribute('accept') or '').lower()
            if accept and not any(t in accept for t in ['image','.png','.jpg','.jpeg','.webp','*/*']): continue
            if candidate.is_disabled(): continue
            if len(files)>1 and candidate.get_attribute('multiple') is None: continue
            candidate.set_input_files(paths)
            return
        if time.monotonic()>=deadline:
            raise PublishError('UPLOAD_CONTROL_MISSING','等待后仍无法确认图片上传按钮或唯一图片文件框，尚未提交')
        self.page.wait_for_timeout(250)
 def prepare(self,manifest,files):
    self.navigate(self.page,PUBLISH)
    tabs=self.page.get_by_text('上传图文',exact=True)
    for tab in tabs.all():
        if tab.is_visible(): tab.click(timeout=5000);break
    self.upload_files(files)
    deadline=time.monotonic()+self.timeout
    while time.monotonic()<deadline:
        self.guard()
        if '上传失败' in self.page.locator('body').inner_text(): raise PublishError('UPLOAD_FAILED','图片上传失败，尚未提交')
        if self.image_count()==len(files) and not self.upload_pending(): break
        self.page.wait_for_timeout(500)
    else: raise PublishError('UPLOAD_NOT_CONFIRMED','未核验全部图片上传完成，尚未提交')
    self._editor('title').fill(manifest.title)
    self._editor('body').fill(manifest.body)
    for tag in manifest.tags: self._tag(tag)
    self._declaration(['AI生成','AI内容','含AI'],self.selectors['ai_toggle'],manifest.ai_generated,manifest.ai_generated)
    self._declaration(['原创声明','声明原创'],self.selectors['original_toggle'],manifest.original_content,False)
 def image_count(self):
    for css in self.selectors['previews']:
        items=[x for x in self.page.locator(css).all() if x.is_visible()]
        if items: return len(items)
    return 0
 def upload_pending(self):
    return any(x.is_visible() for x in self.page.locator('.uploading,.upload-progress,[data-upload-state="uploading"]').all())
 def selected_topics(self):
    result=[]
    for css in self.selectors['selected_topics']:
        for x in self.page.locator(css).all():
            if x.is_visible():
                text=norm(x.inner_text()).lstrip('#')
                if text and text not in result: result.append(text)
    return result
 def _tag(self,tag):
    editor=self._editor('body');editor.press('ControlOrMeta+End');editor.press('Enter');editor.type('#'+tag,delay=30)
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        self.guard()
        for css in self.selectors['topic_options']:
            for option in self.page.locator(css).all():
                if option.is_visible() and norm(option.inner_text()).lstrip('#')==tag:
                    option.click(timeout=3000)
                    if tag not in self.selected_topics(): raise PublishError('TOPIC_NOT_VERIFIED','已点击话题但未核验关联结果，尚未提交')
                    return
        self.page.wait_for_timeout(250)
    raise PublishError('TOPIC_NOT_FOUND','未找到准确匹配的话题选项，尚未提交；不把普通#文本冒充平台话题')
 def _control(self,labels,selectors):
    direct=visible_one(self.page,selectors)
    if direct: return direct
    for role in ['checkbox','switch']:
        items=self.page.get_by_role(role,name=re.compile('|'.join(labels)))
        visible=[x for x in items.all() if x.is_visible()]
        if len(visible)==1: return visible[0]
    return None
 def _declaration(self,labels,selectors,value,required):
    control=self._control(labels,selectors)
    if not control:
        if required: raise PublishError('AI_DECLARATION_NOT_VERIFIED','未找到可核验的AI声明控件，请检查平台要求并适配；尚未提交')
        return
    if control.is_checked()!=value: control.set_checked(value,timeout=3000)
    if control.is_checked()!=value: raise PublishError('DECLARATION_NOT_VERIFIED','声明状态未核验，尚未提交')
 def verify(self,manifest,expected_count):
    self.guard()
    if self.image_count()!=expected_count or self.upload_pending(): raise PublishError('IMAGE_COUNT_MISMATCH','图片数量或上传状态不一致，尚未提交')
    if self._editor('title').input_value()!=manifest.title: raise PublishError('TITLE_MISMATCH','页面标题与已确认素材不一致，尚未提交')
    if self.selected_topics()!=manifest.tags: raise PublishError('TAGS_MISMATCH','页面话题或顺序不符，尚未提交')
    actual=norm(self._editor('body').inner_text())
    for tag in reversed(manifest.tags):
        suffix='#'+tag
        if actual.endswith(suffix): actual=actual[:-len(suffix)].rstrip()
    if actual!=norm(manifest.body): raise PublishError('BODY_MISMATCH','页面正文与已确认素材不一致，尚未提交')
    if manifest.ai_generated:
        control=self._control(['AI生成','AI内容','含AI'],self.selectors['ai_toggle'])
        if not control or not control.is_checked(): raise PublishError('AI_DECLARATION_NOT_VERIFIED','AI声明未核验，尚未提交')
 def submit_once(self):
    self.guard()
    if self.submits: raise PublishError('DUPLICATE_SUBMIT','同一浏览器任务不会再次点击发布')
    button=visible_one(self.page,self.selectors['publish'])
    if not button:
        candidates=[x for x in self.page.get_by_role('button',name='发布',exact=True).all() if x.is_visible()]
        button=candidates[0] if len(candidates)==1 else None
    if not button or not button.is_enabled() or norm(button.inner_text()) not in {'发布','发布笔记','立即发布'}:
        raise PublishError('PUBLISH_BUTTON_NOT_READY','发布按钮不可确认，提交状态未知，请勿盲目重试')
    self.submits+=1
    button.click(timeout=10000)
 def verify_result(self,manifest,baseline):
    # Read-only checks. A button click or success toast alone never means published.
    for wait in [1500,4000,8000]:
        self.page.wait_for_timeout(wait)
        self.guard()
        page,found=self._manager()
        try:
            if not found: continue
            records,valid=self._records(page)
            if not valid or not baseline.verified: continue
            matches=[r for r in records if r['id'] not in baseline.ids and r['title']==norm(manifest.title)]
            if len(matches)!=1: continue
            record=matches[0];status=record['status'] or ''
            if any(x in status for x in ['未通过','不通过','失败']): state='rejected'
            elif any(x in status for x in ['审核中','待审核','发布中']): state='pending_review'
            elif status=='已发布': state='published'
            else: continue
            return {'state':state,'note_id':record['id'],'note_url':'https://www.xiaohongshu.com/explore/'+record['id'],'platform_status':status}
        finally: page.close()
    return {'state':'submitted_unverified','message':'已执行一次提交，但没有取得新笔记ID及明确状态；请到创作者平台核对，禁止自动重发'}
 def screenshot(self,path): self.page.screenshot(path=str(path),full_page=True)
