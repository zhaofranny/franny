import json
from types import SimpleNamespace
import pytest
from franny.data import Store
from franny.errors import GenerationBusyError, GenerationCooldownError
from franny.generation import generate, CopyDraft, Draft, validate_draft
from franny.service import create_and_save
from franny.editorial import approve, refresh_review


def test_parallel_generation_and_expired_owner_release(tmp_path):
    db=Store(tmp_path/'lease.db')
    first=db.reserve_generation('deepseek',now=100,lease_seconds=130)
    with pytest.raises(GenerationCooldownError): db.reserve_generation('deepseek',now=101)
    with pytest.raises(GenerationBusyError): db.reserve_generation('deepseek',now=109)
    second=db.reserve_generation('deepseek',now=231)
    db.release_generation('deepseek',first)
    with pytest.raises(GenerationBusyError): db.reserve_generation('deepseek',now=240)
    db.release_generation('deepseek',second)
    db.reserve_generation('deepseek',now=241)


@pytest.mark.parametrize('long_title,long_body',[(True,False),(False,True),(True,True)])
def test_paid_copy_preserved_when_length_needs_editing(tmp_path,long_title,long_body):
    seed=generate('午餐','成年人',{},demo=True)
    raw={k:v for k,v in seed.items() if k in CopyDraft.model_fields}
    if long_title: raw['title']='上班已经够忙了减脂能不能少一点纠结多一点顺手的小安排'
    if long_body: raw['body']+='这是合成测试中的一段额外文本。'*70
    calls=[]
    class Completion:
        def create(self,**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content='```json\n'+json.dumps(raw)+'\n```'))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=Completion()))
    db=Store(tmp_path/'copy.db')
    _,p=create_and_save(db,'午餐','成年人',{},provider='deepseek',client=client)
    assert p['body']==raw['body'] and p['title']==raw['title']
    assert p['generation_issues'] and len(calls)==1 and len(db.drafts())==1
    with pytest.raises(ValueError): approve(p,'编辑','已核对来源')
    # Editor uses strict schema, so the longer response cannot silently become publishable.
    with pytest.raises(ValueError): validate_draft({k:v for k,v in p.items() if k in Draft.model_fields})


def test_failed_response_releases_lease_but_preserves_click_cooldown(tmp_path):
    class Completion:
        def create(self,**kwargs):
            raise RuntimeError('synthetic failure')
    db=Store(tmp_path/'failed.db')
    client=SimpleNamespace(chat=SimpleNamespace(completions=Completion()))
    with pytest.raises(RuntimeError): create_and_save(db,'午餐','成年人',{},provider='deepseek',client=client)
    with db.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM generation_jobs').fetchone()[0]==0
        assert con.execute('SELECT COUNT(*) FROM generation_limits').fetchone()[0]==1
    assert not db.drafts()
