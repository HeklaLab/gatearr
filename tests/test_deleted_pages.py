import json,re
from sqlalchemy import select
from app import page_builder,i18n,visual_builder
from app.db import SessionLocal
from app.models import ContentPage,Guide,AccessService
from test_portal import setup,post,logout,login_user
from test_content_pages import create_page,save_page


def archive(client,key):
    with SessionLocal() as db:version=page_builder.row_for(db,key).version
    assert post(client,'/admin/pages/'+key+'/archive',{'version':version},'/admin/pages').status_code==303
    return version+1


def purge(client,key,version,confirm='delete'):
    return post(client,'/admin/pages/'+key+'/purge',{'version':version,'confirm':confirm},'/admin/pages')


def test_deleted_directory_style_and_permanent_removal_with_stable_ids(client):
    setup(client);key,value=create_page(client,'deleted-example');assert save_page(client,key,value,True).status_code==200
    with SessionLocal() as db:
        i18n.store_content(db,'page:'+key[2:]+':title','Example help','fr','Une aide');db.commit()
    version=archive(client,key)
    page=client.get('/admin/pages').text
    assert 'data-page-group="deleted"' in page and 'page-deleted-actions' in page
    assert 'fa-rotate-left' in page and 'Delete permanently' in page
    assert purge(client,key,version,confirm='').status_code==400
    assert purge(client,key,version-1).status_code==409
    assert purge(client,key,version).status_code==303
    with SessionLocal() as db:
        assert db.get(ContentPage,int(key[2:])) is None
        assert not any(x['key'].startswith('page:'+key[2:]+':') for x in __import__('app.content_catalog',fromlist=['sources']).sources(db))
        assert i18n.content(db,'page:'+key[2:]+':title','Example help','fr')=='Example help'
    assert client.get('/admin/design/'+key).status_code==404
    assert post(client,'/admin/pages/'+key+'/restore',{'version':version},'/admin/pages').status_code==404
    new,_=create_page(client,'deleted-example') # address is available again
    assert int(new[2:])>int(key[2:]) # old URLs/menus cannot silently target another page


def test_purge_requires_archived_page_admin_and_csrf_and_protects_home(client):
    setup(client);key,_=create_page(client,'protected-delete')
    assert purge(client,key,0).status_code==404
    assert purge(client,'home',0).status_code==404
    version=archive(client,key)
    assert client.post('/admin/pages/'+key+'/purge',data={'version':version,'confirm':'delete','csrf':'bad'}).status_code==403
    logout(client);login_user(client)
    assert post(client,'/admin/pages/'+key+'/purge',{'version':version,'confirm':'delete'},'/account').status_code==403
    with SessionLocal() as db:assert db.get(ContentPage,int(key[2:])) is not None


def test_purged_seeded_pages_do_not_respawn_and_keep_application_guides(client):
    setup(client);client.get('/admin/pages')
    with SessionLocal() as db:
        rows=list(db.scalars(select(ContentPage).where(ContentPage.system_key.in_(['faq','guide:emby']))))
        keys=['p-'+str(row.id) for row in rows]
        guides=[(g.id,g.draft,g.published) for g in db.scalars(select(Guide))]
    for key in keys:assert purge(client,key,archive(client,key)).status_code==303
    for _ in range(2):assert client.get('/admin/pages').status_code==200
    with SessionLocal() as db:
        assert not list(db.scalars(select(ContentPage).where(ContentPage.system_key.in_(['faq','guide:emby']))))
        assert guides==[(g.id,g.draft,g.published) for g in db.scalars(select(Guide))]
        assert db.get(AccessService,'emby') is not None
    assert client.get('/access/emby?view=guide').status_code==404
    assert client.get('/home').status_code==200
