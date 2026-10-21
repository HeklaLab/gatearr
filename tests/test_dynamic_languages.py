import json,os,sqlite3,subprocess,sys,hashlib
from sqlalchemy import select
from app import i18n,main,portal,access
from app.db import SessionLocal
from app.models import User,Language,ContentTranslation,Guide,MenuItem,Config,AccessService
from app.content_catalog import sources
from app.mailer import compose
from test_portal import setup,post,logout,login_user

def language(client,code='es',enabled=True):
    return post(client,'/admin/translations/languages',{'code':code,'name':'Español' if code=='es' else code,**({'enabled':'on'} if enabled else {})},'/admin/translations')

def ui(client,key,value,code='es'):
    return post(client,'/admin/translations',{'edit_locale':code,'key':key,'value':value},'/admin/translations')

def translate(client,key,value,code='es',stamp=None):
    with SessionLocal() as db:entry=next(item for item in sources(db) if item['key']==key)
    return post(client,'/admin/translations',{'edit_locale':code,'scope':'email' if key.startswith('mail:') else 'content','key':key,'source_hash':stamp or i18n.source_hash(entry['source']),'value':value},'/admin/translations')

def test_english_is_default_and_dynamic_languages_can_be_prepared_and_enabled(client):
    assert '<html lang="en">' in client.get('/setup').text
    setup(client)
    assert language(client,enabled=False).status_code==303
    assert 'Español' in client.get('/admin/translations?edit_locale=es').text
    assert ui(client,'My account','Mi cuenta').status_code==303
    assert post(client,'/language',{'locale':'es','next':'/account'},'/account').status_code==400
    assert post(client,'/admin/translations/languages/es',{'name':'Español','enabled':'on'},'/admin/translations').status_code==303
    assert post(client,'/language',{'locale':'es','next':'/account'},'/account').status_code==303
    page=client.get('/account').text
    assert '<html lang="es">' in page and 'Mi cuenta' in page and i18n.translate('New password','es') in page
    assert language(client,'ES').status_code==409
    assert language(client,'../../x').status_code==400
    assert post(client,'/admin/translations/languages/en',{'name':'English'},'/admin/translations').status_code==303
    assert post(client,'/admin/translations/languages/es',{'name':'Español'},'/admin/translations').status_code==303
    assert '<html lang="fr">' in client.get('/home').text


def test_source_editors_have_one_field_per_element_and_mail_language_is_dynamic(client):
    setup(client);language(client)
    for path in ('/admin','/admin/portal','/admin/guides','/admin/mail-editor'):
        page=client.get(path).text
        for field in ('title_fr','title_en','body_fr','body_en','login_text_en','label_en'):
            assert 'name="'+field+'"' not in page
    assert 'Español' in client.get('/home').text
    assert post(client,'/account/language',{'locale':'es'},'/account').status_code==303
    post(client,'/language',{'locale':'fr','next':'/account'},'/account')
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin==True))
        assert owner.locale=='fr'


def test_content_translations_preserve_placeholders_and_draft_boundaries(client):
    setup(client);language(client)
    assert post(client,'/admin/portal/block',{'version':0,'kind':'text','region':'main','order':5,'span':12,'title':'Welcome member','body':'Hello {username}'},'/admin/portal').status_code==303
    with SessionLocal() as db:
        block=next(item for item in portal.load(db,True)['blocks'] if item['title']=='Welcome member');ident=block['id']
        assert not any(key.endswith(('_fr','_en')) for key in block)
    key='block:'+ident+':title'
    assert translate(client,key,'Bienvenido').status_code==303
    assert translate(client,'block:'+ident+':body','Hola').status_code==400
    assert translate(client,'block:'+ident+':body','Hola {username}').status_code==303
    assert post(client,'/admin/portal/publish',{'version':1},'/admin/portal').status_code==303
    post(client,'/language',{'locale':'es','next':'/home'},'/home')
    assert 'Bienvenido' in client.get('/home').text and 'Hola Owner' in client.get('/home').text
    assert post(client,'/admin/portal/block',{'version':2,'block_id':ident,'kind':'text','region':'main','order':5,'span':12,'title':'Updated source','body':'Hello {username}'},'/admin/portal').status_code==303
    assert 'Bienvenido' in client.get('/home').text
    page=client.get('/admin/translations?scope=content&edit_locale=es&q=Updated').text
    assert i18n.translate('Translation needs review','es') in page
    assert translate(client,key,'Old translation',stamp=i18n.source_hash('deleted source')).status_code==409
    assert post(client,'/admin/portal/publish',{'version':3},'/admin/portal').status_code==303
    assert 'Updated source' in client.get('/home').text
    block_html=client.get('/home').text.split('data-block-id="'+ident+'"')[1].split('</section>')[0]
    assert 'Bienvenido' not in block_html


