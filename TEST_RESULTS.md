# v0.3 检查与测试记录

日期：2026-10-24（北京时间）；Python 3.12.14。在现有项目增量修改，原四模块保留。

## 实际执行

- `.venv/bin/python -m pytest -q`：**68 passed in 2.61s**。
- `.venv/bin/pip check`：No broken requirements found。
- `compileall`、`git diff --check`：通过。
- 独立8502测试端口启动Streamlit，使用 `work/qa-v03.db`，未停止旧8501进程；`GET /`返回200，`GET /_stcore/health`返回ok。
- `python scripts/smoke_pipeline.py --db work/v03-smoke.db`：导入6条虚构示例，分析6条，保存1条离线示例草稿。mode明确为offline_template。
- `.env`、`.streamlit/secrets.toml`、数据库目录均被Git忽略；源代码、测试和文档的常见真实密钥模式扫描无匹配（不是全面秘密扫描保证）。

## 新增覆盖

- DeepSeek/千问/OpenAI/Ollama的配置、官方endpoint约束、地域配置、模型名、超时、输出预算及密钥不出现在配置repr。
- 真实OpenAI SDK经httpx.MockTransport构造兼容接口HTTP请求，检查模型、JSON参数、max_tokens、非思考参数和聚合分析，不发送原笔记链接。
- 四家协议模拟分别走“CSV→SQLite→排名→标题分析→模型文案→素材库”，不必生成图片字段或完成人工审核才保存草稿。
- 429仅发生一次HTTP请求，SDK关闭自动重试；解析嵌套insufficient_quota后写入300秒冷却；再次点击不调用模型。
- 兼容DeepSeek402、千问Arrearage、普通429及Retry-After秒数；错误报告不包含原始敏感错误文本。
- 已有notes与drafts表不重建、不清空，旧草稿原始JSON保持不变；SQLite在线备份可重新打开并验证原记录。
- Streamlit访问口令、无API Key控件、服务端密钥不出现在UI序列化或草稿数据库；导入示例后模型模拟生成成功即显示素材库记录。
- 保留原先CSV、评分、健康风险、图片排版、审核失效、导出等回归检查。

## 真实验证边界

没有可用的真实API密钥，没有安装/下载Ollama模型，当前出站白名单没有模型提供方域名。因此没有执行付费API或真实本地模型推理；不能把协议模拟与离线模板当作真实模型成功。真实CSV也尚未提供，数据路径用同一合法CSV导入器和合成样本验证。

当前会话本地没有找到原data目录中的业务数据库；没有修改用户线上托管实例的数据库。修复位于新分支feature/franny-provider-mvp，保留旧部署分支，避免触发临时磁盘重部署。代码数据库兼容性不代表Streamlit Community Cloud保证磁盘持久；切换前需备份，建议新建并行测试实例。

## v0.3.1 引用校验修复

- 全套74项测试通过，compileall与diff检查通过。
- 用模型模拟分别复现未知来源、主张来源无效、引用原句不在正文、来源列表遗漏：均只调用一次，保留原文与标题，保存待核查草稿；无效关联不会冒充有效证据，未处理警告前不能审核。
- Streamlit集成验证警告草稿进入素材库，普通保存不会静默清除警告，明确处理后可保存；全程不二次调用模型。
- 具体用户那次API响应未记录，无法断言截图唯一根因。新增分类能将后续配置、输入和引用问题分开；仍未执行真实付费API调用。
- 修复分支独立于线上feature/franny-provider-mvp，不自动触发线上重部署；数据库和旧记录不改写。
