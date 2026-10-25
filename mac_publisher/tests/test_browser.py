import shutil
from pathlib import Path
from PIL import Image
import pytest
from playwright.sync_api import sync_playwright
from xhs_publisher.adapter import BrowserAdapter,PublishError
from xhs_publisher.bundle import Manifest

HTML='''<html><body><div class="user-name">本地测试账号</div><input type="file" accept="image/png" multiple><div class="img-preview-area"></div><input placeholder="填写标题"><div class="ql-editor" contenteditable="true"></div><label data-testid="ai-declaration"><input type="checkbox">AI生成</label><div class="publish-page-publish-btn"><button onclick="document.body.dataset.clicks=String(Number(document.body.dataset.clicks||0)+1)">发布</button></div><script>document.querySelector('input[type=file]').addEventListener('change',e=>{const area=document.querySelector('.img-preview-area');area.innerHTML='';for(const f of e.target.files){const d=document.createElement('div');d.className='pr';d.textContent=f.name;area.append(d)}});</script></body></html>'''

@pytest.fixture
def context():
    executable=shutil.which('chromium')
    with sync_playwright() as p:
        if not executable and not Path(p.chromium.executable_path).exists():pytest.skip('No installed browser')
        b=p.chromium.launch(headless=True,executable_path=executable)
        ctx=b.new_context();ctx.set_offline(True)
        try: yield ctx
        finally: ctx.close();b.close()

def test_real_chromium_upload_fill_and_single_click(context,tmp_path):
    requests=[];context.on('request',lambda r:requests.append(r.url))
    class FixtureAdapter(BrowserAdapter):
        def navigate(self,page,url):page.set_content(HTML)
    adapter=FixtureAdapter(context,timeout=2)
    path=tmp_path/'test.png';Image.new('RGB',(80,100),'green').save(path)
    manifest=Manifest(title='仅本地测试',body='这是合成页面上的文案，不会发布到小红书。',tags=[],images=['test.png'],ai_generated=True,original_content=True)
    adapter.prepare(manifest,[path]);adapter.verify(manifest,1)
    assert adapter.current_account()=='本地测试账号'
    adapter.submit_once()
    assert adapter.page.locator('body').get_attribute('data-clicks')=='1'
    with pytest.raises(PublishError):adapter.submit_once()
    assert not requests

def test_verification_screen_stops_browser(context):
    adapter=BrowserAdapter(context);adapter.page.set_content('<body>请完成安全验证</body>')
    with pytest.raises(PublishError) as err:adapter.guard()
    assert err.value.code=='PLATFORM_VERIFICATION'


def test_header_name_without_legacy_css_and_delayed_render(context):
    adapter=BrowserAdapter(context)
    adapter.page.set_content('''<html><body><nav>首页 笔记管理 发布笔记</nav><div style="position:fixed;right:40px;top:20px" id="account"></div><script>setTimeout(()=>{document.getElementById('account').textContent='ins审美搬运小工'},300)</script></body></html>''')
    adapter.verify_account('ins审美搬运小工',timeout=2)
    assert adapter.current_account()=='ins审美搬运小工'
    assert adapter.submits==0


def test_body_mention_does_not_verify_account(context):
    adapter=BrowserAdapter(context)
    adapter.page.set_content('<body><div style="position:fixed;right:40px;top:20px">另一个账号</div><div style="margin-top:200px">ins审美搬运小工</div></body>')
    with pytest.raises(PublishError) as exc: adapter.verify_account('ins审美搬运小工',timeout=0)
    assert exc.value.code=='ACCOUNT_MISMATCH'
    assert adapter.submits==0


def test_missing_account_is_distinct_from_mismatch(context):
    adapter=BrowserAdapter(context);adapter.page.set_content('<body><div>首页</div></body>')
    with pytest.raises(PublishError) as exc: adapter.verify_account('ins审美搬运小工',timeout=0)
    assert exc.value.code=='ACCOUNT_NAME_UNREADABLE'
