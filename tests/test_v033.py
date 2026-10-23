import json
import pytest
from sqlalchemy import select
from app import main,portal
from app.db import SessionLocal
from app.models import User,Guide
from app.access import category_icon
from app.connection_health import checks as REAL_CONNECTION_CHECKS
from test_portal import setup,post


def test_invitation_pending_and_verified(client,monkeypatch):
    setup(client);monkeypatch.setattr(main,'enqueue_mail',lambda *args:None)
    with SessionLocal() as db:uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
    assert post(client,'/admin/user-email',{'id':uid,'email':'pending@example.com','locale':'en'},'/admin/users').status_code==200
    page=client.get('/admin/users').text
    assert 'value="pending@example.com"' in page and 'Resend invitation' in page
    with SessionLocal() as db:db.get(User,uid).email='pending@example.com';db.commit()
    page=client.get('/admin/users').text
    assert f'name="id" value="{uid}"' not in page and 'Resend invitation' not in page


def test_permission_filter_reflows_and_subtitles_survive(client,monkeypatch):
    setup(client)
    from app import tools_proxy
    monkeypatch.setattr(tools_proxy,'allowed_tools',lambda db,user:[])
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'));layout=portal.load(db)
        layout['blocks']=[{'id':'apps','kind':'applications','region':'main','span':12,'order':10,'columns':3,'applications':['access:emby','radarr','account'],'subtitles':{'access:emby':'Watch with the family'}}]
        portal.validate(layout);row=portal.for_display(layout,'en',user,db)['main'][0]
        assert [a['key'] for a in row['cards']]==['access:emby','account'] and row['visible_columns']==2
        assert row['cards'][0]['subtitle']=='Watch with the family'
    with pytest.raises(ValueError):portal.validate({**layout,'blocks':[{**layout['blocks'][0],'subtitles':{'account':'x'*301}}]})


@pytest.mark.parametrize('title,icon',[('Computer','desktop'),('Phone','mobile-screen-button'),('Smart TV','tv'),('Browser','globe'),('Windows','brands:windows'),('iPhone','brands:apple')])
def test_category_icons_respect_custom(title,icon):
    assert category_icon({'title':title,'icon':'link'})==icon
    assert category_icon({'title':title,'icon':'star'})=='star'


def test_guide_preview_exposes_selectable_steps(client):
    setup(client)
    with SessionLocal() as db:g=db.scalar(select(Guide));gid=g.id;version=g.version;article=json.loads(g.draft)
    preview=post(client,f'/admin/visual-guide/{gid}/preview',{'version':version,'payload':json.dumps(article)},'/admin')
    assert preview.status_code==200 and 'data-step-id=' in preview.text


def test_identity_and_security_navigation(client):
    setup(client)
    with SessionLocal() as db:uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
    page=client.get(f'/admin/users/{uid}').text
    assert 'View portal as demo' in page and page.index('View portal as demo')<page.index('Account status')
    assert 'Open portal as this user' not in page
    nav=client.get('/admin/security').text
    assert 'href="/admin/security"' not in nav.split('</nav>')[0]
    assert nav.index('href="/admin/emby"')<nav.index('href="/admin/security"')
    assert post(client,f'/admin/users/{uid}/assist',{},'/admin/users').status_code==303
    home=client.get('/home').text
    assert home.index('Logged as demo')<home.index('<div class="shell">') and 'Assistance mode' not in home


def test_admin_email_change_returns_login(client,monkeypatch):
    setup(client)
    from app import user_management
    monkeypatch.setattr(user_management,'notification',lambda *args:None);monkeypatch.setattr(user_management,'queue_user',lambda *args,**kwargs:None)
    with SessionLocal() as db:uid=db.scalar(select(User.id).where(User.emby_id=='admin-1'));main.set_config(db,'smtp_host','smtp.test');db.commit()
    r=post(client,f'/admin/users/{uid}/account',{'action':'email','email':'new-owner@example.com'},'/admin')
    assert r.status_code==303 and r.headers['location']=='/login'


def test_mail_blocks_roundtrip_and_require_link(client):
    setup(client)
    assert 'mail-builder-copy' in client.get('/admin/mail-editor').text
    html='<h2>Hello ${username}</h2><hr><p>Instructions</p><a href="${link}">Start</a>'
    data={'purpose':'invite','mail_locale':'en','subject':'Welcome','html':html,'action':'save'}
    assert post(client,'/admin/mail-editor',data,'/admin/mail-editor').status_code==303
    assert '&lt;hr&gt;' in client.get('/admin/mail-editor').text
    assert post(client,'/admin/mail-editor',{**data,'html':'<p>Missing link</p>'},'/admin/mail-editor').status_code==400


