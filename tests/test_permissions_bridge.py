from test_portal import reviewed_post
import json,re,time
from copy import deepcopy
from types import SimpleNamespace
import httpx,pytest
from sqlalchemy import select
from app import main,permissions as p,admin_features,seerr_login
from app.db import SessionLocal
from app.models import User,PolicyState,PermissionGroup,GroupMember,SeerrSession,SeerrTicket,Session,Config
from app.security import encrypt,digest
from test_portal import setup,post,csrf,logout,login_user
ORIGINAL_CLIENT=httpx.Client

@pytest.fixture
def policy_api(client,monkeypatch):
    setup(client)
    from app.security import encrypt
    with SessionLocal() as db:
        for k,v in {'radarr_enabled':'true','radarr_url':'http://radarr.test','radarr_api_key':encrypt('fixture-key')}.items():main.set_config(db,k,v)
        db.commit()
    store={key:{'EnableAllFolders':False,'EnabledFolders':[],'ExcludedSubFolders':[],'IsAdministrator':False,'IsDisabled':False,'EnableSubtitleDownloading':True,'SimultaneousStreamLimit':0,'AccessSchedules':[],'BlockedTags':[]} for key in ('user-1','admin-1')}
    writes=[]
    api=SimpleNamespace(user=lambda uid:{'Id':uid,'Policy':deepcopy(store[uid])},libraries=lambda:[{'Id':'11111111111111111111111111111111','Name':'Movies'},{'Id':'22222222222222222222222222222222','Name':'Films'}],policy=lambda uid,value:(writes.append((uid,deepcopy(value))),store[uid].update(value)),users=lambda:[],copy_options=lambda:[])
    monkeypatch.setattr(p,'emby',api);monkeypatch.setattr(admin_features,'emby',api)
    with SessionLocal() as db:uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
    return uid,store,writes,api


def test_group_merge_is_deterministic_and_restricts_streams():
    a={'EnableSubtitleDownloading':True,'SimultaneousStreamLimit':0,'EnableAllFolders':False,'EnabledFolders':['a'],'BlockedTags':['bad']}
    b={'EnableSubtitleDownloading':False,'SimultaneousStreamLimit':2,'EnableAllFolders':False,'EnabledFolders':['b'],'BlockedTags':['adult']}
    result=p.merge([a,b]);reverse=p.merge([b,a])
    assert result['EnableSubtitleDownloading'] is False and result['SimultaneousStreamLimit']==2
    assert set(result['EnabledFolders'])=={'a','b'} and set(result['BlockedTags'])=={'bad','adult'}
    assert all(p.normalize(k,v)==p.normalize(k,reverse[k]) for k,v in result.items())
    with pytest.raises(ValueError):p.merge([{'AccessSchedules':[{'DayOfWeek':'Monday'}]},{'AccessSchedules':[{'DayOfWeek':'Tuesday'}]}])
    with pytest.raises(ValueError):p.merge([{'IsAdministrator':True}])


def test_individual_permission_write_readback_drift_and_access_control(client,policy_api):
    uid,store,writes,api=policy_api;path=f'/admin/users/{uid}'
    page=client.get(path+"?tab=emby").text;assert 'Maximum simultaneous streams' in page
    with SessionLocal() as db:version=db.get(PolicyState,uid).version
    data={'field':'SimultaneousStreamLimit','value':'2','hash':p.fingerprint(0),'version':version}
    assert post(client,path+'/permission',data,path).status_code==303
    assert store['user-1']['SimultaneousStreamLimit']==2
    assert 'sync-green' in client.get(path+"?tab=emby").text
    count=len(writes);store['user-1']['SimultaneousStreamLimit']=4
    assert 'Different from saved permissions' in client.get(path+"?tab=emby").text and len(writes)==count
    assert post(client,path+'/permission',data,path).status_code==409
    assert client.post(path+'/permission',data={**data,'csrf':'bad'}).status_code==403
    logout(client);login_user(client)
    assert post(client,path+'/permission',data,'/account').status_code==403


def test_failed_policy_readback_is_red_not_success(client,policy_api,monkeypatch):
    uid,store,writes,api=policy_api;path=f'/admin/users/{uid}'
    client.get(path+"?tab=emby");monkeypatch.setattr(api,'policy',lambda *args:None)
    assert post(client,path+'/permission',{'field':'EnableSubtitleDownloading','value':'false','hash':p.fingerprint(True),'version':0},path).status_code==303
    page=client.get(path+"?tab=emby").text
    assert 'sync-red' in page and 'Remote verification failed' in page
    assert store['user-1']['EnableSubtitleDownloading'] is True


