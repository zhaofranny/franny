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

## v0.2.3 account DOM compatibility
28 tests passed, including 5 real offline Chromium tests. New browser cases: delayed top-right account name without legacy CSS, body mention cannot impersonate account, missing name differs from a mismatch. No live website/API calls or publication. Sandbox initially prevented Chromium launch; rerun with approved local browser execution passed all tests.

## v0.2.4 focus and UI status
26 targeted non-browser tests pass including active-session login click -> focus handoff without launching a duplicate process, focus requests cannot publish, and no contradictory starting status. macOS osascript activation cannot be verified on Linux; prior v0.2.3 offline-browser account tests unchanged.

## v0.2.5 upload chooser
34 tests pass, including 8 real offline Chromium cases. New cases verify visible button chooses correct one among multiple hidden image/video inputs; delayed extension-only input works; ambiguous inputs stop without submit. After adding saved-material restore UI, 26 non-browser tests pass. No live Xiaohongshu upload or publication verified.

## v0.2.6 page readiness and upgrade lifecycle
41 tests pass, including 12 offline real Chromium tests and 3 upgrade helper tests. New browser cases cover blank login route classified as render timeout, delayed route transition to authenticated dashboard, actual visible login form blocked, authenticated page not reloaded. Upgrade helper only targets exact project login workers and refuses publication workers. Existing delayed upload tests pass after readiness polling correction. No live Xiaohongshu or Mac end-to-end verification performed.

## v0.2.7 same-tab account continuity
44 tests pass, including 15 offline Chromium cases. New cases verify existing creator tab reused without creating or closing tabs, tab-scoped sessionStorage survives baseline inspection, multiple creator tabs stop rather than guess, diagnostics omit URL query/fragment. No live Mac/Xiaohongshu publication verified.

## v0.3.0 editorial direction and approved one-click continuation
54 tests passed, including 17 offline real Chromium cases. Coverage: approved publication waits for manual login and resumes once; changed materials or wrong account cannot continue; challenge does not auto-resume; topic candidate with view count selectable; scoped onboarding close; five editorial directions, diary data requirement, white PNG cards, local-only source URLs, fabricated browsing history rejected. No live paid API call, no real Xiaohongshu publication or Mac end-to-end verification.
