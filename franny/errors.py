"""Allowlisted diagnostics: never render raw API bodies, headers or credentials."""
import json
import re
import sqlite3
from openai import APIConnectionError, APITimeoutError, APIStatusError
from pydantic import ValidationError

class GenerationResponseError(ValueError):
    pass

def explain_error(exc):
    status = getattr(exc,'status_code',None) if isinstance(exc,APIStatusError) else None
    api_code = getattr(exc,'code',None) if isinstance(exc,APIStatusError) else None
    if isinstance(exc,APITimeoutError):
        code, message = 'API_TIMEOUT','连接模型超时。请稍后重试；若持续出现，请检查部署服务器到 api.openai.com 的连接。'
    elif isinstance(exc,APIConnectionError):
        code, message = 'API_CONNECTION','部署服务器无法连接 OpenAI。请检查服务器出站网络、DNS和TLS；不是你浏览器的本地连接。'
    elif status == 401:
        code, message = 'API_AUTH_401','OpenAI 拒绝了密钥。请从 OpenAI API Keys 页面复制完整有效密钥，确认未撤销、没有误填登录密码；替换后按回车。'
    elif status == 429 and api_code in {'insufficient_quota','billing_hard_limit_reached','billing_not_active'}:
        code, message = 'API_QUOTA_429','API 余额或项目预算不足。请检查 OpenAI API Billing、项目预算和用量限制；ChatGPT 订阅不包含 API 额度。充值或调整限制后再试。'
    elif status == 429:
        code, message = 'API_RATE_429','请求被限流，或 API 项目额度受限。请先查看 OpenAI API 用量与账单；余额正常时等待片刻再试，避免连续点击。'
    elif status == 403:
        code, message = 'API_PERMISSION_403','OpenAI 拒绝访问。请检查项目/密钥权限、服务支持地区及提供商政策；具体原因需在提供商后台确认。'
    elif status == 404:
        code, message = 'API_MODEL_404','模型不存在或当前项目无权访问。请确认模型名称和项目权限；可使用该项目已开放的模型。'
    elif status == 400:
        code, message = 'API_REQUEST_400','模型拒绝了请求参数。请确认使用支持 Chat Completions 与 JSON 输出的模型（如有权使用的 gpt-4o-mini）。'
    elif status and status >= 500:
        code, message = 'API_SERVER','OpenAI 服务暂时异常，请稍后重试。'
    elif isinstance(exc,ValidationError):
        code, message = 'OUTPUT_VALIDATION','模型已返回内容，但标题长度、正文或图文卡片等字段不符合要求。可重新生成，或缩小选题范围；这不等于密钥无效。'
    elif isinstance(exc,(GenerationResponseError,json.JSONDecodeError)):
        code, message = 'OUTPUT_INCOMPLETE','模型输出被截断、拒绝生成或缺少完整结构。请换一个具体健康生活选题后重试；不要反复检查密钥。'
    elif isinstance(exc,ValueError):
        code, message = 'CONTENT_CHECK','输入或模型内容未通过完整性与证据引用检查。请检查选题、人群、模型设置后重试。'
    elif isinstance(exc,sqlite3.Error):
        code, message = 'STORAGE_ERROR','草稿写入数据库失败。请检查部署服务的磁盘空间与数据库写权限。'
    else:
        code, message = 'GENERATION_ERROR','生成流程出现未分类错误。请让维护者根据此代码检查部署日志，切勿公开密钥或完整请求内容。'
    result={'code':code,'message':message}
    rid=getattr(exc,'request_id',None) if isinstance(exc,APIStatusError) else None
    if isinstance(rid,str) and re.fullmatch(r'req_[A-Za-z0-9_-]{1,100}',rid):
        result['request_id']=rid
    return result
