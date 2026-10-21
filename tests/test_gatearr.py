import json
from copy import deepcopy
from types import SimpleNamespace
import httpx
import pytest
from sqlalchemy import select
from app import main, portal, integrations
from app.db import SessionLocal
from app.models import User, Config, IntegrationJob, Token
from app.security import encrypt, decrypt, digest
from app.emby import EmbyClient, EmbyError
from app.mailer import send, DEFAULTS_BY_LOCALE
from test_portal import setup, csrf, post, logout, login_user, prepare_user


def test_languages_public_account_and_errors(client):
    response = client.get('/setup', headers={'accept-language':'en-US,en;q=0.9'})
    assert '<html lang="en">' in response.text and 'Welcome home.' in response.text
    setup(client)
    assert post(client,'/language',{'locale':'en','next':'/admin'},'/admin').status_code == 303
    page=client.get('/admin').text
    assert 'Branding' in page and 'Emails' in page
    page=client.get('/admin/emails').text
    assert 'SMTP server' in page and 'Email templates' in page
    assert 'No TLS (test network)' in page
    assert 'Votre portail' not in page
    error=client.post('/logout',data={'csrf':'bad'})
    assert error.status_code == 403 and 'Form expired' in error.text
    assert post(client,'/language',{'locale':'en','next':'https://evil.test'},'/admin').headers['location']=='/'
    with SessionLocal() as db:
        assert db.scalar(select(User)).locale=='en'


