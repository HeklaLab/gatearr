import json
import pytest
from copy import deepcopy
from contextlib import contextmanager
from sqlalchemy import select,delete
from app import main,portal,widgets,tracearr,application_information,visual_builder
from app.db import SessionLocal
from app.models import User,Config,ContentPage
from app.security import encrypt
from test_portal import setup
from test_visual_studio import design


def configured(db):
    for service in ('seerr','tracearr','radarr','sonarr','bazarr','tdarr'):
        for key,value in {'enabled':'true','url':'https://'+service+'.test','api_key':encrypt('test'),'interface_enabled':'true','public_url':'https://'+service+'.example'}.items():main.set_config(db,service+'_'+key,value)


def test_default_fallback_and_builder_templates_keep_end_user_apps_first_without_writes(client):
    setup(client)
    with SessionLocal() as db:
        configured(db);db.execute(delete(Config).where(Config.key.in_(['portal_draft','portal_published'])));db.commit()
        before=[(r.id,r.draft,r.published) for r in db.scalars(select(ContentPage))]
        value=portal.load(db);first=next(b for b in value['blocks'] if b['id']=='main-applications');admin=next(b for b in value['blocks'] if b['id']=='admin-applications')
        assert first['applications']==['access:emby','access:seerr']
        assert set(admin['applications'])=={'radarr','sonarr','bazarr','tracearr','tdarr'} and admin['visibility']=='admins'
        stats=next(b for b in value['blocks'] if b['kind']=='widget_tracearr')
        assert first['order']<stats['order']<admin['order']
        assert 'tracearr' not in first['information']
        assert db.get(Config,'portal_published') is None
    response=client.get('/admin/design/home');assert response.status_code==200
    with SessionLocal() as db:
        assert before==[(r.id,r.draft,r.published) for r in db.scalars(select(ContentPage))]
        assert db.get(Config,'portal_published') is None
    assert 'home_preset' in response.text


def test_old_member_card_becomes_a_statistics_widget_and_admin_interface(client):
    setup(client)
    with SessionLocal() as db:
        configured(db);db.commit()
    value=deepcopy(portal.DEFAULT);value['blocks']=[dict(id='tracearr-card',kind='applications',region='main',span=12,order=10,columns=1,applications=['tracearr'],information={'tracearr':dict(enabled=True,metrics=['plays','activity'],period='month')})]
    response=design(client,'home','preview',value)
    assert response.status_code==200,response.text
    assert 'Sessions' in response.text and 'This month' in response.text and 'widget-activity' in response.text
    from app.applications import normalize
    with SessionLocal() as db:
        actual=normalize(value,db)
        stats=next(b for b in actual['blocks'] if b['kind']=='widget_tracearr')
        assert stats['metrics']==['plays','activity'] and stats['period']=='month'
        app=next(b for b in actual['blocks'] if b['kind']=='applications')
        assert app['visibility']=='admins' and app['applications']==['tracearr']
        assert 'tracearr' not in app.get('information',{})
        assert normalize(actual,db)==actual


@pytest.mark.parametrize('native_id',['admin-1','user-1'])
def test_tracearr_card_live_statistics_and_opt_out(client,monkeypatch,native_id):
    setup(client)
    @contextmanager
    def connection(db):yield object()
    monkeypatch.setattr(tracearr,'connection',connection)
    monkeypatch.setattr(widgets,'emby',main.emby)
    seen=[]
    def history(db,user,connection,params):
        seen.append((user.id,params));return [dict(duration_ms=3600000,show_title='Fargo',started_at='2026-10-28T12:00:00Z',bitrate=2000,is_transcode=False)]
    monkeypatch.setattr(tracearr,'history',history)
    with SessionLocal() as db:
        configured(db);owner=db.scalar(select(User).where(User.emby_id==native_id))
        result=widgets.display(db,owner,dict(id='stats',kind='widget_tracearr',metrics=['plays','watch_time','activity'],period='30days'))
        assert result['metrics'][0]['value']==1 and result['metrics'][1]['value']=='1 h 00'
        assert result['chart'] and seen[0][0]==owner.id
        widgets.preference(db,owner).statistics=False;db.commit()
        assert widgets.display(db,owner,dict(id='stats',kind='widget_tracearr',metrics=['plays'])) is None
        assert application_information.display(db,owner,'tracearr',dict(enabled=True,metrics=['plays'])) is None


