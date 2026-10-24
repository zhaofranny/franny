import json
from types import SimpleNamespace
import pytest
from franny.generation import generate, CopyDraft
from franny.editorial import approve, is_approved
from franny.data import Store
from franny.service import create_and_save
from franny.errors import explain_error, EvidenceValidationError, GenerationInputError
from franny.providers import ProviderConfigError

@pytest.mark.parametrize('kind',['unknown_source','unknown_claim','missing_quote','missing_source'])
def test_evidence_error_preserves_copy_and_saves(tmp_path,kind):
    seed=generate('午餐','成年人',{},demo=True)
    raw={k:v for k,v in seed.items() if k in CopyDraft.model_fields}
    if kind=='unknown_source': raw['source_ids']=['INVENTED_SOURCE']
    if kind=='unknown_claim': raw['claims'][0]['source_id']='INVENTED_SOURCE'
    if kind=='missing_quote': raw['claims'][0]['quote']='不在正文中的句子'
    if kind=='missing_source': raw['source_ids']=[]
    calls=[]
    class Completion:
        def create(self,**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(raw)))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=Completion()))
    db=Store(tmp_path/'preserve.db')
    _,p=create_and_save(db,'午餐','成年人',{},provider='deepseek',text_only=True,client=client)
    assert p['body']==raw['body'] and p['title']==raw['title']
    assert p['evidence_issues']
    assert len(calls)==1 and len(db.drafts())==1
    assert 'INVENTED_SOURCE' not in p['source_ids']
    assert all(c['quote'] in p['body'] for c in p['claims'])
    assert not is_approved(p)
    with pytest.raises(ValueError): approve(p,'编辑','已复核')

def test_safe_diagnostic_codes():
    assert explain_error(EvidenceValidationError('SECRET'))['code']=='EVIDENCE_ALIGNMENT'
    assert explain_error(GenerationInputError('SECRET'))['code']=='INPUT_INVALID'
    assert explain_error(ProviderConfigError('SECRET'))['code']=='PROVIDER_CONFIG'
    for e in [EvidenceValidationError('SECRET'),GenerationInputError('SECRET'),ProviderConfigError('SECRET')]:
        assert 'SECRET' not in json.dumps(explain_error(e))

def test_ui_retains_warning_until_editor_handles_it(tmp_path,monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    import franny.generation as generation
    seed=generate('午餐','成年人',{},demo=True)
    raw={k:v for k,v in seed.items() if k in CopyDraft.model_fields}
    raw['claims'][0]['quote']='并不在正文的句子'
    calls=[]
    class Completion:
        def create(self,**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(raw)))])
    monkeypatch.setenv('APP_PASSWORD','local-test-pass')
    monkeypatch.setenv('DEEPSEEK_API_KEY','SYNTHETIC_TEST_KEY')
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'ui.db'))
    monkeypatch.setattr(generation,'make_client',lambda cfg:SimpleNamespace(chat=SimpleNamespace(completions=Completion())))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run()
    app.text_input[0].set_value('local-test-pass');app.button[0].click().run()
    next(b for b in app.button if b.label=='生成原创草稿').click().run()
    assert not app.exception
    assert app.session_state['draft']['evidence_issues']==['QUOTE_NOT_IN_BODY']
    assert len(app.expander)==1 and len(calls)==1
    next(b for b in app.button if b.label=='保存修改并重新检查').click().run()
    assert not app.exception and app.session_state['draft']['evidence_issues']
    next(c for c in app.checkbox if c.label.startswith('已逐条处理引用警告')).check()
    next(b for b in app.button if b.label=='保存修改并重新检查').click().run()
    assert not app.exception
    assert app.session_state['draft']['evidence_issues']==[]
    assert len(calls)==1
