import pytest
from app import page_presets,portal,visual_builder,page_builder
from app.db import SessionLocal
from test_portal import setup,post
from test_content_pages import create_page,save_page


def test_page_button_tracks_slug_and_page_permissions_and_visibility(client):
    setup(client)
    key,target=create_page(client,'button-target')
    assert save_page(client,key,target,True).status_code==200
    source_key,source=create_page(client,'button-source')
    source['blocks']=[page_presets.block('button','open-target',button_action='page',page_key=key,title='Go to my page',new_tab=True)]
    assert save_page(client,source_key,source,True).status_code==200
    page=client.get('/pages/button-source').text
    assert 'href="/pages/button-target" target="_blank" rel="noopener noreferrer">Go to my page' in page
    target['page_settings']['slug']='renamed-target'
    assert save_page(client,key,target,True).status_code==200
    assert 'href="/pages/renamed-target"' in client.get('/pages/button-source').text
    target['page_settings']['audience']=dict(everyone=False,admins=False,groups=[])
    assert save_page(client,key,target,True).status_code==200
    assert 'Go to my page' not in client.get('/pages/button-source').text
    target['page_settings']['audience']=dict(everyone=True,admins=True,groups=[])
    assert save_page(client,key,target,True).status_code==200
    with SessionLocal() as db:page_builder.row_for(db,key).archived=True;db.commit()
    assert 'Go to my page' not in client.get('/pages/button-source').text
    # An archived target does not lock the source editor.
    assert save_page(client,source_key,source).status_code==200


def test_page_buttons_in_header_footer_and_system_pages_are_safe(client):
    setup(client)
    with SessionLocal() as db:
        for page in ('header','footer','login','account'):
            value=visual_builder.load(db,page,True)
            block=page_presets.block('button','go-home',button_action='page',page_key='home',title='Return home')
            if page=='header':block.update(parent=value['blocks'][0]['id'],slot=0)
            value['blocks'].append(block)
            checked=visual_builder.validate(db,page,value)
            assert checked['blocks'][-1]['button_action']=='page'
        value=visual_builder.load(db,'home',True)
        value['blocks']=[page_presets.block('button','bad-target',button_action='page',page_key='javascript:bad')]
        with pytest.raises(ValueError):visual_builder.validate(db,'home',value)


def test_footer_rejects_accordion_without_changing_saved_content(client):
    setup(client)
    with SessionLocal() as db:
        value=visual_builder.load(db,'footer',True);version=visual_builder.version(db,'footer')
        value['blocks'].append(page_presets.block('accordion','not-supported',items=[]))
        with pytest.raises(ValueError,match='Accordion'):visual_builder.validate(db,'footer',value)
        assert visual_builder.version(db,'footer')==version
        assert all(b['kind']!='accordion' for b in visual_builder.load(db,'footer',True)['blocks'])
