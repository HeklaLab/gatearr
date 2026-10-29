import json,re
from app import page_builder,visual_builder,portal
from app.db import SessionLocal
from test_portal import setup,post,logout,login_user
from test_content_pages import create_page,save_page


def item(page,title):
    return next(row for row in re.findall(r'<article class="page-directory-item">.*?</article>',page,re.S) if title in row)


def test_activation_keeps_published_content_and_pending_draft_independent(client):
    setup(client);key,value=create_page(client,'page-actions')
    row=item(client.get('/admin/pages').text,'Example help')
    assert 'Disabled' in row and 'Publish this page from the builder' in row
    assert post(client,'/admin/pages/'+key+'/enable',{'version':0},'/admin/pages').status_code==400
    assert save_page(client,key,value,True).status_code==200
    with SessionLocal() as db:version=page_builder.row_for(db,key).version
    value['blocks'].append(dict(id='pending',kind='text',title='Pending draft marker',body='',region='main',span=12,order=100))
    assert save_page(client,key,value,version=version).status_code==200
    with SessionLocal() as db:
        row=page_builder.row_for(db,key);version=row.version;published=row.published;draft=row.draft
    assert post(client,'/admin/pages/'+key+'/disable',{'version':version},'/admin/pages').status_code==303
    assert client.get('/pages/page-actions').status_code==404
    with SessionLocal() as db:
        row=page_builder.row_for(db,key)
        assert row.published==published and row.draft==draft and not row.enabled
        assert key not in [p['key'] for p in page_builder.catalog(db,db.get(__import__('app.models',fromlist=['User']).User,1))]
    assert post(client,'/admin/pages/'+key+'/enable',{'version':version},'/admin/pages').status_code==409
    assert post(client,'/admin/pages/'+key+'/enable',{'version':version+1},'/admin/pages').status_code==303
    assert 'Pending draft marker' not in client.get('/pages/page-actions').text
    with SessionLocal() as db:
        row=page_builder.row_for(db,key);assert row.published==published and row.draft==draft
    assert save_page(client,key,value,True).status_code==200
    assert 'Pending draft marker' in client.get('/pages/page-actions').text


def test_action_groups_and_home_has_no_activation_or_access_controls(client):
    setup(client);page=client.get('/admin/pages').text
    guide=item(page,'Emby access guides')
    assert 'Edit guide' in guide and guide.count('class="page-action-pair')==2
    assert '/disable"' in guide and '/archive"' in guide
    home=item(page,'Home page')
    assert 'fa-lock' not in home and 'page-publication-pair' not in home
    assert '/home/enable' not in home and '/home/disable' not in home and '/home/archive' not in home
    assert post(client,'/admin/pages/home/enable',{'version':0},'/admin/pages').status_code==404
    assert post(client,'/admin/pages/home/disable',{'version':0},'/admin/pages').status_code==404
    with SessionLocal() as db:
        value=portal.load(db,True);version=portal.version(db)
    value['page_settings']={**page_builder.HOME_SETTINGS,'audience':dict(everyone=False,admins=False,groups=[])}
    assert post(client,'/admin/design/home/publish',{'payload':json.dumps(value),'version':version},'/admin').status_code==200
    assert client.get('/home').status_code==200
    with SessionLocal() as db:assert portal.load(db)['page_settings']['audience']['everyone']


def test_page_list_publication_is_protected_and_csrf_checked(client):
    setup(client);key,_=create_page(client,'protected-actions')
    with SessionLocal() as db:version=page_builder.row_for(db,key).version
    assert client.post('/admin/pages/'+key+'/publish',data={'csrf':'bad','version':version}).status_code==403
    logout(client);login_user(client)
    assert post(client,'/admin/pages/'+key+'/publish',{'version':version},'/account').status_code==403


def test_duplicate_address_in_existing_page_editor_has_actionable_message(client):
    setup(client)
    first,_=create_page(client,'taken-address')
    second,value=create_page(client,'other-address')
    value['page_settings']['slug']='taken-address'
    with SessionLocal() as db:version=page_builder.row_for(db,second).version
    response=save_page(client,second,value,version=version)
    assert response.status_code==400
    assert 'This page address is already in use. Choose another address.' in response.text
    assert '<p data-error-message>Invalid value.</p>' not in response.text


def test_disabled_guide_keeps_snapshot_and_blocks_all_public_entry_points(client):
    setup(client)
    with SessionLocal() as db:
        page_builder.ensure_defaults(db);db.commit()
        row=page_builder.guide_row(db,'emby');key='p-'+str(row.id);version=row.version;published=row.published;slug=row.slug
        value=visual_builder.load(db,key,True)
    assert post(client,'/admin/pages/'+key+'/disable',{'version':version},'/admin/pages').status_code==303
    assert client.get('/access/emby?view=guide').status_code==404
    assert client.get('/access/emby/default_computer').status_code==404
    assert client.get('/pages/'+slug).status_code==404
    # Publishing content remains independent of visibility, too.
    assert save_page(client,key,value,True).status_code==200
    with SessionLocal() as db:
        row=page_builder.row_for(db,key);assert not row.enabled and row.published
        version=row.version
    assert post(client,'/admin/pages/'+key+'/enable',{'version':version},'/admin/pages').status_code==303
    assert client.get('/access/emby?view=guide').status_code==200
