"""SMTP history spans all send paths, including failed attempts and rolled-back drafts."""
import smtplib
from types import SimpleNamespace
import pytest
from sqlalchemy import select,func
from app import main,mailer
from app.db import SessionLocal
from app.models import MailDelivery,Config,User
from test_portal import setup,smtp,post,logout,login_user
from test_rich_mail import edit


@pytest.fixture
def transport(monkeypatch):
    state=SimpleNamespace(messages=[],fail=None,quit_error=False,refused=None)
    class SMTP:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):
            if state.quit_error:raise smtplib.SMTPServerDisconnected('private-connection-detail')
        def ehlo(self):pass
        def starttls(self,**kwargs):pass
        def login(self,*args):pass
        def send_message(self,message):
            if state.fail:raise state.fail
            state.messages.append(message)
            return state.refused
    monkeypatch.setattr(mailer.smtplib,'SMTP',SMTP);monkeypatch.setattr(mailer.smtplib,'SMTP_SSL',SMTP)
    return state


def values(**extra):return dict(app_name='Gatearr',username='Alex',link='https://example.com/reset?token=private-recovery-token',minutes='30',title='Series',season='2',**extra)


def records():
    with SessionLocal() as db:return list(db.scalars(select(MailDelivery).order_by(MailDelivery.id)))


@pytest.mark.parametrize('mode',['plain','starttls','ssl'])
def test_records_real_acceptance_for_each_smtp_transport(client,transport,mode):
    setup(client);smtp(client)
    with SessionLocal() as db:
        main.set_config(db,'smtp_mode',mode);db.commit()
        for purpose in mailer.DEFAULTS:
            if not purpose.endswith('_subject'):continue
            mailer.send(db,'alex@example.com',purpose.removesuffix('_subject'),values())
    rows=records()
    assert len(rows)==len(transport.messages)==6
    assert all(r.state=='accepted' and not r.error and r.recipient=='alex@example.com' for r in rows)
    assert next(r for r in rows if r.purpose=='new_season').context=='notification'
    assert set(r.purpose for r in rows)=={'invite','verify','reset','email_changed','password_changed','new_season'}


@pytest.mark.parametrize('ending',['commit','rollback','close'])
def test_delivery_log_survives_outer_transaction_without_persisting_other_edits(client,transport,ending):
    setup(client);smtp(client)
    with SessionLocal() as db:
        db.add(Config(key='unrelated-change',value='draft'));db.flush()
        mailer.send(db,'alex@example.com','verify',values())
        if ending=='commit':db.commit()
        elif ending=='rollback':db.rollback()
    assert len(records())==1
    with SessionLocal() as db:assert (db.get(Config,'unrelated-change') is not None)==(ending=='commit')


def test_unsaved_template_test_logs_exact_subject_without_saving_draft(client,transport):
    setup(client);smtp(client)
    response=edit(client,action='test',subject='Unsaved message for ${username}')
    assert response.status_code==200
    rows=records();assert len(rows)==1 and rows[0].context=='template_test'
    assert rows[0].subject=='Unsaved message for Owner' and rows[0].state=='accepted'
    with SessionLocal() as db:assert db.get(Config,'invite_subject') is None


def test_smtp_test_is_logged_but_connection_probe_is_not(client,transport):
    setup(client);smtp(client)
    assert post(client,'/admin/smtp-test',{},'/admin/emails').status_code==200
    assert len(records())==1 and records()[0].context=='smtp_test'
    assert post(client,'/admin/smtp-connection-test',{},'/admin/emails').status_code==303
    assert len(records())==1


