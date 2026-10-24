# 云端部署 v0.2

仓库 `zhaofranny/franny`，分支 `feature/franny-mvp-cloud`，入口 `app.py`，Python 3.12。

## 已部署实例升级

如果Streamlit实例跟踪上述分支，GitHub分支更新后通常会自动重新部署；等待平台完成安装。新增 `packages.txt` 用于中文字体。若字体未安装，在应用管理界面Reboot后重试。界面应显示 `v0.2 · 邪修减肥大法 / 省力习惯派`。

默认正式在线模式，没有API密钥不能生成。侧栏可临时输入自己的密钥。若使用服务器密钥，在应用管理的Secrets中设置：

```toml
OPENAI_API_KEY = "你自己的OpenAI密钥"
OPENAI_MODEL = "gpt-4o-mini"
APP_PASSWORD = "你自己设置的强口令"
```

不把真实密钥或口令提交到Git，也不要发给聊天。保存配置后刷新，输入访问口令；只有设置访问口令才会启用服务器密钥。需要模型权限、余额及api.openai.com出站访问。

## 新部署

登录 https://share.streamlit.io/ ，Create app，填写上述仓库/分支/入口，点击Deploy，使用平台实际生成的URL。云端容器localhost和私有IP不是访问者可用地址。

Community Cloud本地SQLite不是持久存储保证。示例体验可以使用；存放真实数据应部署到具有持久磁盘的Python服务器，设置 `DATABASE_PATH` 为磁盘路径，启用访问控制并定期备份。现有单口令不提供多租户隔离。

## 自建服务器

安装依赖、中文字体后，使用进程管理器常驻运行：

```bash
.venv/bin/python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

配置HTTPS反向代理与WebSocket，健康检查 `/_stcore/health`。通过平台生成的域名或自己的域名访问。当前会话无法查看你的Streamlit部署日志，也无法代填部署账号Secrets；GitHub同步成功不等于外部部署已成功。
