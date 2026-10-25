"""Read normal, permitted, visible Xiaohongshu pages. No private API or hidden state."""
import math
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote,urljoin,urlsplit
from urllib.robotparser import RobotFileParser
from .journal import atomic_json

HOME='https://www.xiaohongshu.com'
FIELDS={
 'title':['#detail-title','.note-content .title','.note-scroller h1'],
 'body':['#detail-desc','.note-content .desc','.note-text'],
 'author':['.author-container .username','.author-wrapper .username'],
 'published_raw':['.note-content .date','.bottom-container .date','time'],
 'likes':['.interact-container .like-wrapper .count','.like-wrapper .count'],
 'saves':['.interact-container .collect-wrapper .count','.collect-wrapper .count'],
 'comments':['.interact-container .chat-wrapper .count','.chat-wrapper .count'],
}
class ResearchBlocked(ValueError):pass

def now():return datetime.now(timezone.utc).isoformat()

def note_url(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in {'xiaohongshu.com','www.xiaohongshu.com'} or p.username or p.password or p.port not in (None,443):
        raise ResearchBlocked('请使用浏览器展开后的完整小红书HTTPS笔记链接，不读取短链接或其他网站')
    m=re.fullmatch(r'/(?:explore|discovery/item|search_result)/([a-fA-F0-9]{24})/?',p.path)
    if not m:raise ResearchBlocked('无法识别原帖链接，请提供完整笔记地址')
    return HOME+'/explore/'+m[1].lower()

def count(raw):
    m=re.fullmatch(r'(\d+(?:\.\d+)?)\s*([万千wWkK]?)\+?',(raw or '').replace(',','').strip())
    if not m:return None
    value=float(m[1])*{'万':10000,'w':10000,'W':10000,'千':1000,'k':1000,'K':1000}.get(m[2],1)
    return int(value) if value<=10**12 and value.is_integer() else None

def visible(page,selectors):
    for css in selectors:
        for item in page.locator(css).all()[:30]:
            if item.is_visible():
                text=item.inner_text(timeout=2000).strip()
                if text:return text
    return None

def guard(page):
    p=urlsplit(page.url)
    if p.hostname not in {'www.xiaohongshu.com','xiaohongshu.com'}:raise ResearchBlocked('页面跳转到非笔记站点，已停止')
    text=page.locator('body').inner_text(timeout=5000)
    if any(t in text for t in ['请完成安全验证','访问频繁','访问异常','异常访问','操作频繁','验证码验证','安全验证']):
        raise ResearchBlocked('遇到平台验证或访问限制，已停止，未绕过')
    if 'login' in p.path.lower() or any(t in text for t in ['登录后查看','登录后可查看']):
        raise ResearchBlocked('笔记站需要本人登录；创作者平台登录不等于笔记站登录，请在笔记页手动处理后明确重试')
    for css in ['.login-modal','.login-mask','.login-container']:
        if any(el.is_visible() for el in page.locator(css).all()):raise ResearchBlocked('笔记页显示登录弹窗，已停止；请本人手动登录后重试')
    if any(t in text for t in ['笔记不存在','笔记已删除','内容无法展示']):raise ResearchBlocked('原帖不存在或当前不可访问，未保存为成功结果')

def extract(page,url):
    values={name:visible(page,css) for name,css in FIELDS.items()}
    samples=[]
    for el in page.locator('.comments-container .comment-item .content,.comments-container .comment-item .note-text').all()[:50]:
        if el.is_visible():
            text=el.inner_text(timeout=2000).strip()
            if text and text not in samples:samples.append(text[:500])
        if len(samples)>=20:break
    published=None
    match=re.search(r'(?<!\d)(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})(?:日)?',values['published_raw'] or '')
    if match:
        from datetime import date
        try:published=date(int(match[1]),int(match[2]),int(match[3])).isoformat()
        except ValueError:pass
    raw={k:values[k] for k in ['likes','saves','comments']}
    result={**values,'url':note_url(url),'source_url':url,'published_at':published,'counts_raw':raw,'collected_at':now(),'comment_samples':samples,'comments_basis':'仅当前可见评论，未读取全部评论','origin':'visible_dom'}
    result.update({k:count(v) for k,v in raw.items()})
    result['missing_fields']=[k for k in ['title','body','author','published_at','likes','saves','comments'] if result.get(k) is None]
    return result

def rank(records):
    # Relative to this collected sample only, never a platform-wide viral ranking.
    def score(n):
        counts=[n.get(k) for k in ['likes','saves','comments']]
        if all(v is None for v in counts):return None
        return (counts[0] or 0)+2*(counts[1] or 0)+3*(counts[2] or 0)
    return sorted([{**n,'observed_weighted_interactions':score(n)} for n in records],key=lambda n:-(n['observed_weighted_interactions'] if n['observed_weighted_interactions'] is not None else -1))

def reference_summary(records):
    blocks=[]
    for n in records[:3]:
        if n.get('origin')!='visible_dom' or not n.get('body'):continue
        body=n['body'][:350]
        comments='；'.join(c[:60] for c in n.get('comment_samples',[])[:2])
        blocks.append('【公开参考，不是本人记录；观点未经医学核实】\n标题：'+(n.get('title') or '缺失')[:60]+'\n正文必要片段：'+body+'\n当前可见评论片段：'+(comments or '缺失，不推断评论区反馈'))
    if not blocks:raise ResearchBlocked('没有真实读取到的正文，不能生成参考摘要')
    return '\n\n'.join(blocks)[:2000]

def collect(context,base,keyword='减肥邪修',urls=None,limit=5,permitted=False):
    base=Path(base);local=base/'.local';run=uuid.uuid4().hex
    report={'run_id':run,'state':'running','started_at':now(),'collected':0,'attempted':0,'keyword':keyword,'message':'正在读取正常页面可见内容','files':[]}
    def status():
        atomic_json(local/'research_status.json',report)
        atomic_json(local/'research'/'runs'/run/'report.json',report)
    status();page=None;success=False
    try:
        if not permitted:raise ResearchBlocked('请先确认平台允许本次自动化读取并拥有数据使用权')
        if not 1<=limit<=30 or not 1<=len(keyword)<=60:raise ResearchBlocked('读取数量须为1–30，关键词须为1–60字')
        urls=urls or []
        if len(urls)>30:raise ResearchBlocked('原帖链接最多30条')
        for url in urls:note_url(url)
        response=context.request.get(HOME+'/robots.txt',timeout=15000)
        if response.status==404:policy='User-agent: *\nAllow: /'
        elif response.status==200:
            policy=response.text()
            if not re.search(r'(?mi)^\s*user-agent\s*:',policy):raise ResearchBlocked('公开robots响应无法识别，未开始读取笔记')
        else:raise ResearchBlocked('无法确认公开robots政策，未开始读取笔记')
        robot=RobotFileParser();robot.parse(policy.splitlines())
        existing=[p for p in context.pages if not p.is_closed() and urlsplit(p.url).hostname in {'www.xiaohongshu.com','xiaohongshu.com'}]
        if len(existing)>1:raise ResearchBlocked('请只保留一个笔记站标签页，避免读取错误页面')
        page=existing[0] if existing else context.new_page()
        search=HOME+'/search_result?keyword='+quote(keyword)+'&source=web_explore_feed'
        targets=list(urls)
        if not targets:
            if not robot.can_fetch('*',search):raise ResearchBlocked('公开robots政策不允许自动读取检索页，未继续；可使用有权提供的参考摘要')
            r=page.goto(search,wait_until='domcontentloaded',timeout=30000)
            if r and r.status>=400:raise ResearchBlocked('检索页面访问失败，未继续')
            page.wait_for_timeout(2000);guard(page)
            for a in page.locator('a[href]').all():
                if not a.is_visible():continue
                href=urljoin(HOME,a.get_attribute('href') or '')
                try:canonical=note_url(href)
                except ResearchBlocked:continue
                if canonical not in {note_url(u) for u in targets}:targets.append(href)
                if len(targets)>=limit:break
        seen=set()
        for url in targets:
            if report['collected']>=limit:break
            canonical=note_url(url)
            if canonical in seen:continue
            seen.add(canonical)
            if not robot.can_fetch('*',url):raise ResearchBlocked('公开robots政策不允许读取该笔记，已停止')
            report['attempted']+=1;status()
            r=page.goto(url,wait_until='domcontentloaded',timeout=30000)
            if r and r.status>=400:raise ResearchBlocked('笔记页面访问失败，已停止，未伪造成功')
            deadline=time.monotonic()+8
            while True:
                guard(page)
                if visible(page,FIELDS['title']) and visible(page,FIELDS['body']):break
                if time.monotonic()>=deadline:break
                page.wait_for_timeout(500)
            record=extract(page,url)
            if not record.get('title') or not record.get('body'):continue
            file=local/'research'/'runs'/run/'notes'/(canonical.rsplit('/',1)[-1]+'.json')
            atomic_json(file,record);report['files'].append(str(file));report['collected']+=1;status()
            page.wait_for_timeout(2000)
        report['state']='completed' if report['collected']>=limit else 'partial'
        report['message']='已读取真实可见笔记；高互动仅按本次样本排序，缺失数据不估计' if report['collected'] else '未读取到可用正文，未生成虚构参考；可由你提供合法摘要'
        success=True
    except ResearchBlocked as exc:report.update(state='blocked',message=str(exc))
    except Exception:report.update(state='blocked',message='浏览器或网络读取失败，已停止；没有使用模拟正文补齐')
    finally:
        report['ended_at']=now();status()
        if page and not success:
            try:page.bring_to_front()
            except Exception:pass
    return report
