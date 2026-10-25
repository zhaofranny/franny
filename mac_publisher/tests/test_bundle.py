import io
import json
import zipfile
from pathlib import Path
from PIL import Image
import pytest
from xhs_publisher.bundle import load_bundle,Manifest,BundleError,import_zip

@pytest.fixture
def bundle(tmp_path):
    Image.new('RGB',(120,160),'green').save(tmp_path/'01.png')
    data={'title':'今晚吃饭，少一点纠结','body':'这是一份独立的合成测试文案，只用于本地测试，不会发到小红书。','tags':[],'images':['01.png'],'ai_generated':True,'original_content':True}
    (tmp_path/'manifest.json').write_text(json.dumps(data,ensure_ascii=False))
    return tmp_path

def test_fingerprint_tracks_every_material_change(bundle):
    m,_,old=load_bundle(bundle)
    m.body+='修改'
    (bundle/'manifest.json').write_text(m.model_dump_json())
    assert load_bundle(bundle)[2]!=old
    current=load_bundle(bundle)[2]
    Image.new('RGB',(120,160),'orange').save(bundle/'01.png')
    assert load_bundle(bundle)[2]!=current

@pytest.mark.parametrize('text',['7天瘦10斤','靠催吐减重','这是离线风格示例'])
def test_dangerous_or_demo_not_publishable(bundle,text):
    raw=json.loads((bundle/'manifest.json').read_text());raw['body']=text
    (bundle/'manifest.json').write_text(json.dumps(raw))
    with pytest.raises(BundleError): load_bundle(bundle)

def test_image_escape_and_duplicate(bundle,tmp_path):
    raw=json.loads((bundle/'manifest.json').read_text());raw['images']=['../outside.png']
    (bundle/'manifest.json').write_text(json.dumps(raw))
    with pytest.raises(BundleError): load_bundle(bundle)
    raw['images']=['01.png','01.png'];(bundle/'manifest.json').write_text(json.dumps(raw))
    with pytest.raises(BundleError): load_bundle(bundle)

def test_zip_path_traversal(tmp_path):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:z.writestr('../evil.txt','x')
    with pytest.raises(BundleError): import_zip(buf.getvalue(),tmp_path/'unzip')
    assert not (tmp_path/'evil.txt').exists()

def test_import_previous_franny_zip(bundle,tmp_path):
    raw=json.loads((bundle/'manifest.json').read_text());raw['mode']='deepseek'
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        z.writestr('draft.json',json.dumps(raw));z.writestr('images/01.png',(bundle/'01.png').read_bytes())
    folder=import_zip(buf.getvalue(),tmp_path/'unzip')
    m,images,_=load_bundle(folder)
    assert len(images)==1 and m.ai_generated
