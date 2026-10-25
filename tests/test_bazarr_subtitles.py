"""Conservative profile writes and independent user/group subtitle permission."""
from contextlib import contextmanager
from copy import deepcopy
import json
from types import SimpleNamespace
from urllib.parse import parse_qs
import httpx
import pytest
from sqlalchemy import select
from app import bazarr_subtitles as bs, main
from app.db import SessionLocal
from app.models import User, PermissionGroup, GroupMember
from app.security import encrypt
from test_portal import setup, post, logout, login_user, csrf
from test_permissions_bridge import policy_api


def profile(pid,name):
    return {'profileId':pid,'name':name,'cutoff':1,'items':[{'id':1,'language':'en','forced':'False','hi':'False','audio_exclude':'True','audio_only_include':'False'}],'mustContain':['1080p'],'mustNotContain':['cam'],'originalFormat':1,'tag':'shared'}


@pytest.fixture
def bazarr(client,monkeypatch):
    setup(client)
    state=SimpleNamespace(profiles=[profile(1,'Shared'),profile(2,'Private')],languages=[{'code2':'en','code3':'eng','name':'English','enabled':True},{'code2':'fr','code3':'fra','name':'French','enabled':False},{'code2':'de','code3':'deu','name':'German','enabled':True}],writes=[],failure=None,reject_update=False,change=None)
    def handle(request):
        if state.failure:return httpx.Response(state.failure)
        if request.url.path.endswith('/languages/profiles'):
            if state.change:state.change(state)
            return httpx.Response(200,json=deepcopy(state.profiles))
        if request.url.path.endswith('/languages'):return httpx.Response(200,json=deepcopy(state.languages))
        assert request.method=='POST' and request.url.path.endswith('/settings')
        data=parse_qs(request.content.decode());state.writes.append(deepcopy(data))
        if not state.reject_update:
            state.profiles=json.loads(data['languages-profiles'][0])
            if 'languages-enabled' in data:
                for row in state.languages:row['enabled']=row['code2'] in data['languages-enabled']
        return httpx.Response(204)
    @contextmanager
    def connection(db):
        with httpx.Client(base_url='http://bazarr.test/tools/bazarr/app/',transport=httpx.MockTransport(handle)) as remote:yield remote
    monkeypatch.setattr(bs,'connection',connection)
    with SessionLocal() as db:
        for key,value in {'bazarr_enabled':'true','bazarr_url':'http://bazarr.test','bazarr_api_key':encrypt('secret-api-key')}.items():main.set_config(db,key,value)
        db.commit()
    response=post(client,'/admin/bazarr/subtitles',{'enabled':'on','profile_id':'1'},'/admin/integrations')
    assert response.status_code==303,response.text
    return state


def allow_user():
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'));user.bazarr_subtitles=True;db.commit();return user.id


def submit(client,code='fr',**changes):
    with SessionLocal() as db:
        payload={'languages':code if isinstance(code,list) else [code],'profile_id':bs.config(db,'bazarr_subtitles_profile'),'connection':bs.connection_id(db),'subtitle_version':db.scalar(select(User.bazarr_subtitle_version).where(User.emby_id=='user-1'))}
    payload.update(changes)
    return post(client,'/account/subtitles/language',payload,'/account')


def test_add_preserves_all_profiles_options_and_enabled_languages(client,bazarr):
    before=deepcopy(bazarr.profiles);allow_user();logout(client);login_user(client)
    account=client.get('/account').text
    assert 'Subtitle languages' in account and 'Choose your preferred subtitle languages.' in account and 'Shared' not in account
    response=submit(client)
    assert response.status_code==303,response.text
    assert response.headers['location']=='/account?saved=subtitle-languages'
    assert bazarr.profiles[1]==before[1]
    assert bazarr.profiles[0]['items'][:-1]==before[0]['items']
    assert {k:v for k,v in bazarr.profiles[0].items() if k!='items'}=={k:v for k,v in before[0].items() if k!='items'}
    assert bazarr.profiles[0]['items'][-1]=={'id':2,'language':'fr','forced':'False','hi':'False','audio_exclude':'False','audio_only_include':'False'}
    assert set(bazarr.writes[0]['languages-enabled'])=={'en','de','fr'}
    assert 'secret-api-key' not in account
    assert submit(client).headers['location']=='/account?saved=subtitle-languages'
    assert len(bazarr.writes)==1


