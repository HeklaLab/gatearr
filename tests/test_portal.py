import re
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, update
from fastapi.testclient import TestClient
from app import main
from app.db import SessionLocal
from app.models import User, Token, Session, Config, MenuItem, MailJob
from app.security import digest, decrypt
from app.settings import settings

PASSWORD = 'AdminPassword123!'

def csrf(client, path='/login'):
    response = client.get(path, follow_redirects=True)
    assert response.status_code == 200, response.text
    return re.search(r'name="csrf" value="([^"]+)"', response.text)[1]

def post(client, path, data, page='/login'):
    return client.post(path, data={'csrf': csrf(client, page), **data}, follow_redirects=False)

def setup(client,empty_journeys=False):
    client.cookies.set("gatearr_language","fr")
    response=post(client, '/setup', {'app_name':'Gatearr','public_url':'http://testserver','media_server':'emby','url':'http://emby.test/emby','api_key':'test-api-key'}, '/setup')
    if response.status_code==303:
        result=post(client,'/setup/admin',{'user_id':'admin-1','password':PASSWORD},'/setup/admin')
        assert result.status_code==303,result.text
        with SessionLocal() as db:
            owner=db.scalar(select(User).where(User.emby_id=='admin-1'))
            owner.email='owner@example.com'  # Fixture-only verified contact address.
            if empty_journeys:
                from app.models import Guide,AccessService
                db.query(Guide).delete()
                service=db.get(AccessService,'emby');service.access_draft=service.access_published=None;service.access_version=0;service.entry_mode='direct'
            db.commit()
        for step in ('seerr','tools','smtp'):
            assert post(client,'/admin/setup/'+step,{'action':'skip'},'/admin/setup/'+step).status_code==303
        assert post(client,'/admin/setup/finish',{},'/admin/setup/finish').status_code==303
    return response

def login_user(client):
    return post(client, '/login', {'name': 'demo', 'password': 'DemoPassword123!'})

def logout(client):
    return post(client, '/logout', {}, '/account')

def smtp(client):
    return post(client, '/admin/smtp', {'smtp_host': 'mailpit', 'smtp_port': '1025', 'smtp_mode': 'plain', 'smtp_from': 'portal@example.com', 'smtp_username': '', 'smtp_password': ''}, '/admin')

def reset_token():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.emby_id == 'user-1'))
        return main.issue_token(db, user, 'reset')

def prepare_user(client):
    assert setup(client).status_code == 303
    assert smtp(client).status_code == 303
    logout(client)
    assert login_user(client).status_code == 303
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.emby_id == 'user-1'))
        user.email = 'demo@example.com'
        db.commit()

def test_setup_once_and_admin_login(client):
    assert client.get('/login', follow_redirects=False).headers['location'] == '/setup'
    assert setup(client).status_code == 303
    assert 'Your portal' in client.get('/admin').text
    assert post(client, '/setup', {'name': 'Other', 'email': 'other@example.com', 'password': PASSWORD}, '/admin').status_code == 403
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.admin.is_(True)))
        assert admin.password_hash is None
        assert admin.emby_id=='admin-1'
    logout(client)
    assert post(client, '/login', {'name': 'Owner', 'password': PASSWORD}).status_code == 303

def test_csrf_rotation_origin_and_security_headers(client):
    old_csrf = csrf(client, '/setup')
    assert client.post('/setup', data={'csrf': 'wrong'}).status_code == 403
    old_cookie = client.cookies.get('gatearr_session')
    assert setup(client).status_code == 303
    assert client.cookies.get('gatearr_session') != old_cookie
    assert client.post('/logout', data={'csrf': old_csrf}).status_code == 403
    assert client.post('/logout', data={'csrf': csrf(client, '/admin')}, headers={'origin': 'https://evil.example'}).status_code == 403
    response = client.get('/admin')
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['referrer-policy'] == 'same-origin'
    assert "script-src 'none'" in response.headers['content-security-policy']
    assert 'test-api-key' not in response.text
    assert 'httponly' in setup_cookie(client).lower()

def setup_cookie(client):
    other = TestClient(main.app)
    return other.get('/login').headers['set-cookie']

