"""Server-only provider configuration. Never serialize this object to UI or storage."""
from dataclasses import dataclass, field
import re
from urllib.parse import urlsplit
from .settings import setting

class ProviderConfigError(ValueError):
    pass

class ProviderKeyFormatError(ProviderConfigError):
    pass

def validate_key(key):
    # Never echo any part of the input; reasons are fixed, safe labels.
    if not key.isascii():
        reason='包含非ASCII字符（例如中文、全角引号或全角符号）'
    elif any(ch.isspace() for ch in key):
        reason='包含密钥中间的空格、换行或制表符'
    elif any(not ch.isprintable() for ch in key):
        reason='包含不可见控制字符'
    elif key.lower() in {'your-api-key','your_api_key','sk-xxx','replace-me','your-key'}:
        reason='仍为示例占位值'
    else:
        return key
    raise ProviderKeyFormatError('所选模型的服务端密钥'+reason+'。请仅在当前应用的Secrets中核对对应配置项；程序未发送API请求，不会显示密钥内容。')

@dataclass(frozen=True)
class ProviderSpec:
    label: str
    key_env: str
    model_env: str
    default_model: str
    endpoint: str

PROVIDERS = {
    'deepseek': ProviderSpec('DeepSeek 官方','DEEPSEEK_API_KEY','DEEPSEEK_MODEL','deepseek-flash','https://api.deepseek.com'),
    'qwen': ProviderSpec('阿里云百炼 · 千问','DASHSCOPE_API_KEY','QWEN_MODEL','qwen-plus','https://dashscope.aliyuncs.com/compatible-mode/v1'),
    'openai': ProviderSpec('OpenAI（可选）','OPENAI_API_KEY','OPENAI_MODEL','gpt-4o-mini','https://api.openai.com/v1'),
    'ollama': ProviderSpec('Ollama · 本机模型','', 'OLLAMA_MODEL','qwen3:8b','http://127.0.0.1:11434/v1'),
}

@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str
    base_url: str = field(repr=False)
    api_key: str = field(repr=False)
    timeout: int = 60
    max_tokens: int = 2200

def validate_endpoint(name, url):
    try:
        parsed=urlsplit(url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError()
        if name=='ollama':
            valid=parsed.scheme=='http' and parsed.hostname in {'localhost','127.0.0.1','::1'} and parsed.path.rstrip('/')=='/v1'
        elif name=='qwen':
            host=parsed.hostname or ''
            valid=parsed.scheme=='https' and (host in {'dashscope.aliyuncs.com','dashscope-intl.aliyuncs.com','dashscope-us.aliyuncs.com'} or bool(re.fullmatch(r'[a-zA-Z0-9-]+\.(?:cn-beijing|ap-southeast-1|us-east-1|ap-northeast-1)\.maas\.aliyuncs\.com',host))) and parsed.path.rstrip('/')=='/compatible-mode/v1' and parsed.port in (None,443)
        else:
            valid=parsed.scheme=='https' and parsed.hostname=={'openai':'api.openai.com','deepseek':'api.deepseek.com'}[name] and parsed.port in (None,443) and parsed.path.rstrip('/') in ('','/v1')
        if not valid: raise ValueError()
    except (ValueError, KeyError) as exc:
        raise ProviderConfigError('服务端模型接口地址不合规；仅允许对应官方域名，本机模式仅允许回环地址') from exc
    return url.rstrip('/')

def load_provider(name=None):
    name=name or setting('LLM_PROVIDER','deepseek')
    if name not in PROVIDERS:
        raise ProviderConfigError('LLM_PROVIDER必须为deepseek、qwen、openai或ollama')
    spec=PROVIDERS[name]
    model=setting(spec.model_env,spec.default_model).strip()
    if not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,120}',model):
        raise ProviderConfigError('服务端模型名称格式无效')
    endpoint=setting({'qwen':'DASHSCOPE_BASE_URL','ollama':'OLLAMA_BASE_URL'}.get(name,'UNUSED_PROVIDER_ENDPOINT'),spec.endpoint).strip() if name in {'qwen','ollama'} else spec.endpoint
    endpoint=validate_endpoint(name,endpoint)
    key=setting(spec.key_env).strip() if spec.key_env else 'ollama'
    if not key:
        raise ProviderConfigError('服务端尚未配置所选模型的API密钥')
    if name!='ollama':
        validate_key(key)
    try:
        timeout=int(setting('LLM_TIMEOUT_SECONDS','60'))
        tokens=int(setting('LLM_MAX_TOKENS','2200'))
        if not 5<=timeout<=120 or not 512<=tokens<=6000: raise ValueError()
    except ValueError as exc:
        raise ProviderConfigError('LLM_TIMEOUT_SECONDS需为5–120，LLM_MAX_TOKENS需为512–6000') from exc
    return ProviderConfig(name,model,endpoint,key,timeout,tokens)

def make_client(config):
    from openai import OpenAI
    # One request per click: no automatic retry or fallback to another paid service.
    return OpenAI(api_key=config.api_key,base_url=config.base_url,timeout=config.timeout,max_retries=0)

def extra_parameters(config):
    if config.name=='deepseek' and config.model in {'deepseek-flash','deepseek-v4-pro'}:
        return {'extra_body':{'thinking':{'type':'disabled'}}}
    if config.name=='qwen':
        return {'extra_body':{'enable_thinking':False}}
    if config.name=='ollama':
        return {'reasoning_effort':'none'}
    return {}
