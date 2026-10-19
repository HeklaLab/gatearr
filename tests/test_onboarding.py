import json
import os
import sqlite3
import stat
import subprocess
import sys
from copy import deepcopy
import httpx
import pytest
from sqlalchemy import select
from app import main,onboarding
from app.bootstrap import prepare
from app.db import SessionLocal
from app.models import Config,User
from app.security import decrypt,origin
from app.emby import JellyfinClient,EmbyError
from test_portal import setup,post,logout,login_user,PASSWORD


def claim(client):
    return post(client,'/setup',{'app_name':'My Gate','public_url':'http://testserver','media_server':'jellyfin','url':'http://jellyfin.test','api_key':'key'},'/setup')


def test_first_run_requires_verified_media_and_optional_steps_can_be_skipped(client):
    assert client.get('/setup/admin').status_code==403
    assert claim(client).status_code==303
    assert client.get('/admin').status_code==401
    assert post(client,'/setup/admin',{'user_id':'admin-1','password':'wrong'},'/setup/admin').status_code==401
    assert post(client,'/setup/admin',{'user_id':'admin-1','password':PASSWORD},'/setup/admin').status_code==303
    with SessionLocal() as db:
        assert db.get(Config,'media_server').value=='jellyfin'
        assert decrypt(db.get(Config,'emby_api_key').value)=='key'
        assert db.scalar(select(User).where(User.emby_id=='user-1')).admin is False
        assert db.scalar(select(User).where(User.emby_id=='admin-1')).admin is True
    for step in ('seerr','tools','smtp'):
        assert post(client,'/admin/setup/'+step,{'action':'skip'},'/admin/setup/'+step).status_code==303
    assert post(client,'/admin/setup/finish',{},'/admin/setup/finish').status_code==303
    assert 'My Gate' in client.get('/admin').text
    logout(client)
    assert login_user(client).status_code==303
    assert 'Sign in with your Jellyfin account.' not in client.get('/login').text
    assert client.get('/admin/setup').status_code==403


def test_failed_required_connection_does_not_mark_setup_ready(client,monkeypatch):
    def fail(*args):raise EmbyError('unavailable')
    monkeypatch.setattr(onboarding,'probe_media',fail)
    assert claim(client).status_code==502
    with SessionLocal() as db:
        assert db.get(Config,'onboarding_media_verified') is None
        assert db.get(Config,'emby_api_key') is None
        assert db.get(Config,'setup_complete') is None
    assert client.get('/setup/admin').status_code==403


