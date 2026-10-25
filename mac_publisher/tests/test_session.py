import os
import time
from types import SimpleNamespace
import pytest
from xhs_publisher.journal import Journal,atomic_json
from xhs_publisher.session import session_state,enqueue,run_session,SessionUnavailable


def test_closed_or_stale_session_cannot_queue(tmp_path):
    atomic_json(tmp_path/'browser_session.json',{'session':'old','pid':os.getpid(),'state':'ready','heartbeat':time.time()-20})
    assert not session_state(tmp_path)
    with pytest.raises(SessionUnavailable):enqueue(tmp_path,tmp_path/'bundle','hash','job')
    assert not (tmp_path/'requests').exists()


def test_handoff_never_serializes_cookie_or_creates_browser(tmp_path):
    atomic_json(tmp_path/'browser_session.json',{'session':'live','pid':os.getpid(),'state':'ready','heartbeat':time.time()})
    assert enqueue(tmp_path,tmp_path/'bundle','hash','job')==os.getpid()
    import json
    command=json.loads((tmp_path/'requests'/'live-job.json').read_text())
    assert set(command)=={'session','bundle','approved_hash','job_id','retry'}


def test_publish_uses_exact_login_adapter_once(tmp_path,monkeypatch):
    local=tmp_path/'.local';journal=Journal(local)
    job,_=journal.reserve('account','hash')
    token='session';monkeypatch.setattr('uuid.uuid4',lambda:SimpleNamespace(hex=token))
    atomic_json(local/'requests'/f'{token}-{job}.json',{'session':token,'bundle':'bundle','approved_hash':'hash','job_id':job})
    class Page:
        closed=False
        def is_closed(self):return self.closed
        def wait_for_timeout(self,ms): self.closed=True
    adapter=SimpleNamespace(page=Page());seen=[]
    def fake_publish(received,received_journal,*args,**kwargs):
        assert received is adapter and received_journal is journal
        seen.append(received)
        journal.update(job,'blocked',code='LOGIN_REQUIRED')
        return journal.get(job)
    monkeypatch.setattr('xhs_publisher.engine.publish',fake_publish)
    run_session(adapter,journal,tmp_path,'account')
    assert seen==[adapter]
    assert journal.get(job)['state']=='blocked'
    assert not list((local/'requests').glob('*'))
    assert session_state(local)['state']=='closed'


def test_old_session_queue_never_published(tmp_path,monkeypatch):
    local=tmp_path/'.local';journal=Journal(local);job,_=journal.reserve('account','hash')
    atomic_json(local/'requests'/f'old-{job}.json',{'session':'old','job_id':job})
    monkeypatch.setattr('uuid.uuid4',lambda:SimpleNamespace(hex='new'))
    class Page:
        closed=False
        def is_closed(self): return self.closed
        def wait_for_timeout(self,ms):self.closed=True
    monkeypatch.setattr('xhs_publisher.engine.publish',lambda *args,**kwargs:pytest.fail('stale task replayed'))
    run_session(SimpleNamespace(page=Page()),journal,tmp_path,'account')
    assert journal.get(job)['state']=='failed_pre_submit'


def test_focus_existing_session_does_not_enqueue_publish(tmp_path):
    from xhs_publisher.session import request_focus
    import json
    atomic_json(tmp_path/'browser_session.json',{'session':'live','pid':os.getpid(),'state':'ready','heartbeat':time.time()})
    assert request_focus(tmp_path)==os.getpid()
    command=json.loads(next((tmp_path/'requests').glob('*.json')).read_text())
    assert command=={'session':'live','action':'focus'}


def test_focus_request_brings_same_page_forward_without_publishing(tmp_path,monkeypatch):
    local=tmp_path/'.local';journal=Journal(local)
    monkeypatch.setattr('uuid.uuid4',lambda:SimpleNamespace(hex='live'))
    atomic_json(local/'requests'/'live-focus.json',{'session':'live','action':'focus'})
    class Page:
        closed=False
        focused=0
        def is_closed(self):return self.closed
        def wait_for_timeout(self,ms):self.closed=True
        def bring_to_front(self):self.focused+=1
    page=Page()
    monkeypatch.setattr('xhs_publisher.session.focus_browser',lambda p:p.bring_to_front())
    monkeypatch.setattr('xhs_publisher.engine.publish',lambda *a,**k:pytest.fail('focus must never publish'))
    run_session(SimpleNamespace(page=page),journal,tmp_path,'account')
    assert page.focused==1
    assert not journal.history()


def test_ui_existing_session_login_click_requests_focus(monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    import xhs_publisher.session as session
    requests=[]
    monkeypatch.setattr(session,'session_state',lambda _: {'state':'ready','pid':os.getpid(),'session':'live'})
    monkeypatch.setattr(session,'request_focus',lambda _:requests.append('focus') or os.getpid())
    app=AppTest.from_file(str(Path(__file__).parents[1]/'publisher_app.py'),default_timeout=15).run()
    next(b for b in app.button if b.label=='打开浏览器，手动登录').click().run()
    assert not app.exception
    assert requests==['focus']
    assert not any('正在启动独立浏览器' in message.value for message in app.info)
