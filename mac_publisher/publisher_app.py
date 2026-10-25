import json
import hashlib
import os
import subprocess
import sys
import uuid
from pathlib import Path
import streamlit as st
from xhs_publisher import VERSION
from xhs_publisher.bundle import Manifest,load_bundle,import_zip,BundleError
from xhs_publisher.journal import Journal,atomic_json
from xhs_publisher.session import session_state,enqueue,request_focus,SessionUnavailable
from xhs_publisher.production import SPECS,DIRECTIONS,source_links_valid,settings,generate,build_bundle,ProductionError

BASE=Path(__file__).resolve().parent
LOCAL=BASE/'.local';LOCAL.mkdir(exist_ok=True);LOCAL.chmod(0o700)
JOURNAL=Journal(LOCAL)
st.set_page_config(page_title='Franny · Mac本地发布',page_icon='🌿',layout='wide')
st.title('🌿 Franny · Mac 本地发布')
st.caption(f'v{VERSION} · 单账号 · 真实浏览器 · 不调用私有发布API · 结果不明不自动重发')


def start(action,*extra):
    if action=='publish':
        args=dict(zip(extra[::2],extra[1::2]))
        active=session_state(LOCAL)
        if active.get('state')=='ready':
            return enqueue(LOCAL,args['--bundle'],args['--approved-hash'],args['--job-id'],'--retry-preparation' in extra)
        if active.get('state')=='busy': raise SessionUnavailable('浏览器正在处理另一任务，请等待完成')
    active=session_state(LOCAL)
    if action=='login' and active.get('state') in {'ready','busy'}:
        pid=request_focus(LOCAL)
        atomic_json(LOCAL/'login_status.json',{'state':'focusing','message':'正在唤起已有小红书窗口，不会重复打开浏览器…'})
        return pid
    if action=='login': atomic_json(LOCAL/'login_status.json',{'state':'starting','message':'正在启动独立浏览器…'})
    command=[sys.executable,'-m','xhs_publisher.worker',action,'--base',str(BASE),*extra]
    log=(LOCAL/'worker.log').open('a',encoding='utf-8')
    try: return subprocess.Popen(command,cwd=BASE,stdout=log,stderr=log,start_new_session=True).pid
    finally: log.close()

def read_json(path):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError): return {}

login,material,history=st.tabs(['① 登录账号','② 预览与发布','③ 发布记录'])
with login:
    st.write('首次使用先手动登录。浏览器数据只保存在本机专用配置目录，不读取你的日常Chrome配置，也不导出Cookie。')
    st.caption('使用前需确认你的操作符合平台当前规则。出现登录、验证码或风控时，由你手动处理，工具不会绕过。')
    if st.button('打开浏览器，手动登录'):
        try: st.session_state['login_pid']=start('login')
        except SessionUnavailable as exc: st.error(str(exc))
    @st.fragment(run_every=2)
    def login_progress():
        state=read_json(LOCAL/'login_status.json')
        active=session_state(LOCAL)
        if state and not (active.get('state') in {'ready','busy'} and state.get('state')=='starting'):
            st.info(state.get('message',state['state']))
        account=read_json(LOCAL/'account.json')
        if account: st.success('本地绑定的浏览器显示名：'+account['account_name'])
        active=session_state(LOCAL)
        if active.get('state')=='ready':
            st.success('实时浏览器会话已就绪。点击上方按钮可唤起现有窗口，无需重复登录')
            st.caption('若窗口被遮住：按Control+上箭头，选择小红书创作服务平台窗口。')
        elif active.get('state')=='busy': st.info('同一浏览器正在执行任务，请查看③发布记录')
        else: st.warning('当前没有就绪的实时浏览器会话。绑定名称只是历史记录，请点击上方登录按钮。')
    login_progress()
