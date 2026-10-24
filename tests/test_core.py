import io
import json
from types import SimpleNamespace
from zipfile import ZipFile
import pandas as pd
import pytest
from franny.data import parse_csv, Store
from franny.analysis import rank_notes, analyze
from franny.generation import generate
from franny.health import review
from franny.export import export_bundle

RAW = open('examples/notes.csv', 'rb').read()

def test_import_and_upsert(tmp_path):
    df = parse_csv(RAW)
    db = Store(tmp_path / 'notes.db')
    db.import_notes(df)
    df.loc[0, 'likes'] = 999
    db.import_notes(df)
    assert len(db.notes()) == 6
    assert db.notes().iloc[0].likes == 999
    assert db.save_draft('{}') == 1
    assert len(db.drafts()) == 1

@pytest.mark.parametrize('old,new', [('1200','-1'), ('1200','1.5'), ('1200','NaN'), ('1200','inf'), ('2026-09-20 12:00:00','2099-01-01'), ('https://www.xiaohongshu.com/explore/demo001','https://evil.com/a')])
def test_reject_invalid(old,new):
    with pytest.raises(ValueError):
        parse_csv(RAW.replace(old.encode(),new.encode()))

def test_missing_and_empty():
    for raw in [b'title,url\na,b', b'title,url,published_at,likes,saves,comments\n']:
        with pytest.raises(ValueError):
            parse_csv(raw)

def test_score_filter_and_recency():
    df = parse_csv(RAW)
    result = rank_notes(df, keyword='午餐', min_interactions=10, since='2026-09-01', until='2026-10-24', now='2026-10-24T00:00:00Z')
    assert len(result) == 2
    assert result.score.between(0,100).all()
    same = pd.concat([df.iloc[[0]],df.iloc[[0]]],ignore_index=True)
    same.loc[1,'published_at'] = '2026-10-20T00:00:00+00:00'
    assert rank_notes(same,now='2026-10-24T00:00:00Z').iloc[0].published_at.startswith('2026-10-20')
    assert rank_notes(df,keyword='[').empty
    assert analyze(df)['sample_size'] == 6
    assert analyze(df)['themes']['饮食搭配'] >= 1

@pytest.mark.parametrize('text', ['保证必瘦', '7天瘦10斤', '不吃主食', '局部减脂'])
def test_health_block(text):
    assert review(text)['status'] == 'blocked'

def test_generation_and_export():
    p = generate('午餐','成年人',{},demo=True)
    assert p['mode'] == 'offline_template'
    assert p['health_review']['status'] == 'needs_review'
    with ZipFile(io.BytesIO(export_bundle(p))) as z:
        assert set(z.namelist()) == {'draft.md','draft.json','image_prompts.json','REVIEW.txt'}
        assert json.loads(z.read('draft.json'))['title'] == p['title']
    p['health_review']['status'] = 'blocked'
    with pytest.raises(ValueError): export_bundle(p)

def test_openai_contract():
    expected = generate('午餐','成年人',{},demo=True)
    from franny.generation import Draft
    allowed = {k:v for k,v in expected.items() if k in Draft.model_fields}
    class Completions:
        def create(self, **kwargs):
            assert kwargs['response_format'] == {'type':'json_object'}
            assert 'url' not in json.loads(kwargs['messages'][1]['content'])
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(allowed)))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    assert generate('午餐','成年人',{},client=client)['mode'] == 'openai'
    allowed['source_ids'] = ['invented']
    with pytest.raises(ValueError): generate('午餐','成年人',{},client=client)

def test_missing_api_key(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with pytest.raises(ValueError): generate('午餐','成年人',{})
