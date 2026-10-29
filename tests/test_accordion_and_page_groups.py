"""Desktop page-builder changes: FAQ artwork, safe rich answers and direct access guides."""
import json,re,importlib.util
from copy import deepcopy
from unittest.mock import patch
import pytest
from sqlalchemy import select,text
from app import main,page_builder,page_presets,visual_builder
from app.db import SessionLocal
from app.models import ContentPage,Config,AccessService
from test_portal import setup,post
from test_content_pages import create_page,save_page
from test_icon_uploads import png


def test_home_identity_is_fixed_and_pages_are_grouped(client):
    setup(client)
    key,value=create_page(client)
    html=client.get('/admin/pages').text
    assert [m for m in re.findall('data-page-group="(.*?)"',html)]==['home','access','other']
    assert 'Emby access guides' in html and 'Application journey' not in html.split('<script')[0]
    assert '/pages/guides' not in html
    with SessionLocal() as db:
        home=visual_builder.load(db,'home',True);version=visual_builder.version(db,'home')
    home['page_settings']=dict(page_builder.HOME_SETTINGS,title='Renamed')
    response=post(client,'/admin/design/home/save',dict(payload=json.dumps(home),version=version),'/admin')
    assert response.status_code==400 and 'cannot be renamed' in response.text
    assert post(client,'/admin/pages/home/archive',dict(version=0),'/admin').status_code==404
    with SessionLocal() as db:assert visual_builder.load(db,'home').get('page_settings',page_builder.HOME_SETTINGS)['title']=='Home'


def test_access_guide_is_a_subpage_only_block_and_has_a_fresh_preset(client):
    setup(client,fresh_layout=True)
    with SessionLocal() as db:
        home=visual_builder.load(db,'home',True)
        assert all(b['kind'] not in ('guides','guide_embed') for b in home['blocks'])
        emby=page_builder.guide_row(db,'emby')
        value=json.loads(emby.published)
        assert value['page_settings']['title']=='Emby access guides'
        assert [b['kind'] for b in value['blocks']]==['text','button','guide_embed','button','accordion','page_menu']
        home['blocks'].append(page_presets.block('guide_embed','invalid-access',service_key='emby'))
    assert post(client,'/admin/design/home/preview',dict(payload=json.dumps(home)),'/admin').status_code==400
    key,value=create_page(client,preset='blank')
    value['blocks']=[page_presets.block('guide_embed','access',service_key='emby')]
    assert save_page(client,key,value,True).status_code==200
    assert 'Choose your device' in client.get('/pages/help-extra').text
    value['blocks'][0]['kind']='guides'
    assert save_page(client,key,value).status_code==400


def test_accordion_rich_text_is_saved_without_media_or_executable_markup(client):
    setup(client)
    key,value=create_page(client)
    value['blocks']=[page_presets.block('accordion','faq',items=[dict(id='one',question='Plain question <b>not bold</b>',rich=True,answer='<p><strong>Bold</strong> <em>Italic</em> <u>Underlined</u> <span style="color:#159eff;background-image:url(https://bad.test/x)">Colour</span></p><ul><li>First</li></ul><ol><li>Second</li></ol><font color="#123456">Legacy colour</font><img src="/static/services/emby.png"><script>alert(1)</script><iframe src="https://bad.test"></iframe>')])]
    assert save_page(client,key,value,True).status_code==200
    response=client.get('/pages/help-extra')
    assert response.status_code==200
    for markup in ('<strong>Bold</strong>','<em>Italic</em>','<u>Underlined</u>','<ul><li>First</li></ul>','<ol><li>Second</li></ol>','color:#159eff'):
        assert markup in response.text
    answer=re.search(r'<div class="accordion-answer rich-copy">(.*?)</div></details>',response.text,re.S)[1]
    assert '<img' not in answer and '<script' not in answer and '<iframe' not in answer and 'bad.test' not in answer
    assert '&lt;b&gt;not bold&lt;/b&gt;' in response.text
    with SessionLocal() as db:
        stored=json.loads(db.get(ContentPage,int(key[2:])).published)['blocks'][0]['items'][0]['answer']
        assert '<img' not in stored and '<script' not in stored


