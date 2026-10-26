import json,re,os,sqlite3,subprocess,sys
from copy import deepcopy
from pathlib import Path
import pytest
from sqlalchemy import select
from app import main,portal,footer,i18n
from app.visual_builder import load,version
from app.db import SessionLocal
from app.models import User,AccessService,Guide,IconAsset
from test_portal import setup,post,logout,login_user
from test_icon_uploads import png


def design(client,page,action,value,revision=0):
    return post(client,'/admin/design/'+page+'/'+action,{'payload':json.dumps(value),'version':revision},'/admin/design/'+page)


def test_login_preview_save_publish_and_conflicts(client):
    setup(client)
    with SessionLocal() as db:value=load(db,'login',True)
    form=next(b for b in value['blocks'] if b['kind']=='login_form')
    form.update(span=4,order=1,style={'surface':'#112233','accent':'#11aaff','button_hover':'#22bbff'})
    value['colors']={'bg':'#030509','gradient':True,'gradient_start':'#09111c','gradient_end':'#010205','angle':160}
    value['blocks'].append({'id':'announcement','kind':'text','region':'main','span':12,'order':50,'title':'Draft announcement','body':'<script>evil()</script><b>Welcome</b>','rich':True})
    assert design(client,'login','preview',value).status_code==200
    with SessionLocal() as db:assert version(db,'login')==0
    assert design(client,'login','save',value).status_code==200
    assert 'Draft announcement' not in client.get('/login').text
    assert design(client,'login','publish',value,1).status_code==200
    assert design(client,'login','save',value,1).status_code==409
    logout(client)
    page=client.get('/login').text
    assert 'Draft announcement' in page and '<b>Welcome</b>' in page and '<script>evil()' not in page
    assert '#09111c' in page and 'name="name"' in page and 'name="password"' in page
    assert '<nav class="admin-navigation"' not in page
    assert login_user(client).status_code==303
    assert client.get('/account').status_code==200


@pytest.mark.parametrize('bad', ['no-form','two-forms','hidden-form','cycle','style','link','private-block'])
def test_signin_page_rejects_inaccessible_or_unsafe_design(client,bad):
    setup(client)
    with SessionLocal() as db:value=load(db,'login',True)
    form=next(b for b in value['blocks'] if b['kind']=='login_form')
    if bad=='no-form':value['blocks'].remove(form)
    if bad=='two-forms':value['blocks'].append({**form,'id':'second-form'})
    if bad=='hidden-form':form['visibility']='admins'
    if bad=='cycle':form['parent']=form['id']
    if bad=='style':form['style']={'bg':'red;url(https://evil.test)'}
    if bad=='link':value['blocks'].append({'id':'button','kind':'button','region':'main','span':12,'order':1,'url':'javascript:alert(1)'})
    if bad=='private-block':value['blocks'].append({'id':'private','kind':'services','region':'main','span':12,'order':1})
    assert design(client,'login','publish',value).status_code==400
    with SessionLocal() as db:assert version(db,'login')==0


def test_nested_columns_uploaded_image_footer_and_public_rendering(client):
    setup(client)
    token=re.search('name="csrf" value="([^"]+)"',client.get('/admin').text)[1]
    r=client.post('/admin/assets',data={'csrf':token},files={'icon_file':('logo.png',png(),'image/png')},headers={'Accept':'application/json'})
    assert r.status_code==200;url=r.json()['url']
    with SessionLocal() as db:value=load(db,'footer',True)
    value['blocks']=[{'id':'columns','kind':'columns','region':'main','span':12,'order':1,'columns':2}, {'id':'image','kind':'image','region':'main','span':12,'order':2,'parent':'columns','slot':0,'url':url,'alt':'Uploaded logo'}, {'id':'copy','kind':'text','region':'main','span':12,'order':3,'parent':'columns','slot':1,'title':'Community','body':'<p><b>Join us</b><img src=x onerror=evil()></p>','rich':True}]
    value['colors']={'bg':'#101820','text':'#eeeeff','align':'center'}
    assert design(client,'footer','save',value).status_code==200
    assert 'Uploaded logo' not in client.get('/forgot').text
    preview=design(client,'footer','preview',value)
    assert preview.status_code==200 and 'Uploaded logo' in preview.text
    assert design(client,'footer','publish',value,1).status_code==200
    html=client.get('/forgot').text
    assert url in html and '<b>Join us</b>' in html and 'onerror' not in html
    assert 'cols-2' in html and '#101820' in html
    with SessionLocal() as db:assert len(footer.load(db)['design']['blocks'])==3


