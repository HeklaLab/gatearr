import json,time
from types import SimpleNamespace
from contextlib import contextmanager
import httpx,pytest
from sqlalchemy import select
from app import main,themes,widgets,tracearr,captcha,library_updates
from app.db import SessionLocal
from app.models import User,Config,GroupMember,PermissionGroup,CaptchaToken,LibraryEvent,LibraryPreference,MailJob,PortalCache
from app.security import digest,encrypt
from app.integrations import SyncError
from test_portal import setup,post,csrf

def block(kind='widget_media',**kw):return {'id':'widget','kind':kind,'region':'main','span':4,'order':10,**kw}
def cfg(db,**values):
    for k,v in values.items():main.set_config(db,k,v)
    db.commit()
def member(db):return db.scalar(select(User).where(User.emby_id=='user-1'))

def test_six_presets_preserve_customizations_and_css_policy(client):
    setup(client)
    assert len(themes.PRESETS)==3
    with SessionLocal() as db:
        for p in themes.PRESETS.values():themes.validate({'mode':'user','preset':'boreal','dark':p['dark'],'light':p['light']})
        v=themes.load(db);v['mode']='user';v['light']['accent']='#123456';cfg(db,themes_published=json.dumps(v))
        u=member(db);u.theme_preference='auto'
        assert '@media(prefers-color-scheme:dark)' in themes.css(db,u)
        u.theme_preference='light';assert '#123456' in themes.css(db,u)
        u.theme_preference='dark';assert 'color-scheme:dark' in themes.css(db,u)
    assert 'theme-capsule' in client.get('/home').text
    assert post(client,'/account/theme',{'theme':'light','next':'//evil.example'},'/account').headers['location']=='/account'

def test_preset_applies_both_palettes_with_revision_and_undo(client):
    setup(client)
    assert post(client,'/admin/branding/themes',{'version':0,'preset':'electric-lime'},'/admin/branding/themes').status_code==303
    with SessionLocal() as db:
        v=themes.load(db,True);assert v['preset']=='electric-lime' and v['light']['accent']=='#c5f52c'
    assert post(client,'/admin/branding/themes',{'version':0,'preset':'neon-rose'},'/admin/branding/themes').status_code==409
    assert post(client,'/admin/branding/themes',{'version':1,'action':'undo'},'/admin/branding/themes').status_code==303
    with SessionLocal() as db:assert themes.load(db,True)['preset']=='boreal'


def test_widget_group_role_precedence_and_overlap(client):
    setup(client)
    with SessionLocal() as db:
        u=member(db);g=PermissionGroup(name='Family');db.add(g);db.flush();db.add(GroupMember(group_id=g.id,user_id=u.id));db.flush()
        choices=[block(id='general'),block(id='role',visibility='members'),block(id='group',groups=[g.id])]
        assert widgets.choose(db,choices,u)=={'group'}
        assert widgets.conflicts([block(id='a'),block(id='b')])
        assert not widgets.conflicts([block(id='a'),block(id='b',priority=1)])
        with pytest.raises(ValueError):widgets.validate(block(metrics=['secret']))
        with pytest.raises(ValueError):widgets.validate(block(show_logo='true'))


@pytest.mark.parametrize('metric,kind,total',[('movies','Movie',13),('series','Series',7),('movies','Movie',0)])
def test_media_widget_counts_current_user_without_admin_library_selection(client,monkeypatch,metric,kind,total):
    setup(client);calls=[]
    def api(method,path,**kw):
        calls.append((path,kw.get('params',{})))
        return {'TotalRecordCount':total}
    monkeypatch.setattr(widgets,'emby',SimpleNamespace(request=api))
    with SessionLocal() as db:
        u=member(db)
        # Old saved selections must not restrict or broaden the native user query.
        value=widgets.media_metrics(db,u,block(libraries=['films','private','duplicate'],metrics=[metric]))
        assert value['metrics']==[{'label':widgets.METRICS['widget_media'][metric],'value':total}]
        assert calls==[('/Users/'+u.emby_id+'/Items',{'Recursive':'true','IncludeItemTypes':kind,'Limit':0})]
        assert 'libraries' not in value


