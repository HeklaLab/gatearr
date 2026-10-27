import json,random,struct,zlib,re
from sqlalchemy import select
from app import main,widgets
from app.db import SessionLocal
from app.models import Config,IconAsset,User,AccessService,MenuItem
from app.icons import MAX_BYTES
from app.security import encrypt
from app.image_sources import local_path
from app.rich_mail import clean
from test_icon_uploads import chunk,png
from test_portal import setup,csrf,post

def test_five_megabyte_limit_is_enforced_in_file_and_form_parser(client):
    setup(client)
    raw=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1024,768,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\0'+random.Random(i).randbytes(4096) for i in range(768))))+chunk(b'IEND',b'')
    assert 2*1024*1024<len(raw)<MAX_BYTES==5*1024*1024
    response=client.post('/admin/assets',data={'csrf':csrf(client,'/admin')},files={'icon_file':('large.png',raw,'image/png')},headers={'Accept':'application/json'})
    assert response.status_code==200
    assert client.get(response.json()['url']).content==raw
    rejected=client.post('/admin/assets',data={'csrf':csrf(client,'/admin')},files={'icon_file':('too-big.png',b'x'*(MAX_BYTES+1),'image/png')})
    assert rejected.status_code in (400,413)

def test_remote_images_are_rejected_or_removed_across_editors(client):
    setup(client)
    assert post(client,'/admin/settings',{'app_name':'Family','login_text':'Welcome','public_url':'http://testserver','logo_url':'https://example.com/logo.png'},'/admin/branding').status_code==400
    page=client.get('/admin/branding');assert 'name="logo_url"' not in page.text
    assert 'example.com' not in clean('<img src="https://example.com/a.png"><a href="https://example.org">Link</a>')
    assert 'https://example.org' in clean('<a href="https://example.org">Link</a>')
    assert local_path('https://evil.example/media/icons/'+'a'*64+'.png') is None
    assert local_path('http://testserver/static/gatearr-logo.png')=='/static/gatearr-logo.png'
    page=client.get('/admin/design/home').text
    boot=json.loads(re.search(r'<script[^>]*id="studio-data"[^>]*>(.*?)</script>',page,re.S)[1])
    layout=boot['layout'];layout['blocks']=[{'id':'image','kind':'image','region':'main','span':12,'order':10,'url':'https://example.com/image.png'}]
    assert post(client,'/admin/design/home/save',{'payload':json.dumps(layout),'version':boot['version']},'/admin/design/home').status_code==400

def test_builder_logos_and_disabled_dependencies_follow_media_server(client,monkeypatch):
    setup(client)
    import app.connection_health as health
    monkeypatch.setattr(health,'checks',lambda db:{'emby':{'state':'connected'},'seerr':{'state':'unconfigured'},'tracearr':{'state':'error'}})
    with SessionLocal() as db:
        main.set_config(db,'media_server','jellyfin');db.commit()
        data=widgets.builder_data(db)
        assert set(data['types'])=={'widget_tracearr','widget_library'}
        assert data['icons']['widget_media']=='/static/services/jellyfin.png'
        assert data['icons']['widget_seerr']=='/static/services/seerr.png'
        assert data['icons']['widget_tracearr']=='/static/services/tracearr.png'
        assert data['enabled']['widget_media'] and not data['enabled']['widget_seerr'] and not data['enabled']['widget_tracearr']
        from app.service_assets import service_icon
        db.get(AccessService,'emby').icon='link';db.flush()
        assert service_icon(db,'emby','jellyfin')=='/static/services/jellyfin.png'
        db.add(MenuItem(label='Emby',url='http://media',access_service='emby',icon='link',icon_url='/static/services/emby.png',position=1));db.flush()
        from app.applications import catalog
        assert next(a for a in catalog(db,editor=True) if a['key']=='access:emby')['image']=='/static/services/jellyfin.png'

def test_legacy_tracearr_mail_edit_cannot_bypass_dependency(client):
    setup(client)
    assert post(client,'/admin/mail-templates',{'new_season_subject':'New season','mail_locale':'en','reset_subject':'Reset','reset_body':'${link}','verify_subject':'Verify','verify_body':'${link}'},'/admin/emails').status_code==409
    assert '/admin/mail-editor?purpose=new_season' not in client.get('/admin/translations?scope=email').text
    with SessionLocal() as db:
        main.set_config(db,'tracearr_enabled','true');main.set_config(db,'tracearr_url','http://tracearr');main.set_config(db,'tracearr_api_key',encrypt('key'));db.commit()
    assert '/admin/mail-editor?purpose=new_season' in client.get('/admin/translations?scope=email').text

