# Franny v0.3 · 原有四模块的多模型修复版

在现有Streamlit + SQLite项目上增量修改，保留“导入数据、爆款分析、原创生产、素材库”。优先流程：合法真实CSV → 评分/标题主题分析 → 原创文案 → 自动保存。没有爬虫、自动发布、第三方代充或套餐升级要求。

## 本次检查与修复

- 原来只有OpenAI官方调用；密钥可以通过浏览器输入并显示，截图容易泄漏。现在移除全部API Key输入/显示控件，只在Python服务端读取环境变量或Streamlit Secrets，不把配置对象传入session_state、草稿、导出或前端。
- 原SDK `max_retries=1` 会重试429；现为 `max_retries=0`，不自动修复/重复生成、不切换其他付费服务。每次真实点击至多一个HTTP生成请求，失败不会把模板冒充结果。
- 部分兼容接口把错误码放在嵌套 `error.code`；现支持嵌套余额错误、DeepSeek 402、千问Arrearage。无法确认原因的429保持“可能限流或额度”的表述，不将所有429误判为余额不足。
- 点击间隔8秒，429后SQLite记录共享冷却（限流按Retry-After秒数，默认60秒，范围30–900秒；余额错误默认300秒）。不阻塞sleep，不自动重试；刷新网页不会清除数据库冷却。不是跨服务商的计费硬上限或完整并发队列。
- 默认“优先生成文案”，不再让缺少图片字段或不足5个备选标题阻断文案保存。图文模式仍可选，原有排版/编辑/健康审核保留。
- 同一笔记仍按URL覆盖最新互动数；升级不删除表、不清空数据库、不改写旧草稿，仅增加冷却表。旧OpenAI草稿与新版DeepSeek/千问/Ollama草稿都可继续编辑。

## 先选生成方式

| 方案 | 配置 | 适用性与费用 |
| --- | --- | --- |
| DeepSeek 官方 | `LLM_PROVIDER=deepseek`，`DEEPSEEK_API_KEY` | 国内官方渠道；是否有余额/免费权益以自己账号为准 |
| 阿里云百炼千问 | `LLM_PROVIDER=qwen`，`DASHSCOPE_API_KEY` | 国内官方渠道，密钥和接口地域必须匹配；不承诺免费额度 |
| OpenAI（可选） | `LLM_PROVIDER=openai`，`OPENAI_API_KEY` | API独立计费，与Codex/ChatGPT订阅分开 |
| Ollama本机模型 | `LLM_PROVIDER=ollama`，无需API Key | 在自己硬件上运行已下载模型，无按次API费用；需算力、内存和下载 |
| 离线风格示例 | 网页手动开启开关 | 完全不调用API，固定演示文案，不是模型原创，不可正式审核 |