@pytest.mark.parametrize('art',[dict(icon='circle-question'),dict(icon_url='/static/services/emby.png')])
def test_accordion_artwork_and_background_are_independent_options(client,art):
    setup(client)
    key,value=create_page(client)
    item=dict(id='one',question='Artwork question',answer='Answer',**art)
    value['blocks']=[page_presets.block('accordion','faq',items=[item])]
    assert save_page(client,key,value,True).status_code==200
    html=client.get('/pages/help-extra').text
    assert 'accordion-heading-icon' in html and 'accordion-watermark' not in html
    item['watermark']=True
    assert save_page(client,key,value,True).status_code==200
    assert 'accordion-watermark' in client.get('/pages/help-extra').text
    item.update(icon='',icon_url='',watermark=False)
    assert save_page(client,key,value,True).status_code==200
    html=client.get('/pages/help-extra').text
    assert 'accordion-heading-icon' not in html and 'accordion-watermark' not in html


def test_accordion_uploaded_png_and_svg_use_existing_asset_validation(client):
    setup(client)
    key,value=create_page(client)
    from test_portal import csrf
    assets=[('logo.png',png(32,32),'image/png'),('logo.svg',b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><rect width="20" height="20" fill="blue"/></svg>','image/svg+xml')]
    for name,raw,mime in assets:
        uploaded=client.post('/admin/assets',data={'csrf':csrf(client,'/admin')},files={'icon_file':(name,raw,mime)},headers={'Accept':'application/json'})
        assert uploaded.status_code==200,uploaded.text
        value['blocks']=[page_presets.block('accordion','faq',items=[dict(id='logo',question='Logo',answer='Text',icon_url=uploaded.json()['url'],watermark=True)])]
        assert save_page(client,key,value,True).status_code==200
        assert uploaded.json()['url'] in client.get('/pages/help-extra').text
    value['blocks'][0]['items'][0]['icon_url']='https://untrusted.test/image.png'
    assert save_page(client,key,value).status_code==400


def test_directory_removal_migration_preserves_other_content_and_guide_addresses(client):
    setup(client)
    with SessionLocal() as db:
        page_builder.ensure_defaults(db)
        directory=ContentPage(slug='guides',system_key='directory',draft=json.dumps(page_presets.layout('Access guides','guides',blocks=[page_presets.block('guides','dir')])),version=0)
        directory.published=directory.draft;db.add(directory);db.flush();directory_id=directory.id
        home=visual_builder.load(db,'home',True);home['page_settings']=dict(page_builder.HOME_SETTINGS,title='Old home name')
        home['blocks'].extend([page_presets.block('guides','old-directory'),page_presets.block('guide_embed','old-embed',service_key='emby'),page_presets.block('page_menu','links',page_ids=['p-'+str(directory.id)])])
        for cfg in ('portal_draft','portal_published'):main.set_config(db,cfg,json.dumps(home))
        row=page_builder.guide_row(db,'emby');layout=json.loads(row.draft);layout['page_settings']['title']='Emby · Access guide';row.draft=row.published=json.dumps(layout)
        original=tuple(db.execute(text("SELECT access_draft,access_published FROM access_services WHERE key='emby'")).one())
        db.commit()
        module=importlib.util.spec_from_file_location('remove_directory','migrations/versions/0029_access_guide_pages.py');migration=importlib.util.module_from_spec(module);module.loader.exec_module(migration)
        with patch.object(migration.op,'get_bind',return_value=db.connection()):migration.upgrade()
        db.commit();db.expire_all()
        assert db.get(ContentPage,directory_id).archived
        home=visual_builder.load(db,'home')
        assert home['page_settings']['title']=='Home'
        assert all(b['kind'] not in ('guides','guide_embed') for b in home['blocks'])
        assert next(b for b in home['blocks'] if b['id']=='links')['page_ids']==[]
        assert tuple(db.execute(text("SELECT access_draft,access_published FROM access_services WHERE key='emby'")).one())==original
    assert client.get('/pages/guides').status_code==404
    assert client.get('/access/emby?view=guide').status_code==200
    assert 'data-page-group="access"' in client.get('/admin/pages').text
