import json, os, sqlite3, subprocess, sys
from pathlib import Path
import httpx
import pytest
from sqlalchemy import select
from app import main, versioning, footer, default_journeys, access, i18n
from app.release import VERSION
from app.db import SessionLocal
from app.models import Config, Guide, AccessService
from test_portal import setup, post, csrf, logout, login_user
from test_icon_uploads import png


def remote(monkeypatch, version='0.4.0', revision='b'*40, fail=False):
    original=httpx.Client;calls=[]
    def handler(req):
        calls.append(req)
        assert req.url.host=='api.github.com'
        assert not req.headers.get('authorization')
        if fail:return httpx.Response(503)
        if '/git/' in req.url.path:return httpx.Response(200,json={'object':{'type':'commit','sha':revision}})
        return httpx.Response(200,json={'tag_name':'v'+version,'draft':False,'prerelease':False,'body':'<script>untrusted</script>Release notes','html_url':'https://malicious.test'})
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    return calls


def test_version_page_and_update_notification_are_admin_only_and_escaped(client,monkeypatch):
    setup(client);calls=remote(monkeypatch)
    assert post(client,'/admin/updates/check',{},'/admin/updates').status_code==303
    page=client.get('/admin/updates').text
    assert ('Gatearr '+VERSION) in page and '0.4.0' in page and i18n.translate('Installed release history','en') in page
    assert 'untrusted' not in page and 'malicious.test' not in page
    assert 'class="update-notice"' in client.get('/account').text
    assert len(calls)==1
    logout(client);login_user(client)
    assert 'class="update-notice"' not in client.get('/account').text
    assert client.get('/admin/updates').status_code==403
    assert post(client,'/admin/updates/check',{},'/account').status_code==403
    logout(client)
    assert 'class="update-notice"' not in client.get('/login').text


def test_release_cache_backoff_failure_retention_and_opt_out(client,monkeypatch):
    setup(client);calls=remote(monkeypatch)
    with SessionLocal() as db:
        assert versioning.check(db)['available']
        assert versioning.check(db)['available'] and len(calls)==1
    remote(monkeypatch,fail=True)
    with SessionLocal() as db:
        state=versioning.check(db,True)
        assert state['available'] and state['state']=='error' and state['version']=='0.4.0'
        main.set_config(db,'release_check','{}');main.set_config(db,'release_checks_enabled','false');db.commit()
        assert versioning.check(db)['state']=='unchecked'
    assert client.post('/admin/updates/check',data={'csrf':'bad'}).status_code==403
    assert post(client,'/admin/updates/settings',{},'/admin/updates').status_code==303
    assert 'GitHub could not be reached' not in client.get('/admin/updates').text


@pytest.mark.parametrize('tag,available',[('0.0.9',False),('0.1.0',False),('0.2.1',False),('0.2.2',False),('0.2.3',False),('0.2.4',False),('0.3.0',False),('0.3.2',False),('0.3.3',False),('0.3.4',False),('0.3.5',True),('0.10.0',True)])
def test_semantic_version_comparison(client,monkeypatch,tag,available):
    setup(client);remote(monkeypatch,version=tag)
    monkeypatch.setattr(versioning,'BUILD_REVISION','')
    with SessionLocal() as db:assert versioning.check(db,True)['available'] is available


def test_same_version_rebuild_and_invalid_release_are_handled(client,monkeypatch):
    setup(client);remote(monkeypatch,version=VERSION);monkeypatch.setattr(versioning,'BUILD_REVISION','a'*40)
    with SessionLocal() as db:assert not versioning.check(db,True)['available']
    remote(monkeypatch,version='../../bad')
    with SessionLocal() as db:
        state=versioning.check(db,True)
        assert state['state']=='error' and state['url']=='https://github.com/HeklaLab/gatearr/releases/tag/v'+VERSION
    assert 'Updates and changelog' in client.get('/admin').text


def test_bounded_github_response():
    with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,content=b'x'*131073))) as client:
        with pytest.raises(ValueError,match='Oversized'):versioning.read_json(client,'/releases/latest')


def edit_footer(client,**values):
    with SessionLocal() as db:version=footer.version(db)
    return post(client,'/admin/footer',{'version':version,**values},'/admin/footer')