DeepSeek和千问官方均支持OpenAI兼容接口，因此复用现有SDK，无需重建四模块。2026-10-24核对的文档：[DeepSeek接入](https://api-docs.deepseek.com/)、[JSON输出](https://api-docs.deepseek.com/guides/json_mode/)、[千问接口与地域](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)、[千问结构化输出](https://help.aliyun.com/zh/model-studio/qwen-structured-output)、[Ollama兼容接口](https://docs.ollama.com/api/openai-compatibility)。地域开通、可用模型和计费以对应账号控制台为准，切换SDK不能绕过网络限制或计费。

默认DeepSeek模型 `deepseek-flash`，默认千问 `qwen-plus`（关闭思考模式，适合JSON），OpenAI `gpt-4o-mini`，Ollama `qwen3:8b`。可在服务端修改模型名，选择支持非流式Chat Completions和JSON对象输出的模型。DeepSeek较新官方模型关闭thinking，千问发送enable_thinking=false；不要选仅支持思考/流式的模型。

## 本地配置与启动

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

用本地编辑器修改 `.env`，例如先接DeepSeek官方：

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=在这里填你自己的官方密钥
DEEPSEEK_MODEL=deepseek-flash
APP_PASSWORD=你自己设置的强访问口令
DATABASE_PATH=data/franny.db
LLM_TIMEOUT_SECONDS=60
LLM_MAX_TOKENS=2200
```

```bash
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

打开 http://localhost:8501 ，输入访问口令。网页只能选择服务商，看不到API密钥，也不能修改服务端地址。选择了未配置的服务商会明确禁用生成。只有设置 `APP_PASSWORD` 后网页才启用真实模型调用，防止公共访客消耗服务器额度。口令只适合单人/可信团队，不提供多租户角色或防暴力破解机制。

不要把真实密钥提交到Git、发到聊天或截图；以前露出的密钥若还未撤销，应去对应官方控制台撤销并重新配置。`.env`与`.streamlit/secrets.toml`已经被忽略。真实私有数据也不要上传开放实例。

## 不花API费用的本机方案

先按Ollama官方方式安装本机运行时，确认硬件足够，再下载模型，例如：

```bash
ollama pull qwen3:8b
ollama serve
```

如果安装程序已启动后台服务，不要重复serve。在 `.env` 设置：

```dotenv
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3:8b
OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
APP_PASSWORD=你自己设置的强访问口令
```

必须选择已下载的本地模型，而非云模型。下载模型与运行占用网络、存储和硬件资源，不是零成本保证。小模型JSON合规率/文案质量需要实测，失败时可换具体选题或调整输出预算。**Streamlit Community Cloud的127.0.0.1不是你的电脑**，该托管实例不能通过这个地址访问你本机Ollama；本机方案需Streamlit和Ollama在同一电脑/服务器运行。本版本不安装或下载大模型，不公开本机端口到公网。

## 完整本地测试

无需密钥、不消耗额度的自动测试：

```bash
python -m pytest -q
python scripts/smoke_pipeline.py --csv examples/notes.csv --db work/smoke.db
```

smoke默认明确使用离线示例，验证导入、分析、保存，不宣称在线模型已实测。测试套件还用真实OpenAI SDK + httpx.MockTransport检查四家协议、参数、一次请求、冷却、密钥不进入前端/SQLite、旧数据保留及SQLite备份。

已配置模型后的真实单次测试（官方API可能产生费用，Ollama需要已下载模型）：

```bash
python scripts/smoke_pipeline.py --csv /你的路径/合法笔记.csv --db work/live-smoke.db --provider deepseek --live
# 本机方案改为 --provider ollama --live
```

UI操作：导入拥有权限的CSV → 爆款分析设置关键词/日期/互动筛选 → 原创生产选栏目、人群，保持“优先生成文案” → 生成成功自动写入素材库。无需先生成PNG或完成人工审核才保存；审核仅控制正式发布包导出。不存在跳过医学核查的自动发布。

## CSV契约

UTF-8或UTF-8 BOM，1–50000行、最大10MB；时间无时区则按北京时间，拒绝未来日期。六列中英文均可：

| 英文列 | 中文列 |
| --- | --- |
| title | 标题 |
| url | 笔记链接 |
| published_at | 发布时间 |
| likes | 点赞数 |
| saves | 收藏数 |
| comments | 评论数 |

标题必填、最长500字；小红书HTTPS链接不请求原网页，导入移除追踪参数；计数为0至10^12整数。全批校验后事务写入；同URL覆盖数值，不自动合并短链接和完整链接。`examples/notes.csv`全为虚构，仅演示字段，不当作真实爆款证据。真实CSV需要你从本人或有权使用的数据来源提供。

评分仍为 `100×(1−exp(−ln(1+点赞+2×收藏+3×评论)/8))×0.5^(发布天数/半衰期)`，默认30天，仅启发式排序。标题主题/痛点分析是规则推断，不代表正文或真实用户研究，不保证爆款。

## 安全、数据保留与升级

密钥只在后端配置及SDK请求头中使用。接口地址固定到对应官方域名；千问允许文档列出的地域/业务空间域名，仅由服务端配置；Ollama仅允许回环HTTP地址。无前端自定义地址，防止把密钥发送到任意网站。

输出只保存文案、模型名、提供方和token用量（若返回），不保存配置对象、密钥、SDK对象、原始错误或完整请求头。异常只显示白名单诊断，关闭Streamlit详细报错；请勿自行开启SDK HTTP DEBUG日志。

导入数据、保存草稿和审核仍使用原 `DATABASE_PATH`，没有数据库重建或清空。新增 `generation_limits` 表不修改 `notes`/`drafts` 旧内容。素材库增加SQLite在线备份下载。多个人共用一个访问口令时能看见同一个素材库。

**先备份再切换部署分支。** Streamlit Community Cloud的本地磁盘不保证跨重部署持久；代码兼容旧数据不等于托管平台保证保留磁盘。当前修复放在独立分支，避免自动更新原线上实例。详见 `DEPLOYMENT.md`。

## 健康与图片

保留邪修栏目口语反差风格，但不生成极端节食、脱水掉秤、催吐、滥用药物或虚构效果。给模型的只有聚合分析与内置WHO/CDC静态证据，不包含笔记原文、链接或图片。引用ID和规则扫描不等于事实核查，所有健康主张仍需人工对照原文。

文案模式返回标准草稿供编辑/导出；图文模式可生成本地1080×1440 PNG字卡，所需Pillow依赖已列出，Linux中文字体见 `packages.txt`。缺字体不妨碍文案生成与素材库保存。AI插画接口仍预留，未接入小红书自动发布。

## 主要文件

- `app.py`：原有四模块界面，服务端配置状态、默认文案模式、自动保存、备份下载。
- `franny/providers.py` / `settings.py`：多模型后端配置和客户端，不输出密钥。
- `franny/generation.py`：文案/图文JSON响应与内容校验。
- `franny/service.py`：生成冷却与写入素材库。
- `franny/errors.py`：安全的兼容接口错误分类。
- `franny/data.py`：原有CSV/SQLite + 增量冷却表/在线备份。
- `franny/analysis.py`、`editorial.py`、`health.py`、`cards.py`、`export.py`：保留评分、风格、核查、图片与导出。
- `tests/`、`scripts/smoke_pipeline.py`：无付费自动测试与本地单次测试。

当前未配置真实模型密钥，本环境也未开放各模型域名出站；未声称真实付费API或本机大模型已经跑通。以自己的密钥/本机模型完成最后一次实测即可确认部署可用性，不需要购买第三方代充或升级Codex。
