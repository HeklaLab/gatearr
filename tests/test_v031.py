"""0.3.1 acceptance: explicit rows/permissions, password enforcement and simpler admin."""
import json,re,os,sqlite3,subprocess,sys
from pathlib import Path
from sqlalchemy import select
from app import main,portal
from app.models import User,Config,Language,MenuItem
from app.db import SessionLocal
from app.security import password_ok
from test_portal import setup,post,logout,login_user,smtp
from test_visual_studio import design


def test_two_application_rows_have_exact_order_without_implicit_account(client):
    setup(client)
    with SessionLocal() as db:
        main.set_config(db,'radarr_enabled','true');main.set_config(db,'sonarr_enabled','true');main.set_config(db,'bazarr_enabled','true')
        for tool in ('radarr','sonarr','bazarr'):
            main.set_config(db,tool+'_url','http://'+tool+':1234')
            main.set_config(db,tool+'_api_key','test-key')
        owner=db.scalar(select(User).where(User.admin.is_(True)));owner.tool_access='["radarr","sonarr","bazarr"]';db.commit()
        value=portal.load(db)
    value['blocks']=[{'id':'first','kind':'applications','region':'main','span':12,'order':10,'columns':2,'applications':['access:emby','radarr']},{'id':'second','kind':'applications','region':'main','span':12,'order':20,'columns':3,'applications':['sonarr','account','bazarr']}]
    assert design(client,'home','publish',value).status_code==200
    html=client.get('/home').text
    assert html.count('class="application-grid"')==2
    assert html.count('Manage my account')==1
    assert html.index('href="/tools/radarr"')<html.index('href="/tools/sonarr"')<html.index('Manage my account')<html.index('href="/tools/bazarr"')
    logout(client);login_user(client)
    html=client.get('/home').text
    assert 'href="/tools/radarr"' not in html and 'Manage my account' in html
    assert client.get('/tools/radarr').status_code==403
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.name=='demo'));user.tool_access='["sonarr"]';db.commit()
    html=client.get('/home').text
    assert 'href="/tools/sonarr"' in html and 'href="/tools/bazarr"' not in html
    assert client.get('/tools/sonarr').status_code==200


def test_admin_needs_explicit_tool_permission_and_app_selection(client):
    setup(client)
    with SessionLocal() as db:
        main.set_config(db,'radarr_enabled','true')
        main.set_config(db,'radarr_url','http://radarr:7878')
        main.set_config(db,'radarr_api_key','test-key')
        db.commit();value=portal.load(db)
    value['blocks']=[{'id':'apps','kind':'applications','region':'main','span':12,'order':10,'columns':1,'applications':['radarr']}]
    assert design(client,'home','publish',value).status_code==200
    assert 'href="/tools/radarr"' not in client.get('/home').text
    assert client.get('/tools/radarr').status_code==403
    # No automatic account card when it was not selected.
    assert 'Manage my account' not in client.get('/home').text


def test_builder_rows_are_full_width_and_login_has_no_applications(client):
    setup(client)
    with SessionLocal() as db:value=portal.load(db)
    block={'id':'apps','kind':'applications','region':'main','span':12,'order':10,'columns':2,'applications':['account']};value['blocks']=[block]
    for change in ({'span':6},{'region':'sidebar'},{'parent':'no-parent'},{'columns':7},{'applications':['account','account']},{'applications':['javascript:evil']}):
        original=block.copy();block.update(change)
        assert design(client,'home','save',value).status_code==400
        block.clear();block.update(original)
    assert design(client,'login','save',value).status_code==400


def test_password_policy_enforced_for_changes_reset_and_clone_before_remote_calls(client,fake,sent):
    setup(client);smtp(client)
    policy={'enabled':'on','minimum':'15','uppercase':'on','lowercase':'on','digit':'on','symbol':'on'}
    assert post(client,'/admin/security',policy,'/admin/security').status_code==303
    with SessionLocal() as db:
        for bad in ('short','lowercaseonlylong','PASSWORDONLYLONG1!','LongPasswordNoDigit!','LongPasswordNoSymbol1'):
            try:password_ok(bad,db)
            except ValueError:pass
            else:raise AssertionError('Weak password accepted')
        password_ok('ValidLongPassword123!',db)
        user=db.scalar(select(User).where(User.name=='demo'));uid=user.id;user.email='demo@example.com';raw=main.issue_token(db,user,'reset');db.commit()
    assert post(client,'/reset',{'token':raw,'password':'short','confirm':'short'},'/forgot').status_code==400
    assert post(client,'/admin/users/'+str(uid)+'/account',{'action':'password','password':'short','confirm':'short'},'/admin').status_code==400
    assert post(client,'/admin/emby/clone',{'name':'New','source_id':'user-1','password':'short'},'/admin').status_code==400
    assert not fake.changes
    logout(client);login_user(client)
    assert post(client,'/account/password',{'current':'DemoPassword123!','password':'short','confirm':'short'},'/account').status_code==400
    assert not fake.changes
    assert 'minlength="15"' in client.get('/account').text


