import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest
from openai import OpenAI, RateLimitError, APIStatusError
from streamlit.testing.v1 import AppTest
from franny.providers import load_provider, make_client, validate_endpoint, ProviderConfigError
from franny.generation import generate, CopyDraft
from franny.data import Store, parse_csv
from franny.analysis import rank_notes, analyze
from franny.service import create_and_save
from franny.errors import explain_error, GenerationCooldownError

@pytest.mark.parametrize('provider,key_name,model',[('deepseek','DEEPSEEK_API_KEY','deepseek-flash'),('qwen','DASHSCOPE_API_KEY','qwen-plus'),('openai','OPENAI_API_KEY','gpt-4o-mini'),('ollama',None,'qwen3:8b')])
def test_config_and_actual_sdk_options(monkeypatch,provider,key_name,model):
    if key_name: monkeypatch.setenv(key_name,' test-credential-do-not-print ')
    config=load_provider(provider)
    assert config.model==model
    assert 'test-credential' not in repr(config)
    client=make_client(config)
    assert client.max_retries==0 and client.timeout==60
    client.close()

@pytest.mark.parametrize('provider,url',[
    ('qwen','https://evil.example/compatible-mode/v1'),
    ('openai','https://api.openai.com.evil.example/v1'),
    ('deepseek','http://api.deepseek.com'),
    ('qwen','https://dashscope.aliyuncs.com/compatible-mode/v1?key=secret'),
    ('ollama','http://192.168.1.4:11434/v1'),
    ('ollama','http://user:pass@127.0.0.1:11434/v1'),
])
def test_endpoint_safety(provider,url):
    with pytest.raises(ProviderConfigError): validate_endpoint(provider,url)

def test_regional_qwen_and_invalid_configuration(monkeypatch):
    monkeypatch.setenv('DASHSCOPE_API_KEY','synthetic')
    monkeypatch.setenv('DASHSCOPE_BASE_URL','https://workspace-demo.cn-beijing.maas.aliyuncs.com/compatible-mode/v1')
    assert 'cn-beijing' in load_provider('qwen').base_url
    monkeypatch.setenv('LLM_TIMEOUT_SECONDS','nonsense')
    with pytest.raises(ProviderConfigError): load_provider('qwen')

def copy_fixture():
    raw=generate('午餐','成年人',{},demo=True)
    # A synthetic model response tests the transport contract, not factual quality.
    return {k:v for k,v in raw.items() if k in CopyDraft.model_fields}

