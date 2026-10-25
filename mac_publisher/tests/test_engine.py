import json
from PIL import Image
import pytest
from xhs_publisher.bundle import load_bundle
from xhs_publisher.journal import Journal
from xhs_publisher.engine import publish
from xhs_publisher.adapter import Baseline,PublishError

def setup(tmp_path):
    root=tmp_path/'bundle';root.mkdir();Image.new('RGB',(64,64),'green').save(root/'1.png')
    (root/'manifest.json').write_text(json.dumps({'title':'一篇本地测试文案','body':'仅用于本地验证发布状态，不会发送到真实站点。','tags':[],'images':['1.png'],'ai_generated':True,'original_content':True}))
    return root,load_bundle(root)[2],Journal(tmp_path/'state')

class Adapter:
    clicks=0
    def open(self): pass
    def current_account(self):return '测试账号'
    def baseline(self):return Baseline(True,set())
    def prepare(self,*args):pass
    def verify(self,*args):pass
    def submit_once(self):self.clicks+=1
    def verify_result(self,*args):return {'state':'published','note_id':'a'*24,'note_url':'https://www.xiaohongshu.com/explore/'+'a'*24,'platform_status':'已发布'}

def test_verified_publication_and_no_duplicate(tmp_path):
    root,fp,journal=setup(tmp_path);adapter=Adapter()
    result=publish(adapter,journal,root,fp,'测试账号')
    assert result['state']=='published' and adapter.clicks==1
    assert publish(adapter,journal,root,fp,'测试账号')['id']==result['id']
    assert adapter.clicks==1

def test_timeout_after_click_never_allows_blind_retry(tmp_path):
    root,fp,journal=setup(tmp_path)
    class Broken(Adapter):
        def submit_once(self):self.clicks+=1;raise TimeoutError()
    adapter=Broken();result=publish(adapter,journal,root,fp,'测试账号')
    assert result['state']=='unknown'
    publish(adapter,journal,root,fp,'测试账号',retry_prepare=True)
    assert adapter.clicks==1

def test_wrong_account_never_clicks(tmp_path):
    root,fp,journal=setup(tmp_path);adapter=Adapter()
    assert publish(adapter,journal,root,fp,'其他账号')['state']=='blocked'
    assert adapter.clicks==0

def test_missing_receipt_is_not_success(tmp_path):
    root,fp,journal=setup(tmp_path)
    class NoReceipt(Adapter):
        def verify_result(self,*args):return {'state':'submitted_unverified'}
    adapter=NoReceipt()
    assert publish(adapter,journal,root,fp,'测试账号')['state']=='submitted_unverified'
    assert adapter.clicks==1


def test_login_failure_preserves_stage_and_local_screenshot(tmp_path):
    root,fp,journal=setup(tmp_path)
    class LoginFailure(Adapter):
        def open(self):raise PublishError('LOGIN_REQUIRED','需要登录')
        def screenshot(self,path):Image.new('RGB',(20,20),'white').save(path)
    adapter=LoginFailure();artifacts=tmp_path/'artifacts'
    result=publish(adapter,journal,root,fp,'测试账号',artifact_dir=artifacts)
    assert result['state']=='blocked' and adapter.clicks==0
    assert result['result']['stage']=='open_creator'
    assert result['result']['failure_screenshot']=='failure.png'
    assert (artifacts/'failure.png').is_file()


def test_one_approved_click_waits_for_login_then_submits_once(tmp_path):
    root,fp,journal=setup(tmp_path)
    class NeedsLogin(Adapter):
        logged=False
        waits=0
        def open(self):
            if not self.logged:raise PublishError('LOGIN_REQUIRED','请本人扫码')
        def wait_for_manual_login(self,account):
            assert account=='测试账号'
            self.waits+=1;self.logged=True
    adapter=NeedsLogin();result=publish(adapter,journal,root,fp,'测试账号')
    assert result['state']=='published' and adapter.waits==1 and adapter.clicks==1
    assert publish(adapter,journal,root,fp,'测试账号')['id']==result['id']
    assert adapter.clicks==1


def test_login_wait_material_changes_cannot_submit(tmp_path):
    root,fp,journal=setup(tmp_path)
    class Changed(Adapter):
        def open(self):raise PublishError('LOGIN_REQUIRED','请本人扫码')
        def wait_for_manual_login(self,account):
            Image.new('RGB',(64,64),'red').save(root/'1.png')
    adapter=Changed();result=publish(adapter,journal,root,fp,'测试账号')
    assert result['result']['code']=='MATERIAL_CHANGED' and adapter.clicks==0


def test_challenge_never_auto_resumes(tmp_path):
    root,fp,journal=setup(tmp_path)
    class Challenged(Adapter):
        def open(self):raise PublishError('PLATFORM_VERIFICATION','需要安全验证')
        def wait_for_manual_login(self,account):pytest.fail('Must stop on challenge')
    adapter=Challenged()
    assert publish(adapter,journal,root,fp,'测试账号')['state']=='blocked'
    assert adapter.clicks==0


def test_login_with_different_account_does_not_continue(tmp_path):
    root,fp,journal=setup(tmp_path)
    class WrongAccount(Adapter):
        logged=False
        def open(self):
            if not self.logged:raise PublishError('LOGIN_REQUIRED','请本人扫码')
        def wait_for_manual_login(self,account):self.logged=True
        def current_account(self):return '另一个账号'
    adapter=WrongAccount();result=publish(adapter,journal,root,fp,'测试账号')
    assert result['state']=='blocked' and adapter.clicks==0
