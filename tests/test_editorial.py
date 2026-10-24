import io
from copy import deepcopy
from zipfile import ZipFile
from PIL import Image
import pytest
from streamlit.testing.v1 import AppTest
from pathlib import Path
from franny.editorial import approve, is_approved, refresh_review, public_text
from franny.generation import generate, validate_draft
from franny.cards import render_cards
from franny.export import export_bundle
from franny.health import review

@pytest.fixture
def draft():
    return generate('省力习惯','成年人',{},demo=True)

@pytest.mark.parametrize('text',['靠催吐控制体重','断水掉秤','每天只吃500千卡','泻药减重','7天暴瘦10斤'])
def test_dangerous_style_blocked(text):
    assert review(text)['status'] == 'blocked'

def test_approval_invalidated_by_edit(draft):
    with pytest.raises(ValueError): approve(draft,'编辑','核对WHO原文')
    draft['mode']='openai'
    p=approve(draft,'编辑','逐条核对WHO饮食与活动原文，未承诺效果')
    assert is_approved(p)
    for field in ['body','title','cover_prompt']:
        edited=deepcopy(p);edited[field]+='修改'
        assert not is_approved(edited)
    assert 'approval' not in refresh_review(p)
    unsafe=deepcopy(p);unsafe['cards'][0]['text']='断水掉秤'
    with pytest.raises(ValueError): approve(unsafe,'编辑','test')
    with pytest.raises(ValueError): approve(draft,'','')

def test_png_and_formal_bundle(draft):
    images=render_cards(draft)
    assert len(images)==4
    for raw in images.values():
        im=Image.open(io.BytesIO(raw))
        assert im.size==(1080,1440) and im.format=='PNG'
    with pytest.raises(ValueError): export_bundle(draft,images,publish_ready=True)
    draft['mode']='openai'
    p=approve(draft,'编辑','已对照来源检查全部卡片与正文')
    with ZipFile(io.BytesIO(export_bundle(p,images,publish_ready=True))) as z:
        assert 'publish.txt' in z.namelist()
        assert len([n for n in z.namelist() if n.startswith('images/')])==4
    with pytest.raises(ValueError): export_bundle(p,publish_ready=True)
    p['body']+='必瘦'
    with pytest.raises(ValueError): export_bundle(p,images,publish_ready=True)

def test_dangerous_images_cannot_bypass(draft):
    draft['cards'][0]['text']='只喝水'
    with pytest.raises(ValueError): render_cards(draft)
    with pytest.raises(ValueError): export_bundle(draft)

def test_claim_alignment_and_title_limit(draft):
    from franny.generation import Draft
    fields={k:v for k,v in draft.items() if k in Draft.model_fields}
    fields['claims'][0]['quote']='不存在的正文'
    with pytest.raises(ValueError): validate_draft(fields)
    fields['claims']=[]
    fields['title']='很长的标题'*10
    with pytest.raises(ValueError): validate_draft(fields)

def test_login_gate(tmp_path,monkeypatch):
    monkeypatch.setenv('APP_PASSWORD','test-passphrase')
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'gate.db'))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
    assert not app.exception and not app.tabs
    app.text_input[0].set_value('wrong')
    app.button[0].click().run()
    assert len(app.error)==1 and not app.tabs
    app.text_input[0].set_value('test-passphrase')
    app.button[0].click().run()
    assert not app.exception and len(app.tabs)==4

def test_online_is_default_no_fake_generation(tmp_path,monkeypatch):
    monkeypatch.delenv('APP_PASSWORD',raising=False)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'default.db'))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
    assert not app.exception
    assert app.toggle[0].value is False
    assert next(b for b in app.button if b.label=='生成原创草稿').disabled

def test_formal_ui_review_and_export(tmp_path,monkeypatch):
    import franny.generation as generation
    real=generation.generate
    def fake(*args,**kwargs):
        # Deterministic SDK-free UI fixture, never used by production code.
        p=real('省力习惯','成年人',{},demo=True)
        p['mode']='openai'
        return p
    monkeypatch.setattr(generation,'generate',fake)
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'flow.db'))
    monkeypatch.delenv('APP_PASSWORD',raising=False)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run()
    next(w for w in app.text_input if 'API Key' in w.label).set_value('mock-key').run()
    next(b for b in app.button if b.label=='生成原创草稿').click().run()
    assert not app.exception
    next(b for b in app.button if b.label=='生成原创封面和配图 PNG').click().run()
    next(w for w in app.text_input if w.label=='审核人').set_value('编辑')
    next(w for w in app.text_area if w.label.startswith('逐条核对记录')).set_value('对照WHO原文复核全部正文与字卡，不承诺效果')
    next(w for w in app.checkbox if w.label.startswith('已核对全部')).check()
    next(b for b in app.button if b.label=='确认当前版本人工审核').click().run()
    assert not app.exception
    assert is_approved(app.session_state['draft'])
    assert len(app.session_state['card_images'])==4
    next(w for w in app.text_input if w.label=='最终标题').set_value('省力习惯，从顺手开始')
    next(b for b in app.button if b.label=='保存修改并重新检查').click().run()
    assert not app.exception
    assert not is_approved(app.session_state['draft'])
    assert 'card_images' not in app.session_state
