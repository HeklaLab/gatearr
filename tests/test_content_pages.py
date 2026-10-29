"""Page publication, audience enforcement and guide composition are server contracts."""
import json
import re
import pytest
from sqlalchemy import select
from app import main, page_builder, page_presets, visual_builder
from app.db import SessionLocal
from app.models import ContentPage, User, PermissionGroup, GroupMember, AccessService
from test_portal import setup,post,logout,login_user


def create_page(client,slug='help-extra',preset='faq'):
    response=post(client,'/admin/pages',dict(title='Example help',slug=slug,preset=preset),'/admin/pages')
    assert response.status_code==303,response.text
    key=response.headers['location'].rsplit('/',1)[-1]
    with SessionLocal() as db:return key,visual_builder.load(db,key,True)


def save_page(client,key,value,publish=False,version=None):
    if version is None:
        with SessionLocal() as db:version=visual_builder.version(db,key)
    return post(client,f'/admin/design/{key}/'+('publish' if publish else 'save'),dict(payload=json.dumps(value),version=version),'/admin/pages')


def test_page_draft_published_snapshot_and_unique_addresses(client):
    setup(client)
    key,value=create_page(client)
    assert client.get('/pages/help-extra').status_code==404
    assert save_page(client,key,value,True).status_code==200
    assert 'Which' not in client.get('/pages/help-extra').text
    value['blocks'][0]['body']='Private draft wording'
    value['page_settings']['slug']='renamed-help'
    assert save_page(client,key,value).status_code==200
    assert 'Private draft wording' not in client.get('/pages/help-extra').text
    assert client.get('/pages/renamed-help').status_code==404
    assert save_page(client,key,value,True).status_code==200
    assert client.get('/pages/help-extra').status_code==404
    assert 'Private draft wording' in client.get('/pages/renamed-help').text
    assert save_page(client,key,value,version=0).status_code==409
    assert post(client,'/admin/pages',dict(title='Duplicate',slug='renamed-help'),'/admin/pages').status_code==400


def test_permissions_filter_links_and_enforce_urls_including_admins(client):
    setup(client)
    key,value=create_page(client)
    value['page_settings']['audience']=dict(everyone=False,admins=False,groups=[])
    assert save_page(client,key,value,True).status_code==200
    assert client.get('/pages/help-extra').status_code==404
    assert client.get('/admin/design/'+key).status_code==200
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.emby_id=='admin-1'))
        assert key not in [p['key'] for p in page_builder.catalog(db,owner)]
    value['page_settings']['audience']['admins']=True
    assert save_page(client,key,value,True).status_code==200
    assert client.get('/pages/help-extra').status_code==200
    logout(client);login_user(client)
    assert client.get('/pages/help-extra').status_code==404


def test_group_admin_or_everyone_audience_semantics(client):
    setup(client)
    with SessionLocal() as db:
        group=PermissionGroup(name='Family');db.add(group);db.flush()
        owner=db.scalar(select(User).where(User.emby_id=='admin-1'))
        member=User(name='Member',active=True,admin=False);ungrouped=User(name='No group',active=True,admin=False)
        db.add_all([member,ungrouped]);db.flush();db.add(GroupMember(group_id=group.id,user_id=member.id));db.flush()
        meta=dict(audience=dict(everyone=False,admins=False,groups=[group.id]))
        assert page_builder.allowed(db,member,meta)
        assert not page_builder.allowed(db,owner,meta)
        assert not page_builder.allowed(db,ungrouped,meta)
        meta['audience']['admins']=True
        assert page_builder.allowed(db,owner,meta)
        meta['audience']['everyone']=True
        assert page_builder.allowed(db,ungrouped,meta)


def test_page_menu_filters_restricted_pages_and_has_watermarks(client):
    setup(client)
    key,value=create_page(client)
    value['page_settings']['icon']='circle-question'
    assert save_page(client,key,value,True).status_code==200
    with SessionLocal() as db:
        home=visual_builder.load(db,'home',True)
        home['blocks']=[page_presets.block('page_menu','page-links',page_ids=[key],menu_layout='list')]
        visual_builder.save(db,'home',home,visual_builder.version(db,'home'),True)
    response=client.get('/home')
    assert 'layout-list' in response.text and 'service-symbol-watermark' in response.text
    assert '/pages/help-extra' in response.text
    value['page_settings']['audience']=dict(everyone=False,admins=False,groups=[])
    assert save_page(client,key,value,True).status_code==200
    assert '/pages/help-extra' not in client.get('/home').text


