import json
import httpx
import pytest
from openai import OpenAI
from pathlib import Path
from streamlit.testing.v1 import AppTest
from franny.providers import load_provider, ProviderKeyFormatError
from franny.errors import explain_error

@pytest.mark.parametrize('bad_key',['你的DeepSeek官方密钥','粘贴你刚创建的完整密钥','sk-test\nsecondline','sk-test\u200bhidden','sk-test full width','sk-xxx','your-api-key'])
def test_bad_key_rejected_before_client(monkeypatch,bad_key):
    monkeypatch.setenv('DEEPSEEK_API_KEY',bad_key)
    with pytest.raises(ProviderKeyFormatError) as err:
        load_provider('deepseek')
    assert bad_key not in str(err.value)
    report=explain_error(err.value)
    assert report['code']=='KEY_CONFIG_ENCODING'
    assert bad_key not in json.dumps(report,ensure_ascii=False)

def test_sdk_header_encoding_error_is_not_content_failure():
    calls=[]
    client=OpenAI(api_key='中文测试占位符',base_url='https://api.deepseek.com',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(lambda req:calls.append(req) or httpx.Response(200,json={})) ))
    with pytest.raises(UnicodeEncodeError) as caught:
        client.chat.completions.create(model='deepseek-flash',messages=[{'role':'user','content':'test'}])
    assert not calls
    report=explain_error(caught.value)
    assert report['code']=='KEY_CONFIG_ENCODING'
    assert '中文测试占位符' not in json.dumps(report,ensure_ascii=False)
    client.close()

def test_frontend_shows_safe_config_warning_without_api_call(tmp_path,monkeypatch):
    import franny.generation as generation
    monkeypatch.setenv('APP_PASSWORD','test-pass')
    monkeypatch.setenv('DEEPSEEK_API_KEY','仅用于测试的占位文字')
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'ui.db'))
    def must_not_call(*args,**kwargs): raise AssertionError('No API call should occur')
    monkeypatch.setattr(generation,'make_client',must_not_call)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run()
    app.text_input[0].set_value('test-pass');app.button[0].click().run()
    assert not app.exception
    assert next(b for b in app.button if b.label=='生成原创草稿').disabled
    assert any('非ASCII字符' in w.value for w in app.warning)
    assert '仅用于测试的占位文字' not in str(app)

@pytest.mark.parametrize('stage,expected',[('client_init','CLIENT_CONFIG'),('provider_config','CLIENT_CONFIG'),('model_request','REQUEST_CONFIG'),('validate_copy','RESPONSE_DATA')])
def test_sdk_value_error_has_safe_stage(stage,expected):
    from franny.errors import stage_call
    def fail(): raise ValueError('SYNTHETIC_SECRET_ERROR')
    with pytest.raises(ValueError) as err:
        stage_call(stage,fail)
    report=explain_error(err.value)
    assert report['code']==expected and report['stage']==stage
    assert 'SYNTHETIC_SECRET_ERROR' not in json.dumps(report)
