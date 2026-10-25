import json
import urllib.error
import pytest
from xhs_publisher.production import Draft,ProductionError,generate,build_bundle,settings
from xhs_publisher.bundle import load_bundle


def data():
    return dict(titles=['减脂人别和意志力硬刚','晚饭别再开意志力会议','把健康习惯变顺手'],body=('下班已经够累了，晚饭就别再给自己加一场意志力考试。可以先想好今晚吃什么，把蔬菜、主食和蛋白质食物搭配起来，外卖也能按这个思路选。饮料先选白水，想吃零食时先停下来看看自己是饿了还是只是累了。活动也从方便的开始，比如坐久了起来走走，天气合适就散一小段步。睡前给自己留一点收尾时间，别把所有改变都挤在同一天。这里聊的是普通成年人的日常习惯，身体不舒服或有特殊饮食需求时要咨询专业人员。姐妹们，你最想先把哪件小事变顺手？'),tags=['减脂生活','晚餐搭配','生活习惯','日常活动','上班族'],cover='别和意志力硬刚',cards=['晚餐先想好搭配，蔬菜、主食和蛋白质食物都考虑到。','活动从顺路开始，坐久了起来走走，按自己的状态安排。','改变不用挤在一天，先挑一件顺手的小事，你会选哪件？'])

def test_production_to_publish_bundle(tmp_path):
    draft=Draft(**data())
    root=build_bundle(draft,tmp_path/'bundle')
    manifest,files,fingerprint=load_bundle(root)
    assert len(files)==4 and manifest.ai_generated and manifest.body==draft.body
    assert len(fingerprint)==64
    assert len({p.read_bytes() for p in files})==4


def test_key_missing_no_request(monkeypatch):
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:pytest.fail('request made'))
    with pytest.raises(ProductionError,match='密钥'): generate('晚餐搭配','DeepSeek',{})


def test_quota_is_redacted(monkeypatch):
    def fail(*a,**k): raise urllib.error.HTTPError('https://example.com',429,'SECRET',{},None)
    monkeypatch.setattr('urllib.request.urlopen',fail)
    with pytest.raises(ProductionError,match='限流') as exc: generate('晚餐搭配','DeepSeek',{'DEEPSEEK_API_KEY':'sk-private'})
    assert 'SECRET' not in str(exc.value) and 'sk-private' not in str(exc.value)


def test_online_response(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,*args): return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(data())}}]}).encode()
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:Response())
    assert generate('晚餐搭配','DeepSeek',{'DEEPSEEK_API_KEY':'sk-private'}).cover=='别和意志力硬刚'


def test_unsafe_card_rejected(tmp_path):
    d=data();d['cards'][0]='保证你三天暴瘦，效果显著'
    with pytest.raises(ProductionError): build_bundle(d,tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_local_settings(tmp_path):
    (tmp_path/'.local').mkdir()
    (tmp_path/'.local'/'generation.json').write_text(json.dumps({'DEEPSEEK_API_KEY':'local-key'}))
    assert settings(tmp_path)['DEEPSEEK_API_KEY']=='local-key'


def test_ui_generate_handoff(monkeypatch):
    from pathlib import Path
    import xhs_publisher.production as production
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(production,'generate',lambda *args:Draft(**data()))
    app=AppTest.from_file(str(Path(__file__).parents[1]/'publisher_app.py'),default_timeout=15).run()
    button=next(b for b in app.button if b.label=='一键生成文案和原创图卡')
    button.click().run()
    assert not app.exception
    assert app.session_state['imported']['title']==data()['titles'][0]
    assert len(app.session_state['imported']['images'])==4
    next(b for b in app.button if b.label=='生成本地预览（不发布）').click().run()
    assert not app.exception
    assert app.session_state['preview']['fingerprint']
    assert next(b for b in app.button if b.label=='确认并发布到小红书').disabled
