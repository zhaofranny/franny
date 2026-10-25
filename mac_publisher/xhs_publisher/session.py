"""Local file handoff to the SAME browser process. No cookies exported."""
import json
import os
import time
from pathlib import Path
from .journal import atomic_json

class SessionUnavailable(ValueError): pass

def session_state(local):
    try:
        state=json.loads((Path(local)/'browser_session.json').read_text())
        if time.time()-state['heartbeat']>8 or state['heartbeat']>time.time()+2: return {}
        os.kill(int(state['pid']),0)
        return state
    except (OSError,ValueError,KeyError,TypeError): return {}

def enqueue(local,bundle,approved_hash,job_id,retry=False):
    state=session_state(local)
    if state.get('state')!='ready':
        raise SessionUnavailable('独立浏览器尚未就绪或正在执行任务。请到①登录并保持该窗口打开，不必重新生成素材。')
    request={'session':state['session'],'bundle':str(Path(bundle).resolve()),'approved_hash':approved_hash,'job_id':job_id,'retry':retry}
    atomic_json(Path(local)/'requests'/(state['session']+'-'+job_id+'.json'),request)
    return state['pid']

def request_focus(local):
    import uuid
    state=session_state(local)
    if state.get('state') not in {'ready','busy'}:
        raise SessionUnavailable('没有可唤起的浏览器会话，请先打开浏览器登录')
    atomic_json(Path(local)/'requests'/(state['session']+'-focus'+uuid.uuid4().hex+'.json'),{'session':state['session'],'action':'focus'})
    return state['pid']

def focus_browser(page):
    import sys
    import subprocess
    page.bring_to_front()
    # Playwright activates the tab; macOS also needs application activation.
    if sys.platform=='darwin':
        application='org.chromium.Chromium' if not os.getenv('XHS_BROWSER_PATH') else 'com.google.Chrome'
        result=subprocess.run(['osascript','-e','tell application id "'+application+'" to activate'],capture_output=True,timeout=5)
        if result.returncode: raise SessionUnavailable('macOS未能切到浏览器前台，请按Control+上箭头查找独立Chrome窗口')


def run_session(adapter,journal,base,account):
    import uuid
    base=Path(base);local=base/'.local';token=uuid.uuid4().hex
    queue=local/'requests';queue.mkdir(exist_ok=True);queue.chmod(0o700)
    def status(state):
        atomic_json(local/'browser_session.json',{'session':token,'pid':os.getpid(),'state':state,'heartbeat':time.time()})
    # Old sessions cannot replay requests; safely release only never-submitted reservations.
    for path in queue.glob('*.json'):
        if path.name.startswith(token+'-'): continue
        job_id=path.stem.split('-',1)[-1];job=journal.get(job_id)
        if job and job['state']=='preparing': journal.update(job_id,'failed_pre_submit',code='SESSION_REPLACED',message='原浏览器会话已结束，旧排队任务未提交；需明确确认后重试')
        path.unlink(missing_ok=True)
    try:
        while not adapter.page.is_closed():
            status('ready')
            for path in sorted(queue.glob(token+'-*.json')):
                processing=path.with_suffix('.processing')
                path.replace(processing)  # Claimed requests are never replayed after crashes.
                try:
                    request=json.loads(processing.read_text())
                    if request.get('session')!=token: continue
                    if request.get('action')=='focus':
                        try:
                            focus_browser(adapter.page)
                            atomic_json(local/'login_status.json',{'state':'logged_in','message':'已请求将现有小红书窗口切到前台，不会重复启动浏览器'})
                        except Exception:
                            atomic_json(local/'login_status.json',{'state':'focus_failed','message':'窗口仍在运行，但未能切到前台；请按Control+上箭头，选择小红书创作服务平台窗口'})
                        continue
                    job=journal.get(request.get('job_id',''))
                    if not job or job['state']!='preparing' or job['account']!=account: continue
                    status('busy')
                    from .engine import publish
                    result=publish(adapter,journal,request['bundle'],request['approved_hash'],account,job_id=job['id'],retry_prepare=bool(request.get('retry')),artifact_dir=base/'output'/job['id'])
                    atomic_json(base/'output'/job['id']/'result.json',result)
                    journal.update(job['id'],result['state'],browser_message='使用登录时的同一浏览器会话；任务已结束，窗口保留。不会自动重发。')
                except Exception:
                    # Durable submitting boundary still forbids retry if task reached click.
                    job_id=processing.stem.split('-',1)[-1]
                    job=journal.get(job_id)
                    if job and job['state'] in {'preparing','ready'}:
                        journal.update(job_id,'failed_pre_submit',code='SESSION_TASK_ERROR',message='本机会话任务处理失败，尚未提交；不显示原始异常')
                    elif job and job['state'] in {'submitting','submitted_unverified'}:
                        journal.update(job_id,'unknown',code='SESSION_TASK_ERROR',message='任务结果不明，请先核对官方后台，禁止盲目重发')
                finally: processing.unlink(missing_ok=True)
            adapter.page.wait_for_timeout(500)
    finally:
        status('closed')
        # Never leave a queued reservation stuck when this session closes.
        for path in queue.glob(token+'-*.json'):
            job_id=path.stem.split('-',1)[-1];job=journal.get(job_id)
            if job and job['state']=='preparing': journal.update(job_id,'failed_pre_submit',code='SESSION_CLOSED',message='登录浏览器已关闭，排队任务未提交')
            path.unlink(missing_ok=True)
