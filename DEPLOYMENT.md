# 云端访问与部署

本项目必须运行在支持 Python 长驻进程与 WebSocket 的服务上。云端容器的 localhost 不等于访问者电脑的 localhost；0.0.0.0 是监听地址，也不是可访问域名。当前 Codex 会话没有可调用的入站端口转发工具。

## Streamlit Community Cloud（适合先体验）

1. 登录 https://share.streamlit.io/ ，连接有权访问 zhaofranny/franny 的 GitHub 账户。
2. Create app：仓库 `zhaofranny/franny`，分支 `feature/franny-mvp-cloud`，入口 `app.py`，Python 3.12。
3. 点击 Deploy，等待安装完成，打开平台实际生成的 `https://….streamlit.app` 地址。
4. 默认无需密钥，可加载虚构示例并体验离线模板。API密钥仅在侧栏临时填写，勿提交至GitHub。在线调用还需要部署服务可访问api.openai.com。

**数据保留：** Community Cloud 本地SQLite不是持久存储保证，重启/休眠/重部署可能丢失数据。适合示例体验；真实业务需要持久磁盘及备份。使用平台的访问控制限制访问人群，当前应用本身没有登录隔离。

## 支持持久磁盘的云服务器

部署源代码并安装 requirements.lock.txt；将环境变量 DATABASE_PATH 设置为挂载持久磁盘中的绝对路径。运行：

```bash
.venv/bin/python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

通过主机平台入口或反向代理提供 HTTPS 域名并启用 WebSocket 转发，健康检查路径 `/_stcore/health`。加入身份验证后再存放真实数据。不要把云端私有IP或localhost当成用户可访问的地址。

部署账号授权/创建服务需要由对应账号拥有者完成。只有托管平台返回成功状态和真实URL后才能确认已部署。
