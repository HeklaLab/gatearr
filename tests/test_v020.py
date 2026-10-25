import json,time,re
from copy import deepcopy
from pathlib import Path
import httpx,pytest
from sqlalchemy import select
from app import main,themes,footer,support,tools_proxy
from app.db import SessionLocal
from app.models import User,Session,MediaSession,SupportSession,ToolGrant,AuditEvent,MailJob,Config
from app.security import encrypt,decrypt,digest
from test_portal import setup,post,logout,login_user,csrf

def member(db):return db.scalar(select(User).where(User.emby_id=='user-1'))

def test_setup_error_preserves_nonsecret_fields(client,monkeypatch):
    from app.emby import EmbyError
    monkeypatch.setattr('app.onboarding.probe_media',lambda *args:(_ for _ in ()).throw(EmbyError('no')))
    response=post(client,'/setup',{'app_name':'My portal','public_url':'http://testserver','media_server':'emby','url':'http://private.test:8096','api_key':'dont-echo-this','browser_url':'https://media.test'},'/setup')
    assert response.status_code==502 and 'My portal' in response.text and 'http://private.test:8096' in response.text
    assert 'dont-echo-this' not in response.text
    with SessionLocal() as db:assert db.get(Config,'emby_api_key') is None


def test_themes_modes_customization_and_enforcement(client):
    setup(client)
    light=client.get('/theme.css').text
    assert 'prefers-color-scheme:dark' not in light and themes.DARK['bg'] in light
    with SessionLocal() as db:value=themes.load(db,True)
    response=post(client,'/admin/branding/themes',{'version':0,'mode':'dark','action':'publish'},'/admin/branding/themes')
    assert response.status_code==303
    assert 'prefers-color-scheme:dark' not in client.get('/theme.css').text
    assert post(client,'/account/theme',{'theme':'light'},'/account').status_code==400
    assert post(client,'/admin/branding/themes',{'version':1,'palette':'dark',**value['dark'],'bg':'red;url(x)'},'/admin/branding/themes').status_code==400


def test_rich_footer_columns_sanitization_and_publication(client):
    setup(client)
    data={'version':0,'action':'columns','count':2,'column_0':'<p><strong>Welcome</strong><script>bad()</script></p>','column_1':'<a href="https://example.com">About</a><img src="javascript:alert(1)">'}
    assert post(client,'/admin/footer',data,'/admin/footer').status_code==303
    assert 'About' not in client.get('/login').text
    assert post(client,'/admin/footer',{'version':1,'action':'publish'},'/admin/footer').status_code==303
    page=client.get('/home').text
    assert 'footer-cols-2' in page and '<strong>Welcome</strong>' in page and 'bad()' not in page and 'javascript:' not in page
    assert post(client,'/admin/footer',{**data,'version':2,'count':1},'/admin/footer').status_code==303


