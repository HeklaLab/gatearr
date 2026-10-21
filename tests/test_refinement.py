"""Cross-cutting acceptance tests for the unified portal settings."""
import json,os,sqlite3,subprocess,sys
from copy import deepcopy
from pathlib import Path
import httpx
import pytest
from sqlalchemy import select
from app import main,i18n,portal,integrations,connection_health
from app.models import User,Language,Config,ConnectionCheck,IntegrationJob
from app.db import SessionLocal
from app.security import encrypt
from app.emby import EmbyClient,EmbyError,JellyfinClient
from app.sync_status import user_statuses
from test_portal import setup,post,logout,login_user
REAL_CHECKS=connection_health.checks


def test_fresh_install_has_only_english_and_one_user_language(tmp_path):
    dbpath=tmp_path/'fresh.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(dbpath)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True,capture_output=True)
    with sqlite3.connect(dbpath) as db:
        assert db.execute('SELECT code FROM languages WHERE enabled=1').fetchall()==[('en',)]
        assert db.execute('SELECT count(*) FROM languages').fetchone()[0]==21
        assert 'mail_locale' not in {row[1] for row in db.execute('PRAGMA table_info(users)')}
    assert {'en','fr','es','de'}<=set(i18n.CATALOGS)
    assert (Path('app/locales')/'fr.json').exists()


def test_setup_requires_explicit_api_key_and_has_breadcrumbs(client,monkeypatch):
    page=client.get('/setup').text
    assert 'name="setup_token"' not in page and 'wizard-steps' in page and 'aria-current="step"' in page
    assert 'name="api_key" required' in page
    assert not hasattr(main.settings,'emby_api_key') and not hasattr(main.settings,'setup_token')
    assert post(client,'/setup',{'app_name':'Gatearr','public_url':'http://testserver','media_server':'emby','url':'http://media.test'},'/setup').status_code==400
    def rejected(*args):raise EmbyError('denied')
    monkeypatch.setattr('app.onboarding.probe_media',rejected)
    assert post(client,'/setup',{'app_name':'Gatearr','public_url':'http://testserver','media_server':'emby','url':'http://media.test','api_key':'bad-key'},'/setup').status_code==502
    with SessionLocal() as db:assert db.get(Config,'setup_complete') is None


def test_sections_are_separate_and_completed_setup_is_hidden(client):
    setup(client)
    index=client.get('/admin').text
    assert '/admin/setup' not in index
    assert client.get('/admin/setup',follow_redirects=False).headers['location']=='/admin/integrations'
    assert client.get('/admin/setup/media',follow_redirects=False).headers['location']=='/admin/integrations'
    branding=client.get('/admin/branding').text;emails=client.get('/admin/emails').text
    assert 'action="/admin/settings"' in branding and 'action="/admin/smtp"' not in branding
    assert 'action="/admin/smtp"' in emails and 'action="/admin/settings"' not in emails
    assert 'action="/admin/menu"' in client.get('/admin/services').text
    users=client.get('/admin/users').text
    assert 'username-link' in users and 'action="/admin/settings"' not in users
    for path in ('/admin/branding','/admin/emails','/admin/services','/admin/users','/admin/translations','/admin/integrations','/admin/portal','/admin/guides'):
        assert 'Back to admin' in client.get(path).text and 'admin-back' not in client.get(path).text


def test_hover_color_is_validated_and_follows_draft_publication(client):
    setup(client)
    values={'version':'0','nav_position':'left',**portal.DEFAULT['theme'],'button_hover':'#234567'}
    assert post(client,'/admin/portal/theme',values,'/admin/portal').status_code==303
    assert '--button_hover:#234567' in client.get('/theme.css?draft=1').text
    assert '--button_hover:#234567' not in client.get('/theme.css').text
    assert post(client,'/admin/portal/publish',{'version':'1'},'/admin/portal').status_code==303
    assert '--button_hover:#234567' in client.get('/theme.css').text
    assert post(client,'/admin/portal/theme',{**values,'version':'2','button_hover':'red;url(evil)'},'/admin/portal').status_code==400


