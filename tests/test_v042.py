"""Group language boundaries, honest promotional counts and quota semantics."""
import json
import httpx
import pytest
from contextlib import contextmanager
from sqlalchemy import select
from app import main,i18n,widgets,tools_proxy
from app.db import SessionLocal
from app.models import User,PermissionGroup,GroupMember,Language
from test_portal import setup,post,logout,login_user
from test_permissions_bridge import policy_api


def grouped_user():
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'));user.locale='fr'
        group=PermissionGroup(name='Family',locale=None,version=0);db.add(group);db.flush()
        db.add(GroupMember(group_id=group.id,user_id=user.id));db.commit()
        return user.id,group.id


def test_group_language_default_explicit_disabled_and_personal_restore(client,policy_api):
    setup(client);uid,gid=grouped_user()
    assert post(client,'/admin/translations/policy',{'language_policy':'group'},'/admin/translations').status_code==303
    with SessionLocal() as db:
        assert i18n.user_language(db,db.get(User,uid))=='en'
        assert db.get(User,uid).locale=='fr'
    path=f'/admin/groups/{gid}/language'
    assert post(client,path,{'version':0,'locale':'fr'},f'/admin/groups/{gid}').status_code==303
    assert post(client,path,{'version':0,'locale':'en'},f'/admin/groups/{gid}').status_code==409
    with SessionLocal() as db:
        assert i18n.user_language(db,db.get(User,uid))=='fr'
        db.get(Language,'fr').enabled=False;db.commit()
        assert i18n.user_language(db,db.get(User,uid))=='en'
        db.get(Language,'fr').enabled=True;db.commit()
    assert post(client,'/admin/translations/policy',{'language_policy':'user'},'/admin/translations').status_code==303
    with SessionLocal() as db:assert i18n.user_language(db,db.get(User,uid))=='fr'


def test_group_policy_enforced_on_all_personal_language_endpoints(client):
    setup(client);uid,gid=grouped_user()
    post(client,'/admin/translations/policy',{'language_policy':'group'},'/admin/translations')
    assert post(client,f'/admin/users/{uid}/language',{'locale':'fr'},'/admin/users').status_code==409
    logout(client);login_user(client)
    for path in ('/language','/account/language'):
        assert post(client,path,{'locale':'fr','next':'/home'},'/account').status_code==409
    assert post(client,'/admin/translations/policy',{'language_policy':'user'},'/account').status_code==403
    page=client.get('/account').text
    assert 'managed-language' in page and 'data-auto-language' not in page
    assert '<html lang="en"' in page
    with SessionLocal() as db:assert db.get(User,uid).locale=='fr'


def test_policy_validation_and_no_inactive_group_language(client):
    setup(client);uid,gid=grouped_user()
    assert post(client,'/admin/translations/policy',{'language_policy':'any'},'/admin/translations').status_code==400
    assert post(client,f'/admin/groups/{gid}/language',{'version':0,'locale':'de'},'/admin/groups').status_code==400
    with SessionLocal() as db:
        assert i18n.language_policy(db)=='user'
        assert db.get(PermissionGroup,gid).version==0


@pytest.mark.parametrize('count,step,expected',[(2604,100,'2\u202f600+'),(2600,100,'2\u202f600'),(284,10,'280+'),(4,100,'4'),(0,10,'0'),(100,100,'100')])
def test_promotion_never_exaggerates_or_claims_more_at_exact_threshold(count,step,expected):
    assert widgets.media_count(count,{'count_mode':'promotion','round_to':step})==expected
    assert widgets.media_count(count,{'count_mode':'exact'})==count


def test_quota_period_uses_actual_days_and_never_invents_calendar_reset():
    metric=widgets.quota_metric('movies_left',{'limit':7,'remaining':5,'days':9})
    assert metric['context_values']=={'days':9} and metric['remaining']==5
    assert metric['percent']==71.43
    assert widgets.quota_metric('series_left',{'limit':3,'remaining':0})['percent']==0
    assert widgets.quota_metric('movies_left',{'limit':0})['context']=='Unlimited requests'
    assert widgets.quota_metric('movies_left',{'limit':7,'remaining':5},unrestricted=True)['value']=='∞'
    assert widgets.quota_metric('movies_left',{'limit':7,'remaining':8})['context']=='Quota unavailable'
    assert widgets.quota_metric('movies_left',{'limit':7,'remaining':5})['context']=='Current quota period'


def test_malformed_remote_quota_is_a_service_error_not_a_broken_portal(client,monkeypatch):
    setup(client)
    @contextmanager
    def connection(db,user):yield None,7
    monkeypatch.setattr('app.seerr_permissions.connection',connection)
    monkeypatch.setattr('app.seerr_permissions.read_permissions',lambda *_:0)
    monkeypatch.setattr(widgets,'request',lambda *_:[])
    from app.integrations import SyncError
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'))
        with pytest.raises(SyncError):widgets.seerr_metrics(db,user,{'metrics':['movies_left']})


def test_widget_preview_matches_saved_metrics_and_promotion(client):
    setup(client)
    with SessionLocal() as db:
        result=widgets.display(db,None,{'kind':'widget_media','metrics':['episodes'],'count_mode':'promotion','round_to':100},True)
        assert result['metrics']==[{'label':'Episodes','value':'14\u202f200+'}]
    for value in (0,1,'100',True):
        with pytest.raises(ValueError):widgets.validate({'kind':'widget_media','round_to':value})


def test_tdarr_runtime_bridge_is_before_bundles_and_css_stays_in_proxy(client,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        for key,value in {'tdarr_enabled':'true','tdarr_url':'http://tdarr.private:8265'}.items():main.set_config(db,key,value)
        db.scalar(select(User).where(User.admin.is_(True))).tool_access='["tdarr"]';db.commit()
    native=httpx.AsyncClient
    async def upstream(req):
        if req.url.path.endswith('.css'):return httpx.Response(200,text='a{background:url(/assets/a.png)} @import "/theme.css";',headers={'content-type':'text/css'})
        return httpx.Response(200,text='<html><head><base href="/"><script src="/static/app.js"></script></head><body><div id="root"></div></body></html>',headers={'content-type':'text/html'})
    monkeypatch.setattr(tools_proxy.httpx,'AsyncClient',lambda **kw:native(transport=httpx.MockTransport(upstream),**kw))
    result=client.get('/tools/tdarr/app/tdarr/').text
    assert result.index('/static/tdarr-proxy.js')<result.index('/tools/tdarr/app/tdarr/static/app.js')
    assert result.count('<base ')==1
    css=client.get('/tools/tdarr/app/tdarr/a.css').text
    assert 'url(/tools/tdarr/app/tdarr/assets/a.png)' in css
    assert '"/tools/tdarr/app/tdarr/theme.css"' in css
