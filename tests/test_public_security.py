"""Regression cases for the public-portal / privileged native-API boundary."""
import copy,json,time
import httpx,pytest
from sqlalchemy import select
from app import main,tools_proxy,support
from app.emby import EmbyClient,EmbyError
from app.db import SessionLocal
from app.models import User,Session,Config,AccessService
from app.security import encrypt
from test_portal import setup,post,csrf,logout,login_user

def test_blank_password_is_rejected_before_native_authentication(client,fake,monkeypatch):
    setup(client);logout(client);called=[]
    monkeypatch.setattr(fake,'authenticate',lambda *a:called.append(a) or {'User':fake.owner(),'AccessToken':'token'})
    response=post(client,'/login',{'name':'Owner','password':''})
    assert response.status_code==401 and not called

def test_native_passwordless_identity_is_not_accepted_as_password_auth(client,monkeypatch):
    original=httpx.Client
    def transport(request):return httpx.Response(200,json={'User':{'Id':'u','HasPassword':False},'AccessToken':'unsafe-token'})
    monkeypatch.setattr('app.emby.httpx.Client',lambda **kw:original(transport=httpx.MockTransport(transport),**kw))
    with pytest.raises(EmbyError):EmbyClient('http://media','key').authenticate('u','ignored-by-a-passwordless-server')

def test_disabled_native_admin_loses_existing_portal_access(client,fake,monkeypatch):
    setup(client);original=fake.user
    def disabled(uid):
        value=copy.deepcopy(original(uid))
        if uid=='admin-1':value['Policy']['IsDisabled']=True
        return value
    monkeypatch.setattr(fake,'user',disabled)
    assert client.get('/admin/users').status_code==403
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.emby_id=='admin-1'))
        assert not owner.active and not list(db.scalars(select(Session).where(Session.user_id==owner.id)))

def test_native_outage_does_not_allow_privileged_writes(client,fake,monkeypatch):
    setup(client);token=csrf(client,'/admin/branding')
    monkeypatch.setattr(fake,'user',lambda *a:(_ for _ in ()).throw(EmbyError('offline')))
    response=client.post('/admin/settings',data={'csrf':token,'app_name':'Must not be written','login_text':'Welcome','public_url':'http://testserver'},follow_redirects=False)
    assert response.status_code==503
    with SessionLocal() as db:assert main.config(db,'app_name')=='Gatearr'

def test_native_administrator_token_is_never_returned_in_browser_url(client,fake,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)));session=db.scalar(select(Session).where(Session.user_id==owner.id))
        support.capture(db,owner,{'AccessToken':'native-admin-canary','ServerId':'server'},session.digest)
        service=db.get(AccessService,'emby');service.browser_url='https://media.example';db.commit()
    monkeypatch.setattr('app.emby.emby.request',lambda *a,**kw:{'Id':'admin-1','Policy':{'IsAdministrator':True}})
    response=client.get('/services/emby/open',follow_redirects=False)
    assert response.status_code==303 and response.headers['location']=='https://media.example/web/index.html'
    assert 'native-admin-canary' not in response.headers['location']

@pytest.mark.parametrize('path',['%2e%2e/api','%252e%252e/api','%2e%2fsecret','folder%2f..%2fsecret','folder%5csecret'])
def test_proxy_refuses_encoded_path_escape_before_contacting_upstream(client,monkeypatch,path):
    setup(client);seen=[]
    with SessionLocal() as db:
        db.scalar(select(User).where(User.admin.is_(True))).tool_access='["radarr"]'
        for key,value in {'radarr_enabled':'true','radarr_url':'http://private.test:7878','radarr_api_key':encrypt('canary')}.items():main.set_config(db,key,value)
        db.commit()
    original=httpx.AsyncClient
    async def upstream(request):seen.append(request);return httpx.Response(200,stream=httpx.ByteStream(b'ok'))
    monkeypatch.setattr(tools_proxy.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(upstream),**kw))
    assert client.get('/tools/radarr/app/'+path).status_code==400
    assert not seen

def test_reset_link_is_not_sent_in_same_origin_referer(client):
    setup(client)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'));raw=main.issue_token(db,user,'reset')
    response=client.get('/reset?token='+raw)
    assert response.status_code==200 and response.headers['referrer-policy']=='strict-origin'

