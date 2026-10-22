import json,time,re
from html.parser import HTMLParser
from sqlalchemy import select
from app import main,versioning
from app.db import SessionLocal
from app.models import Config
from app.release import VERSION
from app.mailer import compose
from test_portal import setup,post
from test_release_footer import remote


def test_update_cache_is_reinterpreted_after_upgrade_without_network(client):
    setup(client)
    with SessionLocal() as db:
        main.set_config(db,'release_check',json.dumps({'available':True,'state':'success','version':VERSION,'checked_at':int(time.time()),'checked_version':'0.3.3'}));db.commit()
        assert not versioning.status(db)['available']
    assert 'class="update-notice"' not in client.get('/account').text
    assert 'class="update-banner"' not in client.get('/admin/updates').text
    with SessionLocal() as db:
        main.set_config(db,'release_check',json.dumps({'available':True,'state':'error','version':'0.3.3'}));db.commit()
        assert not versioning.status(db)['available']
        main.set_config(db,'release_check','[]');db.commit()
        assert versioning.status(db)['state']=='unchecked'


def test_upgrade_invalidates_check_interval_but_identical_rebuild_is_not_an_update(client,monkeypatch):
    setup(client);calls=remote(monkeypatch,version=VERSION)
    monkeypatch.setattr(versioning,'BUILD_REVISION','a'*40)
    with SessionLocal() as db:
        main.set_config(db,'release_check',json.dumps({'available':True,'state':'success','version':VERSION,'checked_at':int(time.time()),'checked_version':'0.3.3'}));db.commit()
        state=versioning.check(db)
        assert state['checked_version']==VERSION and not state['available']
        assert len(calls)==1 # No commit/tag comparison for an identical version.
        versioning.check(db);assert len(calls)==1


class ReleaseDetails(HTMLParser):
    def __init__(self):super().__init__();self.entries=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='details' and 'data-release-version' in attrs:self.entries.append((attrs['data-release-version'],'open' in attrs))


def test_updates_only_expand_installed_release_and_do_not_duplicate_github_notes(client,monkeypatch):
    setup(client);entry={'version':VERSION,'date':'2026-10-22','changes':['Current changes']}
    monkeypatch.setattr(versioning,'CHANGELOG',[entry,entry,{'version':'0.3.3','date':'2026-10-22','changes':['Older changes']}])
    with SessionLocal() as db:
        main.set_config(db,'release_check',json.dumps({'state':'success','version':'0.3.5','available':True,'notes':'Duplicated GitHub notes'}));db.commit()
    page=client.get('/admin/updates').text;parser=ReleaseDetails();parser.feed(page)
    assert parser.entries==[(VERSION,True),('0.3.3',False)]
    assert 'Duplicated GitHub notes' not in page
    assert 'updates-overview' in page and 'update-feedback' in page and 'update-reset' in page
    assert 'sync-green">● Current version' in page


def test_email_image_width_survives_save_reload_and_multipart_render(client):
    setup(client)
    content='<img src="https://example.com/banner.png" width="180" style="width:180px;max-width:100%;height:auto" alt="Banner"><p><a href="${link}">Reset</a></p>'
    assert post(client,'/admin/mail-editor',{'purpose':'reset','mail_locale':'en','subject':'Reset ${app_name}','html':content},'/admin/mail-editor').status_code==303
    page=client.get('/admin/mail-editor?purpose=reset').text
    assert 'mail-template-selector' in page
    assert 'width=&#34;180&#34;' in page or 'width="180"' in page or 'width=&quot;180&quot;' in page
    with SessionLocal() as db:
        message=compose(db,'member@example.com','reset',{'app_name':'Gatearr','username':'Alex','link':'https://portal.test/reset?token=example','minutes':'30','_locale':'en'})
    html=message.get_body(preferencelist=('html',)).get_content()
    assert 'width="180"' in html
    assert re.search(r'max-width:\s*100%',html)
    from app.rich_mail import clean
    assert 'expression' not in clean('<img src="https://example.com/a.png" style="width:expression(alert(1))">')
    assert 'https://portal.test/reset?token=example' in html
