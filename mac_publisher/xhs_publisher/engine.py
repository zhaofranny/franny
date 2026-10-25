from pathlib import Path
from .bundle import load_bundle, BundleError
from .adapter import PublishError


def verify_account(adapter,account):
    if hasattr(adapter,'verify_account'):
        adapter.verify_account(account)
    elif adapter.current_account()!=account:
        raise PublishError('ACCOUNT_NOT_VERIFIED','当前浏览器账号与已绑定账号不一致或无法核验，尚未提交')


def publish(adapter,journal,root,approved_hash,account,job_id=None,retry_prepare=False,artifact_dir=None):
    manifest,files,fingerprint=load_bundle(root)
    if fingerprint!=approved_hash: raise BundleError('素材在确认后发生变化，请重新预览确认；尚未提交')
    if job_id:
        row=journal.get(job_id)
        if not row or row['account']!=account or row['fingerprint']!=fingerprint: raise BundleError('任务与确认素材不匹配')
        if row['state']!='preparing': return row
        job=job_id
    else:
        job,created=journal.reserve(account,fingerprint,retry_prepare)
        if not created: return journal.get(job)
    submitted=False
    stage="open_creator"
    try:
        adapter.open()
        stage="verify_account"
        verify_account(adapter,account)
        stage="read_baseline"
        baseline=adapter.baseline()
        stage="prepare_editor"
        adapter.prepare(manifest,files)
        stage="verify_editor"
        adapter.verify(manifest,len(files))
        if load_bundle(root)[2]!=fingerprint: raise PublishError('MATERIAL_CHANGED','准备期间素材发生变化，尚未提交')
        stage="verify_account"
        verify_account(adapter,account)
        if artifact_dir:
            artifact_dir=Path(artifact_dir);artifact_dir.mkdir(parents=True,exist_ok=True)
            adapter.screenshot(artifact_dir/'before_submit.png')
        journal.update(job,'ready',message='页面图片、文字、话题和声明已核对')
        # Durable boundary BEFORE the click: even a crash/timeout cannot permit blind resubmission.
        journal.update(job,'submitting',title=manifest.title)
        submitted=True
        stage="submit"
        adapter.submit_once()
        journal.update(job,'submitted_unverified',message='已点击一次提交，正在只读回查')
        stage="verify_receipt"
        result=adapter.verify_result(manifest,baseline)
        state=result.pop('state')
        if state not in {'published','pending_review','rejected','submitted_unverified'}:
            raise PublishError('INVALID_RECEIPT','未取得可信的发布状态')
        if state in {'published','pending_review','rejected'}:
            import re
            if not re.fullmatch(r'[a-f0-9]{24}',result.get('note_id','')) or result.get('note_url')!='https://www.xiaohongshu.com/explore/'+result['note_id']:
                raise PublishError('INVALID_RECEIPT','回执缺少可核验笔记ID或链接')
        journal.update(job,state,**result)
    except Exception as exc:
        known=isinstance(exc,PublishError)
        code=exc.code if known else 'LOCAL_BROWSER_ERROR'
        message=str(exc) if known else '浏览器或本地存储操作异常；不公开原始异常与会话信息'
        state='unknown' if submitted else ('blocked' if code in {'LOGIN_REQUIRED','LOGIN_OR_VERIFICATION','PLATFORM_VERIFICATION','ACCOUNT_NOT_VERIFIED','ACCOUNT_MISMATCH','ACCOUNT_NAME_UNREADABLE'} else 'failed_pre_submit')
        diagnostic={'stage':stage,'error_type':type(exc).__name__ if type(exc).__module__ in {'builtins','playwright._impl._errors'} else 'PublishError'}
        try:
            if hasattr(adapter,'diagnostics'): diagnostic.update(adapter.diagnostics())
        except Exception: diagnostic['page_diagnostics_unavailable']=True
        if artifact_dir:
            try:
                artifact_dir=Path(artifact_dir);artifact_dir.mkdir(parents=True,exist_ok=True)
                adapter.screenshot(artifact_dir/'failure.png')
                diagnostic['failure_screenshot']='failure.png'
            except Exception: diagnostic['failure_screenshot_unavailable']=True
        journal.update(job,state,code=code,message=message,**diagnostic)
    return journal.get(job)
