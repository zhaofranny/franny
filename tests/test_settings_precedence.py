import pytest
import streamlit as st
from franny.settings import setting, setting_source
from franny.providers import load_provider, ProviderConfigError, validate_key, ProviderKeyFormatError

def test_saved_secrets_beats_old_placeholder_environment(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','旧的中文占位密钥')
    monkeypatch.setattr(st,'secrets',{'DEEPSEEK_API_KEY':'TEST_SYNTHETIC_ASCII_CREDENTIAL'})
    assert setting('DEEPSEEK_API_KEY')=='TEST_SYNTHETIC_ASCII_CREDENTIAL'
    assert setting_source('DEEPSEEK_API_KEY')=='Streamlit Secrets'
    assert load_provider('deepseek').api_key=='TEST_SYNTHETIC_ASCII_CREDENTIAL'

def test_clear_in_secrets_does_not_revive_old_credential(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','OLD_SYNTHETIC_CREDENTIAL')
    monkeypatch.setattr(st,'secrets',{'DEEPSEEK_API_KEY':''})
    assert setting('DEEPSEEK_API_KEY')==''
    with pytest.raises(ProviderConfigError): load_provider('deepseek')

def test_environment_and_defaults_still_work(monkeypatch):
    monkeypatch.setattr(st,'secrets',{})
    monkeypatch.setenv('DEEPSEEK_API_KEY','LOCAL_SYNTHETIC_CREDENTIAL')
    assert setting('DEEPSEEK_API_KEY')=='LOCAL_SYNTHETIC_CREDENTIAL'
    assert setting_source('DEEPSEEK_API_KEY')=='服务器环境变量'
    monkeypatch.delenv('UNUSED_TEST_SETTING',raising=False)
    assert setting('UNUSED_TEST_SETTING','fallback')=='fallback'
    assert setting_source('UNUSED_TEST_SETTING')=='默认值/未配置'

@pytest.mark.parametrize('key,reason',[('中文占位','非ASCII'),('sk-test\nabc','换行'),('sk-test\x00abc','控制字符'),('sk-xxx','示例占位')])
def test_precise_reason_without_leaking_key(key,reason):
    with pytest.raises(ProviderKeyFormatError) as caught:
        validate_key(key)
    assert reason in str(caught.value)
    assert key not in str(caught.value)