def test_tracearr_identity_uses_server_and_external_id_only(client):
    setup(client)
    with SessionLocal() as db:
        u=member(db);cfg(db,tracearr_server_id='server-a')
        users=[{'id':'person-a','username':u.name,'accounts':[{'server_id':'server-b','server_type':'emby','external_user_id':u.emby_id}]},{'id':'person-b','username':'different','accounts':[{'server_id':'server-a','server_type':'emby','external_user_id':u.emby_id}]}]
        with httpx.Client(base_url='http://tracearr/',transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'data':users}))) as c:
            assert tracearr.identity(db,u,c)==('person-b','server-a')
        users.append(users[-1])
        with httpx.Client(base_url='http://tracearr/',transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'data':users}))) as c:
            with pytest.raises(SyncError):tracearr.identity(db,u,c)


def test_tracearr_cursor_pagination_and_cycle_guard():
    seen=[]
    def api(req):
        seen.append(req.url.params.get('cursor'))
        return httpx.Response(200,json={'data':[{'id':len(seen)}],'meta':{'nextCursor':'next' if len(seen)==1 else None}})
    with httpx.Client(base_url='http://tracearr/',transport=httpx.MockTransport(api)) as c:assert len(tracearr.rows(c,'users'))==2
    assert seen==[None,'next']
    with httpx.Client(base_url='http://tracearr/',transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'data':[],'meta':{'nextCursor':'same'}}))) as c:
        with pytest.raises(SyncError):tracearr.rows(c,'users')


def test_tracearr_history_rejects_foreign_account_payload(client,monkeypatch):
    setup(client);monkeypatch.setattr(tracearr,'identity',lambda *a:('person','server'))
    with SessionLocal() as db,httpx.Client(base_url='http://tracearr/',transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'data':[{'server_id':'other','user':{'id':'person'}}]}))) as c:
        with pytest.raises(SyncError):tracearr.history(db,member(db),c)


def test_captcha_is_scoped_single_use_expiring_and_fail_closed(client,monkeypatch):
    setup(client)
    with SessionLocal() as db:cfg(db,captcha_login='true',captcha_forgot='true')
    monkeypatch.setattr(captcha,'call',lambda action,scope,body=None:{'success':True,'nonce':'a'*64,'token':'redeemed-token','expires':(int(time.time())+60)*1000})
    r=client.post('/captcha/login/redeem',json={'token':'challenge'},headers={'Origin':'http://testserver'});assert r.json()['success']
    assert not client.post('/captcha/login/redeem',json={'token':'challenge'},headers={'Origin':'http://testserver'}).json()['success']
    wrong=post(client,'/forgot',{'email':'nobody@example.com','cap-token':'redeemed-token'},'/forgot');assert wrong.status_code==400
    assert post(client,'/login',{'name':'no','password':'bad','cap-token':'redeemed-token'},'/login').status_code==401
    assert post(client,'/login',{'name':'no','password':'bad','cap-token':'redeemed-token'},'/login').status_code==400
    assert client.post('/captcha/login/challenge',headers={'Origin':'https://evil.example'}).status_code==403


def test_captcha_assets_local_and_csp_uses_nonce_not_unsafe_inline(client):
    setup(client)
    with SessionLocal() as db:cfg(db,captcha_login='true')
    r=client.get('/login');assert '/static/cap/cap.min.js' in r.text and 'cap-widget' in r.text
    csp=r.headers['content-security-policy'];assert "'wasm-unsafe-eval'" in csp and "'nonce-" in csp and "worker-src 'self' blob:" in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp
    assert client.get('/static/cap/hashwx.wasm').status_code==200


def test_missing_tracearr_hides_notifications_and_mail_template(client):
    setup(client)
    assert 'Notify me about new seasons' not in client.get('/account').text
    assert client.get('/admin/mail-editor?purpose=new_season').status_code==404
    assert 'href="/admin/mail-editor?purpose=new_season"' not in client.get('/admin/emails').text
    assert post(client,'/account/library-notifications',{'email':'on','seasons':'on'},'/account').status_code==409
    with SessionLocal() as db:cfg(db,tracearr_enabled='true',tracearr_url='http://tracearr',tracearr_api_key=encrypt('test'))
    assert 'New seasons of my series' not in client.get('/account').text
    from test_portal import smtp
    smtp(client)
    assert 'New seasons of my series' in client.get('/account').text
    assert client.get('/admin/mail-editor?purpose=new_season').status_code==200
    assert 'href="/admin/mail-editor?purpose=new_season"' in client.get('/admin/emails').text