def test_svg_is_sanitized_and_font_icons_are_constrained(client):
    setup(client)
    def upload(raw):return client.post('/admin/assets',data={'csrf':csrf(client,'/admin/footer')},files={'icon_file':('icon.svg',raw,'image/svg+xml')},follow_redirects=False)
    response=upload(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0 L10 10" stroke="#159eff"/></svg>')
    assert response.status_code==303
    from urllib.parse import parse_qs,urlsplit
    asset=parse_qs(urlsplit(response.headers['location']).query)['asset'][0]
    public=client.get(asset);assert public.status_code==200 and public.headers['content-type'].startswith('image/svg+xml') and 'sandbox' in public.headers['content-security-policy']
    assert upload(b'<svg><script>alert(1)</script></svg>').status_code==400
    assert upload(b'<svg><image href="https://evil.test/x"/></svg>').status_code==400
    assert post(client,'/admin/menu',{'label':'Test','url':'https://example.com','icon':'★','position':1},'/admin/services').status_code==400
    assert post(client,'/admin/menu',{'label':'Test','url':'https://example.com','icon':'film','position':1},'/admin/services').status_code==303


def test_assistance_identity_readonly_actor_and_expiry(client):
    setup(client)
    with SessionLocal() as db:uid=member(db).id;owner=db.scalar(select(User).where(User.admin.is_(True))).id
    assert post(client,f'/admin/users/{uid}/assist',{},'/admin/users').status_code==303
    home=client.get('/home').text
    assert 'Logged as demo' in home and 'Welcome, demo.' in home
    assert client.get('/admin').status_code==403
    assert post(client,'/account/theme',{'theme':'dark'},'/account').status_code==403
    assert 'must sign in to Gatearr again' in client.get('/services/emby/open').text
    with SessionLocal() as db:
        event=db.scalar(select(AuditEvent).where(AuditEvent.action=='assistance.start'));assert event.actor_id==owner and event.subject_id==uid
        row=db.scalar(select(SupportSession));row.expires=int(time.time())-1;db.commit()
    assert 'logged-as-banner' not in client.get('/home').text
    assert client.get('/admin').status_code==200


def test_admin_account_notifications_encrypted_and_invalidation(client,fake,sent):
    setup(client)
    with SessionLocal() as db:
        u=member(db);uid=u.id;u.email='old@example.com';main.set_config(db,'smtp_host','test');db.commit()
    assert post(client,f'/admin/users/{uid}/account',{'action':'email','email':'new@example.com'},'/admin/users').status_code==303
    with SessionLocal() as db:
        jobs=list(db.scalars(select(MailJob)));assert len(jobs)==2
        assert all('old@example.com' not in j.payload and 'new@example.com' not in j.payload for j in jobs)
    main.deliver_mail();assert {m[0] for m in sent}=={'old@example.com','new@example.com'}
    assert post(client,f'/admin/users/{uid}/account',{'action':'password','password':'ChangedPassword123!','confirm':'ChangedPassword123!'},'/admin/users').status_code==303
    assert fake.password_value=='ChangedPassword123!'
    main.deliver_mail();assert sent[-1][1]=='password_changed'
    with SessionLocal() as db:
        audit=' '.join(e.action+e.detail for e in db.scalars(select(AuditEvent)))
        assert 'ChangedPassword123!' not in audit and 'new@example.com' in audit


def test_tool_ticket_origin_acl_replay_and_revocation(client):
    setup(client)
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)))
        owner.tool_access='["radarr"]'
        for key,value in {'radarr_enabled':'true','radarr_public_url':'https://radarr.test','radarr_url':'http://private.test:7878','radarr_api_key':encrypt('secret')}.items():main.set_config(db,key,value)
        db.commit()
    assert client.get('/tools/sonarr').status_code==403
    page=client.get('/tools/radarr');assert page.status_code==200 and 'secret' not in page.text and 'private.test' not in page.text
    assert 'src="/tools/radarr/app/"' in page.text and 'radarr.test' not in page.text
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)));owner.tool_access='[]';owner.admin=False;db.commit()
    assert client.get('/tools/radarr/app/').status_code==401


def test_tracearr_integration_does_not_join_email_propagation_workers(client):
    from app.integrations import SERVICES
    setup(client)
    assert SERVICES==('seerr',)
    assert 'Tracearr' in client.get('/admin/integrations').text
    assert post(client,'/admin/integrations',{'service':'tracearr','enabled':'on'},'/admin/integrations').status_code==400
    assert client.head('/healthz').status_code==200 and client.head('/',follow_redirects=False).status_code==303


def test_proxy_strips_browser_credentials_streams_and_uses_fixed_upstream(client,monkeypatch):
    setup(client)
    observed=[]
    async def transport(req):
        observed.append(req)
        return httpx.Response(200,stream=httpx.ByteStream(b'<html>Radarr UI</html>'),headers={'content-type':'text/html','set-cookie':'upstream=private','x-frame-options':'DENY'})
    original=httpx.AsyncClient
    monkeypatch.setattr(tools_proxy.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(transport),**kwargs))
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)));owner.tool_access='["radarr"]'
        session=db.scalar(select(Session).where(Session.user_id==owner.id))
        for key,value in {'radarr_enabled':'true','radarr_public_url':'https://radarr.test','radarr_url':'http://private.test:7878','radarr_api_key':encrypt('server-only-key')}.items():main.set_config(db,key,value)
        db.add(ToolGrant(digest=digest('test-cookie'),session_digest=session.digest,user_id=owner.id,tool='radarr',expires=int(time.time())+60,redeemed=True));db.commit()
    client.cookies.set('gatearr_tool_session','test-cookie',domain='radarr.test',path='/')
    result=client.get('/tools/radarr/app/api/v3/movie?sortKey=title',headers={'Authorization':'Bearer evil','X-Api-Key':'evil','X-Forwarded-Host':'evil.test'})
    assert result.status_code==200 and b'Radarr UI' in result.content
    assert str(observed[0].url)=='http://private.test:7878/tools/radarr/app/api/v3/movie?sortKey=title'
    assert observed[0].headers['X-Api-Key']=='server-only-key'
    assert 'authorization' not in observed[0].headers and 'cookie' not in observed[0].headers and 'x-forwarded-host' not in observed[0].headers
    assert 'set-cookie' not in result.headers and 'x-frame-options' not in result.headers
    assert client.post('/tools/radarr/app/api/v3/movie',json={},headers={'origin':'https://evil.test'}).status_code==403
    assert len(observed)==1