def test_my_account_after_automatic_tools_and_added_applications(client):
    setup(client)
    with SessionLocal() as db:
        main.set_config(db,'radarr_enabled','true');db.commit();value=load(db,'home',True)
    value['blocks'].append({'id':'last-app','kind':'application','region':'main','span':12,'order':100,'service_key':'emby','title':'Another application'})
    assert design(client,'home','publish',value).status_code==200
    html=client.get('/home').text
    assert html.rindex('Another application')>html.rindex('Manage my account')
    assert 'href="/tools/radarr"' not in html  # No explicit grant.
    for key in ('emby','jellyfin','seerr','radarr','sonarr','bazarr'):
        r=client.get('/static/services/'+key+'.png');assert r.status_code==200 and r.content.startswith(b'\x89PNG')


def howto(client,key,action,value,revision=0):
    return post(client,'/admin/visual-howto/'+key+'/'+action,{'payload':json.dumps(value),'version':revision},'/admin/access/'+key)


def test_visual_howto_guide_steps_publish_and_root_guide_mode(client):
    setup(client,empty_journeys=True)
    new=howto(client,'emby','new-guide',{'title':'Connect on iPhone'})
    assert new.status_code==200;gid=new.json()['id']
    article={'title':'Connect on iPhone','summary':'A short guide','device':'mobile','steps':[{'id':'download','title':'Download the app','body':'<b>Open the store</b><script>evil()</script>','rich':True,'link_label':'App Store','link_url':'https://apps.apple.com/','image_url':''},{'id':'connect','title':'Connect','body':'<p>{server_url} · {username}</p>','rich':True,'link_label':'','link_url':'','image_url':''}]}
    path='/admin/visual-guide/'+str(gid)
    result=post(client,path+'/preview',{'payload':json.dumps(article)},'/admin/guides/'+str(gid))
    assert result.status_code==200 and '<b>Open the store</b>' in result.text and '<script>evil' not in result.text
    assert client.get('/help/'+str(gid)).status_code==404
    result=post(client,path+'/publish',{'payload':json.dumps(article),'version':0},'/admin/guides/'+str(gid));assert result.status_code==200
    assert client.get('/help/'+str(gid)).status_code==200
    value={'nodes':[],'mode':'guide','guide_id':gid,'browser_url':'https://media.example.com'}
    with SessionLocal() as db:revision=db.get(AccessService,'emby').access_version
    assert howto(client,'emby','publish',value,revision).status_code==200
    assert '/access/emby/guide/'+str(gid) in client.get('/home').text
    assert client.get('/access/emby',follow_redirects=False).headers['location'].endswith('/guide/'+str(gid))
    assert howto(client,'emby','save',value,revision).status_code==409


def test_visual_howto_nested_tree_reorder_preview_and_invalid_cycle(client):
    setup(client,empty_journeys=True)
    value={'nodes':[{'id':'phone','title':'Phone','kind':'group','parent':'','position':1,'icon':'mobile-screen'}, {'id':'iphone','title':'iPhone','kind':'link','url':'https://apps.apple.com/','parent':'phone','position':2,'icon':'brands:apple'}]}
    preview=howto(client,'emby','preview',{**value,'parent':'phone'})
    assert preview.status_code==200 and 'iPhone' in preview.text
    with SessionLocal() as db:revision=db.get(AccessService,'emby').access_version
    assert howto(client,'emby','publish',value,revision).status_code==200
    assert 'Phone' in client.get('/access/emby').text and 'iPhone' in client.get('/access/emby/phone').text
    value['nodes'][0]['parent']='phone'
    assert howto(client,'emby','save',value,revision+1).status_code==400


def test_visual_routes_are_admin_only_and_require_csrf(client):
    setup(client)
    with SessionLocal() as db:value=load(db,'home',True)
    assert client.post('/admin/design/home/save',data={'payload':json.dumps(value),'version':0,'csrf':'wrong'}).status_code==403
    logout(client);login_user(client)
    for page in ('home','login','footer'):assert client.get('/admin/design/'+page).status_code==403
    assert post(client,'/admin/design/home/preview',{'payload':json.dumps(value)},'/account').status_code==403
    assert post(client,'/admin/visual-howto/emby/preview',{'payload':json.dumps({'nodes':[]})},'/account').status_code==403


