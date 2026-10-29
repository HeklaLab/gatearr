import json,importlib
from copy import deepcopy
from types import SimpleNamespace
from sqlalchemy import create_engine,text,select
from app import page_presets,visual_builder,page_builder,portal,main
from app.db import SessionLocal
from app.models import User
from test_portal import setup
from test_content_pages import create_page,save_page
from test_visual_studio import design


def test_new_page_preset_has_editable_compact_menu_and_no_forced_header(client):
    setup(client);key,value=create_page(client,'compact-nav',preset='blank')
    menus=[b for b in value['blocks'] if b['kind']=='page_menu']
    assert len(menus)==1 and menus[0]['menu_layout']=='pills' and menus[0]['menu_source']=='navigation' and menus[0]['show_back']
    assert save_page(client,key,value,True).status_code==200
    response=client.get('/pages/compact-nav').text
    assert 'layout-pills' in response and 'data-page-back' in response and 'class="page-pill"' in response
    assert 'aria-current="page"' in response and 'published-pages-nav' not in response
    value['blocks']=[];assert save_page(client,key,value,True).status_code==200
    response=client.get('/pages/compact-nav').text
    assert 'class="page-pill"' not in response and 'data-page-back' not in response
    assert 'published-pages-nav' not in client.get('/account').text


def test_automatic_navigation_respects_permissions_visibility_and_selection(client):
    setup(client);key,value=create_page(client,'visible-nav');other,hidden=create_page(client,'hidden-nav')
    hidden['page_settings']['audience']=dict(everyone=False,admins=False,groups=[])
    assert save_page(client,other,hidden,True).status_code==200
    assert save_page(client,key,value,True).status_code==200
    response=client.get('/pages/visible-nav').text
    assert '/pages/visible-nav' in response and '/pages/hidden-nav' not in response
    with SessionLocal() as db:version=page_builder.row_for(db,key).version
    from test_portal import post
    assert post(client,'/admin/pages/'+key+'/disable',dict(version=version),'/admin/pages').status_code==303
    assert client.get('/pages/visible-nav').status_code==404


def test_compact_menu_and_back_work_on_account_footer_but_never_home(client):
    setup(client)
    menu=page_presets.block('page_menu','compact',menu_layout='pills',page_ids=['home'],show_back=True)
    with SessionLocal() as db:
        for page in ('account','footer'):
            value=visual_builder.load(db,page,True);value['blocks'].append(deepcopy(menu))
            visual_builder.save(db,page,value,visual_builder.version(db,page),True)
    assert 'data-page-back' in client.get('/account').text
    assert 'data-page-back' not in client.get('/home').text # footer cannot show Back on Home
    with SessionLocal() as db:home=visual_builder.load(db,'home',True)
    home['blocks']=[menu]
    assert design(client,'home','save',home).status_code==400
    home['blocks'][0]['show_back']=False
    assert design(client,'home','save',home).status_code==200
    with SessionLocal() as db:account=visual_builder.load(db,'account',True)
    for layout in ('cards','tiles','list','pills'):
        next(b for b in account['blocks'] if b['id']=='compact')['menu_layout']=layout
        assert design(client,'account','preview',account).status_code==200


def test_navigation_migration_keeps_draft_and_published_independent_and_is_idempotent(monkeypatch):
    migration=importlib.import_module('migrations.versions.0034_page_navigation_block')
    engine=create_engine('sqlite://')
    with engine.begin() as db:
        db.execute(text('CREATE TABLE content_pages(id INTEGER PRIMARY KEY,draft TEXT,published TEXT,version INTEGER)'))
        draft=dict(blocks=[dict(id='draft',kind='text',order=10,body='Pending')]);published=dict(blocks=[dict(id='published',kind='text',order=20,body='Public')])
        authored=dict(blocks=[dict(id='custom-menu',kind='page_menu',order=20,menu_layout='cards')])
        db.execute(text('INSERT INTO content_pages VALUES (1,:draft,:published,4),(2,:authored,:authored,8)'),dict(draft=json.dumps(draft),published=json.dumps(published),authored=json.dumps(authored)))
        monkeypatch.setattr(migration,'op',SimpleNamespace(get_bind=lambda:db));migration.upgrade()
        row=db.execute(text('SELECT * FROM content_pages WHERE id=1')).mappings().one()
        assert row['version']==5
        for field,marker in [('draft','Pending'),('published','Public')]:
            value=json.loads(row[field]);assert value['blocks'][0]['body']==marker
            menu=value['blocks'][1];assert menu['kind']=='page_menu' and menu['order']<value['blocks'][0]['order']
        migration.upgrade()
        assert db.execute(text('SELECT version FROM content_pages WHERE id=1')).scalar()==5
        row=db.execute(text('SELECT * FROM content_pages WHERE id=2')).mappings().one()
        assert row['version']==8 and row['draft']==json.dumps(authored)
