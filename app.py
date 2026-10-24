import json
import os
from pathlib import Path
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from franny.data import Store, parse_csv
from franny.analysis import rank_notes, analyze
from franny.generation import generate
from franny.export import export_bundle

load_dotenv()
st.set_page_config(page_title="Franny · 原创内容工作台", page_icon="🌿", layout="wide")
st.title("🌿 Franny · 减脂内容工作台")
st.caption("合法元数据分析 → 原创草稿 → 健康核查 → 本地导出")
store = Store(os.getenv("DATABASE_PATH", "data/franny.db"))
with st.sidebar:
    st.header("生成设置")
    demo = st.toggle("离线示例模式", value=True)
    key = st.text_input("OpenAI API Key（仅本次会话）", type="password")
    model = st.text_input("模型", value=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    st.info("不采集笔记、不自动发布。在线生成仅发送选题、人群与聚合分析，不发送原始链接。")
import_tab, analysis_tab, create_tab, history_tab = st.tabs(["导入数据", "爆款分析", "原创生产", "素材库"])
with import_tab:
    st.write("上传拥有合法使用权限的 CSV；支持中英文列名。时间默认北京时间。")
    sample = Path("examples/notes.csv").read_bytes()
    st.download_button("下载虚构示例 CSV", sample, "example_notes.csv", "text/csv")
    uploaded = st.file_uploader("CSV（UTF-8，最多10MB）", type=["csv"])
    authorized = st.checkbox("我确认拥有导入数据的合法使用权限（示例数据为虚构）")
    if st.button("导入上传文件", disabled=not (uploaded and authorized)):
        try:
            df = parse_csv(uploaded.getvalue())
            n = store.import_notes(df)
            st.success(f"已写入/更新 {n} 条；同一链接覆盖更新互动数据")
        except ValueError as exc:
            st.error(str(exc))
    if st.button("加载虚构示例", disabled=not authorized):
        st.success(f"已写入 {store.import_notes(parse_csv(sample))} 条虚构笔记")
    st.dataframe(store.notes(), hide_index=True, use_container_width=True)
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
    st.dataframe(ranked, hide_index=True, use_container_width=True)
    top_n = st.slider("分析排序前 N 篇", 1, 100, 20)
    insights = analyze(ranked.head(top_n))
    st.warning(insights["basis"])
    st.json(insights)
    if len(ranked):
        st.bar_chart(ranked.head(15).set_index("title")[["score"]])
with create_tab:
    topic = st.text_input("选题方向", "上班族如何安排均衡午餐")
    audience = st.text_input("目标人群", "普通健康成年人")
    st.caption("AI 会基于选题方向与聚合主题生成原创选题、标题、正文、标签及原创图片提示词。图片接口已预留，本阶段不生成图片。")
    if st.button("生成原创草稿", type="primary"):
        try:
            with st.spinner("生成中…"):
                payload = generate(topic, audience, insights, key or None, model, demo)
                store.save_draft(json.dumps(payload, ensure_ascii=False))
                st.session_state["draft"] = payload
        except Exception as exc:
            # Never show API exception details that might contain request metadata.
            st.error(str(exc) if isinstance(exc, ValueError) and not key else "生成失败，请检查密钥、网络、配额或模型响应格式后重试。")
    if "draft" in st.session_state:
        p = st.session_state["draft"]
        st.subheader(p["title"])
        st.write(p["body"])
        st.write(" ".join("#" + t for t in p["tags"]))
        st.json(p)
        st.warning(p["health_review"]["note"])
        if p["health_review"]["status"] == "blocked":
            st.error("高风险表述已阻止导出：" + "、".join(p["health_review"]["flags"]))
        else:
            st.download_button("下载待审核素材 ZIP", export_bundle(p), "franny_draft.zip", "application/zip")
with history_tab:
    for draft_id, created, raw in store.drafts():
        p = json.loads(raw)
        with st.expander(f"#{draft_id} · {created} UTC · {p['title']}"):
            st.write(p["body"])
            st.json(p["health_review"])
            if p["health_review"]["status"] != "blocked":
                st.download_button("导出素材", export_bundle(p), f"draft_{draft_id}.zip", key=f"export_{draft_id}")
