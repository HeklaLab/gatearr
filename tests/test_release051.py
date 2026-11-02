"""0.5.1 contracts: purpose-aware mail, guide scopes/breadcrumbs and safe live health."""
import asyncio
import json
import time
import pytest
from sqlalchemy import select
from app import main,portal,page_builder,page_presets,visual_builder,connection_health,i18n
from app.db import SessionLocal
from app.models import Config,Guide,ConnectionCheck,AccessService,MenuItem,User
from app.rich_mail import validate
from app.mailer import DEFAULTS
from test_portal import setup,post,logout,login_user
from test_content_pages import save_page
from test_application_behavior import row,state,write

@pytest.mark.parametrize('purpose',['invite','verify','reset','email_changed','password_changed','new_season'])
def test_template_link_requirement_matches_purpose_in_all_actions(client,monkeypatch,purpose):
    setup(client)
    # The seasonal template is offered only when Tracearr is configured.
    monkeypatch.setattr('app.tracearr.configured',lambda db:True)
    monkeypatch.setattr('app.email_editor.send',lambda *a,**kw:None)
    body='<p>Notification for ${username}</p><p style="font-size:24px">Saved formatting</p>'
    required=purpose in ('invite','verify','reset')
    for action in ('preview','save','test'):
        response=post(client,'/admin/mail-editor',dict(purpose=purpose,mail_locale='en',subject='Account update',html=body,action=action),'/admin/mail-editor')
        assert response.status_code==(400 if required else 303 if action=='save' else 200),response.text
    response=post(client,'/admin/mail-templates',{**{k:DEFAULTS[k] for k in ('reset_subject','reset_body','verify_subject','verify_body')},purpose+'_body':'Notification without a link'},'/admin')
    assert response.status_code==(400 if required else 303)
    if not required:
        with SessionLocal() as db:assert main.config(db,purpose+'_body')=='Notification without a link'
    with pytest.raises(ValueError):validate('<p>${unknown}</p>',html=True,purpose=purpose)
    assert 'script' not in validate(body+'<script>bad()</script><a href="${link}">Continue</a>',html=True,purpose=purpose)

@pytest.mark.parametrize('service',['emby','seerr'])
def test_guide_scope_and_breadcrumb_survive_publication(client,service):
    setup(client);client.get('/admin/pages')
    with SessionLocal() as db:
        app=db.get(AccessService,service)
        if not app:app=AccessService(key=service,name=service.title(),entry_mode='structured',browser_url='https://example.test');db.add(app)
        content=dict(title='Editable guide title',summary='',device='other',steps=[dict(id='s1',title='Install',body='<p><span style="font-size:24px;color:#123456">Instructions</span></p>',rich=True)])
        guide=Guide(service_key=service,draft=json.dumps(content),published=json.dumps(content),version=1);db.add(guide);db.flush();gid=guide.id
        app.access_published=json.dumps([dict(id='parent',kind='group',title='My computer',position=1,parent=''),dict(id='leaf',kind='guide',title='My Windows PC',position=2,parent='parent',guide_id=gid)])
        app.access_draft=app.access_published;app.entry_mode='structured';db.commit()
        page=page_builder.guide_row(db,service)
        if page is None:
            page_builder.ensure_defaults(db);db.commit();page=page_builder.guide_row(db,service)
        key='p-'+str(page.id);layout=visual_builder.load(db,key,True)
    layout['blocks']=[page_presets.block('text','intro',title='',body='LANDING INTRO',journey_scope='landing'),page_presets.block('accordion','faq',journey_scope='landing',items=[dict(id='a',question='LANDING FAQ',answer='Answer')]),page_presets.block('text','common',title='',body='COMMON CONTENT',journey_scope='all'),page_presets.block('guide_embed','guide',service_key=service)]
    assert save_page(client,key,layout,True).status_code==200
    landing=client.get('/access/'+service+'?view=guide');assert landing.status_code==200
    assert 'LANDING INTRO' in landing.text and 'LANDING FAQ' in landing.text
    for url in ['/access/'+service+'/parent?view=guide','/access/'+service+'/guide/'+str(gid)]:
        page=client.get(url);assert page.status_code==200,page.text
        assert 'LANDING INTRO' not in page.text and 'LANDING FAQ' not in page.text and 'COMMON CONTENT' in page.text
    final=client.get('/access/'+service+'/guide/'+str(gid)).text
    assert f'href="/access/{service}/parent?view=guide"' in final
    assert '<span aria-current="page">My Windows PC</span>' in final
    assert '<h1>Editable guide title</h1>' in final and 'Other device' not in final
    assert 'font-size:24px' in final
    preview=post(client,f'/admin/visual-guide/{gid}/preview',dict(version=1,payload=json.dumps(content)),'/admin')
    assert preview.status_code==200 and 'LANDING INTRO' not in preview.text and 'COMMON CONTENT' in preview.text
    layout['blocks'][0]['journey_scope']='all'
    assert save_page(client,key,layout,True).status_code==200
    assert 'LANDING INTRO' in client.get('/access/'+service+'/guide/'+str(gid)).text


