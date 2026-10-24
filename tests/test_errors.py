import json
import sqlite3
import httpx
import pytest
from openai import AuthenticationError, RateLimitError, NotFoundError, BadRequestError, PermissionDeniedError, APIConnectionError, APITimeoutError, InternalServerError
from pydantic import ValidationError
from franny.errors import explain_error, GenerationResponseError
from franny.generation import Draft

@pytest.mark.parametrize('cls,status,api_code,expected',[
    (AuthenticationError,401,'invalid_api_key','API_AUTH_401'),
    (RateLimitError,429,'insufficient_quota','API_QUOTA_429'),
    (RateLimitError,429,'rate_limit_exceeded','API_RATE_429'),
    (NotFoundError,404,'model_not_found','API_MODEL_404'),
    (BadRequestError,400,'bad_parameter','API_REQUEST_400'),
    (PermissionDeniedError,403,'unsupported_country','API_PERMISSION_403'),
    (InternalServerError,500,None,'API_SERVER'),
])
def test_api_diagnostics_never_leak(cls,status,api_code,expected):
    response=httpx.Response(status,request=httpx.Request('POST','https://api.openai.com/v1/chat/completions'),headers={'x-request-id':'req_test123'})
    exc=cls('SECRET_MUST_NOT_LEAK',response=response,body={'code':api_code,'message':'SECRET_MUST_NOT_LEAK'})
    report=explain_error(exc)
    assert report['code']==expected
    assert 'SECRET_MUST_NOT_LEAK' not in json.dumps(report)
    assert report['request_id']=='req_test123'

@pytest.mark.parametrize('exc,code',[
    (APIConnectionError(request=httpx.Request('POST','https://api.openai.com')),'API_CONNECTION'),
    (APITimeoutError(request=httpx.Request('POST','https://api.openai.com')),'API_TIMEOUT'),
    (GenerationResponseError('SECRET'),'OUTPUT_INCOMPLETE'),
    (ValueError('SECRET'),'CONTENT_CHECK'),
    (sqlite3.OperationalError('SECRET'),'STORAGE_ERROR'),
    (RuntimeError('SECRET'),'GENERATION_ERROR'),
])
def test_other_errors(exc,code):
    report=explain_error(exc)
    assert report['code']==code
    assert 'SECRET' not in json.dumps(report)

def test_validation_values_are_not_shown():
    with pytest.raises(ValidationError) as err:
        Draft.model_validate({'title':'SECRET_VALUE'})
    report=explain_error(err.value)
    assert report['code']=='OUTPUT_VALIDATION'
    assert 'SECRET_VALUE' not in json.dumps(report)

@pytest.mark.parametrize('finish,content',[('length','{}'),('content_filter',None),('stop',None),('stop','not-json')])
def test_incomplete_model_response(finish,content):
    from types import SimpleNamespace
    from franny.generation import generate
    class Completions:
        def create(self,**kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish,message=SimpleNamespace(content=content))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    with pytest.raises((GenerationResponseError,json.JSONDecodeError)) as caught:
        generate('均衡午餐','成年人',{},client=client)
    assert explain_error(caught.value)['code']=='OUTPUT_INCOMPLETE'