def test_assistance_can_use_only_live_matching_media_session(client,fake,monkeypatch):
    setup(client)
    from fastapi.testclient import TestClient
    with TestClient(main.app) as member_client:
        login_user(member_client)
        with SessionLocal() as db:
            uid=member(db).id
            from app.models import AccessService
            db.get(AccessService,'emby').browser_url='https://media.test'
            row=db.scalar(select(MediaSession).where(MediaSession.user_id==uid));assert row and 'user-token' not in row.payload
            db.commit()
        # Verify the stored user token with the media adapter before generating the handoff.
        fake.request=lambda method,path,token=None:{'Id':'user-1','Policy':{'IsDisabled':False}} if token=='user-token' else {}
        monkeypatch.setattr('app.emby.emby',fake)
        assert post(client,f'/admin/users/{uid}/assist',{},'/admin/users').status_code==303
        response=client.get('/services/emby/open',follow_redirects=False)
        assert response.status_code==303 and response.headers['location'].startswith('https://media.test/web/index.html?') and 'user-token' in response.headers['location'] and 'owner-token' not in response.headers['location']
        assert response.headers['referrer-policy']=='no-referrer'
        logout(member_client)
        page=client.get('/services/emby/open')
        assert 'must sign in to Gatearr again' in page.text


def test_howto_service_and_tutorial_are_created_without_manual_identifiers(client):
    from app.models import MenuItem,AccessService,Guide
    setup(client)
    r=post(client,'/admin/menu',{'label':'My service','url':'https://service.test','icon':'book','position':1,'access_mode':'howto'},'/admin/services')
    assert r.status_code==303 and r.headers['location'].startswith('/admin/design/home/howto/service-')
    path=r.headers['location']
    r=post(client,'/admin/access/'+path.rsplit('/',1)[-1],{'version':0,'kind':'guide','title':'Connect on Mac','position':1,'guide_id':0},path)
    assert r.status_code==303 and r.headers['location'].startswith('/admin/guides/')
    with SessionLocal() as db:
        item=db.scalar(select(MenuItem).where(MenuItem.label=='My service'));service=db.get(AccessService,item.access_service)
        assert json.loads(service.access_draft)[0]['guide_id']>0 and service.access_published=='[]'


def test_storage_preflight_uses_runtime_uid_and_reports_access_errors(tmp_path):
    from app.bootstrap import check_storage
    check_storage({'DATABASE_URL':'sqlite:///'+str(tmp_path/'data/gatearr.db'),'GATEARR_SECRETS_FILE':str(tmp_path/'data/bootstrap.json')})
    assert not (tmp_path/'data/bootstrap.json').exists()


def test_upgrade_from_012_preserves_accounts_and_secrets_but_removes_tracearr(tmp_path):
    import os,sqlite3,subprocess,sys
    dbpath=tmp_path/'upgrade.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(dbpath)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0012'],env=env,check=True,capture_output=True)
    with sqlite3.connect(dbpath) as db:
        db.execute("INSERT INTO users(id,emby_id,name,admin,active,password_hash,version,preferences_version,newsletter_pending,emby_missing,locale) VALUES(99,'existing-id','Existing user',1,1,NULL,7,2,0,0,'en')")
        db.execute("INSERT INTO config(key,value) VALUES('emby_api_key','encrypted-keep'),('tracearr_api_key','encrypted-retire'),('onboarding_step','tracearr')")
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True,capture_output=True)
    with sqlite3.connect(dbpath) as db:
        assert db.execute('SELECT name,admin,version,theme_preference,tool_access FROM users WHERE id=99').fetchone()==('Existing user',1,7,'auto','[]')
        assert db.execute("SELECT value FROM config WHERE key='emby_api_key'").fetchone()==('encrypted-keep',)
        assert db.execute("SELECT value FROM config WHERE key LIKE 'tracearr_%'").fetchall()==[]
        assert 'newsletter_opt_in' not in {row[1] for row in db.execute('PRAGMA table_info(users)')}
        assert db.execute("SELECT value FROM config WHERE key='onboarding_step'").fetchone()==('tools',)