def test_guide_envelope_preserved_for_all_device_and_article_levels(client):
    setup(client)
    client.get('/admin/pages')
    with SessionLocal() as db:
        row=page_builder.guide_row(db,'emby');key='p-'+str(row.id)
        value=visual_builder.load(db,key,True)
        value['blocks'].insert(0,page_presets.block('text','above',1,body='Envelope introduction'))
        value['blocks'].append(page_presets.block('accordion','below',50,items=[dict(id='help',question='Envelope FAQ',answer='Footer answer')]))
        visual_builder.save(db,key,value,row.version,True)
        service=db.get(AccessService,'emby');nodes=json.loads(service.access_published)
        group=next(n for n in nodes if n['kind']=='group')
        guide=next(n for n in nodes if n['kind']=='guide')
    for path in ['/access/emby?view=guide','/access/emby/'+group['id']+'?view=guide','/access/emby/guide/'+str(guide['guide_id'])]:
        response=client.get(path)
        assert response.status_code==200,response.text
        assert 'Envelope introduction' in response.text and 'Envelope FAQ' in response.text
    value['page_settings']['audience']=dict(everyone=False,admins=False,groups=[])
    assert save_page(client,key,value,True).status_code==200
    assert client.get('/access/emby?view=guide').status_code==404
    assert client.get('/access/emby/guide/'+str(guide['guide_id'])).status_code==404


def test_custom_page_journey_navigation_stays_in_the_page(client):
    setup(client)
    key,value=create_page(client,preset='blank')
    value['blocks']=[page_presets.block('text','intro',body='Stay here'),page_presets.block('guide_embed','journey',20,service_key='emby')]
    assert save_page(client,key,value,True).status_code==200
    first=client.get('/pages/help-extra')
    assert first.status_code==200
    assert '/pages/help-extra?device=' in first.text
    with SessionLocal() as db:
        nodes=json.loads(db.get(AccessService,'emby').access_published)
        node=next(n for n in nodes if n['kind']=='group')
        guide=next(n for n in nodes if n['kind']=='guide')
    assert 'Stay here' in client.get('/pages/help-extra?device='+node['id']).text
    assert 'Stay here' in client.get('/pages/help-extra?guide='+str(guide['guide_id'])).text
    assert client.get('/pages/help-extra?device=missing').status_code==404


def test_archive_and_fresh_preset(client):
    setup(client,fresh_layout=True)
    with SessionLocal() as db:
        home=visual_builder.load(db,'home')
        assert any(b['kind']=='page_menu' for b in home['blocks'])
        assert page_builder.guide_row(db,'emby')
    key,value=create_page(client)
    assert save_page(client,key,value,True).status_code==200
    with SessionLocal() as db:version=visual_builder.version(db,key)
    assert post(client,'/admin/pages/'+key+'/archive',dict(version=version),'/admin/pages').status_code==303
    assert client.get('/pages/help-extra').status_code==404
    assert client.get('/admin/design/'+key).status_code==404


def test_home_always_appears_in_main_navigation(client):
    setup(client)
    with SessionLocal() as db:
        value=visual_builder.load(db,'home',True)
        value['page_settings']=dict(page_builder.HOME_SETTINGS,audience=dict(everyone=False,admins=False,groups=[]))
        visual_builder.save(db,'home',value,visual_builder.version(db,'home'),True)
    response=client.get('/account')
    nav=re.search(r'<nav class="primary-capsule".*?</nav>',response.text,re.S)[0]
    assert 'href="/home"' in nav
    assert client.get('/home').status_code==200


def test_accordion_is_escaped_and_archived_pages_can_be_restored(client):
    setup(client)
    key,value=create_page(client)
    value['blocks']=[page_presets.block('accordion','safe',items=[dict(id='q',question='<script>bad()</script>',answer='<img src=x onerror=bad()>')])]
    assert save_page(client,key,value,True).status_code==200
    html=client.get('/pages/help-extra').text
    assert '&lt;script&gt;bad()&lt;/script&gt;' in html and '<script>bad()' not in html
    with SessionLocal() as db:version=visual_builder.version(db,key)
    assert post(client,'/admin/pages/'+key+'/archive',dict(version=version),'/admin/pages').status_code==303
    assert post(client,'/admin/pages/'+key+'/restore',dict(version=version+1),'/admin/pages').status_code==303
    assert client.get('/pages/help-extra').status_code==200
    value['blocks'][0]['items'][0]['id']='bad id'
    assert save_page(client,key,value,True).status_code==400
