# Franny · 小红书减脂内容分析与原创生产 MVP

Python 3.12 + Streamlit + SQLite。导入合法持有的笔记元数据，分析标题与互动趋势，调用 OpenAI 生成原创草稿，导出本地素材。不含爬虫、笔记正文/图片下载、自动发布或账号登录。

## 快速启动

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

**仅在你自己电脑启动时**，浏览器打开 http://localhost:8501 。云端运行请按 `DEPLOYMENT.md` 配置平台入口，不能从你电脑直接访问云端localhost。默认离线示例模式无需密钥：勾选数据使用权限，点击“加载虚构示例”，切换爆款分析，再生成草稿并下载 ZIP。首次运行自动创建 `data/franny.db`。不要将数据库或 `.env` 提交至 Git。

在线生成：在 `.env` 设置 `OPENAI_API_KEY` 和 `OPENAI_MODEL`，或在侧栏输入会话密钥，然后关闭离线示例模式。使用官方 OpenAI Python SDK 的 Chat Completions JSON 输出，45秒超时、最多重试1次。需要允许访问 `api.openai.com:443`，模型须支持 JSON object 输出。没有密钥、无网络、配额不足或响应不合规时显示失败，不伪装成在线成功。密钥不写入 SQLite。调用会产生服务商费用。

## CSV 数据契约

UTF-8 / UTF-8 BOM，1–50000行、最大10MB；示例 `examples/notes.csv` 所有标题、互动量和链接均为虚构，链接不可作为真实笔记访问。支持：

| 英文列 | 中文列 | 约束 |
| --- | --- | --- |
| title | 标题 | 必填，最长500字 |
| url | 笔记链接 | 小红书域名HTTPS链接，不请求链接 |
| published_at | 发布时间 | ISO日期或日期时间；无时区默认北京时间，不允许未来时间 |
| likes | 点赞数 | 非负整数，最大10^12 |
| saves | 收藏数 | 同上 |
| comments | 评论数 | 同上 |

全批校验后事务写入。URL去除查询参数、片段和末尾斜杠，同一URL重复导入覆盖更新；短链接与完整链接不会自动识别为同一笔记。额外列不存储，中英文列同时出现导致重复字段时拒绝。

## 评分与分析

加权互动 W=点赞+2×收藏+3×评论。

`score = 100 × (1 − exp(−ln(1+W)/8)) × 0.5^(发布天数/半衰期)`

默认半衰期30天，可调整。评分范围0–100，偏重收藏、评论并衰减旧内容；仅为可解释的启发式排序，没有曝光量，不能计算真实互动率或保证爆款。筛选支持总互动量、日期、字面关键词，支持评分、总互动、发布时间及各互动数降序。

分析仅使用当前筛选排序前N条标题：数字清单、提问、场景、误区纠正等结构，以及主题关键词与痛点假设。类别可重叠；没有正文或评论，不能据此声称理解完整内容或真实用户心理。可在 `franny/analysis.py` 扩充词典。

## 原创、图片与健康核查边界

在线模型接收自填方向、目标人群、聚合分析和内置健康证据摘要；不发送原始笔记标题、链接、正文或图片。返回选题、标题、正文、标签、封面及配图提示词，Pydantic校验字段，并校验引用ID。

`franny/generation.py:ImageProvider` 预留 `generate(prompt, size) -> bytes` 原创图片接口；本阶段只导出提示词，不包含生成图片，不下载他人素材。后续可添加 OpenAI Images 等经授权适配器，将原创图片字节存储后加入 ZIP。

内置参考来源：WHO健康饮食、WHO身体活动、CDC体重管理，见 `franny/health.py`。来源是人工维护的静态证据摘要，程序不实时检索，不保证链接长期有效。模型不能自行增加来源ID；来源ID合法不意味着每句已经得到支持。

**事实核查流程：** 生成受限于证据摘要 → 扫描极端节食、承诺减重、局部减脂等高风险表述 → 命中则阻止导出 → 其余草稿保持 `needs_review`，随ZIP导出来源清单与审核提示 → 发布前由编辑逐句对照来源核查，涉及具体数值、疾病或特殊人群时请专业人士复核。此MVP没有将自动扫描冒充医学事实核查；未实现实时检索、逐句蕴含校验或自动发布。规则可能漏检，也可能对否定句误报。无虚构减肥效果、个人经历和前后对比。

素材库保存生成记录（包括被阻止的草稿），导出 `draft.md`、`draft.json`、`image_prompts.json`、`REVIEW.txt`。ZIP通过浏览器下载到本地，仍是待审核素材。

## 测试

```bash
source .venv/bin/activate
python -m pytest -q
```

包含CSV非法数据、幂等更新、评分衰减与筛选、标题推断、健康阻断、ZIP内容、OpenAI客户端模拟以及Streamlit页面导入→生成→历史集成测试。模拟测试不消耗API配额，也不代表在线服务已经实测。最终执行记录见 `TEST_RESULTS.md`。

## 后续接入真实数据

1. 仅使用本人数据、明确授权的数据提供商或平台允许的导出；记录来源、授权范围、导出时间和保留期限。
2. 转换至上述CSV契约，先在本地预览并去除个人信息，确认使用权限后导入。不要将示例数据当成真实趋势。
3. 定期手工导入新的互动快照。目前覆盖最新数值；需要增长率时增加独立的观测快照表和观测时间，不用发布时间代替抓取时间。
4. 在获授权且最小化数据的前提下，未来可扩展正文主题分析；不要复制第三方正文或图片。当前不提供未经授权采集方案。
5. 配置真实OpenAI密钥与网络白名单，少量验证生成质量、引用和费用；添加经过人工审定的本地知识库，再完善逐句证据对齐。

## 文件结构

```text
app.py                       Streamlit四页工作台
franny/data.py               CSV校验与SQLite持久化
franny/analysis.py           评分、筛选、标题分析
franny/generation.py         OpenAI生成、响应模型、图片接口
franny/health.py             参考证据和风险检查
franny/export.py             ZIP导出
franny/__init__.py
examples/notes.csv           虚构示例
tests/test_core.py           业务测试
tests/test_app.py           界面集成测试
requirements.txt            依赖范围
requirements.lock.txt       实测环境精确依赖版本
.env.example                配置示例
.streamlit/config.toml       上传限制与主题
.gitignore
TEST_RESULTS.md             实测结果
```

面向本地单人使用，没有认证与多租户隔离。不要将含私有数据的后台直接开放至公网；如需团队部署再增加身份验证、访问控制和备份。SQLite文件可在停服务后备份；记录会保留用户输入，请勿输入敏感健康信息。
