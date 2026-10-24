from datetime import timedelta
import re
from collections import Counter
import numpy as np
import pandas as pd

THEMES = {
    "饮食搭配": (["吃", "餐", "饮食", "外卖", "食堂"], "日常饮食选择困难"),
    "运动入门": (["运动", "训练", "走路", "力量"], "缺少可坚持的运动安排"),
    "习惯管理": (["习惯", "睡眠", "熬夜", "记录", "坚持"], "难以持续执行健康习惯"),
    "认知与情绪": (["焦虑", "体重", "平台", "反弹", "误区"], "对体重波动和方法有效性的困惑"),
}

def rank_notes(df, keyword="", min_interactions=0, since=None, until=None, sort="score", half_life=30, now=None):
    if half_life <= 0:
        raise ValueError("半衰期必须大于零")
    df = df.copy()
    if df.empty:
        return df.assign(interactions=pd.Series(dtype=float), score=pd.Series(dtype=float))
    dates = pd.to_datetime(df.published_at, utc=True)
    now = pd.Timestamp(now) if now else pd.Timestamp.now(tz="UTC")
    ages = (now - dates).dt.total_seconds().div(86400).clip(lower=0)
    df["interactions"] = df.likes + df.saves + df.comments
    weighted = df.likes + 2 * df.saves + 3 * df.comments
    df["score"] = (100 * (1 - np.exp(-np.log1p(weighted) / 8)) * 0.5 ** (ages / half_life)).round(2)
    mask = df.interactions.ge(min_interactions) & df.title.str.contains(keyword, case=False, regex=False)
    if since:
        mask &= dates >= pd.Timestamp(since, tz="Asia/Shanghai").tz_convert("UTC")
    if until:
        mask &= dates < pd.Timestamp(pd.Timestamp(until).to_pydatetime() + timedelta(days=1)).tz_localize("Asia/Shanghai").tz_convert("UTC")
    if sort not in {"score", "interactions", "published_at", "likes", "saves", "comments"}:
        raise ValueError("不支持的排序")
    return df[mask].sort_values([sort, "url"], ascending=[False, True])

def analyze(df):
    structures, themes, pains = Counter(), Counter(), Counter()
    for title in df.title:
        structures.update(["数字清单"] if re.search(r"[0-9一二三四五六七八九十]+[个步天种条]", title) else [])
        structures.update(["提问式"] if re.search(r"[？?]|如何|怎么|为什么", title) else [])
        structures.update(["场景式"] if any(k in title for k in ["上班", "食堂", "外卖", "新手", "通勤"]) else [])
        structures.update(["误区纠正"] if any(k in title for k in ["误区", "别再", "不是"]) else [])
        matched = False
        for theme, (words, pain) in THEMES.items():
            if any(w in title for w in words):
                themes[theme] += 1
                pains[pain] += 1
                matched = True
        if not matched:
            themes["其他/待人工分类"] += 1
    return {"sample_size": len(df), "basis": "仅基于标题的规则推断，不能代表正文或真实用户研究", "structures": dict(structures), "themes": dict(themes), "pain_points": dict(pains)}