def test_three_tools_share_setup_step_but_have_individual_grants(client,monkeypatch,fake):
    setup(client)
    original=httpx.Client;requests=[]
    def handler(req):
        # Application cards now fetch their media information by default.
        if req.url.host=='emby.test':
            return httpx.Response(200,json={'Items':[],'TotalRecordCount':0} if req.url.path.endswith('/Items') else fake.dto())
        requests.append(req)
        assert req.headers['X-Api-Key']=='private-tool-key'
        return httpx.Response(200,json={'appName':req.url.host.split('.')[0]})
    monkeypatch.setattr(tools_proxy.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    values={'proxy_acknowledge':'on'}
    for name in tools_proxy.TOOLS:
        values.update({name+'_enabled':'on',name+'_url':'http://'+name+'.private',name+'_public_url':'https://'+name+'.test',name+'_api_key':'private-tool-key'})
    assert post(client,'/admin/tools',values,'/admin/integrations').status_code==303
    assert len(requests)==3
    with SessionLocal() as db:
        uid=member(db).id
        assert decrypt(main.config(db,'radarr_api_key'))=='private-tool-key'
    assert post(client,f'/admin/users/{uid}/role',{'tools':['radarr','bazarr']},'/admin/users').status_code==303
    logout(client);login_user(client)
    page=client.get('/home').text
    assert 'href="/tools/radarr"' in page and 'href="/tools/bazarr"' in page and 'href="/tools/sonarr"' not in page
    assert client.get('/admin').status_code==403
    assert client.get('/tools/radarr').status_code==200 and client.get('/tools/sonarr').status_code==403


def test_assistance_exit_invalidates_unredeemed_seerr_ticket(client,fake,monkeypatch):
    from fastapi.testclient import TestClient
    from test_permissions_bridge import configure_bridge
    setup(client);configure_bridge(monkeypatch);monkeypatch.setattr('app.emby.emby',fake)
    with TestClient(main.app) as member_client:
        login_user(member_client)
        with SessionLocal() as db:uid=member(db).id
        assert post(client,f'/admin/users/{uid}/assist',{},'/admin/users').status_code==303
        page=client.get('/services/seerr/open')
        raw=re.search(r'name="ticket" value="([^"]+)"',page.text)[1]
        assert post(client,'/support/stop',{},'/home').status_code==303
        response=client.post('/gatearr-login',data={'ticket':raw},headers={'origin':'http://testserver','host':'requests.test'},follow_redirects=False)
        assert response.status_code==403


def test_tool_websocket_uses_same_live_grant_and_checks_origin(client,monkeypatch):
    import asyncio
    from starlette.websockets import WebSocketDisconnect
    setup(client);observed=[]
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)));owner.tool_access='["radarr"]'
        session=db.scalar(select(Session).where(Session.user_id==owner.id))
        for key,value in {'radarr_enabled':'true','radarr_public_url':'https://radarr.test','radarr_url':'http://private.test:7878','radarr_api_key':encrypt('ws-server-key')}.items():main.set_config(db,key,value)
        db.add(ToolGrant(digest=digest('ws-test-cookie'),session_digest=session.digest,user_id=owner.id,tool='radarr',expires=int(time.time())+60,redeemed=True));db.commit()
    class Remote:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def __aiter__(self):return self.messages()
        async def messages(self):yield '{"event":"update"}'
        async def send(self,value):pass
    def connection(url,**kwargs):observed.append((url,kwargs));return Remote()
    monkeypatch.setattr('websockets.asyncio.client.connect',connection)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/tools/radarr/app/signalr',headers={'origin':'https://evil.test','cookie':'gatearr_session='+client.cookies.get('gatearr_session')}):pass
    with client.websocket_connect('/tools/radarr/app/signalr',headers={'origin':'http://testserver','cookie':'gatearr_session='+client.cookies.get('gatearr_session')}) as ws:
        assert ws.receive_json()=={'event':'update'}
    assert len(observed)==1 and observed[0][0]=='ws://private.test:7878/tools/radarr/app/signalr'
    assert observed[0][1]['additional_headers']=={'X-Api-Key':'ws-server-key'} and observed[0][1]['proxy'] is None
