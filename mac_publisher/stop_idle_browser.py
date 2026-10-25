"""Upgrade helper: stop only idle login workers belonging to the target project."""
import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import time
import fcntl


def matching_workers(output,base):
    found=[]
    for line in output.splitlines():
        try:
            pid,command=line.strip().split(None,1);args=shlex.split(command)
            if 'xhs_publisher.worker' not in args or '--base' not in args: continue
            if Path(args[args.index('--base')+1]).resolve()!=Path(base).resolve(): continue
            action=args[args.index('xhs_publisher.worker')+1]
            found.append((int(pid),action))
        except (ValueError,IndexError):continue
    return found


def stop_idle(base):
    base=Path(base).resolve();local=base/'.local'
    workers=matching_workers(subprocess.check_output(['ps','-axo','pid=,command='],text=True),base)
    try:state=json.loads((local/'browser_session.json').read_text())
    except (OSError,ValueError):state={}
    if any(action!='login' for _,action in workers) or (state.get('state')=='busy' and any(pid==state.get('pid') for pid,_ in workers)):
        raise SystemExit('发布任务正在运行，升级未执行。请等待并核对发布结果，勿强制终止。')
    for pid,_ in workers:
        try:os.kill(pid,signal.SIGTERM)
        except ProcessLookupError:pass
    lock=local/'profile.lock'
    if lock.exists():
        deadline=time.monotonic()+8
        with lock.open('a') as handle:
            while True:
                try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(handle,fcntl.LOCK_UN);break
                except BlockingIOError:
                    if time.monotonic()>=deadline:raise SystemExit('旧浏览器尚未释放，升级未执行。请关闭工具的独立Chrome后重试。')
                    time.sleep(.2)
    print('旧的空闲浏览器进程已检查；登录数据与发布记录保留。')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',required=True)
    stop_idle(parser.parse_args().base)