def test_optional_connection_is_validated_before_saving(client,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        main.set_config(db,'onboarding_required','true');db.commit()
    real=httpx.Client
    def handler(req):return httpx.Response(401,json={'error':'private-debug'})
    monkeypatch.setattr(onboarding.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    response=post(client,'/admin/setup/seerr',{'url':'https://seerr.test','api_key':'bad-secret','notification_mode':'optional'},'/admin/setup/seerr')
    assert response.status_code==502 and 'bad-secret' not in response.text and 'private-debug' not in response.text
    with SessionLocal() as db:
        assert db.get(Config,'seerr_api_key') is None
        assert db.get(Config,'seerr_enabled') is None
    assert post(client,'/admin/setup/seerr',{'action':'skip'},'/admin/setup/seerr').status_code==303


def test_bootstrap_generates_independent_persistent_owner_only_secrets(tmp_path):
    path=tmp_path/'bootstrap.json'
    env={'GATEARR_SECRETS_FILE':str(path),'DATABASE_URL':'sqlite:///'+str(tmp_path/'fresh.db')}
    prepare(env)
    values=json.loads(path.read_text())
    assert len(values['SECRET_KEY'])>=32
    assert set(values)=={'SECRET_KEY'}
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    other={'GATEARR_SECRETS_FILE':str(path),'DATABASE_URL':env['DATABASE_URL']}
    prepare(other)
    assert other['SECRET_KEY']==env['SECRET_KEY']
    # CLI processes also find the persisted key even when Docker exec does not inherit PID 1's environment.
    child={**os.environ,'GATEARR_SECRETS_FILE':str(path)}
    child.pop('SECRET_KEY',None)
    result=subprocess.run([sys.executable,'-c','from app.settings import settings; assert len(settings.secret_key)>=32; print("ok")'],env=child,capture_output=True,text=True,check=True)
    assert result.stdout.strip()=='ok'


def test_bootstrap_never_replaces_an_existing_installations_encryption_key(tmp_path):
    database=tmp_path/'existing.db'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE config (key TEXT PRIMARY KEY,value TEXT)')
        db.execute("INSERT INTO config VALUES ('setup_complete','true')")
    env={'GATEARR_SECRETS_FILE':str(tmp_path/'bootstrap.json'),'DATABASE_URL':'sqlite:///'+str(database)}
    with pytest.raises(RuntimeError,match='SECRET_KEY existante'):prepare(env)
    assert not (tmp_path/'bootstrap.json').exists()
    provided={**env,'SECRET_KEY':'explicit-secret-'+'x'*40}
    prepare(provided)
    assert not (tmp_path/'bootstrap.json').exists()


def test_standard_http_https_ports_have_equivalent_origins():
    assert origin('http://portal.test:80')==origin('http://portal.test')
    assert origin('https://portal.test:443')==origin('https://portal.test')
    assert origin('https://portal.test:8443')!=origin('https://portal.test')
    assert origin('null') is None and origin('https://u:p@portal.test') is None


def test_jellyfin_auth_listing_password_and_libraries_contract(client,monkeypatch):
    observed=[]
    def handler(req):
        observed.append(req)
        if req.url.path=='/Users/AuthenticateByName':return httpx.Response(200,json={'User':{'Id':'jf-user'},'AccessToken':'session-token'})
        assert 'Token="api-secret"' in req.headers['Authorization'] or 'Token="session-token"' in req.headers['Authorization']
        if req.url.path=='/Users':return httpx.Response(200,json=[{'Id':'jf-user','Name':'Alice'}])
        if req.url.path=='/Library/VirtualFolders':return httpx.Response(200,json=[{'ItemId':'films','Name':'Films','Locations':['private-path']}])
        return httpx.Response(204)
    real=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    api=JellyfinClient('https://jellyfin.test','api-secret')
    auth=api.authenticate('Alice','password')
    assert api.users()==[{'Id':'jf-user','Name':'Alice'}]
    assert api.libraries()==[{'Id':'films','Name':'Films'}]
    api.password('jf-user','new-password',auth['AccessToken'])
    request=observed[-1]
    assert request.url.path=='/Users/Password' and request.url.params['userId']=='jf-user'
    assert json.loads(request.content)=={'NewPw':'new-password','ResetPassword':False}
    assert observed[0].headers['Authorization'].startswith('MediaBrowser ')
    assert all('api-secret' not in str(req.url) for req in observed)


def test_jellyfin_copy_uses_supported_endpoints_and_preserves_target_roles(monkeypatch):
    api=JellyfinClient();calls=[]
    state={'source':{'Id':'source','Name':'Template','Policy':{'IsAdministrator':False,'EnableAllFolders':False,'EnabledFolders':['films']},'Configuration':{'OrderedViews':['films']}},'target':{'Id':'target','Name':'Member','Policy':{'IsAdministrator':True,'IsDisabled':True}}}
    def request(method,path,**kwargs):
        calls.append((method,path,deepcopy(kwargs)))
        if path=='/DisplayPreferences/usersettings' and method=='GET':return {'Id':'source-preferences','CustomPrefs':{'homesection0':'resume'}}
        if path.startswith('/Users/') and method=='GET':return deepcopy(state[path.split('/')[-1]])
        if path.endswith('/Policy'):state['target']['Policy']=deepcopy(kwargs['json'])
    monkeypatch.setattr(api,'request',request)
    api.copy_to_existing('source','target',['Policy','Configuration','DisplayPreferences'])
    assert state['target']['Policy']['IsAdministrator'] is True and state['target']['Policy']['IsDisabled'] is True
    assert state['target']['Policy']['EnabledFolders']==['films']
    config=next(call for call in calls if call[1]=='/Users/Configuration')
    assert config[2]['params']['userId']=='target' and config[2]['json']['OrderedViews']==['films']
    display=next(call for call in calls if call[0]=='POST' and call[1]=='/DisplayPreferences/usersettings')
    assert display[2]['params']=={'userId':'target','client':'emby'}
    assert 'Id' not in display[2]['json']


@pytest.mark.parametrize('fail_copy',[False,True])
def test_jellyfin_clone_keeps_account_disabled_during_copy_and_cleans_up_failures(monkeypatch,fail_copy):
    api=JellyfinClient();events=[]
    state={'Id':'new','Name':'Clone','Policy':{'IsDisabled':False,'IsAdministrator':False}}
    monkeypatch.setattr(api,'validate_copy',lambda *args:None)
    monkeypatch.setattr(api,'user',lambda user_id:deepcopy(state))
    def request(method,path,**kwargs):
        events.append((method,path,kwargs))
        if path=='/Users/New':
            assert kwargs['json']=={'Name':'Clone','Password':'new-password'}
            return deepcopy(state)
        if path.endswith('/Policy'):state['Policy']=deepcopy(kwargs['json'])
    monkeypatch.setattr(api,'request',request)
    def copy(*args):
        assert state['Policy']['IsDisabled'] is True and state['Policy']['IsAdministrator'] is False
        if fail_copy:raise EmbyError('copy refused')
    monkeypatch.setattr(api,'copy_to_existing',copy)
    if fail_copy:
        with pytest.raises(EmbyError,match='new user removed'):api.clone('source','Clone','new-password',['Policy'])
        assert events[-1][:2]==('DELETE','/Users/new')
    else:
        result=api.clone('source','Clone','new-password',['Policy'])
        assert result['Policy']['IsDisabled'] is False and result['Policy']['IsAdministrator'] is False
        assert not any(event[0]=='DELETE' for event in events)
