import json
from pathlib import Path
import hmac
from franny.settings import setting, setting_source
from franny.errors import explain_error
from franny.providers import PROVIDERS, ProviderConfigError, load_provider
from franny.service import create_and_save
from franny.editorial import DIRECTIONS, IDEAS, refresh_review, approve, is_approved, fingerprint
from franny.cards import render_cards, THEMES
from franny.health import SOURCES
import streamlit as st
from dotenv import load_dotenv
from franny.data import Store, parse_csv
from franny.analysis import rank_notes, analyze
from franny.generation import Draft, validate_draft
from franny.export import export_bundle

load_dotenv()
st.set_page_config(page_title="Franny · 原创内容工作台", page_icon="🌿", layout="wide")
st.caption("Franny v0.3.4 · 服务端密钥检查已启用")
password = setting("APP_PASSWORD")
if password and not st.session_state.get("authenticated"):
    st.title("Franny · 创作者登录")
    with st.form("login"):
        supplied = st.text_input("访问口令",type="password")
        if st.form_submit_button("进入工作台"):
            if hmac.compare_digest(supplied.encode(),password.encode()):
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("口令不正确")
    st.stop()
st.title("🌿 Franny · 减脂内容工作台")
st.caption("v0.3.4 · 邪修减肥大法 / 省力习惯派")
st.caption("合法元数据分析 → 原创草稿 → 健康核查 → 本地导出")
store = Store(setting("DATABASE_PATH", "data/franny.db"))
with st.sidebar:
    st.header("生成设置")
    demo = st.toggle("离线风格示例（非正式生成）", value=False)
    default_provider=setting("LLM_PROVIDER","deepseek")
    names=list(PROVIDERS)
    provider=st.selectbox("模型服务",names,index=names.index(default_provider) if default_provider in names else 0,format_func=lambda n:PROVIDERS[n].label)
    key_field=PROVIDERS[provider].key_env
    if key_field:
        st.caption("配置项："+key_field+" · 来源："+setting_source(key_field))
    config=None
    try:
        config=load_provider(provider)
    except ProviderConfigError as exc:
        if not demo: st.warning(str(exc))
    if config:
        st.caption("模型："+config.model)
    if not demo and not password:
        st.warning("启用模型调用前，请在服务端设置APP_PASSWORD访问口令。")
    ready = bool(config and password)
    if not demo and ready:
        st.success("服务端配置已读取，实际可用性以调用结果为准")
    st.caption("密钥仅从服务器环境变量或Secrets读取，页面不提供密钥输入或显示。")
    st.caption("没有免费API承诺；不自动重试、不自动切换付费服务。本机Ollama需与应用运行在同一主机。")
    st.info("不采集笔记、不自动发布。在线生成仅发送选题、人群与聚合分析，不发送原始链接。")
import_tab, analysis_tab, create_tab, history_tab = st.tabs(["导入数据", "爆款分析", "原创生产", "素材库"])
with import_tab:
    st.write("上传拥有合法使用权限的 CSV；支持中英文列名。时间默认北京时间。")
    sample = Path("examples/notes.csv").read_bytes()
    st.download_button("下载虚构示例 CSV", sample, "example_notes.csv", "text/csv")
    uploaded = st.file_uploader("CSV（UTF-8，最多10MB）", type=["csv"])
    authorized = st.checkbox("我确认拥有导入数据的合法使用权限（示例数据为虚构）", key="data_authorized")
    if st.button("导入上传文件", disabled=not (uploaded and authorized)):
        try:
            df = parse_csv(uploaded.getvalue())
            n = store.import_notes(df)
            st.success(f"已写入/更新 {n} 条；同一链接覆盖更新互动数据")
        except ValueError as exc:
            st.error(str(exc))
    if st.button("加载虚构示例", disabled=not authorized):
        st.success(f"已写入 {store.import_notes(parse_csv(sample))} 条虚构笔记")
    st.dataframe(store.notes(), hide_index=True, width="stretch")