def test_group_membership_applies_and_removal_restores_baseline(client,policy_api):
    uid,store,writes,api=policy_api
    r=post(client,'/admin/groups',{'name':'Family'},'/admin/groups');path=r.headers['location']
    response=reviewed_post(client,path,{'version':0,'members':[uid],'permission':['SimultaneousStreamLimit','EnableSubtitleDownloading'],'value_SimultaneousStreamLimit':'2','value_EnableSubtitleDownloading':'false','library_mode':'selected','libraries':['11111111111111111111111111111111']},path)
    assert response.status_code==303
    with SessionLocal() as db:
        row=db.get(PolicyState,uid);assert row.pending;p.apply(db,db.get(User,uid),row,api)
    assert store['user-1']['SimultaneousStreamLimit']==2 and not store['user-1']['EnableSubtitleDownloading']
    assert store['user-1']['EnabledFolders']==['11111111111111111111111111111111']
    assert post(client,path,{'version':1,'library_mode':'inherit'},path).status_code==303
    with SessionLocal() as db:p.apply(db,db.get(User,uid),db.get(PolicyState,uid),api)
    assert store['user-1']['SimultaneousStreamLimit']==0 and store['user-1']['EnableSubtitleDownloading']
    assert store['user-1']['EnabledFolders']==[]
    assert post(client,path,{'version':1},path).status_code==409


def test_last_admin_cannot_be_disabled_and_security_change_requires_confirmation(client,policy_api):
    uid,store,writes,api=policy_api
    with SessionLocal() as db:owner=db.scalar(select(User).where(User.admin.is_(True)));owner_id=owner.id
    path=f'/admin/users/{owner_id}';client.get(path+"?tab=emby")
    assert post(client,path+'/permission',{'field':'IsDisabled','value':'true','hash':p.fingerprint(False),'version':0,'confirm_sensitive':'on'},path).status_code==400
    path=f'/admin/users/{uid}';client.get(path+"?tab=emby")
    assert post(client,path+'/permission',{'field':'IsAdministrator','value':'true','hash':p.fingerprint(False),'version':0},path).status_code==400


def configure_bridge(monkeypatch):
    calls=[]
    def handler(req):
        calls.append(req)
        if '/user/jellyfin/' in req.url.path:
            assert req.headers.get('X-Api-Key')=='private-key'
            return httpx.Response(200,json={'id':2,'jellyfinUserId':'user-1'})
        if req.url.path.endswith('/auth/me'):
            if 'connect.sid=' in req.headers.get('cookie',''):return httpx.Response(200,json={'id':2})
            return httpx.Response(401,headers={'set-cookie':'XSRF-TOKEN=csrf-token; Path=/'})
        if req.url.path.endswith('/auth/jellyfin'):
            assert req.headers.get('X-XSRF-TOKEN')=='csrf-token'
            assert not req.headers.get('X-Api-Key')
            assert json.loads(req.content)=={'username':'demo','password':'DemoPassword123!'}
            return httpx.Response(200,json={'id':2},headers={'set-cookie':'connect.sid=s%3Aprivate.session; HttpOnly; Path=/'})
        if req.url.path.endswith('/auth/logout'):return httpx.Response(200,json={'status':'ok'})
        raise AssertionError(str(req.url))
    monkeypatch.setattr(seerr_login,'client',lambda db,cookies=None:ORIGINAL_CLIENT(base_url='http://seerr.test/',cookies=cookies,transport=httpx.MockTransport(handler)))
    with SessionLocal() as db:
        for k,v in {'seerr_url':'http://seerr.test','seerr_api_key':encrypt('private-key'),'seerr_enabled':'true','seerr_public_url':'https://requests.test','seerr_portal_login':'true'}.items():main.set_config(db,k,v)
        db.commit()
    return calls