def test_footer_draft_publish_global_visibility_translation_and_conflicts(client):
    setup(client,locale='fr')
    assert edit_footer(client,kind='link',text='Community',url='https://community.example.com',position=20,new_tab='on').status_code==303
    assert 'community.example.com' not in client.get('/login').text
    assert 'community.example.com' in client.get('/admin/footer/preview').text
    assert edit_footer(client,action='publish').status_code==303
    for path in ('/home','/account','/forgot','/admin'):
        assert 'https://community.example.com' in client.get(path).text
    with SessionLocal() as db:
        item=next(x for x in footer.load(db)['items'] if x['text']=='Community')
        i18n.store_content(db,'footer:'+item['id']+':text','Community','fr','Communauté');db.commit()
    assert 'Communauté' in client.get('/account').text
    assert post(client,'/admin/footer',{'action':'publish','version':0},'/admin/footer').status_code==409
    assert edit_footer(client,action='settings',alignment='center').status_code==303
    assert edit_footer(client,action='publish').status_code==303
    assert 'global-footer' not in client.get('/forgot').text
    assert edit_footer(client,action='reset').status_code==303
    logout(client);login_user(client)
    assert client.get('/admin/footer').status_code==403
    assert post(client,'/admin/footer',{'action':'publish','version':4},'/account').status_code==403


def test_footer_png_upload_escaping_and_invalid_links(client):
    setup(client)
    response=client.post('/admin/footer',data={'csrf':csrf(client,'/admin/footer'),'version':0,'kind':'logo','text':'<script>Logo</script>','url':'https://example.com','position':5},files={'icon_file':('logo.png',png(),'image/png')},follow_redirects=False)
    assert response.status_code==303
    assert edit_footer(client,action='publish').status_code==303
    page=client.get('/forgot').text
    assert 'alt="&lt;script&gt;Logo&lt;/script&gt;"' in page and '/media/icons/' in page
    with SessionLocal() as db:
        logo=next(x for x in footer.load(db)['items'] if x['kind']=='logo')
        assert client.get(logo['icon_url']).content==png()
    for url in ('javascript:alert(1)','https://name:password@example.com'):
        assert edit_footer(client,kind='link',text='Unsafe',url=url,position=0).status_code==400
    assert edit_footer(client,kind='logo',text='Missing logo',position=1).status_code==400


def test_default_device_journeys_and_public_address_placeholders(client):
    setup(client)
    with SessionLocal() as db:
        service=db.get(AccessService,'emby');tree=access.load(service)
        assert service.entry_mode=='structured'
        assert {n['title'] for n in tree if n['kind']=='guide'}=={'Windows','Mac','Linux','Android','iPhone','Smart TV'}
        guides=list(db.scalars(select(Guide)));assert len(guides)==6 and all(g.published for g in guides)
        service.server_url='https://media.example.com:8920';db.commit()
        android=next(g for g in guides if 'Android' in json.loads(g.draft)['title'])
    page=client.get('/access/emby/guide/'+str(android.id)).text
    assert 'play.google.com' in page and 'media.example.com' in page and '8920' in page and 'Owner' in page
    assert 'emby.test' not in page and 'test-api-key' not in page
    assert post(client,'/admin/guides/defaults',{},'/admin/guides').status_code==400
    with SessionLocal() as db:assert len(list(db.scalars(select(Guide))))==6


def test_jellyfin_presets_and_existing_content_are_preserved(client):
    setup(client,empty_journeys=True)
    with SessionLocal() as db:
        main.set_config(db,'media_server','jellyfin');db.commit()
        assert default_journeys.seed(db,activate=True);db.commit()
        guide=db.scalar(select(Guide));article=json.loads(guide.draft)
        assert article['title'].startswith('Jellyfin') and 'Emby' not in guide.draft
        original=db.get(AccessService,'emby').access_draft
        assert not default_journeys.seed(db,activate=True)
        assert db.get(AccessService,'emby').access_draft==original


def test_0011_migration_seeds_existing_empty_portal_without_changing_direct_mode(tmp_path):
    path=tmp_path/'upgrade.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(path)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0010'],env=env,check=True,capture_output=True)
    with sqlite3.connect(path) as db:db.execute("INSERT INTO config VALUES ('setup_complete','true')")
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,check=True,capture_output=True)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM guides').fetchone()[0]==4
        assert db.execute('SELECT entry_mode FROM access_services').fetchone()[0]=='direct'