def test_public_health_is_cached_safe_permission_filtered_and_independent(client,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        main.set_config(db,'radarr_enabled','true');main.set_config(db,'radarr_url','http://private.test');main.set_config(db,'radarr_api_key','test')
        db.merge(ConnectionCheck(service='emby',state='error',detail='SECRET HOST private.internal',checked_at=int(time.time())))
        db.add(MenuItem(label='Emby',url='https://custom.test',icon='link',menu_key='main',position=1,new_tab=True))
        db.commit()
    layout,version=state();layout['blocks']=[row('health','access:emby','guide')];layout['blocks'][0].update(show_status=False,warn_on_problem=True)
    assert write(client,layout,version).status_code==200
    home=client.get('/home').text
    assert 'data-application-health="access:emby"' in home and 'data-application-warning="access:emby"' in home
    assert 'This service is experiencing problems.' in home and 'SECRET HOST' not in home
    monkeypatch.setattr(connection_health,'probe',lambda *a:pytest.fail('A public read must not perform a probe'))
    response=client.get('/api/application-status');assert response.status_code==200
    assert response.headers['cache-control']=='no-store'
    assert response.json()['access:emby']=='offline' and not any(k.startswith('menu:') for k in response.json())
    logout(client);assert login_user(client).status_code==303
    statuses=client.get('/api/application-status').json();assert 'radarr' not in statuses
    with SessionLocal() as db:
        row_=db.get(ConnectionCheck,'emby');row_.checked_at=int(time.time())-151;db.commit()
        assert connection_health.public_status(db,'emby')=='unknown'
    logout(client);assert client.get('/api/application-status',follow_redirects=False).status_code in (303,401)


def test_health_monitor_runs_without_visitors_and_waits_one_minute(monkeypatch):
    calls=[];sleeps=[]
    monkeypatch.setattr(connection_health,'checks',lambda db,refresh=False: calls.append(refresh))
    async def stop_after_first(delay):sleeps.append(delay);raise asyncio.CancelledError()
    monkeypatch.setattr(asyncio,'sleep',stop_after_first)
    with pytest.raises(asyncio.CancelledError):asyncio.run(connection_health.monitor())
    assert calls==[True] and 59<=sleeps[0]<=60


def test_rich_sizes_are_safe_and_retained_in_page_accordion_and_guide_sanitizers():
    from app.footer import clean_html
    from app.accordion import clean_answer
    source='<p><span style="font-size:24px;color:#123456;position:fixed" onclick="bad()"><u>Hello</u></span></p><script>bad()</script>'
    for clean in (clean_html,clean_answer):
        value=clean(source);assert 'font-size:24px' in value and '<u>Hello</u>' in value
        assert 'onclick' not in value and 'position' not in value and 'bad()' not in value
    layout=json.loads(json.dumps(portal.DEFAULT));layout['blocks'][0]['journey_scope']='invalid'
    with pytest.raises(ValueError):portal.validate(layout)


def test_new_public_status_labels_exist_in_all_languages_and_are_editable():
    keys={'Online','Connection problem','Status unavailable','This service is experiencing problems. Access may be disrupted.','Breadcrumb'}
    assert keys<=i18n.PUBLIC_INTERFACE_KEYS
    for locale,catalog in i18n.CATALOGS.items():
        assert keys<=catalog.keys(),locale
        assert all(catalog[k] for k in keys)


def test_final_breadcrumb_keeps_the_branch_when_a_guide_is_reused(client):
    setup(client);client.get('/admin/pages')
    with SessionLocal() as db:
        service=db.get(AccessService,'emby')
        guide=db.scalar(select(Guide).where(Guide.service_key=='emby',Guide.published.is_not(None)))
        assert guide is not None
        gid=guide.id
        service.access_published=json.dumps([dict(id='phone',kind='group',title='Phones',position=1),dict(id='pc',kind='group',title='Computers',position=2),dict(id='first',kind='guide',title='Phone instructions',parent='phone',position=3,guide_id=gid),dict(id='second',kind='guide',title='PC instructions',parent='pc',position=4,guide_id=gid)])
        service.entry_mode='structured';db.commit()
    choices=client.get('/access/emby/pc?view=guide').text
    assert f'/access/emby/guide/{gid}?choice=second' in choices
    result=client.get(f'/access/emby/guide/{gid}?choice=second').text
    assert 'aria-current="page">PC instructions' in result
    assert 'href="/access/emby/pc?view=guide">Computers' in result
    assert 'href="/access/emby/phone?view=guide"' not in result


def test_background_checks_cover_all_enabled_apis_and_skip_disabled(client,monkeypatch):
    setup(client)
    from app.security import encrypt
    calls=[]
    def probe(service,values):
        calls.append(service)
        assert values['url'] and values['key']
        return ('error','Private diagnostic') if service=='radarr' else ('connected','Verified')
    monkeypatch.setattr(connection_health,'probe',probe)
    with SessionLocal() as db:
        for service in ('seerr','radarr','sonarr','bazarr','tracearr','tdarr'):
            main.set_config(db,service+'_enabled','true');main.set_config(db,service+'_url','http://local.test/'+service);main.set_config(db,service+'_api_key',encrypt('mock-key'))
        db.commit()
        outcomes=connection_health._checks(db,True)
        assert set(calls)=={'emby','seerr','radarr','sonarr','bazarr','tracearr','tdarr'}
        assert outcomes['radarr']['state']=='error' and connection_health.public_status(db,'radarr')=='offline'
        calls.clear();connection_health._checks(db);assert not calls
        main.set_config(db,'radarr_enabled','false');db.commit()
        outcomes=connection_health._checks(db,True)
        assert 'radarr' not in calls and outcomes['radarr']['state']=='unconfigured'
        assert connection_health.public_status(db,'radarr')=='unknown'
