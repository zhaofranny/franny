import io
import json
from zipfile import ZipFile, ZIP_DEFLATED

def export_bundle(payload):
    if payload["health_review"]["status"] == "blocked":
        raise ValueError("含高风险健康表述，请重新生成")
    md = f"# {payload['title']}\n\n{payload['body']}\n\n" + " ".join("#" + t.lstrip("#") for t in payload["tags"])
    md += "\n\n---\n待人工事实核查，未经审核请勿发布。\n"
    for s in payload["health_review"]["sources"]:
        md += f"\n- {s['title']}: {s['url']}"
    buf = io.BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as z:
        z.writestr("draft.md", md)
        z.writestr("draft.json", json.dumps(payload, ensure_ascii=False, indent=2))
        z.writestr("image_prompts.json", json.dumps({"cover": payload["cover_prompt"], "illustrations": payload["image_prompts"]}, ensure_ascii=False, indent=2))
        z.writestr("REVIEW.txt", payload["health_review"]["note"] + "\n图片生成适配器尚未配置，压缩包不含图片。")
    return buf.getvalue()
