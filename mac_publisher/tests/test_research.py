from types import SimpleNamespace
from xhs_publisher.research import count,note_url,rank,reference_summary,ResearchBlocked,collect
import pytest


def test_missing_counts_and_share_token_not_fabricated():
    assert count('赞') is None and count(None) is None
    assert count('1.4万')==14000 and count('8,473')==8473
    assert note_url('https://www.xiaohongshu.com/discovery/item/'+'a'*24+'?xsec_token=private')=='https://www.xiaohongshu.com/explore/'+'a'*24
    with pytest.raises(ResearchBlocked):note_url('https://evil.example/explore/'+'a'*24)


def test_ranking_marks_missing_and_never_claims_platform_top():
    records=[{'title':'缺失','likes':None,'saves':None,'comments':None},{'title':'高互动','likes':20,'saves':10,'comments':3}]
    ranked=rank(records)
    assert ranked[0]['observed_weighted_interactions']==49
    assert ranked[1]['observed_weighted_interactions'] is None


def test_unread_sources_cannot_become_reference():
    with pytest.raises(ResearchBlocked):reference_summary([{'title':'标题','body':None,'origin':'visible_dom'}])
    summary=reference_summary([{'title':'晚餐搭配','body':'合成页面的参考内容','origin':'visible_dom','comment_samples':[]}])
    assert '不是本人记录' in summary and '缺失，不推断' in summary


def test_no_permission_no_browser_or_request(tmp_path):
    report=collect(SimpleNamespace(),tmp_path,permitted=False)
    assert report['state']=='blocked' and report['collected']==0 and report['files']==[]


def test_unreadable_robots_response_stops_without_notes(tmp_path):
    request=SimpleNamespace(get=lambda *a,**k:SimpleNamespace(status=200,text=lambda:'<html>登录</html>'))
    report=collect(SimpleNamespace(request=request),tmp_path,permitted=True)
    assert report['state']=='blocked' and report['collected']==0
    assert 'robots' in report['message']


def test_robots_disallow_is_reported_without_navigation(tmp_path):
    request=SimpleNamespace(get=lambda *a,**k:SimpleNamespace(status=200,text=lambda:'User-agent: *\nDisallow: /'))
    page=SimpleNamespace(bring_to_front=lambda:None)
    context=SimpleNamespace(request=request,pages=[],new_page=lambda:page)
    report=collect(context,tmp_path,permitted=True)
    assert report['state']=='blocked' and report['collected']==0 and report['attempted']==0
    assert 'robots' in report['message']
