"""Editorial brief and human review workflow; no platform publishing API."""
import hashlib
import json
from datetime import datetime, timezone
from .health import review

DIRECTIONS = {
    "邪修减肥大法 · 省力习惯派": "标题用口语反差、具体生活场景和轻吐槽抓住注意力，避免科普说明书腔。用省力动作表达健康习惯。邪修只是栏目包装，不提供危险偏方。钩子→场景痛点→3到5个可执行动作→适用边界→真实互动提问。",
    "外卖党 · 搭配派": "围绕外卖选择与搭配，具体到点单动作，不评判食物、不鼓励补偿性运动。",
    "上班族 · 碎片活动派": "把适合个人的活动融入通勤和工作间隙，不宣称碎片活动一定减重。",
}
# Original editorial seeds, not scraped or claimed to be proven viral titles.
IDEAS = [
    "减脂人，别再和意志力硬刚了",
    "减脂邪修：给外卖菜单重新排个位",
    "一下班就没电？运动先别整太复杂",
    "体重秤一响，脑内小剧场又开演了",
    "周日备好这张单，周一少纠结一餐",
]
TITLE_BRIEF = """标题风格：网感强但表达具体，像朋友替读者说出心声。不要写工作汇报式标题，例如‘把自律改成顺手的3件事’、‘健康管理指南’、‘科学减脂新方法’。
先找一个读者能看见的场景或对象（外卖菜单、下班没电、采购清单、体重秤），再用一句有反差的口语点出矛盾。可用‘别硬刚’、‘先别整太复杂’、‘脑内小剧场’等口语，但不要每条硬塞‘邪修’或堆叠流行词。标题必须由正文具体兑现；不能只用‘这招’、‘真相’、‘震惊’制造空洞悬念。
主标题20字内，另给5个互不重复、各20字内的备选，依次尝试：反差吐槽、场景共鸣、好奇提问、低门槛行动、情绪松绑。避免同一句换同义词。标题中的对象、矛盾和承诺在正文开头两句就要接住。
不借‘全网都在用’、‘99%的人不知道’、‘爆火’、‘亲测有效’、虚构第一人称或‘瘦了几斤’制造社会证明。不要宣称省力动作保证减脂、代谢改变或吃法决定体重，不写身材羞辱和身体焦虑。参考种子只学习表达，不照抄，围绕用户选题重新创作。"""


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
    if p.get('mode') not in {'openai','deepseek','qwen','ollama'}:
        raise ValueError('离线示例不能标记为正式发布素材，请使用在线生成')
    if p.get('generation_issues') or len(p.get('title',''))>20 or len(p.get('body',''))>1000:
        raise ValueError('请先在编辑区缩短标题至20字、正文至1000字并保存')
    if p.get('evidence_issues'):
        raise ValueError('来源引用存在待修正项，请在编辑区处理引用警告并保存')
    if p['health_review']['status'] == 'blocked':
        raise ValueError('健康风险未解决，不能确认审核')
    if not reviewer.strip() or not notes.strip():
        raise ValueError('请填写审核人和逐条核对记录')
    p['approval'] = {'reviewer':reviewer.strip(), 'notes':notes.strip(), 'content_sha256':fingerprint(p), 'at':datetime.now(timezone.utc).isoformat(), 'type':'human_attestation'}
    return p

def is_approved(p):
    return (p.get('mode') in {'openai','deepseek','qwen','ollama'} and len(p.get('title',''))<=20 and len(p.get('body',''))<=1000 and not p.get('generation_issues') and not p.get('evidence_issues') and p.get('approval',{}).get('content_sha256') == fingerprint(p)
            and review(public_text(p))['status'] != 'blocked')
