"""Editorial brief and human review workflow; no platform publishing API."""
import hashlib
import json
from datetime import datetime, timezone
from .health import review

DIRECTIONS = {
    "邪修减肥大法 · 省力习惯派": "用反差、吐槽、生活场景和省力动作表达健康习惯。邪修只是栏目包装，不提供危险偏方。钩子→场景痛点→3到5个可执行动作→适用边界→真实互动提问。",
    "外卖党 · 搭配派": "围绕外卖选择与搭配，具体到点单动作，不评判食物、不鼓励补偿性运动。",
    "上班族 · 碎片活动派": "把适合个人的活动融入通勤和工作间隙，不宣称碎片活动一定减重。",
}
IDEAS = [
    "邪修减肥大法：把自律改成顺手的3件事",
    "外卖党省力搭配：先选蔬菜，再把一餐配完整",
    "下班只想躺？给活动安排一个顺路入口",
    "别让体重秤决定心情：记录执行体验",
    "周末采购清单：让工作日少做几次选择",
]

def public_text(p):
    return "\n".join([p.get('title',''), p.get('body',''), *p.get('tags',[]), *p.get('title_options',[]), p.get('cover_prompt',''), *p.get('image_prompts',[]), *[c.get('heading','')+'\n'+c.get('text','') for c in p.get('cards',[])]])

def refresh_review(p):
    p = dict(p)
    p.pop('approval', None)
    p['health_review'] = review(public_text(p))
    return p

def fingerprint(p):
    # Every field influencing text, images, or audit mode invalidates previous approval.
    clean = {k:v for k,v in p.items() if k not in {'approval','health_review'}}
    return hashlib.sha256(json.dumps(clean, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def approve(p, reviewer, notes):
    p = refresh_review(p)
    if p.get('mode') != 'openai':
        raise ValueError('离线示例不能标记为正式发布素材，请使用在线生成')
    if p['health_review']['status'] == 'blocked':
        raise ValueError('健康风险未解决，不能确认审核')
    if not reviewer.strip() or not notes.strip():
        raise ValueError('请填写审核人和逐条核对记录')
    p['approval'] = {'reviewer':reviewer.strip(), 'notes':notes.strip(), 'content_sha256':fingerprint(p), 'at':datetime.now(timezone.utc).isoformat(), 'type':'human_attestation'}
    return p

def is_approved(p):
    return (p.get('mode') == 'openai' and p.get('approval',{}).get('content_sha256') == fingerprint(p)
            and review(public_text(p))['status'] != 'blocked')
