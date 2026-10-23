from test_portal import reviewed_post
import json,time
from contextlib import contextmanager
import httpx,pytest
from sqlalchemy import select
from app import main,seerr_permissions as sp
from app.models import User,PermissionGroup,GroupMember,SeerrPolicyState,Token,Session
from app.db import SessionLocal
from app.security import digest
from test_portal import setup,post,login_user,logout
from test_permissions_bridge import policy_api

@pytest.fixture(autouse=True)
def user_page_api(fake,monkeypatch):
    from app import admin_features
    monkeypatch.setattr(fake,"libraries",lambda:[],raising=False)
    monkeypatch.setattr(fake,"copy_options",lambda:[],raising=False)
    monkeypatch.setattr(admin_features,"emby",fake)



def test_deactivation_blocks_login_recovery_and_survives_sync(client,fake):
    setup(client)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'));uid=user.id;version=user.version
        user.email='demo@example.com';db.commit()
        raw=main.issue_token(db,user,'reset')
    path=f'/admin/users/{uid}'
    response=post(client,path+'/activation',{'action':'disable','confirm':'on','version':version},path)
    assert response.status_code==303
    first=fake.password_value
    assert first!='DemoPassword123!' and len(first)>100 and first not in client.get(path).text
    with SessionLocal() as db:
        user=db.get(User,uid)
        assert user.portal_disabled and not user.active
        assert db.get(Token,digest(raw)).used
        main.sync_users(db);assert not user.active
        with pytest.raises(Exception):main.issue_token(db,user,'reset')
        version=user.version
    assert post(client,path+'/activation',{'action':'enable','confirm':'on','version':version},path).status_code==303
    with SessionLocal() as db:
        user=db.get(User,uid);assert user.active and not user.portal_disabled
        assert main.issue_token(db,user,'reset');version=user.version
    # A second deactivation rotates again, rather than reusing an old success marker.
    assert post(client,path+'/activation',{'action':'disable','confirm':'on','version':version},path).status_code==303
    assert fake.password_value!=first


def test_partial_disable_is_visible_and_cannot_reactivate(client,fake,monkeypatch):
    setup(client)
    with SessionLocal() as db:user=db.scalar(select(User).where(User.emby_id=='user-1'));uid=user.id;v=user.version
    def fail(*a,**k):raise RuntimeError('remote credential never print')
    monkeypatch.setattr(fake,'password',fail);path=f'/admin/users/{uid}'
    assert post(client,path+'/activation',{'action':'disable','confirm':'on','version':v},path).status_code==303
    page=client.get(path).text
    assert 'retry required' in page and 'remote credential never print' not in page
    with SessionLocal() as db:v=db.get(User,uid).version;assert not db.get(User,uid).active
    assert post(client,path+'/activation',{'action':'enable','confirm':'on','version':v},path).status_code==409


def test_cannot_disable_self_or_skip_confirmation(client):
    setup(client)
    with SessionLocal() as db:user=db.scalar(select(User).where(User.admin.is_(True)));uid=user.id;v=user.version
    path=f'/admin/users/{uid}'
    assert post(client,path+'/activation',{'action':'disable','confirm':'on','version':v},path).status_code==409
    assert post(client,path+'/activation',{'action':'disable','version':v},path).status_code==400


def test_single_group_locks_individual_rights_and_restores_access(client,policy_api,monkeypatch):
    uid,store,writes,api=policy_api
    path=post(client,'/admin/groups',{'name':'Family'},'/admin/groups').headers['location']
    @contextmanager
    def native_seerr(db,user):yield None,2
    monkeypatch.setattr(sp,'configured',lambda db:True)
    monkeypatch.setattr(sp,'connection',native_seerr)
    monkeypatch.setattr(sp,'read_permissions',lambda c,rid:32)
    from app import seerr_quotas
    monkeypatch.setattr(seerr_quotas,'read',lambda c,rid:({},dict.fromkeys(seerr_quotas.FIELDS,None)))
    data={'version':0,'members':[uid],'manage_tools':'on','tools':['radarr'],'manage_seerr_access':'on','manage_seerr_permissions':'on','seerr_permission':['32','262144'],'library_mode':'selected','libraries':['11111111111111111111111111111111']}
    assert reviewed_post(client,path,data,path).status_code==303
    with SessionLocal() as db:
        assert json.loads(db.get(User,uid).tool_access)==['radarr']
        assert db.get(SeerrPolicyState,uid).desired==32+262144
    assert post(client,f'/admin/users/{uid}/role',{'admin':'on'},f'/admin/users/{uid}?tab=access').status_code==409
    assert post(client,'/admin/emby/libraries',{'id':uid,'access_mode':'all'},f'/admin/users/{uid}?tab=emby').status_code==409
    other=post(client,'/admin/groups',{'name':'Other'},'/admin/groups').headers['location']
    assert post(client,other,{'version':0,'members':[uid]},other).status_code==409
    assert post(client,f'/admin/users/{uid}/group',{'group_id':''},f'/admin/users/{uid}?tab=access').status_code==303
    with SessionLocal() as db:
        assert db.scalar(select(GroupMember).where(GroupMember.user_id==uid)) is None
        assert json.loads(db.get(User,uid).tool_access)==[]