def test_tdarr_has_no_api_key_and_requires_explicit_admin_grant(client):
    setup(client)
    result=post(client,'/admin/connections/tdarr/save',{'enabled':'on','url':'http://tdarr:8265','public_url':'https://tdarr.example','interface_enabled':'on'},'/admin/integrations');assert result.status_code==303
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)));owner.tool_access='["tdarr"]';db.commit()
    page=client.get('/tools/tdarr');assert page.status_code==200 and 'src="/tools/tdarr/app/tdarr/"' in page.text
    assert "frame-src 'self';" in page.headers['content-security-policy']
    assert "https://tdarr.example" not in page.headers['content-security-policy']
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)));owner.tool_access='[]';db.commit()
    assert client.get('/tools/tdarr').status_code==403


def test_season_baseline_dedup_and_watched_removal(client,monkeypatch):
    setup(client);seasons=[{'Id':'s4','SeriesId':'show','SeriesName':'Fargo','IndexNumber':4}]
    with SessionLocal() as db:cfg(db,tracearr_enabled='true',tracearr_url='http://tracearr',tracearr_api_key=encrypt('key'))
    @contextmanager
    def fake_connection(db):yield object()
    monkeypatch.setattr(tracearr,'connection',fake_connection)
    monkeypatch.setattr(tracearr,'history',lambda *a:[{'grandparent_rating_key':'show','duration_ms':1000,'rating_key':'ep5','watched':True}])
    episodes=[]
    monkeypatch.setattr(widgets,'items',lambda user,kind,*a,**kw:seasons if kind=='Season' else episodes)
    with SessionLocal() as db:
        u=member(db);library_updates.sync_user(db,u);assert not list(db.scalars(select(LibraryEvent)))
        seasons.append({'Id':'s5','SeriesId':'show','SeriesName':'Fargo','IndexNumber':5})
        library_updates.sync_user(db,u);assert not list(db.scalars(select(LibraryEvent)))
        episodes.append({'Id':'ep5'})
        library_updates.sync_user(db,u);library_updates.sync_user(db,u)
        events=list(db.scalars(select(LibraryEvent)));assert len(events)==1 and events[0].watched
        assert events[0].title=='Fargo' and json.loads(events[0].data)['episode_ids']==['ep5']


def test_season_email_delivery_rechecks_dependency_and_preferences(client,monkeypatch,sent):
    setup(client)
    with SessionLocal() as db:
        u=member(db);u.email='member@example.com';cfg(db,tracearr_enabled='true',tracearr_url='http://tracearr',tracearr_api_key=encrypt('key'),smtp_host='smtp')
        pref=widgets.preference(db,u);pref.email=True
        event=library_updates.add_event(db,u,library_updates.source_fingerprint(db),'season','season5','Fargo',{'season':5,'episode_ids':['ep5']})
        monkeypatch.setattr(library_updates,'event_accessible',lambda *a:True)
        library_updates.enqueue_season(db,u,event,pref);library_updates.enqueue_season(db,u,event,pref);db.commit()
        assert len(list(db.scalars(select(MailJob))))==1
        cfg(db,tracearr_enabled='false')
    main.deliver_mail();assert not sent
    with SessionLocal() as db:assert not list(db.scalars(select(MailJob)))


def test_library_feed_is_private_and_checks_native_access(client,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)));other=member(db)
        event=library_updates.add_event(db,other,library_updates.source_fingerprint(db),'request','movie1','Private movie',{'episode_ids':['movie1'],'request_id':12});db.commit();key=event.key
    assert client.get('/library/open/'+key).status_code==404


def test_personalized_season_mail_variables_are_sanitized(client):
    setup(client)
    from app.mailer import compose
    from app.rich_mail import validate
    with SessionLocal() as db:
        validate('<p>${title} — ${season}</p><a href="${link}">Open</a>',html=True)
        msg=compose(db,'x@example.com','new_season',{'app_name':'Gatearr','username':'Member','title':'Fargo','season':'5','link':'https://gatearr.example/library/open/key','minutes':'30','_locale':'en'})
        assert 'Fargo' in str(msg['Subject']) and '5' in msg.get_content()


def test_captcha_instrumentation_is_isolated_from_parent_eval_policy(client):
    setup(client)
    with SessionLocal() as db:cfg(db,captcha_forgot='true')
    parent=client.get('/forgot');frame=client.get('/captcha/frame')
    assert "'unsafe-eval'" not in parent.headers['content-security-policy']
    assert "'unsafe-eval'" in frame.headers['content-security-policy']
    assert "frame-ancestors 'self'" in frame.headers['content-security-policy']
    assert frame.headers['x-frame-options']=='SAMEORIGIN'
    assert '/static/cap-frame.js' in frame.text
    widget=client.get('/static/cap/cap.min.js').text
    assert 'sandbox","allow-scripts"' in widget and '/captcha/frame' in widget