def test_user_login_does_not_inherit_emby_admin_and_sync_preserves_email(client, fake):
    setup(client)
    assert post(client, '/admin/sync', {}, '/admin').status_code == 200
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.emby_id == 'user-1'))
        user.email = 'demo@example.com'
        db.commit()
    post(client, '/admin/sync', {}, '/admin')
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.emby_id == 'user-1'))
        assert user.email == 'demo@example.com'
        assert not user.admin
    logout(client)
    assert login_user(client).status_code == 303
    assert client.get('/admin').status_code == 403
    fake.deleted = True
    with SessionLocal() as db:
        main.sync_users(db)
    assert client.get('/account').status_code == 401

def test_password_change_checks_current_and_revokes_sessions(client, fake):
    prepare_user(client)
    assert post(client, '/account/password', {'current': 'bad', 'password': 'NewPassword123!', 'confirm': 'NewPassword123!'}, '/account').status_code == 502
    assert post(client, '/account/password', {'current': 'DemoPassword123!', 'password': 'NewPassword123!', 'confirm': 'NewPassword123!'}, '/account').status_code == 303
    assert fake.changes == [('user-1', 'NewPassword123!', 'user-token')]
    assert client.get('/account').status_code == 401

def test_email_proof_and_hashed_tokens(client, sent):
    setup(client)
    smtp(client)
    logout(client)
    login_user(client)
    response = post(client, '/account/email', {'email': 'new@example.com', 'current': 'DemoPassword123!'}, '/account')
    assert response.status_code == 200
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.emby_id == 'user-1'))
        assert user.email is None
        job = db.scalar(select(MailJob))
        assert 'new@example.com' not in job.payload
    main.deliver_mail()
    assert sent[0][0] == 'new@example.com'
    raw = sent[0][2]['link'].split('token=')[1]
    with SessionLocal() as db:
        token = db.scalar(select(Token))
        assert token.digest == digest(raw)
        assert raw != token.digest
    assert client.get('/verify-email?token=' + raw).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.emby_id == 'user-1')).email is None
    assert post(client, '/verify-email', {'token': raw}, '/verify-email?token=' + raw).status_code == 200
    assert client.get('/verify-email?token=' + raw).status_code == 400
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.emby_id == 'user-1')).email == 'new@example.com'

def test_forgot_generic_reset_single_use_and_invalidation(client, sent, fake):
    prepare_user(client)
    logout(client)
    known = post(client, '/forgot', {'email': 'demo@example.com'}, '/forgot')
    unknown = post(client, '/forgot', {'email': 'nobody@example.com'}, '/forgot')
    assert known.status_code == unknown.status_code == 200
    assert known.text == unknown.text
    main.deliver_mail()
    raw = sent[0][2]['link'].split('token=')[1]
    token_csrf = csrf(client, '/reset?token=' + raw)
    data = {'csrf': token_csrf, 'token': raw, 'password': 'ResetPassword123!', 'confirm': 'ResetPassword123!'}
    assert client.post('/reset', data=data).status_code == 200
    assert fake.changes[-1] == ('user-1', 'ResetPassword123!', None)
    assert client.post('/reset', data=data).status_code == 400

def test_expired_token_and_disabled_remote_cannot_reset(client, fake):
    prepare_user(client)
    raw = reset_token()
    with SessionLocal() as db:
        db.execute(update(Token).values(expires=main.now()-1))
        db.commit()
    assert client.get('/reset?token=' + raw).status_code == 400
    raw = reset_token()
    fake.disabled = True
    assert post(client, '/reset', {'token': raw, 'password': 'ResetPassword123!', 'confirm': 'ResetPassword123!'}, '/reset?token=' + raw).status_code == 403
    assert fake.changes == []

def test_atomic_token_consumption(client):
    prepare_user(client)
    raw = reset_token()
    def redeem():
        with SessionLocal() as db:
            token = db.get(Token, digest(raw))
            try:
                main.consume(db, token)
                return True
            except main.HTTPException:
                return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: redeem(), range(2))) == [False, True]

def test_rate_limit_login_and_reset(client):
    setup(client)
    logout(client)
    token_csrf = csrf(client)
    for _ in range(10):
        assert client.post('/login', data={'csrf': token_csrf, 'name': 'wrong', 'password': 'wrong'}).status_code == 401
    assert client.post('/login', data={'csrf': token_csrf, 'name': 'wrong', 'password': 'wrong'}).status_code == 429
    for _ in range(5):
        assert post(client, '/forgot', {'email': 'unknown@example.com'}, '/forgot').status_code == 200
    assert post(client, '/forgot', {'email': 'unknown@example.com'}, '/forgot').status_code == 429

