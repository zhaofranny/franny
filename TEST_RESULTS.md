# MVP 实测记录

- 日期：2026-10-24（北京时间）
- 基线：origin/main，afc597ffb27813d075233f90d5553927c8426eb6；在工作分支 work 创建实现，未推送或修改远程 main。
- Python：3.12.14；精确安装版本见 requirements.lock.txt。
- 安装：已在 .venv 安装 requirements.txt 所有依赖。
- `python -m pytest -q`：**17 passed in 1.06s**，最终无测试警告。
- `pip check`：No broken requirements found。
- `git diff --check`：通过。
- `compileall`：通过。
- Streamlit：实际启动于 0.0.0.0:8501。
- HTTP：`GET /` → 200；`GET /_stcore/health` → ok。
- Streamlit AppTest：加载界面、授权勾选、示例导入6条、离线生成、草稿保存与素材库展示通过。
- 业务覆盖：非法CSV/日期/计数/链接、重复导入更新、时间衰减与筛选、主题推断、健康风险阻断、ZIP内容、OpenAI请求契约与未知来源拒绝。

首次依赖下载和服务监听被执行沙箱阻止，使用受支持的权限机制重试后成功。首次界面测试因Streamlit新版相对路径解析差异失败，改用绝对入口路径后通过。日期筛选的依赖弃用警告已修复，最终重新运行全套测试通过。

未执行真实付费OpenAI调用：当前无已配置API密钥，网络白名单未含api.openai.com。在线路径采用模拟客户端验证；离线模板明确标注，不作为在线AI输出。图片只实现接口契约与提示词导出。健康检查是证据约束、风险扫描及人工核查流程，未进行实时医学文献检索，不自动判定医学事实正确。
