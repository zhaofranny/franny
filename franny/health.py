"""Conservative evidence checklist, not an automated medical fact checker."""
import re
SOURCES = [
    {"id": "WHO_ACTIVITY", "title": "WHO Physical activity", "url": "https://www.who.int/news-room/fact-sheets/detail/physical-activity", "fact": "成年人每周建议至少150至300分钟中等强度有氧活动；应按自身情况循序渐进。"},
    {"id": "WHO_DIET", "title": "WHO Healthy diet", "url": "https://www.who.int/news-room/fact-sheets/detail/healthy-diet", "fact": "健康饮食强调多样化，包括蔬菜、水果、豆类、全谷物等。"},
    {"id": "CDC_WEIGHT", "title": "CDC Steps for Losing Weight", "url": "https://www.cdc.gov/healthy-weight-growth/losing-weight/index.html", "fact": "体重管理需要持续的饮食、活动和生活习惯调整，个体结果存在差异。"},
]

def review(text):
    patterns = [r"(?:催吐|断水|脱水减重|脱水掉秤|泻药|利尿剂|饿瘦|饿到|补偿性运动|过午不食|只喝水|生酮治疗)", r"(?:每天|每日|一天).*?(?:只吃|仅吃).*?(?:[1-9]\d{1,2})\s*(?:卡|千卡|大卡|kcal)", r"(?:保证|必瘦|躺瘦|暴瘦|速瘦|排毒|燃脂神器|治愈|根治)", r"(?:\d+|[一二三四五六七八九十]+)\s*(?:天|周|月).*?(?:瘦|减重|减掉|掉秤).*?(?:\d+|[一二三四五六七八九十]+)\s*(?:斤|公斤|kg)", r"(?:不吃|戒掉|零)\s*(?:主食|碳水)", r"(?:局部|定点|只瘦).*?(?:减脂|肚子|腿)"]
    flags = [m.group(0) for p in patterns for m in re.finditer(p, text, re.I)]
    return {"status": "blocked" if flags else "needs_review", "flags": flags, "note": "规则检查不等于事实核查通过。逐条核对健康主张与来源原文；数值、禁忌和特殊人群建议须专业复核。来源为内置参考资料，未进行实时检索。", "sources": SOURCES}