def test_email_templates_english_and_locale_override(client, monkeypatch):
    setup(client)
    captured=[]
    class SMTP:
        def __init__(self,*a,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def ehlo(self):pass
        def send_message(self,message):captured.append(message)
    monkeypatch.setattr('app.mailer.smtplib.SMTP',SMTP)
    with SessionLocal() as db:
        main.set_config(db,'smtp_host','test')
        main.set_config(db,'smtp_from','portal@example.com')
        main.set_config(db,'smtp_port','1025')
        main.set_config(db,'smtp_mode','plain')
        main.set_config(db,'reset_subject','${app_name}: choose a password')
        from app import i18n
        i18n.store_content(db,'mail:reset:subject','${app_name}: choose a password','fr','Ancien sujet français')
        db.commit()
        send(db,'demo@example.com','reset',{'app_name':'Gatearr','username':'demo','minutes':'30','link':'http://testserver/reset?token=x','_locale':'en'})
    assert 'choose a password' in captured[0]['Subject']
    assert 'Hello demo' in captured[0].get_content()
    assert 'Bonjour' not in captured[0].get_content()
    assert 'English' in client.get('/admin?mail_locale=en').text


def builder_post(client,path,data):
    return post(client,path,{'version':version(),**data},'/admin/portal')
def version():
    with SessionLocal() as db:return portal.version(db)


def test_builder_draft_publish_preview_escape_and_menu_positions(client):
    setup(client,locale='fr')
    assert client.get('/admin/portal').status_code==200
    response=builder_post(client,'/admin/portal/block',{'kind':'text','region':'main','order':'11','span':'6','title_fr':'Mon portail unique','title_en':'My unique portal','body_fr':'<script>alert(1)</script>','body_en':'Welcome to Gatearr'})
    assert response.status_code==303
    assert 'Mon portail unique' not in client.get('/home').text
    preview=client.get('/admin/portal/preview').text
    assert 'Mon portail unique' in preview and '&lt;script&gt;' in preview
    assert builder_post(client,'/admin/portal/theme',{'nav_position':'right','sidebar_position':'right','accent':'#123456','bg':'#10151b','surface':'#1a222c','text':'#edf3f9','muted':'#aab8c9'}).status_code==303
    assert '#123456' in client.get('/theme.css?draft=1').text
    assert '#123456' not in client.get('/theme.css').text
    assert builder_post(client,'/admin/portal/publish',{}).status_code==303
    published=client.get('/home').text
    assert 'Mon portail unique' in published and 'nav-right' in published and 'sidebar-right' in published
    assert '#123456' in client.get('/theme.css').text
    assert post(client,'/admin/menu',{'label':'Tracearr','url':'https://tracearr.example.com','icon':'link','position':'1','menu_key':'side'},'/admin').status_code==303
    assert builder_post(client,'/admin/portal/block',{'kind':'menu','region':'sidebar','order':'1','span':'12','menu_key':'side'}).status_code==303
    assert builder_post(client,'/admin/portal/publish',{}).status_code==303
    assert 'Tracearr' in client.get('/home').text
    logout(client)
    login_user(client)
    assert client.get('/admin/portal').status_code==403
    assert client.get('/admin/portal/preview').status_code==403
    assert client.get('/theme.css?draft=1').status_code==403
    assert 'Mon portail unique' in client.get('/home').text


def test_builder_concurrent_admin_and_invalid_block(client):
    setup(client)
    old_version=version()
    data={'kind':'button','region':'main','order':'1','span':'12','url':'javascript:alert(1)','version':old_version}
    assert post(client,'/admin/portal/block',data,'/admin/portal').status_code==400
    assert version()==old_version
    assert builder_post(client,'/admin/portal/theme',{'nav_position':'top','accent':'#abcdef','bg':'#10151b','surface':'#1a222c','text':'#edf3f9','muted':'#aab8c9'}).status_code==303
    assert post(client,'/admin/portal/publish',{'version':old_version},'/admin/portal').status_code==400
    assert client.get('/home').status_code==200


def test_builder_move_delete_restore(client):
    setup(client)
    with SessionLocal() as db:
        published=portal.load(db)
    assert builder_post(client,'/admin/portal/move',{'block_id':'account','direction':'up'}).status_code==303
    with SessionLocal() as db:
        ordered=sorted(portal.load(db,True)['blocks'],key=lambda b:b['order'])
        assert ordered[1]['id']=='account'
    assert builder_post(client,'/admin/portal/delete',{'block_id':'account'}).status_code==303
    assert builder_post(client,'/admin/portal/reset',{}).status_code==303
    with SessionLocal() as db:assert portal.load(db,True)==published


def test_native_clone_contract_and_cleanup(monkeypatch):
    client=EmbyClient();calls=[]
    state={'s':{'Id':'s','Policy':{'IsAdministrator':False,'EnabledFolders':['films']}}}
    def request(method,path,**kwargs):
        body=kwargs.get('json');calls.append((method,path,deepcopy(body)))
        if path=='/Users/CopyDataOptions':return {'DataOptions':[{'Id':'Policy','Name':'Policy'},{'Id':'Configuration','Name':'Configuration'},{'Id':'Password','Name':'Password'}]}
        if method=='GET':return deepcopy(state[path.split('/')[-1]])
        if path=='/Users/New':
            state['t']={'Id':'t','Name':body['Name'],'Policy':{'IsAdministrator':False,'EnabledFolders':['films']}}
            return state['t']
        if path.endswith('/Policy'):state['t']['Policy']=deepcopy(body)
        if path=='/Users/t' and method=='POST':state['t']['Name']=body['Name']
    monkeypatch.setattr(client,'request',request)
    remote=client.clone('s','new-person','InitialPassword123!',['Policy','Configuration'])
    assert remote['Name']=='new-person' and remote['Policy']['IsAdministrator'] is False
    create=next(c for c in calls if c[1]=='/Users/New')
    assert create[2]['CopyFromUserId']=='s' and create[2]['UserCopyOptions']==['Policy','Configuration']
    assert create[2]['Name'].startswith('gatearr-')
    policy_steps=[c[2] for c in calls if c[1].endswith('/Policy')]
    assert policy_steps[0]['IsDisabled'] is True and policy_steps[-1]['IsDisabled'] is False
    assert any(c[2].get('NewPw')=='InitialPassword123!' for c in calls if isinstance(c[2],dict))
    with pytest.raises(ValueError):client.clone('s','unsafe','InitialPassword123!',['Password'])
    calls.clear()
    monkeypatch.setattr(client,'password',lambda *a,**kw: (_ for _ in ()).throw(EmbyError('failed')))
    with pytest.raises(EmbyError,match='new user removed'):client.clone('s','failed','InitialPassword123!',['Policy'])
    assert ('DELETE','/Users/t',None) in calls


def test_libraries_preserve_other_permissions_and_copy_guard(monkeypatch):
    api=EmbyClient();saved=[]
    monkeypatch.setattr(api,'libraries',lambda:[{'Id':'movies','Name':'Movies'},{'Id':'films','Name':'Films'}])
    policy={'IsAdministrator':False,'EnableAllFolders':True,'EnableContentDeletion':False,'BlockedTags':['adults']}
    monkeypatch.setattr(api,'user',lambda uid:{'Id':uid,'Policy':deepcopy(policy)})
    def store(uid,value):
        saved.append(deepcopy(value));policy.update(value)
    monkeypatch.setattr(api,'policy',store)
    api.assign_libraries('u',['films'])
    assert saved[0]['EnabledFolders']==['films'] and saved[0]['EnableAllFolders'] is False
    assert saved[0]['BlockedTags']==['adults'] and saved[0]['EnableContentDeletion'] is False
    api.assign_libraries('u',[],all_folders=True)
    assert policy['EnableAllFolders'] is True
    api.assign_libraries('u',[])
    assert policy['EnableAllFolders'] is False and policy['EnabledFolders']==[]
    assert policy['BlockedTags']==['adults'] and policy['EnableContentDeletion'] is False
    with pytest.raises(ValueError):api.assign_libraries('u',['not-a-library'])


def configured(db,service):
    for key,value in {service+'_enabled':'true',service+'_url':'https://'+service+'.test',service+'_api_key':encrypt('remote-secret')}.items():main.set_config(db,key,value)
    db.commit()

def test_seerr_exact_mapping_and_preserved_preferences(client,monkeypatch):
    prepare_user(client)
    captured=[]
    settings={'username':'Alice','locale':'fr','movieQuotaLimit':5,'movieQuotaDays':7,'watchlistSyncMovies':True,'globalMovieQuotaLimit':99,'email':'old@example.com'}
    def handler(req):
        assert req.headers.get('X-Api-Key')=='remote-secret'
        assert 'remote-secret' not in str(req.url)
        if '/jellyfin/' in req.url.path:return httpx.Response(200,json={'id':8,'jellyfinUserId':'user-1'})
        if req.method=='POST':
            body=json.loads(req.content);captured.append(body);settings.update(body)
        return httpx.Response(200,json=settings)
    real=httpx.Client
    monkeypatch.setattr(integrations.httpx,'Client',lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs))
    with SessionLocal() as db:
        configured(db,'seerr');user=db.scalar(select(User).where(User.emby_id=='user-1'))
        integrations.sync_seerr(db,user)
    assert captured[0]['email']=='demo@example.com' and captured[0]['movieQuotaLimit']==5
    assert captured[0]['locale']=='en' and 'globalMovieQuotaLimit' not in captured[0]