def test_user_sync_indicators_only_include_configured_services(client):
    setup(client)
    with SessionLocal() as db:
        uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
        assert [s['service'] for s in user_statuses(db,'en')[uid]]==['Emby']
        for key,value in {'seerr_enabled':'true','seerr_url':'https://seerr.test','seerr_api_key':encrypt('key')}.items():main.set_config(db,key,value)
        db.commit()
        assert [s['service'] for s in user_statuses(db,'en')[uid]]==['Emby','Seerr']


def test_translation_page_lists_all_sources_for_selected_language(client):
    setup(client)
    post(client,'/admin/translations/languages',{'code':'de','name':'Deutsch','enabled':'on'},'/admin/translations')
    response=client.get('/admin/translations?edit_locale=de&scope=all')
    assert response.status_code==200
    assert response.text.count('class="card translation-entry"')>=len(i18n.INTERFACE_KEYS)
    assert 'branding:app_name' in response.text and 'mail:invite:subject' in response.text
    assert 'name="edit_locale" value="de"' in response.text and 'Next →' not in response.text


def test_single_language_drives_email_and_seerr_and_queues_on_change(client,monkeypatch,sent):
    setup(client)
    post(client,'/admin/translations/languages',{'code':'es','name':'Español','enabled':'on'},'/admin/translations')
    with SessionLocal() as db:
        for key,value in {'seerr_enabled':'true','seerr_url':'https://seerr.test','seerr_api_key':encrypt('key')}.items():main.set_config(db,key,value)
        db.commit()
    assert post(client,'/account/language',{'locale':'es'},'/account').status_code==303
    remote={'email':'owner@example.com','username':'Owner','locale':'en','discoverRegion':'GB','originalLanguage':'de'}
    def handler(req):
        if '/jellyfin/' in req.url.path:return httpx.Response(200,json={'id':7,'jellyfinUserId':'admin-1'})
        if req.method=='POST':
            body=json.loads(req.content);assert body['locale']=='es' and body['discoverRegion']=='GB' and body['originalLanguage']=='de'
            remote.update(body)
        return httpx.Response(200,json=remote)
    real=httpx.Client
    monkeypatch.setattr(integrations.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.emby_id=='admin-1'))
        assert owner.locale=='es'
        assert db.get(IntegrationJob,(owner.id,'seerr')).state=='pending'
        main.mail_token(db,owner,'reset','test-only',owner.email)
        integrations.sync_seerr(db,owner)
    assert sent[-1][2]['_locale']=='es' and remote['locale']=='es'