def test_device_icons_match_in_editor_preview_and_public_page(client):
    from app.models import AccessService
    setup(client)
    editor=client.get('/admin/design/home/howto/emby').text
    boot=json.loads(editor.split('<script id="howto-data" type="application/json">')[1].split('</script>')[0])
    computer=next(n for n in boot['nodes'] if n['title']=='Computer')
    assert computer['icon']=='desktop'
    payload={'nodes':boot['nodes'],'mode':'choices'}
    preview=post(client,'/admin/visual-howto/emby/preview',{'payload':json.dumps(payload)},'/admin/portal')
    assert preview.status_code==200
    assert 'fa-desktop' in preview.text and 'fa-mobile-screen-button' in preview.text and 'fa-tv' in preview.text
    page=client.get('/access/emby').text
    assert 'fa-desktop' in page and 'fa-mobile-screen-button' in page and 'fa-tv' in page


def test_connection_diagnostics_distinguish_reachability_from_authentication(client,monkeypatch):
    import httpx
    from app import connection_health
    from app.security import encrypt
    setup(client);real=httpx.Client
    monkeypatch.setattr(connection_health.socket,'getaddrinfo',lambda *args,**kwargs:[(2,1,6,'',('192.0.2.8',0))])
    monkeypatch.setattr(connection_health.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(lambda req:httpx.Response(403,text='private-secret')),**kw))
    with SessionLocal() as db:
        for key,value in {'seerr_enabled':'true','seerr_url':'https://seerr.test','seerr_api_key':encrypt('secret-key')}.items():main.set_config(db,key,value)
        db.commit();data=REAL_CONNECTION_CHECKS(db,refresh='seerr');d=data['seerr']['diagnostics']
        assert d['reachable'] and not d['api_valid'] and d['http_status']==403 and d['resolved_ips']==['192.0.2.8']
        assert 'private-secret' not in str(data) and 'secret-key' not in str(data)
        assert REAL_CONNECTION_CHECKS(db)['seerr']['diagnostics']==d


def test_smtp_connection_test_uses_saved_settings_without_sending_email(client,monkeypatch):
    from app import connection_health
    calls=[]
    class SMTP:
        def __init__(self,host,port,**kwargs):calls.append((host,port))
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def ehlo(self):return 250,b'local test server'
    setup(client)
    monkeypatch.setattr(connection_health.smtplib,'SMTP',SMTP)
    monkeypatch.setattr(connection_health.socket,'getaddrinfo',lambda *args,**kwargs:[(2,1,6,'',('192.0.2.25',0))])
    with SessionLocal() as db:
        for key,value in {'smtp_host':'smtp.test','smtp_port':'2525','smtp_mode':'plain','smtp_username':''}.items():main.set_config(db,key,value)
        db.commit()
    assert client.post('/admin/smtp-connection-test',data={'csrf':'bad'}).status_code==403
    assert post(client,'/admin/smtp-connection-test',{'smtp_host':'untrusted.test'},'/admin/emails').status_code==303
    assert calls==[('smtp.test',2525)]
    page=client.get('/admin/emails?tab=smtp').text
    assert 'SMTP connection verified' in page and '192.0.2.25' in page
    assert 'data-feedback="test"' in page and 'No email is sent.' in page


def test_smtp_connection_does_not_leak_authentication_errors(client,monkeypatch):
    from app import connection_health
    from app.security import encrypt
    setup(client)
    class SMTP:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def ehlo(self):return 250,b'local'
        def login(self,*args):raise connection_health.smtplib.SMTPAuthenticationError(535,b'private-auth-secret')
    monkeypatch.setattr(connection_health.smtplib,'SMTP_SSL',SMTP)
    monkeypatch.setattr(connection_health.socket,'getaddrinfo',lambda *args,**kwargs:[])
    with SessionLocal() as db:
        for key,value in {'smtp_host':'smtp.test','smtp_port':'465','smtp_mode':'ssl','smtp_username':'account','smtp_password':encrypt('secret-pass')}.items():main.set_config(db,key,value)
        db.commit();d=connection_health.smtp_probe(db)
        assert d['reachable'] and d['state']=='error' and d['detail']=='Authentication rejected'
        assert 'private-auth-secret' not in str(d) and 'secret-pass' not in str(d)


def test_guide_button_preview_requires_a_safe_destination(client):
    setup(client)
    with SessionLocal() as db:gid=db.scalar(select(Guide.id))
    article={'title':'Preview','summary':'','device':'desktop','steps':[{'id':'preview-step','title':'Instructions','body':'Read this first.','link_label':'Help','link_url':''}]}
    path=f'/admin/visual-guide/{gid}/preview'
    without=post(client,path,{'payload':json.dumps(article)},'/admin')
    assert without.status_code==200 and '>Help ↗</a>' not in without.text
    article['steps'][0]['link_url']='https://example.com/help'
    with_button=post(client,path,{'payload':json.dumps(article)},'/admin')
    assert with_button.status_code==200 and 'href="https://example.com/help"' in with_button.text and '>Help ↗</a>' in with_button.text
    article['steps'][0]['link_url']='javascript:alert(1)'
    assert post(client,path,{'payload':json.dumps(article)},'/admin').status_code==400