def test_upgrade_installs_twenty_disabled_languages_retains_config_and_overrides(tmp_path):
    database=tmp_path/'old.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(database)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0014'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO languages VALUES ('es','My Spanish',1)")
        db.execute("INSERT INTO config VALUES ('portal_published', 'existing-layout')")
        db.execute("INSERT INTO config VALUES ('ui_translation_es_custom', 'Keep me')")
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT count(*) FROM languages').fetchone()[0]==21
        assert db.execute("SELECT name,enabled FROM languages WHERE code='es'").fetchone()==('My Spanish',1)
        assert db.execute("SELECT enabled FROM languages WHERE code='fr'").fetchone()[0]==0
        assert db.execute("SELECT value FROM config WHERE key='ui_translation_es_custom'").fetchone()[0]=='Keep me'
        assert db.execute("SELECT value FROM config WHERE key='portal_published'").fetchone()[0]=='existing-layout'


def test_builtin_catalogs_cover_all_sources_and_preserve_placeholders():
    from collections import Counter
    source=i18n.CATALOGS['en']
    assert len(i18n.CATALOGS)==21
    for locale,entries in i18n.CATALOGS.items():
        assert set(entries)==set(source),locale
        for key,value in entries.items():
            assert value and '__PH_' not in value,(locale,key)
            assert Counter(re.findall(r'\$?\{[^{}]+\}',value))==Counter(re.findall(r'\$?\{[^{}]+\}',source[key])),(locale,key)


def test_studio_csp_enables_local_editor_but_public_pages_have_no_scripts(client):
    setup(client)
    for path in ('/admin/portal','/admin/design/login','/admin/footer','/admin/access/emby'):
        csp=client.get(path).headers['content-security-policy']
        assert "script-src 'self'" in csp and "frame-src 'self'" in csp
    csp=client.get('/home').headers['content-security-policy']
    assert "script-src 'self'" in csp and "style-src 'self' 'unsafe-inline'" in csp


def test_unavailable_tool_card_does_not_hide_member_account_access(client):
    setup(client)
    with SessionLocal() as db:
        value=load(db,'home',True)
    value['blocks'].append({'id':'private-tool','kind':'application','region':'main','span':12,'order':100,'service_key':'radarr','title':'Admin Radarr'})
    assert design(client,'home','publish',value).status_code==200
    logout(client);login_user(client)
    page=client.get('/home').text
    assert 'Admin Radarr' not in page and 'Manage my account' in page


def test_builder_submenu_is_shared_by_all_pages_and_guide_levels(client):
    setup(client)
    guide=howto(client,'emby','new-guide',{'title':'Navigation test'})
    assert guide.status_code==200
    gid=guide.json()['id']
    destinations=['/admin/design/login','/admin/design/home','/admin/access-guides','/admin/design/footer']
    pages=[(destinations[0],destinations[0]),(destinations[1],destinations[1]),(destinations[3],destinations[3]),
           ('/admin/access-guides',destinations[2]),('/admin/design/home/howto/emby',destinations[2]),
           ('/admin/design/home/howto/emby?parent=default_computer',destinations[2]),
           (f'/admin/design/home/guide/{gid}',destinations[2])]
    headings=set()
    for route,active in pages:
        response=client.get(route)
        assert response.status_code==200
        menus=re.findall(r'<nav class="studio-pages".*?</nav>',response.text,re.S)
        assert len(menus)==1,route
        assert re.findall(r'<a href="([^"]+)"',menus[0])==destinations
        assert re.findall(r'<a href="([^"]+)"\s+aria-current="page"',menus[0])==[active]
        assert ('id="studio-preset"' in response.text)==(route=='/admin/design/home')
        heading=re.search(r'<div class="studio-heading">.*?</div></div>',response.text,re.S)[0]
        headings.add(heading)
        assert 'Customize your portal' in heading
        assert 'Administration' in heading and 'Portal builder' in heading
        assert 'Drag a block onto the page. Click anything to edit it.' in heading
    assert len(headings)==1