def test_preset_logos_follow_publication_and_keep_custom_uploads(client):
    from app import themes
    setup(client)
    # Applying a draft updates its editor, without changing the public identity.
    assert post(client,'/admin/branding/themes',{'version':0,'preset':'electric-lime'},'/admin/branding/themes').status_code==303
    assert 'src="'+themes.LOGOS['electric-lime']+'"' in client.get('/admin/branding/themes').text
    assert 'src="'+themes.LOGOS['boreal']+'"' in client.get('/home').text
    assert post(client,'/admin/branding/themes',{'version':1,'action':'publish','mode':'user'},'/admin/branding/themes').status_code==303
    for path in ['/home','/account','/admin/branding']:
        assert 'src="'+themes.LOGOS['electric-lime']+'"' in client.get(path).text
    css=client.get('/theme.css').text
    assert themes.LOGOS['electric-lime'] in css
    assert 'brightness(0) invert(1)' in css and 'prefers-color-scheme:dark' in css
    upload=client.post('/admin/settings',data={'csrf':csrf(client,'/admin/branding'),'app_name':'Gatearr','login_text':'Welcome','public_url':'http://testserver'},files={'icon_file':('brand.png',png(),'image/png')},follow_redirects=False)
    assert upload.status_code==303
    with SessionLocal() as db:custom=main.config(db,'logo_url')
    assert custom.startswith('/media/icons/')
    assert post(client,'/admin/branding/themes',{'version':2,'preset':'neon-rose','action':'publish'},'/admin/branding/themes').status_code==303
    page=client.get('/home').text
    assert 'class="custom-logo-dark" src="'+custom+'"' in page
    assert 'data-default-brand-logo' not in page
    assert themes.LOGOS['neon-rose'] in client.get('/theme.css').text
    with SessionLocal() as db:assert main.config(db,'logo_url')==custom


def test_bundled_preset_logo_allowlist_is_exact(client):
    from app import themes
    setup(client)
    for path in themes.LOGOS.values():
        assert local_path(path)==path
        assert client.get(path).headers['content-type']=='image/png'
    assert local_path('/static/branding-variants/other.png') is None
    assert local_path('/static/branding-variants/generation-prompts.txt') is None


def test_custom_logos_for_both_themes_and_fallback(client):
    setup(client)
    data={'csrf':csrf(client,'/admin/branding'),'app_name':'Family','public_url':'http://testserver'}
    images={'icon_file':('dark.png',png(2,2),'image/png'),'icon_file_light':('light.png',png(3,3),'image/png')}
    result=client.post('/admin/settings',data=data,files=images,follow_redirects=False)
    assert result.status_code==303, result.text
    with SessionLocal() as db:
        dark=main.config(db,'logo_url');light=main.config(db,'logo_url_light')
        assert dark and light and dark!=light
    for path in ('/home','/admin/branding','/login'):
        page=client.get(path).text
        assert dark in page and light in page
    css=client.get('/theme.css').text
    assert '--custom-logo-dark-display:block' in css
    response=post(client,'/admin/settings',{'app_name':'Family','public_url':'http://testserver','remove_logo_light':'on'},'/admin/branding')
    assert response.status_code==303
    with SessionLocal() as db:assert main.config(db,'logo_url')==dark and not main.config(db,'logo_url_light')
    page=client.get('/home').text
    assert 'class="custom-logo-light" src="'+dark+'"' in page


def test_custom_logo_legacy_and_light_only_fallback(client):
    setup(client)
    data={'csrf':csrf(client,'/admin/branding'),'app_name':'Family','public_url':'http://testserver'}
    result=client.post('/admin/settings',data=data,files={'icon_file_light':('light.png',png(),'image/png')},follow_redirects=False)
    assert result.status_code==303
    with SessionLocal() as db:
        assert not main.config(db,'logo_url')
        light=main.config(db,'logo_url_light')
    page=client.get('/home').text
    assert 'class="custom-logo-dark" src="'+light+'"' in page
    assert 'class="custom-logo-light" src="'+light+'"' in page
