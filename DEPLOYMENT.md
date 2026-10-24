# v0.3 部署与数据保留

## 不覆盖现有线上实例

当前旧应用跟踪 `feature/franny-mvp-cloud`。本次修复放在同仓库的新分支 `feature/franny-provider-mvp`，不更新旧部署分支、不触发它自动重部署。

请先本地测试。需要云端体验时，创建**并行的新Streamlit应用**：仓库 `zhaofranny/franny`，分支 `feature/franny-provider-mvp`，入口 `app.py`，Python 3.12。保留旧应用直至完成迁移。新应用不会自动获得旧应用的SQLite文件；不要删除旧应用或误以为GitHub保存了数据库。

旧版可先通过笔记表格下载CSV、素材库逐条下载ZIP保存内容。如果需要完整SQLite迁移，必须取得原数据库文件的一致性备份；旧托管实例没有文件导出入口时，不能假设代码更新会保留磁盘。新版本素材库提供SQLite在线备份下载供以后使用。

## 服务端Secrets（以千问为例）

在新应用管理的Secrets中设置，不要在网页输入密钥、提交Git或发到聊天：

```toml
LLM_PROVIDER = "qwen"
DASHSCOPE_API_KEY = "你自己的阿里云百炼官方密钥"
QWEN_MODEL = "qwen-plus"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
APP_PASSWORD = "你自己设置的强口令"
LLM_TIMEOUT_SECONDS = "60"
LLM_MAX_TOKENS = "2200"
```

示例endpoint为北京地域旧域名，官方文档说明仍可使用；也可填控制台业务空间的北京专属地址 `https://业务空间ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`。API密钥必须属于该地域。

DeepSeek改为 `LLM_PROVIDER="deepseek"`，配置 `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL="deepseek-flash"`；OpenAI可选，改为openai并配置OPENAI_API_KEY/OPENAI_MODEL。不用把多家密钥全部配置，更不会自动向多家付费服务发送数据。

保存后使用平台生成的URL访问，输入APP_PASSWORD，在网页选择已配置服务商，先测试“优先生成文案”。导入自有/授权CSV、分析筛选、生成成功会自动出现在素材库。生成前检查官方余额/项目权限；不需要升级Codex，不使用第三方代充。

没有有效密钥或本机模型，软件无法免费调用付费API。可开启明确标注的离线示例体验其他模块；这是模板，不冒充原创模型输出。

## 本地或持久服务器

参考README使用 `.env`，Streamlit和已下载模型的Ollama必须在同一主机（当前仅允许回环地址），本机地址无法从Community Cloud访问你的电脑。Ollama不按次收API费用，但需要自己的硬件，Community Cloud也没有为本项目安装大模型。

真实数据建议部署至持久磁盘，保持原 `DATABASE_PATH`，在停止写入后恢复一致性备份并先验证笔记/草稿数量。启动前最好备份原数据库。新代码不会重建/清空notes和drafts，只增加generation_limits表。

启动命令：

```bash
.venv/bin/python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

反向代理需HTTPS/WebSocket支持，健康检查 `/_stcore/health`。跨服务商网络域名需在你的部署平台允许，不要绕过代理或关闭TLS证书校验。

单访问口令面向单人/可信团队，没有多租户隔离或完整身份审计；配置后所有持有口令的人能访问同一数据库。当前任务没有你的托管账号/真实模型密钥，不会声明云端真实API已成功。
