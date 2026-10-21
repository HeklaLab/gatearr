import os,sqlite3,subprocess,sys
from fastapi.testclient import TestClient
from sqlalchemy import select
from app import main
from app.db import SessionLocal
from app.models import User,Token,Session,Config
from test_portal import setup,post,logout,login_user,csrf,PASSWORD
from test_onboarding import claim


def ids():
    with SessionLocal() as db:return {u.emby_id:u.id for u in db.scalars(select(User))}


def test_roles_revoke_sessions_and_admin_has_normal_account(client):
    setup(client)
    uid=ids()['user-1']
    with TestClient(main.app) as other:
        login_user(other)
        assert other.get('/account').status_code==200
        assert post(other,f'/admin/users/{uid}/role',{'admin':'on'},'/account').status_code==403
        assert post(client,f'/admin/users/{uid}/role',{'admin':'on'},'/admin').status_code==303
        assert other.get('/account').status_code==401
        assert login_user(other).headers['location']=='/home'
        assert other.get('/account').status_code==200 and other.get('/admin').status_code==200
        assert post(client,f'/admin/users/{uid}/role',{},'/admin').status_code==303
        assert other.get('/admin').status_code==401
        login_user(other)
        assert other.get('/admin').status_code==403
    logout(client)
    assert post(client,'/login',{'name':'Owner','password':PASSWORD}).headers['location']=='/home'
    assert client.get('/account').status_code==200
    assert 'local_admin' not in client.get('/login').text
    with SessionLocal() as db:assert all(u.emby_id and u.password_hash is None for u in db.scalars(select(User)))


def test_last_admin_guard_and_self_demotion(client):
    setup(client)
    rows=ids();owner=rows['admin-1'];member=rows['user-1']
    assert post(client,f'/admin/users/{owner}/role',{},'/admin').status_code==409
    assert post(client,f'/admin/users/{member}/role',{'admin':'on'},'/admin').status_code==303
    assert post(client,f'/admin/users/{owner}/role',{},'/admin').headers['location']=='/login'
    assert client.get('/admin').status_code==401
    post(client,'/login',{'name':'Owner','password':PASSWORD})
    assert client.get('/account').status_code==200 and client.get('/admin').status_code==403


def test_setup_capability_bound_to_browser_and_only_one_first_claim(client):
    assert claim(client).status_code==303
    with TestClient(main.app) as other:
        assert other.get('/setup/admin').status_code==403
        assert post(other,'/setup/admin',{'user_id':'admin-1','password':PASSWORD},'/setup').status_code==403
        assert claim(other).status_code==303
        assert client.get('/setup/admin').status_code==403
        assert post(other,'/setup/admin',{'user_id':'admin-1','password':PASSWORD},'/setup/admin').status_code==303
        assert post(other,'/setup/admin',{'user_id':'user-1','password':'DemoPassword123!'},'/admin/setup/seerr').status_code==403
    with SessionLocal() as db:
        assert len(list(db.scalars(select(User).where(User.admin.is_(True)))))==1


def test_setup_expiry_disabled_and_wrong_identity(client,fake,monkeypatch):
    claim(client)
    fake.disabled=True
    assert post(client,'/setup/admin',{'user_id':'user-1','password':'DemoPassword123!'},'/setup/admin').status_code==401
    fake.disabled=False
    monkeypatch.setattr(fake,'authenticate',lambda *args:{'User':fake.dto()})
    assert post(client,'/setup/admin',{'user_id':'admin-1','password':PASSWORD},'/setup/admin').status_code==401
    with SessionLocal() as db:
        db.query(Session).update({'setup_expires':main.now()-1});db.commit()
    assert client.get('/setup/admin').status_code==403


def test_upgrade_retires_local_credentials_without_promoting_media_admin(tmp_path):
    database=tmp_path/'old.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(database)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0007'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO users (id,name,email,admin,active,version,password_hash) VALUES (1,'Local','local@example.com',1,1,0,'old-hash')")
        db.execute("INSERT INTO users (id,name,emby_id,admin,active,version) VALUES (2,'Media','media-1',0,1,0)")
        db.execute("INSERT INTO config VALUES ('setup_complete','true'),('smtp_password','encrypted-original')")
        db.execute("INSERT INTO sessions VALUES ('old',1,'csrf',9999999999,0)")
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT admin,active,password_hash,email FROM users WHERE id=1').fetchone()==(0,0,None,None)
        assert db.execute('SELECT admin,active FROM users WHERE id=2').fetchone()==(0,1)
        assert db.execute('SELECT count(*) FROM sessions').fetchone()==(0,)
        assert db.execute("SELECT value FROM config WHERE key='setup_complete'").fetchone() is None
        assert db.execute("SELECT value FROM config WHERE key='smtp_password'").fetchone()==('encrypted-original',)


def test_disabled_user_cannot_be_granted_admin_and_setup_token_is_not_a_login(client,fake):
    setup(client)
    fake.disabled=True
    with SessionLocal() as db:main.sync_users(db)
    uid=ids()['user-1']
    assert post(client,f'/admin/users/{uid}/role',{'admin':'on'},'/admin').status_code==400
    logout(client)
    assert post(client,'/login',{'name':'unknown@example.com','password':PASSWORD,'local_admin':'on'}).status_code==401
    assert post(client,'/login',{'name':'Owner','password':'unused' }).status_code==401
    assert client.get('/admin').status_code==401