def test_branding_menu_smtp_encryption_and_template_validation(client):
    setup(client)
    response = post(client, '/admin/settings', {'app_name': 'Usarr', 'login_text': '<script>alert(1)</script>', 'logo_url': 'https://example.com/logo.png', 'public_url': 'http://testserver', 'emby_link': 'https://emby.example.com'}, '/admin')
    assert response.status_code == 303
    assert post(client, '/admin/menu', {'label': 'Seerr', 'url': 'javascript:alert(1)', 'icon': 'link', 'position': '1'}, '/admin').status_code == 400
    assert post(client, '/admin/menu', {'label': 'Seerr', 'url': 'https://requests.example.com', 'icon': 'link', 'position': '1', 'new_tab': 'on'}, '/admin').status_code == 303
    assert post(client, '/admin/smtp', {'smtp_host': 'smtp.example.com', 'smtp_port': '587', 'smtp_mode': 'starttls', 'smtp_username': 'smtp-user', 'smtp_password': 'smtp-secret', 'smtp_from': 'portal@example.com'}, '/admin').status_code == 303
    assert 'smtp-secret' not in client.get('/admin').text
    with SessionLocal() as db:
        encoded = db.get(Config, 'smtp_password').value
        assert encoded != 'smtp-secret' and decrypt(encoded) == 'smtp-secret'
    bad = dict(main.DEFAULTS)
    bad['reset_body'] = '${untrusted}'
    assert post(client, '/admin/mail-templates', bad, '/admin').status_code == 400
    logout(client)
    assert '&lt;script&gt;' in client.get('/login').text
    login_user(client)
    page = client.get('/account').text
    assert 'Usarr' in page and 'Seerr' in page and 'noopener noreferrer' in page

def test_failed_mail_retries_without_exposing_secrets(client, monkeypatch):
    prepare_user(client)
    post(client, '/forgot', {'email': 'demo@example.com'}, '/forgot')
    def fail(*args):
        raise RuntimeError('private SMTP credentials')
    monkeypatch.setattr(main, 'send', fail)
    main.deliver_mail()
    with SessionLocal() as db:
        job = db.scalar(select(MailJob))
        assert job.attempts == 1 and job.next_attempt > main.now()

def test_linked_admin_uses_normal_email_recovery(client):
    setup(client)
    smtp(client)
    logout(client)
    assert post(client, '/forgot', {'email': 'owner@example.com'}, '/forgot').status_code == 200
    with SessionLocal() as db:
        token=db.scalar(select(Token))
        assert token and token.purpose=='reset'
        assert db.get(User,token.user_id).emby_id=='admin-1'

def test_health_and_migration_schema(client):
    assert client.get('/healthz').json() == {'status': 'ok'}
    with SessionLocal() as db:
        assert db.execute(main.text('SELECT version_num FROM alembic_version')).scalar() == '0014'


def test_form_limits_and_null_origin(client):
    setup(client)
    token_csrf = csrf(client, '/admin')
    assert client.post('/logout', data={'csrf': token_csrf}, headers={'origin': 'null'}).status_code == 403
    assert client.post('/admin/menu', data={'csrf': token_csrf}).status_code == 400
    assert client.post('/logout', content=b'x' * 65537, headers={'content-type': 'application/x-www-form-urlencoded'}).status_code == 413
    assert client.post('/logout', data={'csrf': token_csrf}, headers={'origin': 'http://testserver'}, follow_redirects=False).status_code == 303


def test_migration_downgrade_and_upgrade(client):
    from alembic import command
    from alembic.config import Config as AlembicConfig
    from sqlalchemy import inspect
    from app.db import engine
    configuration = AlembicConfig('alembic.ini')
    command.downgrade(configuration, 'base')
    assert inspect(engine).get_table_names() == ['alembic_version']
    command.upgrade(configuration, 'head')
    assert 'mail_jobs' in inspect(engine).get_table_names()
    assert client.get('/healthz').status_code == 200
