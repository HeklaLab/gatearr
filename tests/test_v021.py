import json
import httpx
from sqlalchemy import select
from app import main,footer,tools_proxy,themes
from app.db import SessionLocal
from app.models import User,AuditEvent,Language
from app.security import encrypt
from test_portal import setup,post,csrf
from test_icon_uploads import png


def test_single_language_dark_theme_and_parent_navigation(client):
    setup(client)
    with SessionLocal() as db:
        db.get(Language,'fr').enabled=False;db.commit()
    page=client.get('/admin/guides').text
    assert 'class="language-switch"' not in page
    assert 'href="/admin/integrations"' in page
    assert 'Portal builder' in page and 'Back to admin' in page
    assert 'Theme policy' not in client.get('/admin/branding/themes').text
    css=client.get('/theme.css').text
    assert 'color-scheme:dark' in css and 'linear-gradient' in css and '@media' not in css
    with SessionLocal() as db:
        main.set_config(db,'themes_published',json.dumps({'mode':'light','light':{},'dark':{'bg':'#080f24','surface':'#111e3c','gradient_start':'#062751','gradient_end':'#080f24'}}));db.commit()
    assert themes.DARK['bg'] in client.get('/theme.css').text


def test_footer_columns_upload_and_draft_retention(client):
    setup(client)
    page=client.get('/admin/footer').text
    assert 'Legacy footer items' not in page.split('<script id="studio-data"')[0] and 'studio-inspector' in page and 'studio.js' in page
    import re
    design=json.loads(re.search(r'<script id="studio-data" type="application/json">(.*?)</script>',page)[1])['layout']
    assert next(b for b in design['blocks'] if b['kind']=='columns')['columns']==1
    result=client.post('/admin/assets',data={'csrf':csrf(client,'/admin/footer')},files={'icon_file':('logo.png',png(),'image/png')},headers={'Accept':'application/json'},follow_redirects=False)
    assert result.status_code==200
    url=result.json()['url'];assert client.get(url).status_code==200
    assert post(client,'/admin/footer',{'version':0,'action':'columns','count':3,'column_0':'<p>A</p><img src="'+url+'">','column_1':'<b>B</b>','column_2':'<i>C</i>'},'/admin/footer').status_code==303
    assert post(client,'/admin/footer',{'version':1,'action':'columns','count':1},'/admin/footer').status_code==303
    with SessionLocal() as db:
        draft=footer.load(db,True)
        assert len(draft['columns'])==1 and '<i>C</i>' in draft['column_archive'][2]
    assert post(client,'/admin/footer',{'version':2,'action':'publish'},'/admin/footer').status_code==303
    page=client.get('/home').text
    assert 'footer-cols-1' in page and url in page and '<i>C</i>' not in page


def test_audit_names_change_details_and_secret_redaction(client):
    setup(client)
    assert post(client,'/admin/settings',{'app_name':'My Gate','public_url':'http://testserver','login_text':'Welcome','logo_url':'','emby_link':'https://media.test'},'/admin/branding').status_code==303
    page=client.get('/admin/activity').text
    assert 'Owner' in page and 'Portal identity updated' in page and 'Gatearr → My Gate' in page
    assert 'api key: [hidden]' in page and 'demo-key' not in page
    assert 'GET /admin/branding' not in page
    assert 'Viewed a page' in client.get('/admin/activity?all=1').text


def test_subpath_proxy_assets_redirects_origin_and_revocation(client,monkeypatch):
    setup(client);observed=[]
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)));owner.tool_access='["radarr"]'
        for key,value in {'radarr_enabled':'true','radarr_url':'http://private.test:7878','radarr_api_key':encrypt('never-in-html')}.items():main.set_config(db,key,value)
        db.commit()
    original=httpx.AsyncClient
    async def upstream(request):
        observed.append(request)
        if request.url.path.endswith('/redirect'):return httpx.Response(302,stream=httpx.ByteStream(b''),headers={'Location':'http://private.test:7878/tools/radarr/app/movies'})
        if request.url.path.endswith('/bad'):return httpx.Response(302,stream=httpx.ByteStream(b''),headers={'Location':'/login'})
        if request.url.path.endswith('/app.js'):return httpx.Response(200,stream=httpx.ByteStream(b'window.loaded=true;'),headers={'Content-Type':'application/javascript'})
        return httpx.Response(200,stream=httpx.ByteStream(b'<base href="/tools/radarr/app/"><script src="app.js"></script>'),headers={'Content-Type':'text/html'})
    monkeypatch.setattr(tools_proxy.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(upstream),**kw))
    page=client.get('/tools/radarr');assert '<iframe' in page.text and 'src="/tools/radarr/app/"' in page.text
    response=client.get('/tools/radarr/app/');assert response.status_code==200 and "frame-ancestors 'self'" in response.headers['Content-Security-Policy']
    assert client.get('/tools/radarr/app/app.js').text=='window.loaded=true;'
    assert client.get('/tools/radarr/app/redirect',follow_redirects=False).headers['location']=='http://testserver/tools/radarr/app/movies'
    assert client.get('/tools/radarr/app/bad').status_code==502
    assert client.post('/tools/radarr/app/api/v3/movie',json={},headers={'origin':'https://evil.test'}).status_code==403
    assert all('cookie' not in r.headers and r.headers['X-Api-Key']=='never-in-html' for r in observed)
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)));owner.version+=1;db.commit()
    assert client.get('/tools/radarr/app/').status_code==401
