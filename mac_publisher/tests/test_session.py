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