def test_tracearr_bandwidth_units_chart_and_top_series(client,monkeypatch):
    setup(client)
    @contextmanager
    def fake_connection(db):yield object()
    monkeypatch.setattr(tracearr,'connection',fake_connection)
    monkeypatch.setattr(tracearr,'history',lambda *a:[{'duration_ms':8000000,'bitrate':1000,'show_title':'Fargo','started_at':'2026-10-22T00:00:00Z','is_transcode':False}])
    with SessionLocal() as db:
        value=widgets.tracearr_metrics(db,member(db),block('widget_tracearr',metrics=['bandwidth','favorite','activity']))
        assert value['metrics'][0]['value']=='1.00 GB' # kbps × milliseconds / 8 = bytes
        assert value['metrics'][1]['value']=='Fargo' and value['chart'][0]['hours']==2.22


@pytest.mark.parametrize('locale',['ar','cs','da','de','es','fi','fr','he','it','ja','ko','nb','nl','pl','pt-br','ru','sv','tr','uk','zh-cn'])
def test_new_season_mail_is_localized_and_retains_placeholders(locale):
    from app import i18n
    from app.mailer import DEFAULTS
    from string import Template
    pack=i18n.CATALOGS[locale]
    for key in ('Library updates','Library notifications','Show application logo','Connection status','Validated challenges'):
        assert pack.get(key) and pack[key]!=key
    text=pack[DEFAULTS['new_season_body']]
    assert text!=DEFAULTS['new_season_body']
    assert '${link}' in text and '${title}' in text and '${season}' in text
    Template(text).substitute(app_name='Gatearr',username='Member',title='Fargo',season=5,link='https://example.com')


def test_native_disabled_account_cannot_read_widget_cache(client,monkeypatch):
    setup(client)
    monkeypatch.setattr(widgets,'emby',SimpleNamespace(user=lambda uid:{'Policy':{'IsDisabled':True}}))
    with SessionLocal() as db:assert widgets.display(db,member(db),block()) is None


def test_seerr_library_updates_do_not_depend_on_tracearr_health(client,monkeypatch):
    setup(client)
    import app.seerr_permissions as seerr
    with SessionLocal() as db:cfg(db,tracearr_enabled='true',tracearr_url='http://tracearr',tracearr_api_key=encrypt('key'),seerr_enabled='true',seerr_url='http://seerr',seerr_api_key=encrypt('key'))
    @contextmanager
    def unavailable(db):raise SyncError('unavailable');yield
    @contextmanager
    def connected(db,user):yield object(),12
    monkeypatch.setattr(tracearr,'connection',unavailable)
    monkeypatch.setattr(seerr,'connection',connected)
    monkeypatch.setattr(library_updates,'request',lambda *a,**kw:{'results':[]})
    with SessionLocal() as db:
        u=member(db);library_updates.sync_user(db,u)
        assert library_updates.snapshot(db,f'requests:{library_updates.source_fingerprint(db)}:{u.id}')==[]

@pytest.mark.parametrize('period,start,label',[
    ('week','2026-10-26T00:00:00+00:00','This week'),
    ('month','2026-11-01T00:00:00+00:00','This month'),
    ('30days','2026-10-02T12:00:00+00:00','Last 30 days'),
])
def test_tracearr_period_caption_matches_the_actual_query(client,monkeypatch,period,start,label):
    from datetime import datetime,timezone
    setup(client)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return datetime(2026,11,1,12,tzinfo=timezone.utc)
    monkeypatch.setattr(widgets,'datetime',Clock)
    calls=[]
    @contextmanager
    def fake_connection(db):yield object()
    def history(db,user,connection,params):
        calls.append(params);return []
    monkeypatch.setattr(tracearr,'connection',fake_connection)
    monkeypatch.setattr(tracearr,'history',history)
    with SessionLocal() as db:
        b=block('widget_tracearr',metrics=['comparison'],period=period)
        result=widgets.tracearr_metrics(db,member(db),b)
        assert calls[0]['since']==start
        assert result['period_start']==start[:10] and result['period_end']=='2026-11-01'
        b.update(title='',widget=result)
        html=main.templates.env.get_template('widget.html').render(block=b,_=lambda text:text)
        assert label in html
        assert 'datetime="'+start[:10]+'"' in html and 'datetime="2026-11-01"' in html