def test_queue_verified_only_failure_retry_and_secret_redaction(client,monkeypatch):
    prepare_user(client)
    with SessionLocal() as db:
        configured(db,'seerr')
        user=db.scalar(select(User).where(User.emby_id=='user-1'))
        integrations.queue_user(db,user)
        assert db.get(IntegrationJob,(user.id,'seerr')).state=='pending'
    monkeypatch.setattr(integrations,'sync_seerr',lambda *args: (_ for _ in ()).throw(integrations.SyncError('authentication')))
    integrations.run_jobs()
    with SessionLocal() as db:
        job=db.scalar(select(IntegrationJob));assert job.state=='error' and job.attempts==1
        assert job.error=='authentication' and job.next_attempt>main.now()
        integrations.queue_all(db,force=True)
    monkeypatch.setattr(integrations,'sync_seerr',lambda *args:None)
    integrations.run_jobs()
    with SessionLocal() as db:assert db.scalar(select(IntegrationJob)).state=='success'
    logout(client)
    post(client,'/login',{'name':'Owner','password':'AdminPassword123!'})
    assert 'remote-secret' not in client.get('/admin/integrations').text
    assert 'gAAAA' not in client.get('/admin/integrations').text


def test_catalogs_match_and_builder_english(client):
    from app.i18n import CATALOGS
    assert {'en','fr','es','de'}<=set(CATALOGS)
    setup(client)
    post(client,'/language',{'locale':'en','next':'/admin'},'/admin')
    for path,expected in [('/admin/portal','Make it yours.'),('/admin/integrations','API connections and notifications')]:
        page=client.get(path)
        assert page.status_code==200 and expected in page.text


