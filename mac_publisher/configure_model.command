#!/bin/bash
set -euo pipefail
umask 077
cd "$(dirname "$0")"
mkdir -p .local
if [[ ! -f .local/generation.json ]]; then
  cat > .local/generation.json <<'JSON'
{
  "DEEPSEEK_API_KEY": "",
  "DEEPSEEK_MODEL": "deepseek-chat"
}
JSON
fi
chmod 600 .local/generation.json
open -e .local/generation.json
echo '在空引号中粘贴你的DeepSeek官方API密钥，保存后回工作台生成。不要将配置文件或密钥发送到聊天。'
