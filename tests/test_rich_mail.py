import json,os,sqlite3,subprocess,sys
from sqlalchemy import select
from app import main,email_editor
from app.db import SessionLocal
from app.models import User,Config,Token,MailJob
from app.mailer import compose
from app.rich_mail import clean,interpolate,validate
from app.security import decrypt
from test_portal import setup,post,prepare_user,logout,smtp

HTML='<h2>Welcome ${username}</h2><p><strong>Enjoy ${app_name}</strong></p><p><a href="${link}">Join us</a></p><img src="http://testserver/static/gatearr-logo.png" alt="Banner">'

def edit(client,**overrides):
    return post(client,'/admin/mail-editor',{'purpose':'invite','mail_locale':'en','subject':'Welcome ${username}','html':HTML,**overrides},'/admin/mail-editor')

def test_single_language_controls_account_email_and_admin_preference(client,sent):
    prepare_user(client)
    assert post(client,'/account/language',{'locale':'en'},'/account').status_code==303
    post(client,'/language',{'locale':'fr','next':'/account'},'/account')
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'))
        uid=user.id
        assert user.locale=='fr'
        main.mail_token(db,user,'reset','test-token',user.email)
    assert sent[-1][2]['_locale']=='fr'
    assert post(client,'/account/language',{'locale':'de'},'/account').status_code==400
    assert post(client,f'/admin/users/{uid}/language',{'mail_locale':'fr'},'/account').status_code==403
    logout(client)
    post(client,'/login',{'name':'Owner','password':'AdminPassword123!'})
    assert post(client,f'/admin/users/{uid}/language',{'locale':'fr'},'/admin').status_code==303
    with SessionLocal() as db:assert db.get(User,uid).locale=='fr'


def test_editor_saves_bilingual_templates_and_multipart_with_escaped_values(client):
    setup(client)
    assert edit(client).status_code==303
    assert edit(client,mail_locale='fr',subject='Bonjour ${username}',html='<p>Bonjour ${username}</p><a href="${link}">Confirmer</a>').status_code==303
    with SessionLocal() as db:
        en=compose(db,'member@example.com','invite',{'app_name':'Gatearr','username':'<img src=x onerror=bad>','link':'https://portal.test/verify-email?token=a&next=b','minutes':'30','_locale':'en'})
        fr=compose(db,'member@example.com','invite',{'app_name':'Gatearr','username':'Alex','link':'https://portal.test/verify-email?token=a','minutes':'30','_locale':'fr'})
    assert en.get_content_type()=='multipart/alternative'
    html=en.get_body(preferencelist=('html',)).get_content()
    text=en.get_body(preferencelist=('plain',)).get_content()
    assert '&lt;img src=x onerror=bad&gt;' in html and '<strong>' in html and 'gatearr-logo.png' in html
    assert 'href="https://portal.test/verify-email?token=a&amp;next=b"' in html
    assert 'https://portal.test/verify-email?token=a&next=b' in text
    assert fr['Subject']=='Bonjour Alex' and 'Welcome' not in fr.get_body(preferencelist=('html',)).get_content()


def test_rich_mail_removes_active_html_and_unsafe_urls():
    raw='<p style="text-align:center;color:#123456;position:fixed">Safe</p><script>bad()</script><svg onload="bad()"></svg><form><input></form><a href="javascript:alert(1)">Bad</a><img src="data:image/svg+xml,bad" onerror="bad()"><img src="https://example.com/a.png" onload="bad()"><a href="${link}">Verify</a>'
    result=validate(raw,html=True)
    for value in ('<script','bad()','<svg','<form','onerror','onload','javascript:','data:image','position:'):assert value not in result
    assert 'text-align:center' in result and 'https://example.com/a.png' not in result and '${link}' in result
    final=interpolate('<a href="${link}">Go</a>',{'link':'javascript:alert(1)'})
    assert 'javascript:' not in final


def test_editor_preview_and_test_do_not_save_draft_or_create_real_token(client,monkeypatch):
    setup(client)
    assert edit(client,action='preview').status_code==200
    captured=[]
    monkeypatch.setattr(email_editor,'send',lambda db,recipient,purpose,values:captured.append((recipient,compose(db,recipient,purpose,values))))
    assert edit(client,action='test').status_code==200
    assert captured[0][0]=='owner@example.com' and captured[0][1]['Subject']=='Welcome Owner'
    assert 'token=preview' in captured[0][1].get_body(preferencelist=('plain',)).get_content()
    with SessionLocal() as db:
        assert db.get(Config,'invite_html_en') is None
        assert db.get(Config,'invite_subject_en') is None
        assert db.scalar(select(Token)) is None
    page=client.get('/admin/mail-editor?mail_locale=en')
    assert 'script-src \'self\'' in page.headers['content-security-policy']
    assert 'sandbox="allow-same-origin"' in page.text and 'allow-scripts' not in page.text and 'src="/static/mail-editor.js?v=' in page.text
    assert "script-src 'self'" in client.get('/account').headers['content-security-policy']


def test_editor_rejects_missing_link_bad_variables_and_unauthorized_access(client):
    setup(client)
    assert edit(client,html='<p>No link</p>').status_code==400
    assert edit(client,html='<script>${link}</script>').status_code==400
    assert edit(client,html='<a title="${link}">No usable link</a>').status_code==400
    assert edit(client,subject='Hello ${secret}').status_code==400
    assert edit(client,subject='Hello\r\nBcc: bad@example.com').status_code==400
    assert edit(client,mail_locale='de').status_code==400
    assert client.post('/admin/mail-editor',data={'csrf':'bad'}).status_code==403
    logout(client)
    post(client,'/login',{'name':'demo','password':'DemoPassword123!'})
    assert client.get('/admin/mail-editor').status_code==403
    assert post(client,'/admin/mail-editor',{'html':HTML},'/account').status_code==403


def test_admin_invitation_uses_own_template_and_selected_language(client,sent):
    setup(client);smtp(client)
    edit(client)
    with SessionLocal() as db:uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
    assert post(client,'/admin/user-email',{'id':str(uid),'email':'new@example.com','mail_locale':'en'},'/admin').status_code==200
    with SessionLocal() as db:
        assert db.get(User,uid).locale=='en'
        assert db.get(User,uid).email is None
        assert db.scalar(select(Token)).purpose=='verify'
        assert json.loads(decrypt(db.scalar(select(MailJob)).payload))['purpose']=='invite'
    main.deliver_mail()
    assert sent[0][1]=='invite' and sent[0][2]['_locale']=='en'
    assert '/verify-email?token=' in sent[0][2]['link']


def test_email_language_migration_preserves_existing_preferences(tmp_path):
    database=tmp_path/'old.db'
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(database)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0005'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO users (id,name,admin,active,version,locale) VALUES (1,'English',0,1,0,'en'),(2,'French',0,1,0,'fr')")
    subprocess.run([sys.executable,'-m','alembic','upgrade','0006'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:assert db.execute('SELECT locale,mail_locale FROM users ORDER BY id').fetchall()==[('en','en'),('fr','fr')]
    subprocess.run([sys.executable,'-m','alembic','downgrade','0005'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as db:assert db.execute('SELECT name FROM users ORDER BY id').fetchall()==[('English',),('French',)]