@pytest.mark.parametrize('provider',['deepseek','qwen','openai','ollama'])
def test_import_analysis_real_sdk_copy_save_without_key_leak(tmp_path,monkeypatch,provider):
    import franny.generation as generation
    monkeypatch.setenv('DEEPSEEK_API_KEY','TEST_DEEPSEEK_SECRET')
    monkeypatch.setenv('DASHSCOPE_API_KEY','TEST_QWEN_SECRET')
    monkeypatch.setenv('OPENAI_API_KEY','TEST_OPENAI_SECRET')
    config=load_provider(provider)
    calls=[]
    def handle(request):
        calls.append(request)
        body=json.loads(request.content)
        assert body['model']==config.model
        assert body['max_tokens']==2200
        assert body['response_format']=={'type':'json_object'}
        assert 'cards' not in body['messages'][0]['content'] or '不要输出图片、cards' in body['messages'][0]['content']
        if provider=='deepseek': assert body['thinking']=={'type':'disabled'}
        if provider=='qwen': assert body['enable_thinking'] is False
        if provider=='ollama': assert body['reasoning_effort']=='none'
        prompt=json.loads(body['messages'][1]['content'])
        assert prompt['aggregate_insights']['sample_size']==6
        assert 'xiaohongshu.com' not in request.content.decode()
        assert config.api_key not in request.content.decode()
        return httpx.Response(200,json={'id':'test','object':'chat.completion','created':1,'model':config.model,'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(copy_fixture(),ensure_ascii=False)}}],'usage':{'prompt_tokens':120,'completion_tokens':300,'total_tokens':420}})
    client=OpenAI(api_key=config.api_key,base_url=config.base_url,max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(generation,'make_client',lambda config:client)
    db=Store(tmp_path/'original.db')
    df=parse_csv(Path('examples/notes.csv').read_bytes())
    db.import_notes(df)
    _,p=create_and_save(db,'均衡午餐','成年人',analyze(rank_notes(db.notes())),provider=provider,text_only=True)
    assert len(calls)==1 and len(db.notes())==6
    assert p['mode']==provider and p['generation_kind']=='copy'
    assert p['usage']['total_tokens']==420
    assert p['cards']==[] and len(db.drafts())==1
    stored=db.drafts()[0][2]
    for secret in ['TEST_DEEPSEEK_SECRET','TEST_QWEN_SECRET','TEST_OPENAI_SECRET']:
        assert secret not in stored
    with pytest.raises(GenerationCooldownError):
        create_and_save(db,'午餐','成年人',{},provider=provider,text_only=True)
    assert len(calls)==1
    client.close()

def test_429_no_auto_retry_and_nested_quota_cooldown(tmp_path,monkeypatch):
    import franny.generation as generation
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(429,json={'error':{'code':'insufficient_quota','message':'SECRET_DO_NOT_EXPOSE'}},headers={'retry-after':'120'})
    client=OpenAI(api_key='SYNTHETIC_KEY',base_url='https://api.deepseek.com',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    monkeypatch.setenv('DEEPSEEK_API_KEY','SYNTHETIC_KEY')
    monkeypatch.setattr(generation,'make_client',lambda config:client)
    db=Store(tmp_path/'quota.db')
    with pytest.raises(RateLimitError) as caught:
        create_and_save(db,'均衡午餐','成年人',{},provider='deepseek')
    assert len(calls)==1
    report=explain_error(caught.value)
    assert report['code']=='API_QUOTA_429' and report['retry_after_seconds']==300
    assert 'SECRET' not in json.dumps(report)
    with pytest.raises(GenerationCooldownError):
        create_and_save(db,'均衡午餐','成年人',{},provider='deepseek')
    assert len(calls)==1 and not db.drafts()
    client.close()

@pytest.mark.parametrize('status,body,expected',[(402,{'error':{'message':'余额不足'}},'API_QUOTA'),(429,{'error':{'code':'rate_limit_exceeded'}},'API_RATE_429'),(400,{'code':'Arrearage'},'API_QUOTA')])
def test_compatible_error_shapes(status,body,expected):
    response=httpx.Response(status,request=httpx.Request('POST','https://api.deepseek.com'),headers={'retry-after':'45'})
    err=APIStatusError('DO_NOT_ECHO',response=response,body=body)
    report=explain_error(err)
    assert report['code']==expected
    if expected=='API_RATE_429': assert report['retry_after_seconds']==45

def test_old_database_is_preserved_and_backup_reopens(tmp_path):
    path=tmp_path/'old.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE notes(title TEXT NOT NULL,url TEXT PRIMARY KEY,published_at TEXT NOT NULL,likes INTEGER,saves INTEGER,comments INTEGER)')
        db.execute('CREATE TABLE drafts(id INTEGER PRIMARY KEY,created_at TEXT DEFAULT CURRENT_TIMESTAMP,payload TEXT NOT NULL)')
        db.execute('INSERT INTO notes VALUES(?,?,?,?,?,?)',('旧数据','https://www.xiaohongshu.com/explore/synthetic','2020-01-01T00:00:00Z',1,2,3))
        db.execute('INSERT INTO drafts(payload) VALUES(?)',('{"legacy":"untouched"}',))
    store=Store(path)
    assert len(store.notes())==1 and store.drafts()[0][2]=='{"legacy":"untouched"}'
    backup=tmp_path/'backup.db';backup.write_bytes(store.backup_bytes())
    restored=Store(backup)
    assert restored.drafts()==store.drafts()
    assert len(restored.notes())==1

def test_no_credentials_in_ui_and_generation_to_library(tmp_path,monkeypatch):
    import franny.generation as generation
    monkeypatch.setenv('LLM_PROVIDER','deepseek')
    monkeypatch.setenv('DEEPSEEK_API_KEY','TEST_NEVER_RENDER_THIS_KEY')
    monkeypatch.setenv('APP_PASSWORD','test-access')
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'ui.db'))
    class Completion:
        def create(self,**kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(copy_fixture())))])
    monkeypatch.setattr(generation,'make_client',lambda config:SimpleNamespace(chat=SimpleNamespace(completions=Completion())))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run()
    app.text_input[0].set_value('test-access');app.button[0].click().run()
    assert not app.exception
    assert not any('API Key' in w.label for w in app.text_input)
    app.checkbox(key='data_authorized').check().run()
    next(b for b in app.button if b.label=='加载虚构示例').click().run()
    next(b for b in app.button if b.label=='生成原创草稿').click().run()
    assert not app.exception and len(app.expander)==1
    assert app.session_state['draft']['mode']=='deepseek'
    assert app.session_state['draft']['generation_kind']=='copy'
    assert 'TEST_NEVER_RENDER_THIS_KEY' not in str(app)
    assert 'TEST_NEVER_RENDER_THIS_KEY' not in Store(tmp_path/'ui.db').drafts()[0][2]