def test_guides_journeys_menus_and_branding_use_the_created_language(client):
    setup(client,empty_journeys=True);language(client)
    assert post(client,'/admin/menu',{'label':'Requests','url':'https://requests.test','icon':'link','position':'1'},'/admin').status_code==303
    with SessionLocal() as db:mid=db.scalar(select(MenuItem.id))
    assert translate(client,'menu:'+str(mid)+':label','Solicitudes').status_code==303
    assert translate(client,'branding:login_text','Tus servicios en un solo lugar').status_code==303
    assert translate(client,'branding:app_name','Puerta').status_code==303
    response=post(client,'/admin/guides/create',{'service_key':'emby','title':'Mobile setup'},'/admin/guides');gid=int(response.headers['location'].split('/')[-1])
    assert post(client,f'/admin/guides/{gid}',{'version':0,'action':'publish','title':'Mobile setup','step_count':1,'step_0_id':'install','step_0_title':'Connect','step_0_body':'Server {server_host}:{server_port}, user {username}','step_0_link_url':'https://example.com/app','step_0_link_label':'Download'},f'/admin/guides/{gid}').status_code==303
    assert translate(client,f'guide:{gid}:title','Configurar el móvil').status_code==303
    assert translate(client,f'guide:{gid}:install:body','Servidor {server_host}:{server_port}, usuario {username}').status_code==303
    assert post(client,'/admin/guides/service',{'key':'emby','name':'Emby','browser_url':'https://media.example','server_url':'https://media.example:8920'},'/admin/guides').status_code==303
    assert post(client,'/admin/access/emby',{'version':0,'kind':'guide','title':'Phone','guide_id':gid},'/admin/access/emby').status_code==303
    with SessionLocal() as db:ident=access.load(db.get(AccessService,'emby'),True)[0]['id']
    assert translate(client,'journey:emby:'+ident+':title','Teléfono').status_code==303
    assert post(client,'/admin/access/emby',{'version':1,'action':'publish'},'/admin/access/emby').status_code==303
    post(client,'/language',{'locale':'es','next':'/home'},'/home')
    assert 'Solicitudes' in client.get('/home').text
    assert 'Puerta' in client.get('/home').text
    assert 'name="app_name" value="Gatearr"' in client.get('/admin/branding').text
    assert 'Teléfono' in client.get('/access/emby').text
    page=client.get(f'/access/emby/guide/{gid}').text
    assert 'Configurar el móvil' in page and 'Servidor media.example:8920, usuario Owner' in page
    logout(client)
    assert 'Tus servicios en un solo lugar' in client.get('/login').text


def test_new_language_email_templates_and_disabled_language_fallback(client):
    setup(client);language(client)
    assert translate(client,'mail:invite:subject','${app_name} — bienvenido').status_code==303
    html='<h2>Hola ${username}</h2><a href="${link}">Confirmar</a><img src="https://example.com/banner.png">'
    assert post(client,'/admin/mail-editor',{'mail_locale':'es','purpose':'invite','subject':'${app_name} — bienvenido','html':html},'/admin/mail-editor').status_code==303
    with SessionLocal() as db:
        message=compose(db,'member@example.com','invite',{'app_name':'Gatearr','username':'Alex','link':'https://portal.test/verify-email?token=test','minutes':'30','_locale':'es'})
        assert message['Subject']=='Gatearr — bienvenido'
        assert '<h2>Hola Alex</h2>' in message.get_body(preferencelist=('html',)).get_content()
    post(client,'/admin/translations/languages/es',{'name':'Español'},'/admin/translations')
    with SessionLocal() as db:
        message=compose(db,'member@example.com','invite',{'app_name':'Gatearr','username':'Alex','link':'https://portal.test/link','minutes':'30','_locale':'es'})
        assert message['Subject']=='Gatearr — welcome!'


def test_language_management_and_all_translations_are_admin_only(client):
    setup(client);logout(client);login_user(client)
    assert post(client,'/admin/translations/languages',{'code':'de','name':'Deutsch'},'/account').status_code==403
    assert client.get('/admin/translations').status_code==403
    assert post(client,'/admin/translations',{'edit_locale':'en','key':'My account','value':'Wrong'},'/account').status_code==403


def test_migration_preserves_auth_and_moves_legacy_content_to_translation_rows(tmp_path):
    database=tmp_path/'legacy.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(database)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0006'],env=env,check=True,capture_output=True)
    layout={'nav_position':'top','sidebar_position':'left','theme':{},'blocks':[{'id':'custom','kind':'text','region':'main','span':12,'order':1,'title_fr':'Bonjour','title_en':'Hello','body_fr':'Bienvenue {username}','body_en':'Welcome {username}'}]}
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO users (id,name,admin,active,version,locale,mail_locale,password_hash) VALUES (1,'Admin',1,1,7,'fr','en','protected-hash')")
        for key,value in {'portal_draft':json.dumps(layout),'portal_published':json.dumps(layout),'smtp_password':'encrypted-smtp','login_text':'Mon accueil français','reset_subject_fr':'Sujet français','reset_subject_en':'English subject'}.items():db.execute('INSERT INTO config VALUES (?,?)',(key,value))
        db.execute("INSERT INTO menu_items (label,label_en,url,icon,position,new_tab,menu_key) VALUES ('Demandes','Requests','https://example.com','x',1,1,'main')")
    subprocess.run([sys.executable,'-m','alembic','upgrade','0007'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT password_hash,version,locale,mail_locale FROM users').fetchone()==('protected-hash',7,'fr','en')
        assert db.execute("SELECT value FROM config WHERE key='smtp_password'").fetchone()[0]=='encrypted-smtp'
        block=json.loads(db.execute("SELECT value FROM config WHERE key='portal_published'").fetchone()[0])['blocks'][0]
        assert block['title']=='Hello' and 'title_fr' not in block
        assert db.execute("SELECT value FROM content_translations WHERE locale='fr' AND resource='block:custom:title'").fetchone()[0]=='Bonjour'
        assert db.execute('SELECT label,label_en FROM menu_items').fetchone()==('Requests',None)
        assert db.execute("SELECT value FROM config WHERE key='reset_subject'").fetchone()[0]=='English subject'
    subprocess.run([sys.executable,'-m','alembic','downgrade','0006'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        assert json.loads(db.execute("SELECT value FROM config WHERE key='portal_published'").fetchone()[0])==layout
        assert db.execute('SELECT label,label_en FROM menu_items').fetchone()==('Demandes','Requests')
