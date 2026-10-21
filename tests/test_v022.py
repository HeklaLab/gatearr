import json
from pathlib import Path
import httpx
from sqlalchemy import select
from app import main,tools_proxy
from app.icons import FA_ICONS,icon_class
from app.models import User,MenuItem,AccessService
from app.db import SessionLocal
from app.security import decrypt
from test_portal import setup,post,logout,login_user


def tool_values(**extra):
    return {'radarr_enabled':'on','radarr_url':'http://radarr.private:7878','radarr_api_key':'do-not-show-this-key','proxy_acknowledge':'on',**extra}


def test_all_free_icon_styles_are_bundled_and_selected_visually(client):
    setup(client)
    icons=client.get('/static/fontawesome-icons.json').json()
    assert len(icons)==2060 and {entry['style'] for entry in icons}=={'solid','regular','brands'}
    assert all(entry['id'] in FA_ICONS for entry in icons)
    for font in ('fa-solid-900.woff2','fa-regular-400.woff2','fa-brands-400.woff2'):
        assert client.get('/static/'+font).content[:4]==b'wOF2'
    page=client.get('/admin/services').text
    assert 'data-icon-picker' in page and '/static/icon-picker.js' in page
    assert '<select name="icon"' not in page and 'name="icon_url"' not in page
    assert 'name="icon_file"' in page
    assert post(client,'/admin/menu',{'label':'Apple','url':'https://example.com','position':1,'icon':'brands:apple'},'/admin/services').status_code==303
    assert 'fa-brands fa-apple' in client.get('/home').text
    assert post(client,'/admin/menu',{'label':'Regular','url':'https://example.com','position':2,'icon':'regular:address-book'},'/admin/services').status_code==303
    assert 'fa-regular fa-address-book' in client.get('/home').text
    assert post(client,'/admin/menu',{'label':'Unsafe','url':'https://example.com','position':3,'icon':'brands:apple onclick=x'},'/admin/services').status_code==400
    assert post(client,'/admin/menu',{'label':'Remote','url':'https://example.com','position':4,'icon_url':'https://example.com/logo.png'},'/admin/services').status_code==400


def test_howto_service_icon_persists_and_external_url_is_refused(client):
    setup(client)
    assert post(client,'/admin/guides/service',{'key':'emby','name':'Movies','entry_mode':'direct','icon':'brands:apple'},'/admin/guides').status_code==303
    with SessionLocal() as db:assert db.get(AccessService,'emby').icon=='brands:apple'
    assert post(client,'/admin/guides/service',{'key':'emby','name':'Movies','entry_mode':'direct','icon_url':'https://example.com/a.svg'},'/admin/guides').status_code==400


def test_radarr_connection_accepts_prefixed_url_ignores_disabled_partial_fields(client,monkeypatch):
    setup(client);original=httpx.Client;calls=[]
    def transport(req):
        calls.append(req)
        assert req.headers['X-Api-Key']=='do-not-show-this-key'
        assert req.url.path=='/tools/radarr/app/api/v3/system/status'
        return httpx.Response(200,json={'appName':'Radarr'})
    monkeypatch.setattr(tools_proxy.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(transport),**kw))
    assert post(client,'/admin/tools',tool_values(radarr_url='http://radarr.private:7878/tools/radarr/app/',sonarr_url='unfinished',bazarr_url='not-ready'),'/admin/integrations').status_code==303
    assert len(calls)==1
    with SessionLocal() as db:
        assert main.config(db,'radarr_enabled')=='true'
        assert main.config(db,'radarr_url')=='http://radarr.private:7878'
        assert decrypt(main.config(db,'radarr_api_key'))=='do-not-show-this-key'


def test_radarr_root_api_has_explicit_urlbase_error_and_preserves_form(client,monkeypatch):
    setup(client);original=httpx.Client
    def transport(req):
        return httpx.Response(200,json={'appName':'Radarr'}) if req.url.path=='/api/v3/system/status' else httpx.Response(404)
    monkeypatch.setattr(tools_proxy.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(transport),**kw))
    result=post(client,'/admin/tools',tool_values(),'/admin/integrations')
    assert result.status_code==400
    assert 'server and API key are valid' in result.text and '/tools/radarr/app' in result.text
    assert 'radarr.private:7878' in result.text and 'do-not-show-this-key' not in result.text
    assert 'name="radarr_url"' in result.text and 'server and API key are valid' in result.text
    with SessionLocal() as db:assert main.config(db,'radarr_enabled')!='true'


def test_radarr_rejected_key_is_clear_and_does_not_expose_secrets(client,monkeypatch):
    setup(client);original=httpx.Client
    monkeypatch.setattr(tools_proxy.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(lambda req:httpx.Response(401,text='do-not-show-this-key')),**kw))
    result=post(client,'/admin/tools',tool_values(),'/admin/integrations')
    assert result.status_code==400 and 'API key rejected (HTTP 401)' in result.text
    assert 'do-not-show-this-key' not in result.text


def test_configured_tools_are_available_to_admins_and_independent_member_grants(client):
    setup(client)
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)));owner.tool_access='[]'
        for tool in tools_proxy.TOOLS:main.set_config(db,tool+'_enabled','true')
        db.scalar(select(User).where(User.admin.is_(True))).tool_access=json.dumps(list(tools_proxy.TOOLS))
        db.commit()
    page=client.get('/home').text
    for tool in tools_proxy.TOOLS:
        assert 'href="/tools/'+tool+'"' in page
        assert client.get('/tools/'+tool).status_code==200
    # Custom portals without a services block still expose configured admin tools.
    with SessionLocal() as db:
        from app import portal
        layout=portal.load(db);layout['blocks']=[b for b in layout['blocks'] if b['kind']!='applications'];main.set_config(db,'portal_published',json.dumps(layout));db.commit()
    assert 'href="/tools/radarr"' not in client.get('/home').text
    logout(client);login_user(client)
    for tool in tools_proxy.TOOLS:assert client.get('/tools/'+tool).status_code==403
    with SessionLocal() as db:
        member=db.scalar(select(User).where(User.name=='demo'));member.tool_access='["radarr"]';db.commit()
    assert client.get('/tools/radarr').status_code==200 and client.get('/tools/sonarr').status_code==403