def test_permissions_not_implied_by_admin_or_tool_access_and_rechecked(client,bazarr):
    assert submit(client).status_code==403  # Owner has no implicit grant.
    allow_user();logout(client);login_user(client)
    with SessionLocal() as db:
        u=db.scalar(select(User).where(User.emby_id=='user-1'));u.bazarr_subtitles=False;u.tool_access='["bazarr"]';db.commit()
    assert submit(client).status_code==403
    assert 'action="/account/subtitles/language"' not in client.get('/account').text
    assert client.get('/admin/bazarr/subtitle-profiles').status_code==403
    assert bazarr.writes==[]


def test_disabled_changed_connection_profile_and_invalid_language_cannot_write(client,bazarr):
    allow_user();logout(client);login_user(client)
    assert submit(client,'xx').status_code==400
    assert submit(client,profile_id='2').status_code==409
    assert submit(client,connection='old-connection').status_code==409
    with SessionLocal() as db:main.set_config(db,'bazarr_api_key',encrypt('new-key'));db.commit()
    assert submit(client).status_code==409
    assert 'action="/account/subtitles/language"' not in client.get('/account').text
    assert bazarr.writes==[]


def test_stale_profile_snapshot_is_refused(client,bazarr):
    allow_user();logout(client);login_user(client)
    token=csrf(client,'/account');count=0
    def change(state):
        nonlocal count
        count+=1
        if count==2:state.profiles[1]['name']='Changed remotely'
    bazarr.change=change
    with SessionLocal() as db:connection=bs.connection_id(db)
    response=client.post('/account/subtitles/language',data={'csrf':token,'languages':['fr'],'profile_id':'1','connection':connection,'subtitle_version':'0'},follow_redirects=False)
    assert response.status_code==409,response.text
    assert bazarr.writes==[]


@pytest.mark.parametrize('failure',[401,500])
def test_remote_failures_are_safe_and_do_not_write(client,bazarr,failure):
    allow_user();logout(client);login_user(client);bazarr.failure=failure
    assert client.get('/account').status_code==200
    response=submit(client)
    assert response.status_code==502 and 'secret-api-key' not in response.text
    assert bazarr.writes==[]


def test_readback_failure_is_not_reported_as_success(client,bazarr):
    allow_user();logout(client);login_user(client);bazarr.reject_update=True
    response=submit(client)
    assert response.status_code==502 and len(bazarr.writes)==1


def test_admin_selects_one_existing_profile_and_disables_option(client,bazarr):
    options=client.get('/admin/bazarr/subtitle-profiles')
    assert options.json()=={'profiles':[{'id':1,'name':'Shared'},{'id':2,'name':'Private'}]}
    assert post(client,'/admin/bazarr/subtitles',{'enabled':'on','profile_id':'999'},'/admin/integrations').status_code==400
    assert post(client,'/admin/bazarr/subtitles',{},'/admin/integrations').status_code==303
    with SessionLocal() as db:assert not bs.offered(db)
    assert bazarr.writes==[]


def test_group_inheritance_and_removal_restore_individual_permission(client,bazarr):
    from app.group_access import apply_access
    uid=allow_user()
    with SessionLocal() as db:
        user=db.get(User,uid);group=PermissionGroup(name='Subtitle users',policy='{}',access_policy='{"bazarr_subtitles":false}')
        db.add(group);db.flush();apply_access(db,user,group);assert not user.bazarr_subtitles
        group.access_policy='{"bazarr_subtitles":true}';apply_access(db,user,group);assert user.bazarr_subtitles
        group.access_policy='{}';apply_access(db,user,group);assert user.bazarr_subtitles
        apply_access(db,user,None);assert user.bazarr_subtitles
        user.bazarr_subtitles=False;apply_access(db,user,group);group.access_policy='{"bazarr_subtitles":true}';apply_access(db,user,group);assert user.bazarr_subtitles
        apply_access(db,user,None);assert not user.bazarr_subtitles
        db.rollback()


def test_individual_permission_save_is_independent_from_tool_grants(client,bazarr):
    with SessionLocal() as db:user=db.scalar(select(User).where(User.emby_id=='user-1'));uid=user.id
    response=post(client,f'/admin/users/{uid}/role',{'bazarr_subtitles':'on','bazarr_subtitle_limit':'2'},f'/admin/users/{uid}')
    assert response.status_code==303,response.text
    with SessionLocal() as db:
        user=db.get(User,uid);assert user.bazarr_subtitles and user.bazarr_subtitle_limit==2 and not user.admin and json.loads(user.tool_access)==[]
    assert bazarr.writes==[]


