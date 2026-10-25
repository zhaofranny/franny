# 第一版交付测试

2026-10-25，北京时间。

- Python 3.12.14，开发机Linux；不是用户Mac。
- `pytest -q mac_publisher/tests`：13 passed in 2.15s。
- 其中2项在实际安装的Chromium运行，使用离线合成页面：上传图片→显示缩略图→填写文字→核验AI声明→只点击一次；以及遇到验证提示停止。网络请求计数为0。
- 其余覆盖素材哈希变化、ZIP越界、重复图片、离线示例/高风险文案、旧Franny素材包导入、回执核验、账号不符不提交、点击后超时不重发。
- Streamlit AppTest：界面无异常，3个标签页正常。
- compileall与启动脚本bash语法检查通过。
- 没有真实小红书发布记录；本环境网络策略未开放官方创作者域名，未使用用户浏览器或凭据。

Mac首次运行、真实登录DOM、话题关联、AI声明控件及真实发布结果尚未验收。当前默认选择器来自公开页面结构的研究，可能与账号实际界面不同；程序会停在对应步骤，不能承诺直接发布一定成功。没有删除旧项目文件或数据库，没有修改线上部署分支。

## v0.2 production integration

18 targeted tests passed (2026-10-25): generated draft -> four distinct Chinese PNG cards -> validated bundle -> editor -> preview; publish disabled without approval/account; missing-key no request; redacted429; unsafe card rejected; existing bundle/engine deduplication and ambiguous-result protections. Streamlit AppTest has no exceptions and three tabs. Shell scripts pass bash syntax checks. API calls mocked: no paid request, no live Mac or Xiaohongshu publication verified in cloud.

## v0.2.2 session handoff
23 targeted tests passed: same login adapter receives one publication request; stale or closed sessions cannot queue; old session requests never replay; original engine safety, local Chinese cards, generated-editor-preview integration still pass. No real provider charge or Xiaohongshu publication tested from cloud.