@pytest.fixture
def seerr_api(client,monkeypatch):
    setup(client);native={'permissions':32};calls=[]
    @contextmanager
    def connection(db,user):
        def handle(request):
            calls.append(request)
            path=request.url.path
            if path.endswith('/permissions'):
                if request.method=='POST':native.update(json.loads(request.content))
                return httpx.Response(200,json=native)
            if path.endswith('/quota'):return httpx.Response(200,json={'movie':{'limit':5,'remaining':3},'tv':{'limit':0,'remaining':None}})
            if path.endswith('/request'):return httpx.Response(200,json={'pageInfo':{'results':2}})
            return httpx.Response(404)
        with httpx.Client(base_url='http://seerr/',transport=httpx.MockTransport(handle)) as c:yield c,2
    monkeypatch.setattr(sp,'connection',connection);monkeypatch.setattr(sp,'configured',lambda db:True)
    with SessionLocal() as db:uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
    return uid,native,calls


def test_seerr_permission_read_write_verify_and_conflict(client,seerr_api):
    uid,native,calls=seerr_api;path=f'/admin/users/{uid}'
    with SessionLocal() as db:row=sp.inspect_user(db,db.get(User,uid));version=row.version
    response=post(client,path+'/seerr',{'version':version,'seerr_access':'on','seerr_permission':['32','262144']},path+'?tab=seerr')
    assert response.status_code==303 and native['permissions']==262176
    with SessionLocal() as db:
        row=db.get(SeerrPolicyState,uid);assert row.observed==row.desired and not row.pending
    assert post(client,path+'/seerr',{'version':version,'seerr_permission':['32']},path).status_code==409
    native['permissions']=512
    with SessionLocal() as db:row=sp.inspect_user(db,db.get(User,uid));assert row.observed!=row.desired


def test_seerr_statistics_scope_cache_and_missing_values(client,seerr_api):
    uid,native,calls=seerr_api
    with SessionLocal() as db:
        user=db.get(User,uid);member=sp.summary(db,user)
        assert member==[('Movies left',3),('Seasons left','∞'),('Approved',2),('Available',2)]
        requests=[r for r in calls if r.url.path.endswith('/request')]
        assert all(r.url.params.get('requestedBy')=='2' for r in requests)
        count=len(calls);assert sp.summary(db,user)==[list(x) for x in member];assert len(calls)==count
        user.admin=True;sp.summary(db,user)
        assert calls[-1].url.params.get('requestedBy') is None
        user.admin=False
        main.set_config(db,'seerr_access_'+str(uid),'false');db.commit()
        assert sp.summary(db,user) is None


def test_applications_are_consolidated_and_theme_preview_is_local(client):
    setup(client)
    text=client.get('/admin/integrations').text
    assert 'connection-summary' not in text
    assert text.count('action="/admin/connections/emby"')==1
    assert text.count('name="key" value="emby"')==1
    theme=client.get('/admin/branding/themes')
    assert 'theme-preview.js' in theme.text and "script-src 'self'" in theme.headers['content-security-policy']
    assert '<h2>Dark</h2>' in theme.text and '<h2>Light</h2>' in theme.text


