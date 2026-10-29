import json
from copy import deepcopy
from sqlalchemy import select
from app import page_presets,visual_builder,portal,i18n,content_catalog
from app.db import SessionLocal
from app.models import User
from test_portal import setup
from test_content_pages import create_page,save_page
from test_visual_studio import design


def title():return page_presets.block('title','heading',title='{page_title}')


def test_title_block_is_available_on_all_page_builders_and_system_forms_are_preserved(client):
    setup(client);key,value=create_page(client,'heading-page')
    with SessionLocal() as db:guide='p-'+str(__import__('app.page_builder',fromlist=['guide_row']).guide_row(db,'emby').id)
    for page in ('home','login','forgot','reset','account','footer',key,guide):
        with SessionLocal() as db:layout=visual_builder.load(db,page,True)
        layout['blocks'].append(title())
        response=design(client,page,'preview',layout)
        assert response.status_code==200,(page,response.text)
        assert 'class="standalone-title"' in response.text and '{page_title}</h2>' not in response.text
        if page=='login':assert 'name="password"' in response.text
        assert save_page(client,page,layout).status_code==200
    with SessionLocal() as db:
        sources={e['key']:e for e in content_catalog.sources(db)}
        assert sources['page:'+key[2:]+':heading:title']['source']=='{page_title}'
        assert sources['account-block:heading:title']['source']=='{page_title}'


def test_page_title_variable_uses_localized_page_name_and_stays_in_the_draft(client):
    setup(client,locale='fr');key,value=create_page(client,'localized-heading')
    value['blocks']=[title()]
    assert save_page(client,key,value,True).status_code==200
    with SessionLocal() as db:
        i18n.store_content(db,'page:'+key[2:]+':title','Example help','fr','Notre espace');db.commit()
    page=client.get('/pages/localized-heading').text
    assert '<h2 class="standalone-title">Notre espace</h2>' in page
    value['page_settings']['title']='Pending page name'
    assert save_page(client,key,value).status_code==200
    assert 'Notre espace</h2>' in client.get('/pages/localized-heading').text
    preview=design(client,key,'preview',value).text
    assert 'Pending page name</h2>' in preview
    assert save_page(client,key,value,True).status_code==200
    assert 'Pending page name</h2>' in client.get('/pages/localized-heading').text


def test_title_variable_is_escaped_and_footer_uses_current_page_title(client):
    setup(client);key,value=create_page(client,'safe-heading')
    value['page_settings']['title']='<img src=x onerror=bad()>'
    value['blocks']=[title()]
    assert save_page(client,key,value,True).status_code==200
    with SessionLocal() as db:
        footer=visual_builder.load(db,'footer',True);footer['blocks']=[title()]
        visual_builder.save(db,'footer',footer,visual_builder.version(db,'footer'),True)
    response=client.get('/pages/safe-heading').text
    assert response.count('<h2 class="standalone-title">&lt;img src=x onerror=bad()&gt;</h2>')==2
    assert '<img src=x onerror' not in response
    assert '<h2 class="standalone-title">Home</h2>' in client.get('/home').text
    assert '<h2 class="standalone-title">My account</h2>' in client.get('/account').text
    value['blocks'][0]['body']='Hidden body'
    assert save_page(client,key,value).status_code==400


def test_title_content_translation_preserves_page_title_placeholder(client):
    setup(client,locale='fr');key,value=create_page(client,'translate-heading');value['blocks']=[title()]
    assert save_page(client,key,value,True).status_code==200
    with SessionLocal() as db:
        i18n.store_content(db,'page:'+key[2:]+':heading:title','{page_title}','fr','Bienvenue : {page_title}')
        i18n.store_content(db,'page:'+key[2:]+':title','Example help','fr','Aide');db.commit()
    assert '<h2 class="standalone-title">Bienvenue : Aide</h2>' in client.get('/pages/translate-heading').text
    assert i18n.builtin_content(None,'{page_title}','ja')=='{page_title}'