def test_email_verification_queues_integrations_only_after_proof(client,sent):
    prepare_user(client)
    with SessionLocal() as db:configured(db,'seerr')
    assert post(client,'/account/email',{'email':'verified@example.com','current':'DemoPassword123!'},'/account').status_code==200
    with SessionLocal() as db:assert db.scalar(select(IntegrationJob)) is None
    main.deliver_mail()
    raw=sent[0][2]['link'].split('token=')[1]
    assert post(client,'/verify-email',{'token':raw},'/verify-email?token='+raw).status_code==200
    with SessionLocal() as db:
        job=db.scalar(select(IntegrationJob))
        assert job.state=='pending' and job.email_digest==integrations.sync_digest(db,db.get(User,job.user_id),job.service)


def test_connector_identity_mismatch_never_writes(client,monkeypatch):
    prepare_user(client);writes=[]
    def handler(req):
        if req.method!='GET':writes.append(req)
        return httpx.Response(200,json={'id':2,'jellyfinUserId':'someone-else'})
    real=httpx.Client
    monkeypatch.setattr(integrations.httpx,'Client',lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs))
    with SessionLocal() as db:
        configured(db,'seerr')
        with pytest.raises(integrations.SyncError,match='identity_mismatch'):
            integrations.sync_seerr(db,db.scalar(select(User).where(User.emby_id=='user-1')))
    assert writes==[]


def test_migration_preserves_existing_accounts_settings_and_menu(client):
    from alembic import command
    from alembic.config import Config as AlembicConfig
    setup(client)
    post(client,'/admin/menu',{'label':'Service','url':'https://example.com','position':'1','icon':'link'},'/admin')
    with SessionLocal() as db:
        main.set_config(db,'smtp_password',encrypt('preserved-secret'))
        db.commit()
    configuration=AlembicConfig('alembic.ini')
    command.downgrade(configuration,'0002')
    command.upgrade(configuration,'head')
    with SessionLocal() as db:
        user=db.scalar(select(User))
        assert user.email=='owner@example.com' and user.admin and user.locale=='en'
        assert decrypt(db.get(Config,'smtp_password').value)=='preserved-secret'
        from app.models import MenuItem
        item=db.scalar(select(MenuItem));assert item.menu_key=='main' and item.label=='Service' and item.label_en is None


def test_bilingual_menu_labels_keep_structural_css(client):
    setup(client)
    post(client,'/admin/menu',{'label':'Demandes','label_en':'Requests','url':'https://example.com','position':'1','icon':'link'},'/admin')
    post(client,'/language',{'locale':'en','next':'/home'},'/home')
    page=client.get('/home').text
    assert 'Requests' in page and 'Demandes' not in page
    assert 'class="services"' in page and 'class="Service cards"' not in page


def test_disabled_service_jobs_do_not_starve_enabled_service(client,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        for i in range(11):
            user=User(name='queue-user-'+str(i),emby_id='queue-'+str(i),email=f'q{i}@example.com',active=True)
            db.add(user);db.flush()
            db.add(IntegrationJob(user_id=user.id,service='tracearr',email_digest=digest(user.email),state='pending',attempts=0,next_attempt=0,updated_at=0,error=''))
        configured(db,'seerr')
        integrations.queue_user(db,user)
    calls=[]
    monkeypatch.setattr(integrations,'sync_seerr',lambda db,user:calls.append(user.id))
    integrations.run_jobs()
    assert len(calls)==1