def test_group_form_reviews_and_applies_subtitle_permission(client,policy_api):
    uid,store,writes,api=policy_api
    path=post(client,'/admin/groups',{'name':'Subtitle requests'},'/admin/groups').headers['location']
    payload={'version':0,'members':[uid],'manage_bazarr_subtitles':'on','bazarr_subtitles':'on','bazarr_subtitle_limit':'2'}
    review=post(client,path,{**payload,'review_only':'on'},path)
    assert review.status_code==200,review.text
    assert any(d['service']=='Bazarr' and d['label']=='Allow adding subtitle languages in Bazarr' for d in review.json()['users'][0]['differences'])
    assert post(client,path,{**payload,'review_token':review.json()['review_token']},path).status_code==303
    with SessionLocal() as db:
        assert db.get(User,uid).bazarr_subtitles and db.get(User,uid).bazarr_subtitle_limit==2
        group=db.get(PermissionGroup,int(path.rsplit('/',1)[1]));assert json.loads(group.access_policy)['bazarr_subtitles']
    assert post(client,f'/admin/users/{uid}/role',{},f'/admin/users/{uid}').status_code==409


def test_profile_permission_migration_preserves_users_and_existing_config(tmp_path):
    import os,sqlite3,subprocess,sys
    database=tmp_path/'before-subtitles.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(database)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0023'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        db.execute("insert into config(key,value) values('app_name','Keep this portal')")
        db.execute("insert into users(name,admin,active,version) values('Existing admin',1,1,4)");db.commit()
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        assert db.execute('select name,admin,version,bazarr_subtitles from users').fetchone()==('Existing admin',1,4,0)
        assert db.execute("select value from config where key='app_name'").fetchone()[0]=='Keep this portal'


def test_existing_shared_language_uses_personal_slot_without_warning_or_remote_write(client,bazarr):
    uid=allow_user();logout(client);login_user(client)
    result=submit(client,['en'])
    assert result.status_code==303 and result.headers['location']=='/account?saved=subtitle-languages'
    with SessionLocal() as db:assert json.loads(db.get(User,uid).bazarr_subtitle_languages)==['en']
    assert not bazarr.writes
    page=client.get('/account').text
    assert 'This language is already' not in page and 'Languages already included' not in page
    assert 'Subtitles will be added according to availability.' in page
    assert 'Shared' not in page


def test_capacity_is_enforced_server_side_and_removal_frees_a_slot(client,bazarr):
    uid=allow_user()
    with SessionLocal() as db:db.get(User,uid).bazarr_subtitle_limit=1;db.commit()
    logout(client);login_user(client)
    assert submit(client,['en','fr']).status_code==400 and not bazarr.writes
    assert submit(client,['fr']).status_code==303
    assert submit(client,[]).status_code==303
    assert any(i['language']=='fr' for i in bazarr.profiles[0]['items'])
    assert submit(client,['de']).status_code==303
    with SessionLocal() as db:assert json.loads(db.get(User,uid).bazarr_subtitle_languages)==['de']
    assert len(bazarr.writes)==2


def test_two_users_can_select_the_same_language_without_extra_bazarr_updates(client,bazarr):
    uid=allow_user();logout(client);login_user(client);assert submit(client,['fr']).status_code==303
    logout(client)
    from test_portal import PASSWORD
    post(client,'/login',{'name':'Owner','password':PASSWORD})
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.emby_id=='admin-1'));owner.bazarr_subtitles=True;owner_id=owner.id;connection=bs.connection_id(db);db.commit()
    result=post(client,'/account/subtitles/language',{'languages':['fr'],'subtitle_version':0,'profile_id':'1','connection':connection},'/account')
    assert result.status_code==303 and result.headers['location']=='/account?saved=subtitle-languages'
    with SessionLocal() as db:
        assert json.loads(db.get(User,uid).bazarr_subtitle_languages)==['fr']
        assert json.loads(db.get(User,owner_id).bazarr_subtitle_languages)==['fr']
    assert len(bazarr.writes)==1


def test_stale_personal_form_does_not_overwrite_another_save(client,bazarr):
    uid=allow_user();logout(client);login_user(client)
    assert submit(client,['en']).status_code==303
    assert submit(client,['fr'],subtitle_version=0).status_code==409
    with SessionLocal() as db:assert json.loads(db.get(User,uid).bazarr_subtitle_languages)==['en']
    assert not bazarr.writes