def test_seerr_bridge_session_identity_ticket_origin_and_replay(client,monkeypatch,fake):
    setup(client);calls=configure_bridge(monkeypatch)
    # The launch checks the media identity through the configured adapter.
    monkeypatch.setattr('app.emby.emby',fake)
    logout(client);login_user(client)
    page=client.get('/services/seerr/open');assert page.status_code==200
    assert 'private-key' not in page.text and 'DemoPassword123!' not in page.text and 'private.session' not in page.text
    assert 'form-action' in page.headers['content-security-policy'] and 'https://requests.test' in page.headers['content-security-policy']
    ticket=re.search(r'name="ticket" value="([^"]+)"',page.text)[1]
    with SessionLocal() as db:
        stored=db.scalar(select(SeerrSession));assert 'private.session' not in stored.payload
        assert db.get(SeerrTicket,digest(ticket))
    assert client.post('/gatearr-login',data={'ticket':ticket},headers={'origin':'https://evil.test','host':'requests.test'}).status_code==403
    result=client.post('/gatearr-login',data={'ticket':ticket},headers={'origin':'http://testserver','host':'requests.test'},follow_redirects=False)
    assert result.status_code==303 and result.headers['location']=='https://requests.test/'
    assert 'connect.sid=' in result.headers['set-cookie'] and 'HttpOnly' in result.headers['set-cookie'] and 'Secure' in result.headers['set-cookie']
    assert client.post('/gatearr-login',data={'ticket':ticket},headers={'origin':'http://testserver','host':'requests.test'}).status_code==403
    logout(client)
    with SessionLocal() as db:assert db.scalar(select(SeerrSession)) is None
    assert any(str(req.url).endswith('/auth/logout') for req in calls)


def test_seerr_ticket_expires_and_cannot_outlive_portal_session(client,monkeypatch,fake):
    setup(client);configure_bridge(monkeypatch);monkeypatch.setattr('app.emby.emby',fake)
    logout(client);login_user(client)
    page=client.get('/services/seerr/open');ticket=re.search(r'name="ticket" value="([^"]+)"',page.text)[1]
    with SessionLocal() as db:
        row=db.get(SeerrTicket,digest(ticket));row.expires=int(time.time())-1;db.commit()
    assert client.post('/gatearr-login',data={'ticket':ticket},headers={'origin':'http://testserver','host':'requests.test'}).status_code==403
    assert client.post('/gatearr-login',data={'ticket':'guess'},headers={'origin':'http://testserver','host':'requests.test'}).status_code==403


def test_editing_one_permission_does_not_overwrite_unrelated_remote_drift(client,policy_api):
    uid,store,writes,api=policy_api;path=f'/admin/users/{uid}'
    client.get(path+"?tab=emby")
    assert post(client,path+'/permission',{'field':'EnableSubtitleDownloading','value':'false','hash':p.fingerprint(True),'version':0},path).status_code==303
    store['user-1']['EnableSubtitleDownloading']=True
    assert post(client,path+'/permission',{'field':'SimultaneousStreamLimit','value':'3','hash':p.fingerprint(0),'version':1},path).status_code==303
    assert store['user-1']['EnableSubtitleDownloading'] is True
    assert store['user-1']['SimultaneousStreamLimit']==3
    assert 'Different from saved permissions' in client.get(path+"?tab=emby").text


def test_default_palette_matches_logo_and_has_no_white_logo_background():
    from app import portal
    from pathlib import Path
    assert portal.DEFAULT['theme']['accent']=='#159eff' and portal.DEFAULT['theme']['bg']=='#edf4ff'
    css=Path('app/static/style.css').read_text().split('.brand img.gatearr-logo')[-1].split('}')[0]
    assert 'background:transparent' in css and 'padding:0' in css


def test_bridge_rejects_oversized_body_before_processing(client):
    response=client.post('/gatearr-login',content=b'x'*2049,headers={'content-type':'application/x-www-form-urlencoded'})
    assert response.status_code==400


def test_default_seerr_card_needs_public_url_and_respects_manual_menu(client):
    from app.models import MenuItem
    setup(client)
    with SessionLocal() as db:
        main.set_config(db,'seerr_enabled','true');db.commit()
    assert 'data-default-seerr' not in client.get('/home').text
    with SessionLocal() as db:
        main.set_config(db,'seerr_public_url','https://requests.test')
        db.add(MenuItem(label='Seerr',url='https://requests.test',position=99,menu_key='main',new_tab=True));db.commit()
    page=client.get('/home')
    assert page.status_code==200
    # The manual entry takes precedence over the automatic service card.
    assert page.text.count('https://requests.test')==1