def test_connection_health_is_authenticated_cached_and_sanitized(client,monkeypatch):
    setup(client)
    calls=[]
    def handler(req):
        calls.append(str(req.url))
        if req.url.host=='seerr.test':return httpx.Response(403,text='remote-private-token')
        assert req.headers['X-Emby-Token']=='test-api-key'
        return httpx.Response(200,json={'Id':'server'})
    real=httpx.Client
    monkeypatch.setattr(connection_health.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    with SessionLocal() as db:
        for key,value in {'seerr_enabled':'true','seerr_url':'https://seerr.test','seerr_api_key':encrypt('seerr-secret')}.items():main.set_config(db,key,value)
        db.commit()
        checks=REAL_CHECKS(db)
        assert checks['emby']['state']=='connected' and checks['seerr']['state']=='error'
        assert checks['seerr']['detail']=='Authentication rejected'
        assert 'remote-private-token' not in str(checks) and 'seerr-secret' not in str(checks)
        count=len(calls);REAL_CHECKS(db);assert len(calls)==count
        REAL_CHECKS(db,refresh=True);assert len(calls)>count


def test_permission_write_uses_guid_and_preserves_unrelated_policy(monkeypatch):
    api=EmbyClient();guid='0123456789abcdef0123456789abcdef';state={'EnableAllFolders':True,'IsAdministrator':False,'BlockedTags':['restricted'],'ExcludedSubFolders':['old-exclusion']}
    writes=[]
    def request(method,path,**kw):
        if path=='/Library/VirtualFolders/Query':return {'Items':[{'Id':'42','ItemId':'42','Guid':guid,'Name':'Films'}],'TotalRecordCount':1}
        if method=='GET':return {'Id':'user','Policy':deepcopy(state)}
        writes.append(kw['json']);state.update(kw['json'])
    monkeypatch.setattr(api,'request',request)
    assert api.libraries()==[{'Id':guid,'Name':'Films'}]
    api.assign_libraries('user',[guid],False)
    assert writes[-1]['EnabledFolders']==[guid] and writes[-1]['EnableAllFolders'] is False
    assert writes[-1]['ExcludedSubFolders']==[] and writes[-1]['BlockedTags']==['restricted']
    assert '42' not in writes[-1]['EnabledFolders']


def test_upgrade_retains_accounts_connections_and_user_languages_except_removed_french(tmp_path):
    path=tmp_path/'old.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(path)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0009'],env=env,check=True,capture_output=True)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO users (id,name,emby_id,admin,active,version,locale,mail_locale) VALUES (1,'Owner','remote-1',1,1,0,'fr','en')")
        db.execute("INSERT INTO config VALUES ('setup_complete','true'),('emby_api_key','encrypted-original')")
        db.execute("INSERT INTO sessions VALUES ('old-session',1,'csrf',9999999999,0,NULL)")
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True,capture_output=True)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT emby_id,admin,locale FROM users').fetchone()==('remote-1',1,'en')
        assert db.execute("SELECT value FROM config WHERE key='emby_api_key'").fetchone()==('encrypted-original',)
        assert db.execute('SELECT code FROM languages WHERE enabled=1').fetchall()==[('en',)]
        assert db.execute('SELECT count(*) FROM languages').fetchone()[0]==21


def test_upgrade_bootstrap_finds_existing_database_and_keeps_original_secret(tmp_path):
    from app.bootstrap import prepare
    old=tmp_path/'previous.db';target=tmp_path/'gatearr.db';secretfile=tmp_path/'bootstrap.json'
    with sqlite3.connect(old) as db:
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY,name TEXT)')
        db.execute("INSERT INTO users VALUES (1,'Keep me')")
        db.execute('CREATE TABLE config (key TEXT PRIMARY KEY,value TEXT)')
        db.execute("INSERT INTO config VALUES ('emby_api_key','encrypted-existing-key')")
        db.execute('CREATE TABLE alembic_version (version_num TEXT)')
        db.execute("INSERT INTO alembic_version VALUES ('0009')")
    secret='original-encryption-key-'+'x'*40
    secretfile.write_text(json.dumps({'SECRET_KEY':secret,'obsolete_setting':'removed'}))
    env={'DATABASE_URL':'sqlite:///'+str(target),'GATEARR_SECRETS_FILE':str(secretfile)}
    prepare(env)
    assert env['SECRET_KEY']==secret
    assert json.loads(secretfile.read_text())=={'SECRET_KEY':secret}
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT name FROM users').fetchone()==('Keep me',)
        assert db.execute("SELECT value FROM config WHERE key='emby_api_key'").fetchone()==('encrypted-existing-key',)
    assert old.exists()


def test_upgrade_bootstrap_refuses_to_guess_between_multiple_databases(tmp_path):
    from app.bootstrap import prepare
    for name in ('first.db','second.db'):
        with sqlite3.connect(tmp_path/name) as db:
            for table in ('users','config','alembic_version'):db.execute('CREATE TABLE '+table+' (id TEXT)')
    with pytest.raises(RuntimeError,match='Multiple portal databases'):
        prepare({'DATABASE_URL':'sqlite:///'+str(tmp_path/'gatearr.db'),'GATEARR_SECRETS_FILE':str(tmp_path/'bootstrap.json')})
    assert not (tmp_path/'gatearr.db').exists()