def test_multiple_new_languages_are_added_in_one_preserving_write(client,bazarr):
    bazarr.languages.append({'code2':'es','name':'Spanish','enabled':False})
    uid=allow_user();logout(client);login_user(client)
    assert submit(client,['en','fr','es']).status_code==303
    assert len(bazarr.writes)==1
    assert {i['language'] for i in bazarr.profiles[0]['items']}=={'en','fr','es'}
    with SessionLocal() as db:assert json.loads(db.get(User,uid).bazarr_subtitle_languages)==['en','fr','es']


def test_group_capacity_restores_baseline_and_does_not_remove_personal_choices(client,bazarr):
    from app.group_access import apply_access
    uid=allow_user()
    with SessionLocal() as db:
        user=db.get(User,uid);user.bazarr_subtitle_limit=4;user.bazarr_subtitle_languages='["en","fr"]'
        group=PermissionGroup(name='Limited subtitles',policy='{}',access_policy='{"bazarr_subtitles":true,"bazarr_subtitle_limit":1}')
        db.add(group);db.flush();apply_access(db,user,group)
        assert user.bazarr_subtitle_limit==1 and json.loads(user.bazarr_subtitle_languages)==['en','fr']
        apply_access(db,user,None);assert user.bazarr_subtitle_limit==4
        db.rollback()


def test_subtitle_permission_does_not_open_bazarr_interface(client,bazarr):
    allow_user();logout(client);login_user(client)
    assert submit(client,['en']).status_code==303
    assert client.get('/tools/bazarr/app/').status_code in (401,403)
    with SessionLocal() as db:assert json.loads(db.scalar(select(User).where(User.emby_id=='user-1')).tool_access)==[]


def test_subtitle_preferences_migration_preserves_existing_grants_and_config(tmp_path):
    import os,sqlite3,subprocess,sys
    database=tmp_path/'before-preferences.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(database)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0024'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        db.execute("insert into config(key,value) values('bazarr_subtitles_profile','27')")
        db.execute("insert into users(name,admin,active,version,bazarr_subtitles,tool_access) values('Subtitle member',0,1,5,1,'[]')");db.commit()
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        assert db.execute('select version,bazarr_subtitles,tool_access,bazarr_subtitle_limit,bazarr_subtitle_languages,bazarr_subtitle_version from users').fetchone()==(5,1,'[]',3,'[]',0)
        assert db.execute("select value from config where key='bazarr_subtitles_profile'").fetchone()[0]=='27'