def test_french_setup_is_default_reference_and_english_can_be_disabled(client):
    from app import i18n
    from app.models import Language
    response=post(client,'/setup',{'app_name':'Gatearr','public_url':'http://testserver','media_server':'emby','url':'http://emby.test/emby','api_key':'test-api-key','default_locale':'fr'},'/setup')
    assert response.status_code==303
    assert '<html lang="fr"' in client.get('/setup/admin').text
    assert post(client,'/setup/admin',{'user_id':'admin-1','password':'AdminPassword123!'},'/setup/admin').status_code==303
    for step in ('seerr','tools','smtp'):assert post(client,'/admin/setup/'+step,{'action':'skip'},'/admin/setup/'+step).status_code==303
    assert post(client,'/admin/setup/finish',{},'/admin/setup/finish').status_code==303
    with SessionLocal() as db:
        assert i18n.languages(db)=={'en':'English','fr':'Français'}
        assert i18n.default_language(db)=='fr'
        assert db.scalar(select(User).where(User.admin.is_(True))).locale=='fr'
    assert 'language-switch' in client.get('/home').text
    assert post(client,'/admin/translations/languages/en',{'name':'English'},'/admin/translations').status_code==303
    assert 'language-switch' not in client.get('/home').text
    assert post(client,'/admin/translations/languages/fr',{'name':'Français'},'/admin/translations').status_code==400
    assert post(client,'/admin/translations/languages',{'language':'en','enabled':'on'},'/admin/translations').status_code==303
    assert post(client,'/admin/translations/languages/en',{'name':'English'},'/admin/translations').status_code==303
    with SessionLocal() as db:assert i18n.languages(db)=={'fr':'Français'}
    page=client.get('/admin/translations?edit_locale=fr&q=Sign%20in').text
    assert 'Français' in page and 'English source' not in page


def test_disabling_default_selects_active_fallback_and_reassigns_user_languages(client):
    from app import i18n
    setup(client)
    assert post(client,'/admin/translations/languages/fr',{'name':'Français','enabled':'on','default':'on'},'/admin/translations').status_code==303
    with SessionLocal() as db:assert i18n.default_language(db)=='fr'
    assert post(client,'/admin/translations/languages/fr',{'name':'Français'},'/admin/translations').status_code==303
    with SessionLocal() as db:assert i18n.default_language(db)=='en'


def test_email_languages_remain_independent_when_french_is_reference(client):
    from app.mailer import mail_template
    setup(client)
    assert post(client,'/admin/translations/languages/fr',{'name':'Français','enabled':'on','default':'on'},'/admin/translations').status_code==303
    for code,subject in [('fr','Bonjour ${username}'),('en','Hello ${username}')]:
        assert post(client,'/admin/mail-editor',{'purpose':'invite','mail_locale':code,'subject':subject,'html':'<p>${username}</p><a href="${link}">Go</a>'},'/admin/mail-editor').status_code==303
    with SessionLocal() as db:
        assert mail_template(db,'invite','subject','fr')=='Bonjour ${username}'
        assert mail_template(db,'invite','subject','en')=='Hello ${username}'


def test_upgrade_multi_group_preserves_effective_rights_and_unique_ownership(tmp_path):
    import os,sys,subprocess,sqlite3
    database=tmp_path/'multi.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(database)}
    def upgrade(revision):return subprocess.run([sys.executable,'-m','alembic','upgrade',revision],env=env,capture_output=True,text=True)
    assert upgrade('0016').returncode==0
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO users(id,emby_id,name,admin,active,version,preferences_version,emby_missing,locale) VALUES (1,'remote-1','Member',0,1,0,0,0,'en')")
        db.execute("INSERT INTO permission_groups(id,name,policy,version) VALUES (1,'A','{}',0),(2,'B','{}',0)")
        db.execute('INSERT INTO group_members VALUES (1,1),(2,1)')
    # Refuse ambiguous migration before modifying the schema; a retry remains possible.
    assert upgrade('head').returncode!=0
    effective={'EnableAllFolders':False,'EnabledFolders':['movies'],'SimultaneousStreamLimit':2}
    with sqlite3.connect(database) as db:
        assert 'portal_disabled' not in {row[1] for row in db.execute('PRAGMA table_info(users)')}
        db.execute("INSERT INTO policy_states(user_id,baseline,overrides,desired,observed,confirmed,version,pending,error,checked_at) VALUES(1,'{}','{}',:value,:value,:value,0,0,'',0)",{'value':json.dumps(effective)})
    result=upgrade('head');assert result.returncode==0,result.stderr
    with sqlite3.connect(database) as db:
        gid,=db.execute('SELECT group_id FROM group_members WHERE user_id=1').fetchone()
        policy,=db.execute('SELECT policy FROM permission_groups WHERE id=?',(gid,)).fetchone()
        assert json.loads(policy)==effective and gid not in (1,2)
        with pytest.raises(sqlite3.IntegrityError):db.execute('INSERT INTO group_members VALUES (1,1)')