with material:
    st.subheader('选题 → 原创文案与图卡 → 发布')
    if st.button('刷新实时浏览器会话状态'): st.rerun()
    if session_state(LOCAL).get('state')!='ready': st.info('发布前请到①打开并登录独立Chrome，保持窗口打开；登录完成后点击刷新实时浏览器会话状态。')
    provider=st.selectbox('文案模型服务',list(SPECS))
    direction=st.selectbox('内容方向',list(DIRECTIONS))
    topic=st.text_input('今天的选题',DIRECTIONS[direction][0],max_chars=300,key='topic_'+direction)
    with st.expander('参考笔记与真实记录（选填）'):
        reference_notes=st.text_area('参考主题、评论区问题摘要或自己的真实记录',max_chars=2000,help='只提供合法使用的简短摘要，不粘贴他人整篇正文。此摘要会发送给所选模型；没有摘要时生成讨论问题，不编造检索或评论经历。')
        source_text=st.text_area('参考原帖链接，每行一条，最多10条',help='仅随素材保存在本机，不发送给模型，不自动采集，不代表已经核验原帖。')
    st.caption('当前未接入真实站内检索或9张截图自动识别；这里选择的是按你描述整理的内容方向。日记方向需填本人真实记录。')
    st.caption('生成3个标题、150–300字正文、5个话题和4张原创文字图卡。密钥仅读取本机环境变量、Streamlit Secrets或.local/generation.json。规则检查不代替人工健康事实核查。')
    if st.button('一键生成文案和原创图卡',type='primary'):
        try:
            try: secret_config=dict(st.secrets)
            except FileNotFoundError: secret_config={}
            with st.spinner('正在生成文案与图卡，请勿重复点击…'):
                links=source_links_valid([line.strip() for line in source_text.splitlines() if line.strip()])
                draft=generate(topic,provider,settings(BASE,secret_config),direction,reference_notes)
                root=build_bundle(draft,LOCAL/'bundles'/uuid.uuid4().hex,source_links=links,direction=direction)
                m,files,_=load_bundle(root)
            st.session_state['generated_titles']=draft.titles
            st.session_state['imported']={'title':m.title,'body':m.body,'tags':' '.join(m.tags),'images':[str(p) for p in files]}
            st.session_state['editor_key']=uuid.uuid4().hex
            st.session_state.pop('preview',None)
            st.rerun()
        except ProductionError as exc: st.error(str(exc))
        except Exception: st.error('素材生产未完成，未启动发布。请检查本机配置、字体及磁盘权限。')
    if st.session_state.get('generated_titles'):
        st.success('文案与4张图卡已保存到本机并填入下方编辑器。核对内容后点击生成本地预览，再确认发布。')
        for candidate in st.session_state['generated_titles']: st.write('备选标题：'+candidate)
    with st.expander('恢复本机已有素材（无需重新生成）'):
        saved=sorted((LOCAL/'bundles').glob('*/manifest.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:50]
        if saved:
            chosen=st.selectbox('已保存素材，最新在前',saved,format_func=lambda p:p.parent.name,key='saved_bundle')
            if st.button('恢复所选素材'):
                try:
                    m,files,_=load_bundle(chosen.parent)
                    st.session_state['imported']={'title':m.title,'body':m.body,'tags':' '.join(m.tags),'images':[str(p) for p in files]}
                    st.session_state['editor_key']=uuid.uuid4().hex
                    st.session_state.pop('preview',None)
                    st.rerun()
                except (BundleError,ValueError): st.error('所选素材不完整或未通过校验，请选择其他记录')
        else: st.caption('暂无已保存素材')
    st.write('导入现有Franny导出的待审核ZIP（必须含真实图片），或自行输入标题、正文和原创图片。默认不会发布。')
    zipped=st.file_uploader('导入素材 ZIP',type=['zip'],key='bundle_zip')
    if zipped and st.button('读取素材包'):
        try:
            root=import_zip(zipped.getvalue(),LOCAL/'bundles'/uuid.uuid4().hex)
            m,files,_=load_bundle(root)
            st.session_state['imported']={'title':m.title,'body':m.body,'tags':' '.join(m.tags),'images':[str(p) for p in files]}
            st.session_state['editor_key']=uuid.uuid4().hex
            st.session_state.pop('preview',None)
            st.rerun()
        except (BundleError,ValueError): st.error('素材ZIP不完整或含不合规内容，请检查格式和图片；离线模板不能发布')
    seed=st.session_state.get('imported',{})
    revision=st.session_state.get('editor_key','initial')
    title=st.text_input('最终标题',seed.get('title',''),max_chars=20,key='title_'+revision)
    body=st.text_area('正文',seed.get('body',''),height=240,max_chars=1000,key='body_'+revision)
    tags=st.text_input('话题（空格分隔，填写名称即可）',seed.get('tags',''),key='tags_'+revision)
    uploads=st.file_uploader('选择本地原创/已获授权图片，按顺序上传',type=['png','jpg','jpeg','webp'],accept_multiple_files=True)
    ai=st.checkbox('内容包含AI生成文字或图片（会核验平台AI声明控件）',value=True)
    original=st.checkbox('这是我有权声明原创的内容',value=True)
    if st.button('生成本地预览（不发布）'):
        try:
            root=LOCAL/'bundles'/uuid.uuid4().hex;root.mkdir(parents=True)
            images=[]
            if uploads:
                for i,item in enumerate(uploads):
                    ext=Path(item.name).suffix.lower();relative=f'images/{i+1:02d}{ext}'
                    (root/'images').mkdir(exist_ok=True);(root/relative).write_bytes(item.getvalue());images.append(relative)
            else:
                for i,path in enumerate(seed.get('images',[])):
                    source=Path(path);relative=f'images/{i+1:02d}{source.suffix.lower()}'
                    (root/'images').mkdir(exist_ok=True);(root/relative).write_bytes(source.read_bytes());images.append(relative)
            m=Manifest(title=title,body=body,tags=tags.split(),images=images,ai_generated=ai,original_content=original)
            atomic_json(root/'manifest.json',m.model_dump())
            _,files,fingerprint=load_bundle(root)
            st.session_state['preview']={'root':str(root),'fingerprint':fingerprint,'editor':{'title':title,'body':body,'tags':tags,'ai':ai,'original':original},'upload_hashes':[hashlib.sha256(f.getvalue()).hexdigest() for f in uploads]}
        except Exception: st.error('预览未生成：请填写合规标题/正文，提供1–18张有效且不重复的图片，检查话题格式与高风险健康表述')
    preview=st.session_state.get('preview')
    editor_now={'title':title,'body':body,'tags':tags,'ai':ai,'original':original}
    if preview:
        try:
            m,files,fingerprint=load_bundle(preview['root'])
            changed=editor_now!=preview['editor'] or [hashlib.sha256(f.getvalue()).hexdigest() for f in uploads]!=preview['upload_hashes'] or fingerprint!=preview['fingerprint']
            if changed: st.warning('编辑内容发生变化，请重新生成预览；旧预览不能提交')
            st.subheader('本次将发布的内容')
            st.write(m.title);st.write(m.body);st.write(' '.join('#'+t for t in m.tags));st.image([str(f) for f in files],width=230)
            account=read_json(LOCAL/'account.json').get('account_name')
            st.write('目标浏览器账号：'+(account or '尚未登录绑定'))
            rights=st.checkbox('我有权发布这些文字和图片，已完成健康事实核查，并确认账号、内容和AI声明真实',key='rights_'+fingerprint)
            permitted=st.checkbox('我已核对平台当前规则，确认此次本地网页自动化操作在允许范围内',key='permitted_'+fingerprint)
            retry=st.checkbox('仅重新准备上次“尚未提交”就失败的同一素材（不会重发已提交任务）',key='retry_'+fingerprint)
            if st.button('确认并发布到小红书',type='primary',disabled=changed or not account or not rights or not permitted or session_state(LOCAL).get('state')=='busy'):
                job,created=JOURNAL.reserve(account,fingerprint,retry)
                if created:
                    args=['--bundle',preview['root'],'--approved-hash',fingerprint,'--job-id',job]
                    if retry: args.append('--retry-preparation')
                    try: start('publish',*args)
                    except SessionUnavailable as exc:
                        JOURNAL.update(job,'failed_pre_submit',code='SESSION_NOT_READY',message=str(exc))
                        st.error(str(exc))
                        st.stop()
                    st.session_state['active_job']=job
                    st.info('已确认本次一键发布。若平台要求登录，请本人扫码；账号核验通过后自动继续，无需再点发布。请勿关闭独立浏览器。')
                else:
                    st.session_state['active_job']=job
                    st.info('同一账号与素材已有任务，本次未启动重复发布；请查看原记录。')
        except (BundleError,ValueError): st.error('预览素材已损坏或变化，请重新预览')
with history:
    st.caption('只有取得新笔记ID和明确平台状态才显示已发布；审核中、提交待核验和结果不明分开记录。遇到不明结果，先去官方创作者平台核对，不自动重发。')
    labels={'preparing':'正在准备','ready':'准备完成','submitting':'正在提交','published':'已发布','pending_review':'平台审核中','submitted_unverified':'已提交，待核验','unknown':'结果不明，禁止自动重发','blocked':'登录/账号/平台限制','failed_pre_submit':'提交前失败，可明确重试准备','rejected':'平台未通过'}
    @st.fragment(run_every=2)
    def jobs_progress():
        for job in JOURNAL.history():
            with st.expander(f"{labels.get(job['state'],job['state'])} · {job['result'].get('title','图文任务')} · {job['id'][:8]}"):
                st.json(job)
                if job['state']=='preparing' and job['result'].get('stage')=='awaiting_manual_login':
                    st.warning('本次发布已获确认，正在等待你本人扫码登录；成功核验同一账号后自动继续，不需要再点发布。')
                url=job['result'].get('note_url')
                if url: st.link_button('查看笔记链接',url)
                if job['result'].get('code')=='LOGIN_REQUIRED':
                    st.warning('本次在提交前遇到登录页。请在保留的独立Chrome中手动登录，完成后明确重试原素材；不要重复生成。')
                failure=BASE/'output'/job['id']/'failure.png'
                if failure.is_file():
                    st.caption('失败页面截图仅保存在本机，可能包含个人信息；请先遮挡隐私再分享。')
                    with st.expander('查看失败时的小红书页面'): st.image(str(failure))
                path=BASE/'output'/job['id']/'before_submit.png' 
                if path.is_file(): st.image(str(path),caption='提交前页面，仅保存在本机')
                st.download_button('下载此任务记录',json.dumps(job,ensure_ascii=False,indent=2),job['id']+'.json',key='receipt_'+job['id'])
    jobs_progress()
