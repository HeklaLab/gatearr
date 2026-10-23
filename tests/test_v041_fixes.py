"""0.4.1 protects configuration boundaries while improving the admin workflows."""
import json
import httpx
from sqlalchemy import select
from app import main, i18n, tools_proxy
from app.db import SessionLocal
from app.models import Config, User, Language
from app.security import encrypt
from test_portal import setup, post, logout, login_user


def test_connection_probe_uses_unsaved_values_without_persisting(client,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        main.set_config(db,'radarr_url','http://old.private:7878')
        main.set_config(db,'radarr_api_key',encrypt('saved-key'));db.commit()
    observed=[]
    def probe(service,values):
        observed.append((service,values.copy()));values['diagnostics']={'api_valid':True};return 'connected','Verified'
    monkeypatch.setattr('app.connection_health.probe',probe)
    result=post(client,'/admin/connections/test',{'service':'radarr','url':'http://new.private:7878','api_key':'fresh-key'},'/admin/integrations')
    assert result.status_code==200 and result.json()['state']=='connected'
    assert observed[0][1]['url']=='http://new.private:7878' and observed[0][1]['key']=='fresh-key'
    assert 'fresh-key' not in result.text
    with SessionLocal() as db:assert db.get(Config,'radarr_url').value=='http://old.private:7878'
    assert post(client,'/admin/connections/test',{'service':'radarr','url':'http://new.private:7878'},'/admin/integrations').status_code==200
    assert observed[-1][1]['key']=='saved-key'


def test_admin_labels_are_native_but_public_navigation_is_customizable(client):
    setup(client)
    with SessionLocal() as db:
        main.set_config(db,i18n.translation_key('en','Save'),'CUSTOM SAVE')
        main.set_config(db,i18n.translation_key('en','Home'),'My portal')
        main.set_config(db,i18n.translation_key('en','Branding'),'CUSTOM ADMIN')
        db.commit()
    page=client.get('/admin/branding').text
    assert 'My portal' in page and 'CUSTOM ADMIN' not in page
    response=post(client,'/admin/translations',{'edit_locale':'fr','scope':'interface','key':'Branding','value':'No'},'/admin/translations')
    assert response.status_code==400
    assert 'name="key" value="Branding"' not in client.get('/admin/translations').text
    assert 'name="login_text"' not in page


def test_normal_and_assistance_language_changes_have_separate_preferences(client):
    setup(client)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'));uid=user.id;initial=user.locale
    assert post(client,f'/admin/users/{uid}/assist',{},'/admin/users').status_code==303
    assert post(client,'/language',{'locale':'fr','next':'/home'},'/home').status_code==303
    assert '<html lang="fr"' in client.get('/home').text
    with SessionLocal() as db:assert db.get(User,uid).locale==initial
    assert post(client,'/account/theme',{'theme':'dark'},'/account').status_code==403
    assert post(client,'/support/stop',{},'/home').status_code==303
    logout(client);login_user(client)
    assert post(client,'/language',{'locale':'fr','next':'/account'},'/account').status_code==303
    with SessionLocal() as db:assert db.get(User,uid).locale=='fr'
    assert 'Member</small>' not in client.get('/account').text


def test_email_editor_excludes_inactive_languages_without_deleting_translations(client):
    setup(client)
    with SessionLocal() as db:
        db.add(Language(code='de',name='Deutsch',enabled=False))
        i18n.store_content(db,'mail:invite:subject',main.DEFAULTS['invite_subject'],'de','Willkommen ${app_name}');db.commit()
    assert 'value="de"' not in client.get('/admin/mail-editor').text
    assert 'name="key" value="mail:invite:' not in client.get('/admin/translations?edit_locale=de&scope=all').text
    assert client.get('/admin/mail-editor?mail_locale=de',follow_redirects=False).status_code==303
    assert post(client,'/admin/mail-editor',{'purpose':'invite','mail_locale':'de','subject':'Hello','html':'<p>Hello</p>'},'/admin/mail-editor').status_code==400
    with SessionLocal() as db:assert i18n.content(db,'mail:invite:subject',main.DEFAULTS['invite_subject'],'de')=='Willkommen ${app_name}'


def test_unconfigured_tool_grant_rejected_and_existing_grant_retained(client):
    setup(client)
    with SessionLocal() as db:uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
    path=f'/admin/users/{uid}/role'
    assert post(client,path,{'tools':'radarr'},'/admin/users').status_code==400
    with SessionLocal() as db:db.get(User,uid).tool_access='["radarr"]';db.commit()
    assert post(client,path,{},'/admin/users').status_code==303
    with SessionLocal() as db:assert json.loads(db.get(User,uid).tool_access)==['radarr']


def test_tdarr_proxy_maps_assets_and_never_forwards_gatearr_cookies(client,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        for key,value in {'tdarr_enabled':'true','tdarr_url':'http://tdarr.private:8265'}.items():main.set_config(db,key,value)
        db.scalar(select(User).where(User.admin.is_(True))).tool_access='["tdarr"]';db.commit()
    original=httpx.AsyncClient
    client.cookies.set('reverse_proxy_session','must-not-leak')
    observed_cookies=[]
    async def upstream(request):
        assert request.url.host=='tdarr.private' and request.url.path=='/'
        observed_cookies.append(request.headers.get('cookie',''))
        assert 'gatearr_' not in request.headers.get('cookie','') and 'must-not-leak' not in request.headers.get('cookie','') and 'x-api-key' not in request.headers
        return httpx.Response(200,content=b'<html><head></head><body><script src="/assets/app.js"></script></body></html>',headers={'content-type':'text/html','set-cookie':'native=abc; Path=/'})
    monkeypatch.setattr(tools_proxy.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(upstream),**kw))
    response=client.get('/tools/tdarr/app/tdarr/')
    assert response.status_code==200
    assert '<base href="/tools/tdarr/app/tdarr/">' in response.text
    assert 'src="/tools/tdarr/app/tdarr/assets/app.js"' in response.text
    assert '/app/tools/tdarr' not in response.text
    assert 'Path=/tools/tdarr/app/tdarr/' in response.headers['set-cookie']
    assert response.cookies.get('gatearr_tdarr_native_native')=='abc'
    assert client.get('/tools/tdarr/app/tdarr/').status_code==200
    assert observed_cookies[-1]=='native=abc'
    logout(client);login_user(client)
    assert client.get('/tools/tdarr/app/tdarr/').status_code==401


def test_invitation_default_changes_preserve_custom_body(client):
    setup(client)
    from app.mailer import config,DEFAULTS,INVITE_BODY_V040
    with SessionLocal() as db:
        main.set_config(db,'invite_body',INVITE_BODY_V040);db.commit()
        assert 'One portal, all your services.' in config(db,'invite_body')
        main.set_config(db,'invite_body','My custom ${link}');db.commit()
        assert config(db,'invite_body')=='My custom ${link}'
        assert 'Un seul portail' in i18n.content(db,'mail:invite:body',DEFAULTS['invite_body'],'fr')


def test_identity_saves_without_legacy_login_field_and_keeps_login_content(client):
    setup(client)
    with SessionLocal() as db:
        main.set_config(db,'login_text','A custom welcome');db.commit()
    response=post(client,'/admin/settings',{'app_name':'Family','public_url':'http://testserver','brand_display':'name'},'/admin/branding')
    assert response.status_code==303,response.text
    with SessionLocal() as db:assert db.get(Config,'login_text').value=='A custom welcome'
    logout(client)
    assert 'A custom welcome' in client.get('/login').text


def test_tdarr_native_credentials_are_scoped_for_both_http_and_websockets():
    values=tools_proxy.tdarr_headers({'cookie':'gatearr_session=PRIVATE; reverse_proxy_session=PRIVATE; gatearr_tdarr_native_token=native-token','authorization':'Bearer native-auth'})
    assert values=={'cookie':'token=native-token','authorization':'Bearer native-auth'}
