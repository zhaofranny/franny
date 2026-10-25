#!/bin/bash
set -euo pipefail
umask 077
PUBLISHER_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PUBLISHER_ROOT"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "本启动器用于Mac。其他系统请按README手动启动；不能将云端localhost当作Mac地址。"
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "请先从 https://www.python.org/downloads/macos/ 安装Python 3.12，再双击本文件。"
  read -r -p "按回车退出" _publisher_exit
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3,10), "需要Python 3.10+，建议3.12"'
mkdir -p .local output
export PLAYWRIGHT_BROWSERS_PATH="$PUBLISHER_ROOT/.local/browsers"
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
REQ_HASH="$(.venv/bin/python -c 'import hashlib; print(hashlib.sha256(open("requirements.txt","rb").read()).hexdigest())')"
OLD_HASH="$(cat .local/requirements.sha256 2>/dev/null || true)"
if [[ "$REQ_HASH" != "$OLD_HASH" ]]; then
  .venv/bin/python -m pip install --cache-dir .local/pip-cache -r requirements.txt
  printf '%s' "$REQ_HASH" > .local/requirements.sha256
fi
if ! .venv/bin/python -c 'from pathlib import Path; from playwright.sync_api import sync_playwright; p=sync_playwright().start(); exists=Path(p.chromium.executable_path).is_file(); p.stop(); raise SystemExit(0 if exists else 1)'; then
  .venv/bin/python -m playwright install chromium
fi
.venv/bin/python -m xhs_publisher.doctor > .local/environment_check.json
PUBLISHER_PORT="$(.venv/bin/python - <<'PY'
import socket
for port in range(8503,8513):
    try:
        s=socket.socket();s.bind(('127.0.0.1',port));s.close();print(port);break
    except OSError: pass
else: raise SystemExit('没有可用端口8503–8512')
PY
)"
.venv/bin/python -m streamlit run publisher_app.py --server.address 127.0.0.1 --server.port "$PUBLISHER_PORT" --server.headless true --server.fileWatcherType none --browser.gatherUsageStats false &
PUBLISHER_PID=$!
trap 'kill "$PUBLISHER_PID" 2>/dev/null || true' EXIT INT TERM
export FRANNY_LOCAL_PORT="$PUBLISHER_PORT"
.venv/bin/python - <<'PY'
import os,time,urllib.request
url='http://127.0.0.1:'+os.environ['FRANNY_LOCAL_PORT']+'/_stcore/health'
for _ in range(40):
    try:
        with urllib.request.urlopen(url,timeout=1) as r:
            if r.status==200: break
    except Exception: time.sleep(.25)
else: raise SystemExit('本地服务启动失败，请查看终端提示')
PY
open "http://127.0.0.1:$PUBLISHER_PORT"
echo "发布工作台已启动。请保留此终端；结束使用时按Control+C。不要删除.local目录中的账号与防重复记录。"
wait "$PUBLISHER_PID"
