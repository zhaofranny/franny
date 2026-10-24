import io
import json
from zipfile import ZipFile, ZIP_DEFLATED
from .editorial import public_text, is_approved
from .health import review

def export_bundle(payload, images=None, *, publish_ready=False):
    if payload['health_review']['status'] == 'blocked' or review(public_text(payload))['status'] == 'blocked':
        raise ValueError('含高风险健康表述，请修改后重新检查')
    if publish_ready and not is_approved(payload):
        raise ValueError('正式素材必须为模型生成且通过当前版本的人工审核')
    if publish_ready and not images:
        raise ValueError('请先生成当前版本的图片')
    md = f"# {payload['title']}\n\n{payload['body']}\n\n" + ' '.join('#'+t.lstrip('#') for t in payload['tags'])
    status = '人工核查已确认，不代表医学正确或平台审核通过。' if is_approved(payload) else '待人工事实核查，未经审核请勿发布。'
    buf=io.BytesIO()
    with ZipFile(buf,'w',ZIP_DEFLATED) as z:
        z.writestr('draft.md',md+'\n\n---\n'+status+'\n'+'\n'.join(s['title']+': '+s['url'] for s in payload['health_review']['sources']))
        z.writestr('draft.json',json.dumps(payload,ensure_ascii=False,indent=2))
        z.writestr('image_prompts.json',json.dumps({'cover':payload['cover_prompt'],'illustrations':payload['image_prompts']},ensure_ascii=False,indent=2))
        z.writestr('REVIEW.txt',status+'\n'+payload['health_review']['note']+'\n图片为原创本地排版字卡；不包含第三方笔记图片。')
        for name,raw in (images or {}).items():
            if not name.endswith('.png') or '/' in name or '\\' in name or name.startswith('.'):
                raise ValueError('图片文件名无效')
            z.writestr('images/'+name,raw)
        if publish_ready:
            z.writestr('publish.txt',md+'\n')
    return buf.getvalue()
