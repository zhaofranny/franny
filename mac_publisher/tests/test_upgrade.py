import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('stop_idle_browser',Path(__file__).parents[1]/'stop_idle_browser.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)


def test_only_matching_project_workers(tmp_path):
    base=tmp_path/'project'
    output=f'''12 python -m xhs_publisher.worker login --base {base}
13 python -m xhs_publisher.worker publish --base /other
14 python unrelated.py
15 python -m xhs_publisher.worker publish --base {base}
'''
    assert helper.matching_workers(output,base)==[(12,'login'),(15,'publish')]


def test_never_terminates_publication(tmp_path,monkeypatch):
    monkeypatch.setattr(helper.subprocess,'check_output',lambda *a,**k:f'123 python -m xhs_publisher.worker publish --base {tmp_path}')
    monkeypatch.setattr(helper.os,'kill',lambda *a:pytest.fail('Must not kill publication'))
    with pytest.raises(SystemExit,match='发布任务'):helper.stop_idle(tmp_path)


def test_only_idle_login_worker_terminated(tmp_path,monkeypatch):
    monkeypatch.setattr(helper.subprocess,'check_output',lambda *a,**k:f'123 python -m xhs_publisher.worker login --base {tmp_path}')
    killed=[];monkeypatch.setattr(helper.os,'kill',lambda pid,sig:killed.append(pid))
    helper.stop_idle(tmp_path)
    assert killed==[123]
