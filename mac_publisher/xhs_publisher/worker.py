import argparse
import os
import time
from pathlib import Path
from .adapter import BrowserAdapter,PublishError,HOME
from .config import load_selectors
from .journal import Journal,profile_lock,atomic_json,JobConflict
from .engine import publish


def browser_context(p,profile):
    options={'user_data_dir':str(profile),'headless':False}
    executable=os.getenv('XHS_BROWSER_PATH')
    if executable: options['executable_path']=executable
    proxy=os.getenv('HTTPS_PROXY') or os.getenv('HTTP_PROXY')
    if proxy: options['proxy']={'server':proxy}
    return p.chromium.launch_persistent_context(**options)

def run(args):
    from playwright.sync_api import sync_playwright
    base=Path(args.base).resolve();local=base/'.local';local.mkdir(parents=True,exist_ok=True);local.chmod(0o700)
    journal=Journal(local);status=local/'login_status.json';account_file=local/'account.json'
    try:
      with profile_lock(local),sync_playwright() as p:
        profile=local/'browser_profile';profile.mkdir(exist_ok=True);profile.chmod(0o700)
        ctx=browser_context(p,profile)
        try:
          adapter=BrowserAdapter(ctx,load_selectors(base))
          if args.action=='login':
            atomic_json(status,{'state':'waiting_for_login','message':'请在打开的独立浏览器中手动登录，账号识别后会关闭窗口；不自动填写验证码'})
            # Login is user-driven. No use of browser cookies outside the persistent profile.
            response=adapter.page.goto(HOME,wait_until='domcontentloaded',timeout=30000)
            if response and response.status>=400: raise PublishError('PLATFORM_HTTP_DENIED','官方页面访问失败，未保存账号')
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                try: name=adapter.current_account()
                except PublishError: name=None
                if name:
                    atomic_json(account_file,{'account_name':name,'verified_at':time.time()})
                    atomic_json(status,{'state':'logged_in','account_name':name,'message':'已识别当前浏览器显示名；请在工作台确认是你要使用的账号'})
                    return 0
                adapter.page.wait_for_timeout(1000)
            atomic_json(status,{'state':'login_required','message':'180秒内未识别账号，请手动登录后重试；若已登录则需适配账号DOM选择器'})
            return 2
          if not account_file.exists(): raise PublishError('LOGIN_REQUIRED','请先手动登录并绑定当前浏览器账号')
          import json
          account=json.loads(account_file.read_text(encoding='utf-8'))['account_name']
          result=publish(adapter,journal,args.bundle,args.approved_hash,account,job_id=args.job_id,retry_prepare=args.retry_preparation,artifact_dir=base/'output'/args.job_id if args.job_id else base/'output'/'cli')
          atomic_json(base/'output'/result['id']/'result.json',result)
          return 0 if result['state'] in {'published','pending_review'} else 2
        finally: ctx.close()
    except Exception as exc:
        code=exc.code if isinstance(exc,PublishError) else ('PROFILE_BUSY' if isinstance(exc,JobConflict) else 'LOCAL_BROWSER_ERROR')
        message=str(exc) if isinstance(exc,(PublishError,JobConflict)) else '浏览器启动或本地运行失败，请检查运行环境；不会输出原始会话信息'
        if args.action=='login': atomic_json(status,{'state':'blocked','code':code,'message':message})
        elif args.job_id:
            job=journal.get(args.job_id)
            if job and job['state'] in {'preparing','ready'}: journal.update(args.job_id,'failed_pre_submit',code=code,message=message)
            elif job and job['state'] in {'submitting','submitted_unverified'}: journal.update(args.job_id,'unknown',code=code,message=message)
        return 2

def main():
    parser=argparse.ArgumentParser(description='Local single-account browser publisher. No private API or stealth.')
    parser.add_argument('action',choices=['login','publish'])
    parser.add_argument('--base',default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--bundle');parser.add_argument('--approved-hash');parser.add_argument('--job-id')
    parser.add_argument('--retry-preparation',action='store_true')
    args=parser.parse_args()
    if args.action=='publish' and (not args.bundle or not args.approved_hash): parser.error('publish requires --bundle and --approved-hash after material review')
    return run(args)

if __name__=='__main__': raise SystemExit(main())
