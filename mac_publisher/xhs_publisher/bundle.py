import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, field_validator

class BundleError(ValueError): pass

class Manifest(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    title: str=Field(min_length=1,max_length=20)
    body: str=Field(min_length=1,max_length=1000)
    tags: list[str]=Field(default_factory=list,max_length=10)
    images: list[str]=Field(min_length=1,max_length=18)
    ai_generated: bool
    original_content: bool
    @field_validator('tags')
    @classmethod
    def tags_valid(cls,tags):
        tags=[t.strip().lstrip('#') for t in tags]
        if any(not t or len(t)>30 or re.search(r'[\s#\x00-\x1f]',t) for t in tags):
            raise ValueError('标签须为不含空白或#的1–30字话题')
        if len(set(tags))!=len(tags): raise ValueError('标签不能重复')
        return tags
    @field_validator('title','body')
    @classmethod
    def text_valid(cls,value):
        if not value or any(ord(c)<32 and c not in '\n\t' for c in value): raise ValueError('文本含不可用控制字符')
        return value

RISK_PATTERNS=[r'保证.{0,8}(?:瘦|减重)',r'必瘦|暴瘦|催吐|泻药|利尿剂|断水|脱水掉秤',r'(?:不吃|零|戒掉)\s*(?:主食|碳水)',r'\d+\s*(?:天|周|月).{0,12}(?:瘦|减掉|掉秤).{0,6}\d+\s*(?:斤|公斤|kg)',r'局部减脂|燃脂神器',r'离线.{0,8}示例|非在线AI原创']

def load_bundle(root):
    root=Path(root).resolve()
    path=root/'manifest.json'
    if not path.is_file() or path.stat().st_size>1024*1024: raise BundleError('缺少manifest.json或文件超过1MB')
    try: manifest=Manifest.model_validate_json(path.read_text(encoding='utf-8'))
    except Exception as exc: raise BundleError('素材清单格式不符：标题≤20字、正文≤1000字、图片1–18张，需填写真实AI/原创声明') from exc
    combined=manifest.title+'\n'+manifest.body+'\n'+' '.join(manifest.tags)
    if any(re.search(p,combined,re.I) for p in RISK_PATTERNS):
        raise BundleError('内容包含高风险减重表述或离线示例标识，请编辑并人工核查后再发布')
    files=[];hashes=[]
    for relative in manifest.images:
        p=(root/relative).resolve()
        if not p.is_relative_to(root) or not p.is_file() or p.stat().st_size>20*1024*1024:
            raise BundleError('图片路径越界、文件缺失或超过20MB')
        if p.suffix.lower() not in {'.png','.jpg','.jpeg','.webp'}: raise BundleError('仅支持PNG/JPEG/WebP本地图片')
        try:
            with Image.open(p) as image:
                if image.width*image.height>60_000_000: raise BundleError('图片像素过大')
                image.verify()
        except BundleError: raise
        except Exception as exc: raise BundleError('图片无法解码') from exc
        files.append(p);hashes.append(hashlib.sha256(p.read_bytes()).hexdigest())
    if len(set(hashes))!=len(hashes): raise BundleError('存在重复图片，请移除后重试')
    encoded=json.dumps({'manifest':manifest.model_dump(),'image_sha256':hashes},ensure_ascii=False,sort_keys=True).encode()
    return manifest,files,hashlib.sha256(encoded).hexdigest()

def import_zip(raw,target):
    if len(raw)>100*1024*1024: raise BundleError('ZIP不能超过100MB')
    target=Path(target).resolve();target.mkdir(parents=True,exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members=z.infolist()
            if len(members)>100 or sum(x.file_size for x in members)>120*1024*1024: raise BundleError('ZIP解压内容过大')
            for info in members:
                path=(target/info.filename).resolve()
                if not path.is_relative_to(target) or stat.S_ISLNK(info.external_attr>>16) or info.flag_bits&1:
                    raise BundleError('ZIP含越界路径、符号链接或加密文件')
                if info.is_dir(): continue
                if path.suffix.lower() not in {'.json','.png','.jpg','.jpeg','.webp','.txt','.md'}: continue
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(z.read(info))
        manifests=list(target.rglob('manifest.json'))
        if len(manifests)==1: return manifests[0].parent
        drafts=list(target.rglob('draft.json'))
        if len(drafts)!=1: raise BundleError('ZIP需包含唯一manifest.json或draft.json')
        source=drafts[0];data=json.loads(source.read_text(encoding='utf-8'))
        if data.get('mode')=='offline_template': raise BundleError('离线模板不能作为正式发布素材')
        images=sorted(p for p in source.parent.rglob('*') if p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'})
        if not images: raise BundleError('素材包没有图片；请先生成PNG或上传自己的原创图片')
        # Imported declarations are not approvals; UI requires fresh rights/health confirmation.
        manifest=Manifest(title=data['title'],body=data['body'],tags=data.get('tags',[]),images=[str(p.relative_to(source.parent)) for p in images],ai_generated=True,original_content=True)
        (source.parent/'manifest.json').write_text(manifest.model_dump_json(indent=2),encoding='utf-8')
        return source.parent
    except BundleError: raise
    except Exception as exc: raise BundleError('ZIP无法读取或素材格式不完整') from exc
