"""Moving widgets into cards preserves opt-outs, data settings and audiences."""
from copy import deepcopy
import json
import pytest
from sqlalchemy import select
from app import portal,widgets,main
from app.applications import normalize
from app.application_information import display
from app.db import SessionLocal
from app.models import User,PermissionGroup,GroupMember
from test_portal import setup
from test_visual_studio import design


def layout():
    value=deepcopy(portal.DEFAULT)
    value['blocks']=[dict(id='apps',kind='applications',region='main',span=12,order=10,columns=2,applications=['access:emby','access:seerr']),dict(id='metrics',kind='columns',region='main',span=12,order=20,columns=2),dict(id='media',kind='widget_media',region='main',span=12,order=30,parent='metrics',slot=0,metrics=['episodes'],count_mode='promotion',round_to=10,groups=[1],priority=4),dict(id='requests',kind='widget_seerr',region='main',span=12,order=40,parent='metrics',slot=1,metrics=['movies_left'])]
    return value


def test_migration_preserves_settings_and_is_idempotent(client):
    setup(client)
    with SessionLocal() as db:
        source=layout();original=deepcopy(source);value=normalize(source,db)
        assert source==original
        assert [b['kind'] for b in value['blocks']]==['applications']
        info=value['blocks'][0]['information']
        rule=info['access:emby']['rules'][0]
        assert rule['metrics']==['episodes'] and rule['count_mode']=='promotion' and rule['round_to']==10
        assert rule['groups']==[1] and rule['priority']==4
        assert normalize(value,db)==value
        assert portal.validate(value)==value
        info['access:emby']['enabled']=False
        assert normalize(value,db)['blocks'][0]['information']['access:emby']['enabled'] is False


def test_migration_keeps_nonwidget_content_and_temporarily_unselected_settings(client):
    setup(client)
    with SessionLocal() as db:
        source=layout();source['blocks'][0]['applications']=['access:seerr']
        source['blocks'].append(dict(id='note',kind='text',region='main',span=12,order=50,parent='metrics',slot=0,body='Keep this'))
        value=normalize(source,db)
        assert any(b['id']=='metrics' for b in value['blocks'])
        assert next(b for b in value['blocks'] if b['id']=='note')['body']=='Keep this'
        value['blocks'][0]['applications'].append('access:emby')
        value=normalize(value,db)
        assert value['blocks'][0]['information']['access:emby']['rules'][0]['round_to']==10


def test_information_migration_preserves_group_and_parent_role_restrictions(client,monkeypatch):
    setup(client)
    monkeypatch.setattr(widgets,'available',lambda *args:True)
    monkeypatch.setattr(widgets,'display',lambda db,user,block,editor=False:{'metrics':block.get('metrics')})
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'))
        group=PermissionGroup(name='Family');db.add(group);db.flush()
        db.add(GroupMember(group_id=group.id,user_id=user.id));db.flush()
        source=layout();source['blocks'][1]['visibility']='members'
        source['blocks'][2]['groups']=[group.id]
        value=normalize(source,db);info=value['blocks'][0]['information']['access:emby']
        assert display(db,user,'access:emby',info)=={'metrics':['episodes']}
        user.admin=True
        assert display(db,user,'access:emby',info) is None
        user.admin=False;info['rules'][0]['groups']=[group.id+1]
        assert display(db,user,'access:emby',info) is None
        assert display(db,user,'access:emby',{'enabled':False}) is None


def test_builder_option_roundtrip_and_preview(client):
    setup(client)
    with SessionLocal() as db:value=normalize(layout(),db)
    info=value['blocks'][0]['information'];info['access:emby']={'enabled':True,'metrics':['episodes'],'count_mode':'promotion','round_to':100}
    page=design(client,'home','preview',value)
    assert page.status_code==200 and 'application-information' in page.text and '14\u202f200+' in page.text
    assert 'portal-widget' not in page.text
    info['access:emby']['enabled']=False;info['access:seerr']['enabled']=False
    assert 'class="application-information"' not in design(client,'home','preview',value).text
    with SessionLocal() as db:revision=portal.version(db)
    assert design(client,'home','publish',value,revision).status_code==200
    with SessionLocal() as db:
        saved=portal.load(db)
        assert saved['blocks'][0]['information']['access:emby']['enabled'] is False
        assert not {'widget_media','widget_seerr'} & set(widgets.builder_data(db)['types'])


@pytest.mark.parametrize('invalid',[{'enabled':'false'},{'round_to':25},{'metrics':['private']},{'metrics':[{}]},{'rules':[{'groups':['1']}]},{'rules':[{'visibility':'invalid'}]}])
def test_card_information_rejects_invalid_settings(client,invalid):
    setup(client);value=layout();value['blocks']=value['blocks'][:1];value['blocks'][0]['information']={'access:emby':invalid}
    assert design(client,'home','save',value).status_code==400