@pytest.mark.parametrize('failure,error',[(smtplib.SMTPAuthenticationError(535,b'private-auth-secret'),'authentication'),(smtplib.SMTPRecipientsRefused({'alex@example.com':(550,b'private-token')}),'recipients'),(smtplib.SMTPSenderRefused(550,b'private-token','sender@example.com'),'sender'),(smtplib.SMTPDataError(550,b'private-token'),'data'),(OSError('private-host'),'connection')])
def test_failed_attempt_is_logged_without_remote_error_or_secrets(client,transport,failure,error):
    setup(client);smtp(client);transport.fail=failure
    with pytest.raises(type(failure)):
        with SessionLocal() as db:mailer.send(db,'alex@example.com','reset',values())
    rows=records();assert len(rows)==1 and rows[0].state=='failed' and rows[0].error==error
    page=client.get('/admin/activity/mail').text
    for private in ('private-auth-secret','private-token','private-host','private-recovery-token'):assert private not in page


def test_refused_recipients_and_quit_failure_have_correct_acceptance(client,transport):
    setup(client);smtp(client);transport.refused={'alex@example.com':(550,b'private-response')}
    with pytest.raises(smtplib.SMTPRecipientsRefused):
        with SessionLocal() as db:mailer.send(db,'alex@example.com','verify',values())
    transport.refused=None;transport.quit_error=True
    with SessionLocal() as db:mailer.send(db,'alex@example.com','verify',values())
    assert [r.state for r in records()]==['failed','accepted']


def test_subject_redaction_html_escaping_and_admin_boundaries(client,transport):
    setup(client);smtp(client)
    with SessionLocal() as db:
        main.set_config(db,'verify_subject','<script>Test</script> ${link} private-recovery-token');db.commit()
        mailer.send(db,'alex@example.com','verify',values())
    row=records()[0];assert 'private-recovery-token' not in row.subject and '[private]' in row.subject
    page=client.get('/admin/activity/mail').text
    assert '&lt;script&gt;Test&lt;/script&gt;' in page and '<script>Test</script>' not in page
    assert 'private-recovery-token' not in page
    assert 'href="/admin/activity/mail"' in client.get('/admin/emails').text
    assert 'Email log' in client.get('/admin/activity').text
    logout(client);login_user(client)
    assert client.get('/admin/activity/mail').status_code==403
    logout(client)
    assert client.get('/admin/activity/mail',follow_redirects=False).status_code==401


def test_cursor_pagination_is_stable_and_history_is_not_bound_to_queue_or_users(client):
    setup(client)
    with SessionLocal() as db:
        db.add_all([MailDelivery(at=1,recipient='deleted@example.com',subject=f'Message {i}',purpose='verify',context='transactional',state='accepted',error='') for i in range(55)]);db.commit()
    first=client.get('/admin/activity/mail').text
    assert 'Message 54' in first and 'Message 5' in first and 'Message 4<' not in first
    assert 'before=6' in first
    older=client.get('/admin/activity/mail?before=6').text
    assert 'Message 4' in older and 'Message 0' in older and 'Older emails' not in older
    assert client.get('/admin/activity/mail?before=invalid').status_code==422
    assert client.get('/admin/activity/mail?before=-1').status_code==422


def test_queued_transactional_mail_uses_same_history(client,transport):
    setup(client);smtp(client)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'));user.email='alex@example.com';db.commit()
        raw=main.issue_token(db,user,'reset');main.enqueue_mail(db,'reset',raw,user.email)
    main.deliver_mail()
    assert len(records())==1 and records()[0].purpose=='reset' and records()[0].state=='accepted'
    assert raw not in records()[0].subject


def test_mail_log_migration_preserves_existing_configuration(tmp_path):
    import os,sqlite3,subprocess,sys
    database=tmp_path/'before-mail-log.db';env={**os.environ,'DATABASE_URL':'sqlite:///'+str(database)}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0022'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as connection:connection.execute("insert into config(key,value) values('app_name','Keep my portal')");connection.commit()
    subprocess.run([sys.executable,'-m','alembic','upgrade','0023'],env=env,check=True,capture_output=True)
    with sqlite3.connect(database) as connection:
        assert connection.execute("select value from config where key='app_name'").fetchone()[0]=='Keep my portal'
        assert connection.execute('select count(*) from mail_deliveries').fetchone()[0]==0
        assert connection.execute('select version_num from alembic_version').fetchone()[0]=='0023'