def test_adding_tracearr_card_does_not_migrate_or_remove_standalone_statistics(client):
    setup(client)
    from app.applications import normalize
    value=deepcopy(portal.DEFAULT);value['blocks']=[dict(id='apps',kind='applications',region='main',span=12,order=10,columns=1,applications=['tracearr']),dict(id='stats',kind='widget_tracearr',region='main',span=12,order=20,metrics=['plays'],period='month')]
    with SessionLocal() as db:
        actual=normalize(value,db)
        assert any(b['id']=='stats' and b['metrics']==['plays'] for b in actual['blocks'])
        assert sum(b['kind']=='widget_tracearr' for b in actual['blocks'])==1
        assert all('tracearr' not in b.get('information',{}) for b in actual['blocks'] if b['kind']=='applications')
        assert normalize(actual,db)==actual


def test_conversion_positions_statistics_before_new_admin_row_and_preserves_custom_named_link(client):
    setup(client)
    from app.applications import normalize
    from app.models import MenuItem
    value=deepcopy(portal.DEFAULT)
    value['blocks']=[dict(id='members',kind='applications',region='main',span=12,order=10,columns=2,applications=['access:emby','tracearr']),dict(id='account-row',kind='applications',region='main',span=12,order=20,columns=1,applications=['account'])]
    with SessionLocal() as db:
        configured(db);db.add(MenuItem(label='Tracearr',url='https://custom.example.test',menu_key='main',position=1));db.flush()
        actual=normalize(value,db);kinds=[b['kind'] for b in actual['blocks']]
        assert kinds==['applications','widget_tracearr','applications','applications']
        assert actual['blocks'][0]['applications']==['access:emby']
        assert actual['blocks'][2]['applications']==['tracearr'] and actual['blocks'][2]['visibility']=='admins'
        assert actual['blocks'][3]['applications']==['account']
        assert normalize(actual,db)==actual
        from app.applications import catalog
        custom=next(a for a in catalog(db,editor=True) if a['key'].startswith('menu:'))
        assert custom['name']=='Tracearr' and custom['direct_url']=='https://custom.example.test'
        assert value['blocks'][0]['applications']==['access:emby','tracearr']


def test_statistics_preset_depends_on_api_not_interface_or_user_tool_grants(client):
    setup(client)
    with SessionLocal() as db:
        configured(db);main.set_config(db,'tracearr_interface_enabled','false')
        blocks=portal.initial_layout(db,seed_pages=False)['blocks']
        assert sum(b['kind']=='widget_tracearr' for b in blocks)==1
        assert all('tracearr' not in b.get('applications',[]) for b in blocks)
        main.set_config(db,'tracearr_api_key','')
        assert not any(b['kind']=='widget_tracearr' for b in portal.initial_layout(db,seed_pages=False)['blocks'])


def test_moving_legacy_tracearr_card_preserves_its_direct_url_without_an_api(client):
    setup(client)
    from test_application_behavior import row,write,state,card_href
    layout,version=state()
    layout['blocks']=[row('old-tracearr','tracearr','direct',url='https://tracearr.custom.test:9443')]
    assert write(client,layout,version).status_code==200
    html=client.get('/home').text
    assert card_href(html,'tracearr-admin')=='https://tracearr.custom.test:9443'
    with SessionLocal() as db:
        loaded=portal.load(db)
        assert not any(b['kind']=='widget_tracearr' for b in loaded['blocks'])
        assert next(b for b in loaded['blocks'] if b['kind']=='applications')['visibility']=='admins'