@pytest.mark.parametrize('path',['/admin/users','/admin/integrations','/admin/security/captcha','/admin/design/home','/admin/mail-editor','/admin/activity'])
def test_native_admin_does_not_gain_gatearr_admin(client,path):
    setup(client);logout(client);login_user(client)
    # The fixture's member is a native administrator, but has no Gatearr admin role.
    assert client.get(path).status_code==403


def test_proxy_rechecks_native_account_before_injecting_credentials(client,fake,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        db.scalar(select(User).where(User.admin.is_(True))).tool_access='["radarr"]'
        for key,value in {'radarr_enabled':'true','radarr_url':'http://private.test:7878','radarr_api_key':encrypt('never-send')}.items():main.set_config(db,key,value)
        db.commit()
    original=fake.user
    def disabled(uid):
        result=copy.deepcopy(original(uid));result['Policy']['IsDisabled']=True;return result
    monkeypatch.setattr(fake,'user',disabled)
    monkeypatch.setattr(tools_proxy.httpx,'AsyncClient',lambda **kw:pytest.fail('Revoked user reached upstream'))
    assert client.get('/tools/radarr/app/').status_code==401


def test_websocket_and_http_share_path_validation():
    from types import SimpleNamespace
    for raw in (b'/tools/radarr/app/%252e%252e/private',b'/tools/radarr/app/folder%5csecret',b'/tools/radarr/app/%00'):
        assert not tools_proxy.safe_path(SimpleNamespace(scope={'raw_path':raw}),'radarr')
    assert tools_proxy.safe_path(SimpleNamespace(scope={'raw_path':b'/tools/radarr/app/valid%20asset.js'}),'radarr')


def test_assistance_cannot_bypass_read_only_portal_via_native_proxy(client,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        member=db.scalar(select(User).where(User.emby_id=='user-1'));member.tool_access='["radarr"]';uid=member.id
        for key,value in {'radarr_enabled':'true','radarr_url':'http://private.test:7878','radarr_api_key':encrypt('never-send')}.items():main.set_config(db,key,value)
        db.commit()
    assert post(client,f'/admin/users/{uid}/assist',{},'/admin/users').status_code==303
    monkeypatch.setattr(tools_proxy.httpx,'AsyncClient',lambda **kw:pytest.fail('Assistance reached native administration'))
    assert client.get('/tools/radarr/app/').status_code==401

@pytest.mark.parametrize('has_token',[False,True])
def test_unavailable_media_handoff_still_opens_public_browser_without_token(client,monkeypatch,has_token):
    setup(client)
    from app.models import MediaSession
    with SessionLocal() as db:
        service=db.get(AccessService,'emby');service.browser_url='https://play.example.test:8920/emby'
        owner=db.scalar(select(User).where(User.admin.is_(True)))
        session=db.scalar(select(Session).where(Session.user_id==owner.id))
        if has_token:support.capture(db,owner,{'AccessToken':'must-not-leak','ServerId':'server'},session.digest)
        else:
            for row in db.scalars(select(MediaSession).where(MediaSession.user_id==owner.id)):db.delete(row)
        db.commit()
    monkeypatch.setattr('app.emby.emby.request',lambda *args,**kwargs:(_ for _ in ()).throw(EmbyError('session unavailable')))
    response=client.get('/services/emby/open',follow_redirects=False)
    assert response.status_code==303
    assert response.headers['location']=='https://play.example.test:8920/emby/web/index.html'
    assert 'must-not-leak' not in response.headers['location']
    assert response.headers['referrer-policy']=='no-referrer'


def test_demo_media_session_can_read_only_its_own_profile(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app import mock_emby
    monkeypatch.setattr(mock_emby,'DB',str(tmp_path/'mock-media.db'))
    with TestClient(mock_emby.app) as native:
        login=native.post('/emby/Users/AuthenticateByName',json={'Username':'demo','Pw':'DemoPassword123!'})
        assert login.status_code==200
        data=login.json();headers={'X-Emby-Token':data['AccessToken']}
        assert native.get('/emby/Users/'+data['User']['Id'],headers=headers).status_code==200
        assert native.get('/emby/Users/demo-admin-1',headers=headers).status_code==403
        assert native.get('/emby/Users/Query',headers=headers).status_code==403
