"""Page-type restrictions must hold on save as well as in the block palette."""
import json,importlib.util
from unittest.mock import patch
from app import main,page_builder,page_presets,visual_builder
from app.db import SessionLocal
from app.models import ContentPage
from test_portal import setup,post
from test_content_pages import create_page,save_page


def test_application_menu_removed_everywhere_and_applications_home_only(client):
    setup(client)
    key,value=create_page(client)
    with SessionLocal() as db:
        layouts={page:(visual_builder.load(db,page,True),visual_builder.version(db,page)) for page in ('home','login','footer')}
    for page,(layout,version) in layouts.items():
        layout['blocks'].append(page_presets.block('menu','old-menu'))
        assert post(client,f'/admin/design/{page}/save',dict(payload=json.dumps(layout),version=version),'/admin').status_code==400
    value['blocks']=[page_presets.block('applications','apps',applications=['account'],columns=1)]
    assert save_page(client,key,value).status_code==400
    with SessionLocal() as db:
        home=visual_builder.load(db,'home',True)
        home['blocks']=[page_presets.block('applications','apps',applications=['account'],columns=1)]
        visual_builder.save(db,'home',home,visual_builder.version(db,'home'))


def test_access_guide_excludes_widgets_and_alone_supports_button_action(client):
    setup(client);client.get('/admin/pages')
    with SessionLocal() as db:
        row=page_builder.guide_row(db,'emby');guide_key='p-'+str(row.id);guide=visual_builder.load(db,guide_key,True)
    assert save_page(client,guide_key,guide).status_code==200
    for kind in ('widget_library','widget_tracearr'):
        trial=json.loads(json.dumps(guide));trial['blocks'].append(page_presets.block(kind,'widget'))
        assert save_page(client,guide_key,trial).status_code==400
    key,value=create_page(client,preset='blank')
    value['blocks']=[page_presets.device_button('back',10),page_presets.block('guide_embed','guide',20,service_key='emby')]
    assert save_page(client,key,value).status_code==400
    value['blocks'][0].update(button_action='link',url='/pages/help-extra')
    assert save_page(client,key,value,True).status_code==200
    assert 'href="/pages/help-extra"' in client.get('/pages/help-extra').text


def test_footer_offers_permission_filtered_page_menu_and_normal_buttons(client):
    setup(client)
    with SessionLocal() as db:
        value=visual_builder.load(db,'footer',True);version=visual_builder.version(db,'footer')
    value['blocks']=[page_presets.block('page_menu','pages',page_ids=['home'],menu_layout='list'),page_presets.block('button','link',title='Community',url='https://example.com')]
    response=post(client,'/admin/design/footer/publish',dict(payload=json.dumps(value),version=version),'/admin')
    assert response.status_code==200,response.text
    assert 'Community' in client.get('/home').text
    value['blocks'][1]['button_action']='choose_device'
    assert post(client,'/admin/design/footer/save',dict(payload=json.dumps(value),version=response.json()['version']),'/admin').status_code==400


def test_upgrade_cleans_old_blocks_and_converts_non_guide_button_without_losing_other_content(client):
    setup(client);client.get('/admin/pages')
    key,value=create_page(client,preset='blank')
    value['blocks']=[page_presets.block('text','keep',body='Retained content'),page_presets.block('menu','old-menu'),page_presets.block('applications','old-apps',applications=[]),page_presets.device_button('back',40),page_presets.block('guide_embed','guide',50,service_key='emby')]
    with SessionLocal() as db:
        row=db.get(ContentPage,int(key[2:]));row.draft=row.published=json.dumps(value)
        guide=page_builder.guide_row(db,'emby');content=json.loads(guide.draft);content['blocks'].extend([page_presets.block('widget_library','old-library'),page_presets.block('widget_tracearr','old-stats')]);guide.draft=guide.published=json.dumps(content);db.commit()
        spec=importlib.util.spec_from_file_location('scopes','migrations/versions/0031_builder_block_scopes.py');migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        with patch.object(migration.op,'get_bind',return_value=db.connection()):migration.upgrade()
        db.commit();db.expire_all()
        updated=json.loads(db.get(ContentPage,row.id).published)
        assert [b['kind'] for b in updated['blocks']]==['text','button','guide_embed']
        assert updated['blocks'][0]['body']=='Retained content'
        assert updated['blocks'][1]['button_action']=='link' and updated['blocks'][1]['url']=='/pages/help-extra'
        updated_guide=json.loads(db.get(ContentPage,guide.id).published)
        assert not any(b['kind'].startswith('widget_') for b in updated_guide['blocks'])
        assert len([b for b in updated_guide['blocks'] if b.get('button_action')=='choose_device'])==2
