#!/bin/bash
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")" && pwd)"
TARGET="$HOME/Downloads/franny-feature-mac-oneclick-publisher/mac_publisher"
if [[ ! -d "$TARGET/.venv" ]]; then
  echo '没有找到原安装目录。请将新版publisher_app.py、start.command和xhs_publisher文件夹复制到原mac_publisher文件夹；不要删除.local或.venv。'
  read -r -p '按回车退出' _done
  exit 1
fi
"$TARGET/.venv/bin/python" "$SOURCE/stop_idle_browser.py" --base "$TARGET"
if [[ "$SOURCE" != "$TARGET" ]]; then
  cp "$SOURCE/publisher_app.py" "$TARGET/publisher_app.py"
  cp "$SOURCE/start.command" "$TARGET/start.command"
  cp "$SOURCE/stop_idle_browser.py" "$TARGET/stop_idle_browser.py"
  cp "$SOURCE/configure_model.command" "$TARGET/configure_model.command"
  chmod +x "$TARGET/configure_model.command"
  cp "$SOURCE/README.md" "$TARGET/README.md"
  cp "$SOURCE/xhs_publisher/"*.py "$TARGET/xhs_publisher/"
fi
chmod +x "$TARGET/start.command"
echo '升级完成，原登录、素材、发布记录和依赖环境均已保留。'
open "$TARGET/start.command"