with analysis_tab:
    a, b, c = st.columns(3)
    keyword = a.text_input("标题关键词（按字面匹配）")
    minimum = b.number_input("最低总互动", min_value=0, step=100)
    sort = c.selectbox("排序", ["score", "interactions", "published_at", "likes", "saves", "comments"])
    a, b, c = st.columns(3)
    since = a.date_input("开始日期", value=None)
    until = b.date_input("结束日期（含当天）", value=None)
    half = c.slider("热度半衰期（天）", 1, 180, 30)
    if since and until and since > until:
        st.warning("开始日期不能晚于结束日期")
    ranked = rank_notes(store.notes(), keyword, minimum, since, until, sort, half)
    st.metric("筛选后笔记", len(ranked))
    st.caption("评分=100×[1−exp(−ln(1+点赞+2×收藏+3×评论)/8)]×0.5^(发布天数/半衰期)。仅用于当前样本排序，不预测爆款。")
    st.dataframe(ranked, hide_index=True, width="stretch")
    top_n = st.slider("分析排序前 N 篇", 1, 100, 20)
    insights = analyze(ranked.head(top_n))
    st.warning(insights["basis"])
    st.json(insights)
    if len(ranked):
        st.bar_chart(ranked.head(15).set_index("title")[["score"]])
with create_tab:
    st.subheader("邪修减肥大法 · 原创图文")
    st.caption("标题强化反差、场景共鸣与轻吐槽，每次给5个不同角度的备选；正文兑现标题，不虚构效果。")
    direction = st.selectbox("栏目方向", list(DIRECTIONS))
    preset = st.selectbox("选题灵感", ["自定义"] + IDEAS)
    topic = st.text_input("选题方向", preset if preset != "自定义" else IDEAS[0], max_chars=200, key="topic_"+preset)
    audience = st.text_input("目标人群", "普通健康成年上班族", max_chars=200)
    text_only = st.checkbox("优先生成文案（减少输出量，不要求图片字段）",value=True,key="text_only")
    st.caption("公开网页上的导入数据与素材库可能被其他访客看到。私有素材请先配置访问口令或平台访问控制。")
    if st.button("生成原创草稿", type="primary", disabled=not demo and not ready):
        try:
            with st.spinner("生成原创文案并保存…" if text_only else "生成原创图文草稿并保存…"):
                draft_id,payload = create_and_save(store,topic,audience,insights,provider=provider,demo=demo,text_only=text_only,direction=direction)
                st.session_state["draft"] = payload
                st.session_state["draft_revision"] = str(draft_id)
                st.session_state.pop("card_images", None)
                st.session_state.pop("images_hash", None)
                st.success("已保存到素材库")
        except Exception as exc:
            diagnostic = explain_error(exc,provider)
            if diagnostic['code'] in {'GENERATION_COOLDOWN','GENERATION_BUSY'}:
                st.info(diagnostic['message'])
            else:
                st.error(f"生成失败 [{diagnostic['code']}]：{diagnostic['message']}")
            if diagnostic.get("stage"):
                st.caption("处理阶段："+diagnostic["stage"])
            if diagnostic.get("request_id"):
                st.caption("服务商请求编号："+diagnostic["request_id"])
            st.caption("诊断不显示密钥、请求正文或服务商原始错误信息。")
    if "draft" in st.session_state:
        p = st.session_state["draft"]
        revision = st.session_state.get("draft_revision", "legacy")
        st.info("离线风格示例，不能导出正式发布包" if p["mode"] == "offline_template" else "模型原创草稿 · 编辑、核对后导出")
        if p.get("evidence_issues"):
            st.warning("文案已保留并保存到素材库，引用关联需要人工处理；无需重复调用模型。请在编辑区核对来源与原句，处理后才能确认正式审核。")
            st.caption("待处理项："+"、".join(p["evidence_issues"]))
        if p.get("generation_issues"):
            st.warning("文案已保存，标题或正文超过发布长度。请在下方编辑区缩短后保存，无需再次付费生成。")
        st.subheader(p["title"])
        st.write(p["body"])
        st.write(" ".join("#"+t.lstrip("#") for t in p["tags"]))
        st.write("备选标题："+" / ".join(p.get("title_options",[])))
        with st.form("editor_"+revision):
            edited_title = st.text_input("最终标题", p["title"], max_chars=100)
            edited_body = st.text_area("正文", p["body"], height=300, max_chars=6000)
            edited_tags = st.text_input("标签（空格分隔）", " ".join(p["tags"]))
            edited_cards = st.text_area("图文卡片（JSON，可编辑heading和text）",json.dumps(p.get("cards",[]),ensure_ascii=False,indent=2),height=200)
            edited_sources = st.multiselect("引用来源ID",[s["id"] for s in SOURCES],default=p.get("source_ids",[]))
            edited_claims = st.text_area("健康主张核查项（JSON，quote须逐字引用正文）",json.dumps(p.get("claims",[]),ensure_ascii=False,indent=2),height=180)
            resolved = st.checkbox("已逐条处理引用警告，并核对正文与来源",key="evidence_resolved_"+revision) if p.get("evidence_issues") else True
            if st.form_submit_button("保存修改并重新检查"):
                try:
                    fields = {k:p[k] for k in Draft.model_fields if k in p}
                    fields.update(title=edited_title, body=edited_body, tags=edited_tags.split(), cards=json.loads(edited_cards),source_ids=edited_sources,claims=json.loads(edited_claims))
                    updated = validate_draft(fields).model_dump()
                    updated.update({k:p[k] for k in ["mode","direction","schema_version","generation_kind","model","usage"] if k in p})
                    updated["evidence_issues"] = [] if resolved else p.get("evidence_issues",[])
                    updated = refresh_review(updated)
                    draft_id = store.save_draft(json.dumps(updated,ensure_ascii=False))
                    st.session_state.update(draft=updated,draft_revision=str(draft_id))
                    st.session_state.pop("card_images",None)
                    st.session_state.pop("images_hash",None)
                    st.rerun()
                except (ValueError, TypeError, KeyError):
                    st.error("修改未保存：请检查标题长度、正文、JSON格式和引用是否逐字对应原句")
        st.warning(p["health_review"]["note"])
        st.write("**健康主张与证据线索（模型提出，需逐句人工核对）**")
        st.dataframe(p.get("claims",[]), hide_index=True, width="stretch")
        if not p.get("claims"):
            st.warning("没有可用的逐句证据映射，请直接对照下方来源核对全部健康表述。")
        for source in p["health_review"]["sources"]:
            st.markdown(f"[{source['title']}]({source['url']}) — {source['fact']}")
        blocked = p["health_review"]["status"] == "blocked"
        if blocked:
            st.error("高风险表述已阻止图片与导出："+"、".join(p["health_review"]["flags"]))
        theme = st.selectbox("字卡配色",list(THEMES))
        if st.button("生成原创封面和配图 PNG", disabled=blocked):
            try:
                with st.spinner("排版中文字卡…"):
                    st.session_state["card_images"] = render_cards(p,theme)
                    st.session_state["images_hash"] = fingerprint(p)
            except ValueError as exc:
                st.error(str(exc))
        images = st.session_state.get("card_images") if st.session_state.get("images_hash") == fingerprint(p) else None
        if images:
            st.image(list(images.values()),width=230,caption=["封面"]+[f"图文卡 {n}" for n in range(1,len(images))])
        with st.form("review_"+revision):
            reviewer = st.text_input("审核人")
            notes = st.text_area("逐条核对记录（来源、原句、适用边界及修改说明）")
            checked = st.checkbox("已核对全部正文和图片中的健康表述、原创性及适用边界")
            if st.form_submit_button("确认当前版本人工审核", disabled=blocked or p["mode"] == "offline_template"):
                if not checked:
                    st.error("请先完成核对并勾选确认")
                else:
                    try:
                        approved = approve(p,reviewer,notes)
                        store.save_draft(json.dumps(approved,ensure_ascii=False))
                        st.session_state["draft"] = approved
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
        if not blocked:
            st.download_button("下载待审核素材 ZIP",export_bundle(p,images),"franny_draft.zip","application/zip")
        if is_approved(p) and images:
            st.success("当前版本已由编辑确认；不代表医学正确或平台审核通过。")
            st.download_button("下载正式发布素材包",export_bundle(p,images,publish_ready=True),"franny_publish.zip","application/zip")
            st.caption("解压后将images中的PNG上传小红书，复制publish.txt的标题、正文和标签。")
            st.link_button("打开小红书官方创作平台","https://creator.xiaohongshu.com/")
with history_tab:
    st.caption("升级前先下载数据库备份；导出使用SQLite在线备份，不会修改已有笔记或草稿。请妥善保管备份中的私有内容。")
    st.download_button("下载SQLite完整备份",store.backup_bytes(),"franny-backup.sqlite","application/vnd.sqlite3",key="db_backup")
    for draft_id, created, raw in store.drafts():
        p = json.loads(raw)
        with st.expander(f"#{draft_id} · {created} UTC · {p['title']}"):
            st.write(p["body"])
            st.json(p["health_review"])
            if st.button("继续编辑此版本",key=f"open_{draft_id}"):
                st.session_state.update(draft=p,draft_revision=f"history_{draft_id}")
                st.session_state.pop("card_images",None)
                st.session_state.pop("images_hash",None)
                st.rerun()
            if refresh_review(p)["health_review"]["status"] != "blocked":
                st.download_button("导出素材", export_bundle(p), f"draft_{draft_id}.zip", key=f"export_{draft_id}")