def test_password_policy_disabled_but_bounded_and_admin_only(client):
    setup(client)
    assert post(client,'/admin/security',{'minimum':'0'},'/admin').status_code==400
    assert post(client,'/admin/security',{'minimum':'8'},'/admin').status_code==303
    with SessionLocal() as db:
        password_ok('x',db)
        for value in ('','x'*257):
            try:password_ok(value,db)
            except ValueError:pass
            else:raise AssertionError('Invalid password accepted')
    logout(client);login_user(client)
    assert client.get('/admin/security').status_code==403
    assert post(client,'/admin/security',{'minimum':'2'},'/account').status_code==403


def test_navigation_account_and_compact_languages(client):
    setup(client)
    dashboard=client.get('/admin').text
    assert 'admin-sidebar' in dashboard and 'Applications &amp; API' in dashboard
    page=client.get('/admin/integrations')
    assert page.status_code==200 and "script-src 'self'" in page.headers['content-security-policy']
    assert 'admin-back' not in page.text and 'admin-sidebar' in page.text and 'Translations / Labels' in page.text
    assert 'action="/admin/menu"' in page.text and 'action="/admin/connections/emby"' in page.text
    assert client.get('/admin/services',follow_redirects=False).headers['location']=='/admin/integrations'
    account=client.get('/account').text
    assert 'class="service"' not in account and 'Email address' in account
    users=client.get('/admin/users').text
    assert 'Manage libraries' not in users and 'username-link' in users
    assert '●</span> Seerr' not in users
    with SessionLocal() as db:db.add(Language(code='pt-br',name='Português (Brasil)',enabled=False));db.commit()
    languages=client.get('/admin/translations').text
    assert 'name="code"' not in languages and 'manage-languages' not in languages
    assert 'Interface labels' in languages and 'Created content' in languages
    assert post(client,'/admin/translations/languages',{'language':'pt-br'},'/admin/translations').status_code==303
    with SessionLocal() as db:assert db.get(Language,'pt-br').enabled
    assert 'Português (Brasil)' in client.get('/admin/translations').text
    assert post(client,'/admin/translations/languages',{'language':'not-a-language'},'/admin/translations').status_code==400


def test_howto_created_inside_builder_retains_menu_identity(client):
    setup(client)
    post(client,'/admin/menu',{'label':'Community','url':'https://example.com','position':'30'},'/admin')
    with SessionLocal() as db:item_id=db.scalar(select(MenuItem.id))
    r=post(client,'/admin/design/home/enable-howto/'+str(item_id),{},'/admin/portal')
    assert r.status_code==200 and '/admin/design/home/howto/' in r.json()['url']
    assert client.get(r.json()['url']).status_code==200
    with SessionLocal() as db:
        from app.applications import catalog
        entries=[a for a in catalog(db,editor=True) if a['name']=='Community']
        assert len(entries)==1 and entries[0]['key']=='menu:'+str(item_id)
    assert client.get('/admin/design/home/howto/radarr').status_code==400
    assert post(client,'/admin/visual-howto/radarr/new-guide',{'payload':'{}'},'/admin/portal').status_code==400
    assert client.get('/static/services/seerr.png').content.startswith(b'\x89PNG')
    update=client.get('/admin/updates').text
    assert 'Report an issue' in update and 'Request a feature' in update


def test_upgrade_preserves_implicit_admin_tool_access_as_explicit_grants(tmp_path):
    path=tmp_path/'upgrade.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(path)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0015'],env=env,check=True,capture_output=True)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO users (id,name,admin,active,version,locale,preferences_version,emby_missing,tool_access,theme_preference) VALUES (1,'Owner',1,1,0,'en',0,0,'[\"bazarr\"]','dark')")
        db.execute("INSERT INTO config VALUES ('radarr_enabled','true')")
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True,capture_output=True)
    with sqlite3.connect(path) as db:assert set(json.loads(db.execute('SELECT tool_access FROM users WHERE id=1').fetchone()[0]))=={'bazarr','radarr'}


def test_legacy_rows_preserve_menu_boundaries_and_add_account_once(client):
    setup(client)
    with SessionLocal() as db:
        from app.applications import normalize
        public=MenuItem(label='Public',url='https://public.example.com',position=1,menu_key='main');private=MenuItem(label='Private',url='https://private.example.com',position=2,menu_key='private')
        db.add_all([public,private]);db.commit()
        legacy={'blocks':[{'id':'one','kind':'services','order':1,'span':12,'region':'main','menu_key':'main','include_emby':True},{'id':'two','kind':'services','order':2,'span':12,'region':'main','menu_key':'private','include_emby':False}]}
        rows=normalize(legacy,db)['blocks']
        assert 'menu:'+str(private.id) not in rows[0]['applications']
        assert 'menu:'+str(public.id) not in rows[1]['applications']
        assert 'account' not in rows[0]['applications'] and rows[1]['applications'].count('account')==1