def test_fictitious_bazarr_profile_api_is_authenticated_and_persistent(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.mock_bazarr import router
    monkeypatch.setenv('MOCK_DB',str(tmp_path/'fake-bazarr.db'))
    app=FastAPI();app.include_router(router);headers={'X-Api-Key':'demo-bazarr-key'}
    with TestClient(app) as client:
        base='/tools/bazarr/app/api/system/'
        assert client.get(base+'languages/profiles').status_code==401
        rows=client.get(base+'languages/profiles',headers=headers).json();assert rows[0]['profileId']==1
        rows[0]['items'].append({'id':4,'language':'ja','forced':'False','hi':'False'})
        assert client.post(base+'settings',data={'languages-profiles':json.dumps(rows)},headers=headers).status_code==204
    with TestClient(app) as client:assert client.get(base+'languages/profiles',headers=headers).json()==rows


def policy(db,mode='free',days=30):
    main.set_config(db,'bazarr_subtitle_lock_mode',mode)
    main.set_config(db,'bazarr_subtitle_lock_days',str(days))
    main.set_config(db,'bazarr_subtitle_policy_since','0');db.commit()


def test_permanent_lock_blocks_removal_and_replacement_in_forged_posts(client,bazarr):
    uid=allow_user()
    with SessionLocal() as db:policy(db,'permanent')
    logout(client);login_user(client)
    assert submit(client,['en']).status_code==303
    assert submit(client,[]).status_code==409
    assert submit(client,['fr']).status_code==409
    assert submit(client,['en','fr']).status_code==303
    assert submit(client,['en','fr']).status_code==303
    page=client.get('/account').text
    assert 'data-subtitle-locked="true"' in page and 'Locked until an administrator unlocks it.' in page
    with SessionLocal() as db:assert set(bs.language_locks(db,db.get(User,uid)))=={'en','fr'}


def test_timed_lock_expires_and_replacement_starts_a_new_lock(client,bazarr):
    import time
    uid=allow_user()
    with SessionLocal() as db:policy(db,'days',2)
    logout(client);login_user(client);assert submit(client,['en']).status_code==303
    assert submit(client,['fr']).status_code==409
    with SessionLocal() as db:
        user=db.get(User,uid);stamp=json.loads(user.bazarr_subtitle_locks)['en']
        assert 'en' in bs.language_locks(db,user,at=stamp+2*86400-1)
        assert not bs.language_locks(db,user,at=stamp+2*86400)
        user.bazarr_subtitle_locks=json.dumps({'en':int(time.time())-3*86400});db.commit()
    assert submit(client,['fr']).status_code==303
    with SessionLocal() as db:assert 'fr' in bs.language_locks(db,db.get(User,uid))
    assert submit(client,[]).status_code==409


def test_admin_unlock_allows_one_replacement_then_new_language_is_locked(client,bazarr):
    from test_portal import PASSWORD
    uid=allow_user()
    with SessionLocal() as db:policy(db,'permanent')
    logout(client);login_user(client);assert submit(client,['en']).status_code==303
    assert post(client,f'/admin/users/{uid}/subtitle-unlock',{'language':'en'},'/account').status_code==403
    logout(client);post(client,'/login',{'name':'Owner','password':PASSWORD})
    response=post(client,f'/admin/users/{uid}/subtitle-unlock',{'language':'en'},f'/admin/users/{uid}?tab=access')
    assert response.status_code==303,response.text
    with SessionLocal() as db:assert not bs.language_locks(db,db.get(User,uid))
    logout(client);login_user(client);assert submit(client,['fr']).status_code==303
    assert submit(client,[]).status_code==409
    assert len(bazarr.writes)==1


def test_existing_shared_language_is_locked_like_a_new_native_addition(client,bazarr):
    uid=allow_user()
    with SessionLocal() as db:policy(db,'days',30)
    logout(client);login_user(client);assert submit(client,['en']).status_code==303
    assert not bazarr.writes
    with SessionLocal() as db:assert 'en' in bs.language_locks(db,db.get(User,uid))
    assert submit(client,[]).status_code==409


def test_user_card_requires_permission_complete_setup_and_a_valid_remote_profile(client,bazarr):
    uid=allow_user();logout(client);login_user(client)
    assert 'data-subtitle-preferences' in client.get('/account').text
    with SessionLocal() as db:main.set_config(db,'bazarr_subtitles_profile','999');db.commit()
    assert 'data-subtitle-preferences' not in client.get('/account').text
    with SessionLocal() as db:main.set_config(db,'bazarr_subtitles_profile','1');main.set_config(db,'bazarr_subtitles_enabled','false');db.commit()
    assert 'data-subtitle-preferences' not in client.get('/account').text


@pytest.mark.parametrize('mode,days',[('free','30'),('days','90'),('permanent','30')])
def test_admin_configures_replacement_policy(client,bazarr,mode,days):
    result=post(client,'/admin/bazarr/subtitles',{'enabled':'on','profile_id':'1','lock_mode':mode,'lock_days':days},'/admin/integrations')
    assert result.status_code==303,result.text
    with SessionLocal() as db:
        saved=bs.replacement_policy(db);assert saved['mode']==mode and saved['days']==int(days)
    assert not bazarr.writes


def test_invalid_lock_policy_does_not_change_settings(client,bazarr):
    for mode,days in [('invalid','30'),('days','0'),('days','-2'),('days','3651')]:
        assert post(client,'/admin/bazarr/subtitles',{'enabled':'on','profile_id':'1','lock_mode':mode,'lock_days':days},'/admin/integrations').status_code==400
    with SessionLocal() as db:assert bs.replacement_policy(db)['mode']=='free'


def test_lock_migration_preserves_choices_and_initializes_timestamps(tmp_path):
    import os,sqlite3,subprocess,sys
    database=tmp_path/'before-locks.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(database)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0025'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        db.execute('insert into users(name,admin,active,version,bazarr_subtitle_languages) values(?,?,?,?,?)',('Member',0,1,4,'["en","fr"]'));db.commit()
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        version,raw,locks=db.execute('select version,bazarr_subtitle_languages,bazarr_subtitle_locks from users').fetchone()
        assert version==4 and json.loads(raw)==['en','fr']
        assert set(json.loads(locks))=={'en','fr'} and all(type(value) is int and value>0 for value in json.loads(locks).values())
