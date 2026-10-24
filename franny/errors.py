"""Allowlisted diagnostics: never render raw API bodies, headers or credentials."""
import json
import math
import re
import sqlite3
from openai import APIConnectionError, APITimeoutError, APIStatusError
from pydantic import ValidationError
from .providers import ProviderConfigError, ProviderKeyFormatError

SAFE_STAGES = {'provider_config','client_init','model_request','decode_response','validate_copy','validate_draft','evidence_mapping','save_draft'}

def stage_call(stage, function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception as exc:
        # Keep original exception type for status/encoding classification; never copy raw text.
        if stage in SAFE_STAGES:
            try: exc.franny_stage = stage
            except (AttributeError, TypeError): pass
        raise

class EvidenceValidationError(ValueError):
    pass

class GenerationInputError(ValueError):
    pass

class GenerationResponseError(ValueError):
    pass

class GenerationBusyError(ValueError):
    pass

class GenerationCooldownError(ValueError):
    def __init__(self, seconds):
        self.seconds=max(1,int(seconds))
        super().__init__('生成冷却中')

def quota_failure(exc):
    # Some compatible services nest their code. Inspect privately, never echo raw text.
    body=getattr(exc,'body',None)
    body=body if isinstance(body,dict) else {}
    nested=body.get('error',{})
    nested=nested if isinstance(nested,dict) else {}
    codes=[getattr(exc,'code',None),body.get('code'),nested.get('code')]
    known={'insufficient_quota','billing_hard_limit_reached','billing_not_active','insufficient_balance','arrearage','quota.freeallocatedquota','prepaidbalanceexhausted'}
    if any(isinstance(c,str) and c.lower() in known for c in codes): return True
    msgs=[body.get('message'),nested.get('message')]
    return any(isinstance(m,str) and any(t in m.lower() for t in ['insufficient_quota','insufficient balance','余额不足','账户欠费']) for m in msgs)

def retry_after(exc):
    response=getattr(exc,'response',None)
    try:
        value=float(response.headers.get('retry-after','60')) if response is not None else 60
        if not math.isfinite(value): raise ValueError()
        return max(30,min(900,math.ceil(value)))
    except (ValueError,TypeError): return 60

def explain_error(exc, provider=None):
    status=getattr(exc,'status_code',None) if isinstance(exc,APIStatusError) else None
    if isinstance(exc,GenerationBusyError):
        return {"code":"GENERATION_BUSY","message":"上一次生成仍在处理中，请等待完成后查看素材库；本次未重复调用模型。"}
    if isinstance(exc,GenerationCooldownError):
        return {'code':'GENERATION_COOLDOWN','message':f'冷却中，请约{exc.seconds}秒后手动重试；没有再次调用模型。','retry_after_seconds':exc.seconds}
    if isinstance(exc,APITimeoutError):
        code,message='API_TIMEOUT','连接模型超时。请检查部署服务器到所选模型官方接口的网络，稍后手动重试。'
    elif isinstance(exc,APIConnectionError):
        code,message='API_CONNECTION','部署服务器无法连接所选模型。请检查出站网络、DNS、TLS和服务端地址；本机模型必须运行在同一台服务器上。'
    elif status==401:
        code,message='API_AUTH_401','模型服务鉴权失败。请在服务端更新对应服务商的有效密钥，并检查千问密钥与接口地域是否一致。'
    elif status==402 or (status in {400,403,429} and quota_failure(exc)):
        code,message='API_QUOTA_429' if status==429 else 'API_QUOTA','所选模型的官方API额度或余额不足。请查看对应服务商的账单及项目预算；更换Codex/ChatGPT套餐不能解决API余额问题。不会自动重试或转用其他付费服务。'
    elif status==429:
        code,message='API_RATE_429','所选模型返回429，可能是请求频率、并发或未明确说明的额度限制。已暂停重复调用；请查看官方用量/账单，冷却后手动重试。'
    elif status==403:
        code,message='API_PERMISSION_403','所选服务商拒绝访问，请检查账号、项目权限、地域及服务开通状态。'
    elif status==404:
        code,message='API_MODEL_404','模型不存在、未下载或项目无权使用。请检查服务端模型名称；本机Ollama需先下载对应模型。'
    elif status in {400,422}:
        code,message='API_REQUEST_400','模型不支持当前请求参数。请配置支持Chat Completions及JSON输出的模型，优先使用纯文案模式。'
    elif status and status>=500:
        code,message='API_SERVER','模型服务暂时异常，请稍后手动重试。'
    elif isinstance(exc,EvidenceValidationError):
        code,message='EVIDENCE_ALIGNMENT','正文与证据引用未对齐，请在编辑区核对来源和正文原句；无需更换密钥。'
    elif isinstance(exc,GenerationInputError):
        code,message='INPUT_INVALID','选题不能为空且最多200字，目标人群最多200字，栏目必须是列表中的选项。'
    elif isinstance(exc,ValidationError):
        code,message='OUTPUT_VALIDATION','模型已返回内容，但长度或结构不合要求。可换具体选题或使用纯文案模式；不代表密钥无效。'
    elif isinstance(exc,(GenerationResponseError,json.JSONDecodeError)):
        code,message='OUTPUT_INCOMPLETE','模型输出被截断、拒绝、为空或缺少完整结构。请优先使用纯文案模式，检查服务端输出预算，不会自动重试消耗额度。'
    elif isinstance(exc,(ProviderKeyFormatError,UnicodeEncodeError)):
        code,message='KEY_CONFIG_ENCODING','请求配置含HTTP头不支持的字符。请检查服务端API密钥是否仍为中文占位文字、含全角字符或复制错误；不会显示原值，无需更换选题。'
    elif isinstance(exc,ProviderConfigError):
        code,message='PROVIDER_CONFIG','服务端模型配置无效或缺少密钥，请检查所选服务商的Secrets；不需要反复生成。'
    elif isinstance(exc,ValueError):
        stage=getattr(exc,'franny_stage',None)
        if stage in {'provider_config','client_init'}:
            code,message='CLIENT_CONFIG','模型客户端在本地初始化失败，尚未请求模型。请检查服务端密钥、代理和接口配置；不是选题问题。'
        elif stage=='model_request':
            code,message='REQUEST_CONFIG','请求在SDK处理阶段失败。请核对服务端密钥、模型和请求参数；不显示原始错误或密钥。'
        elif stage in {'decode_response','validate_copy','validate_draft','evidence_mapping'}:
            code,message='RESPONSE_DATA','返回内容不符合处理要求。请根据处理阶段检查模型输出，不需要重配工作台口令。'
        else:
            code,message='CONTENT_CHECK','配置、输入或生成内容未通过校验。请维护者检查具体处理阶段，不要反复调用。'
    elif isinstance(exc,sqlite3.Error):
        code,message='STORAGE_ERROR','数据库写入失败，请检查磁盘空间和数据库写权限。'
    else:
        code,message='GENERATION_ERROR','流程出现未分类错误。请维护者检查部署日志；不要公开密钥或完整请求内容。'
    result={'code':code,'message':message}
    stage=getattr(exc,'franny_stage',None)
    if stage in SAFE_STAGES: result['stage']=stage
    if status==429: result['retry_after_seconds']=300 if quota_failure(exc) else retry_after(exc)
    if status==402: result['retry_after_seconds']=300
    rid=getattr(exc,'request_id',None) if isinstance(exc,APIStatusError) else None
    if isinstance(rid,str) and re.fullmatch(r'req_[A-Za-z0-9_-]{1,100}',rid): result['request_id']=rid
    return result
