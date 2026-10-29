"""Member Tracearr access and custom-link guides retain explicit identities and grants."""
import json,re
import pytest
from sqlalchemy import select
from app import main,page_builder,applications,visual_builder,group_access
from app.models import User,AccessService,Guide,MenuItem,PermissionGroup,GroupMember,ContentPage
from app.db import SessionLocal
from test_portal import setup,post,logout,login_user
from test_application_behavior import row,write,state,card_href


def tracearr_ready(db):
    for key,value in dict(enabled='true',url='http://private-tracearr:3000',api_key='private-token',public_url='https://stats.example.test',interface_enabled='true').items():main.set_config(db,'tracearr_'+key,value)


def member(db):return db.scalar(select(User).where(User.emby_id=='user-1'))


def test_native_tracearr_interface_is_admin_only_and_no_longer_offers_user_guides(client):
    setup(client)
    with SessionLocal() as db:
        tracearr_ready(db);owner=db.scalar(select(User).where(User.admin.is_(True)));owner.tool_access='["tracearr"]';db.commit()
        app=next(a for a in applications.catalog(db,editor=True) if a['key']=='tracearr')
        assert app['opening_modes']==['embedded','direct'] and app['howto']==''
    layout,version=state();layout['blocks']=[row('legacy-trace','tracearr','guide')]
    assert write(client,layout,version).status_code==200
    html=client.get('/home').text
    assert 'widget_tracearr' in html and 'href="/tools/tracearr"' in html
    assert client.get('/tools/tracearr').status_code==200
    logout(client);assert login_user(client).status_code==303
    with SessionLocal() as db:member(db).tool_access='["tracearr","tdarr"]';db.commit()
    assert client.get('/tools/tracearr').status_code==403
    assert client.get('/access/tracearr?view=guide').status_code==403
    assert client.get('/pages/guide-tracearr').status_code==404
    assert 'href="/tools/tracearr"' not in client.get('/home').text


def test_tracearr_permission_can_be_saved_from_user_access_and_inherited_from_group(client):
    setup(client)
    with SessionLocal() as db:
        tracearr_ready(db);target=member(db);uid=target.id;db.commit()
    page=client.get('/admin/users/'+str(uid)+'?tab=access').text
    assert 'name="tools" value="tracearr"' in page
    response=post(client,f'/admin/users/{uid}/role',dict(tools='tracearr',bazarr_subtitle_limit='3'),'/admin')
    assert response.status_code==303,response.text
    with SessionLocal() as db:
        target=db.get(User,uid);assert not target.admin and 'tracearr' in json.loads(target.tool_access)
        group=PermissionGroup(name='Statistics members',access_policy=json.dumps(dict(tools=['tracearr'])));db.add(group);db.flush()
        target.tool_access='[]';db.add(GroupMember(group_id=group.id,user_id=uid));group_access.apply_access(db,target,group);db.commit()
        assert not target.admin and json.loads(target.tool_access)==['tracearr']
    logout(client);assert login_user(client).status_code==303
    assert client.get('/tools/tracearr').status_code==403


def test_tracearr_guide_articles_and_aliases_require_the_application_permission(client):
    setup(client)
    with SessionLocal() as db:
        tracearr_ready(db);page_builder.ensure_defaults(db)
        article=json.dumps(dict(title='Tracearr instructions',device='other',summary='Member statistics',steps=[]))
        guide=Guide(service_key='tracearr',draft=article,published=article,version=1);db.add(guide);db.commit();gid=guide.id
    assert client.get('/access/tracearr/guide/'+str(gid)+'?preview=1').status_code==200
    with SessionLocal() as db:owner=db.scalar(select(User).where(User.admin.is_(True)));assert 'tracearr' not in json.loads(owner.tool_access)
    logout(client);login_user(client)
    assert client.get('/access/tracearr/guide/'+str(gid)).status_code==403
    assert client.get('/help/'+str(gid)).status_code==403
    assert client.get('/pages/guide-tracearr?guide='+str(gid)).status_code==404
    with SessionLocal() as db:member(db).tool_access='["tracearr"]';db.commit()
    assert client.get('/access/tracearr/guide/'+str(gid)).status_code==403
    assert client.get('/help/'+str(gid)).status_code==403
    assert client.get('/access/tracearr/guide/'+str(gid)+'?preview=1').status_code==403


@pytest.mark.parametrize('name',['Tracearr','Emby','Radarr','Community'])
def test_manual_url_apps_create_their_own_guide_page_without_name_collisions(client,name):
    setup(client)
    assert post(client,'/admin/menu',dict(label=name,url='https://custom.example.test',position='50',icon='link'),'/admin').status_code==303
    with SessionLocal() as db:item=db.scalar(select(MenuItem).where(MenuItem.label==name));ident=item.id
    page=client.get('/admin/integrations').text
    assert '/admin/design/home/enable-howto/'+str(ident) in page
    created=post(client,'/admin/design/home/enable-howto/'+str(ident),{},'/admin')
    assert created.status_code==200
    with SessionLocal() as db:
        item=db.get(MenuItem,ident);key=item.access_service
        assert key=='service-'+str(ident)
        page=page_builder.guide_row(db,key);pid=page.id
        apps={a['key']:a for a in applications.catalog(db,editor=True)}
        assert apps['menu:'+str(ident)]['howto']==key
        if name=='Tracearr':assert apps['tracearr']['howto']==''
        if name=='Emby':assert apps['access:emby']['howto']=='emby'
    assert client.get('/admin/design/p-'+str(pid)).status_code==200
    assert client.get(created.json()['url']).status_code==200
    again=post(client,'/admin/design/home/enable-howto/'+str(ident),dict(open_editor='on'),'/admin')
    assert again.status_code==303 and again.headers['location']==created.json()['url']
    with SessionLocal() as db:assert db.scalar(select(ContentPage.id).where(ContentPage.system_key=='guide:'+key))==pid
    layout,version=state();layout['blocks']=[row('custom-guide','menu:'+str(ident),'guide')]
    assert write(client,layout,version).status_code==200
    assert card_href(client.get('/home').text,'custom-guide')=='/access/'+key+'?view=guide'
    assert post(client,'/admin/menu',dict(id=ident,label=name,url='https://updated.example.test',position='50',access_service=key,icon='link'),'/admin').status_code==303
    with SessionLocal() as db:assert db.get(AccessService,key).browser_url=='https://updated.example.test'


def test_other_native_admin_tools_still_do_not_expose_guide_editors(client):
    setup(client)
    for key in ('radarr','sonarr','bazarr','tdarr'):
        assert client.get('/admin/design/home/howto/'+key).status_code==400
    logout(client);login_user(client)
    assert post(client,'/admin/visual-howto/tracearr/new-guide',dict(payload=json.dumps(dict(title='Not allowed'))),'/account').status_code==403


def test_tracearr_uses_the_same_guide_then_journey_publication_flow(client):
    setup(client)
    with SessionLocal() as db:
        tracearr_ready(db);db.scalar(select(User).where(User.admin.is_(True))).tool_access='["tracearr"]';db.commit()
    created=post(client,'/admin/visual-howto/tracearr/new-guide',dict(payload=json.dumps(dict(title='Use your statistics'))),'/admin')
    assert created.status_code==200,created.text
    gid=created.json()['id']
    article=dict(title='Use your statistics',summary='Your personal viewing activity',device='other',steps=[dict(id='sign-in',title='Sign in',body='Use your Tracearr account.',link_label='',link_url='',image_url='')])
    with SessionLocal() as db:version=db.get(Guide,gid).version
    published=post(client,f'/admin/visual-guide/{gid}/publish',dict(payload=json.dumps(article),version=version),'/admin')
    assert published.status_code==200,published.text
    with SessionLocal() as db:version=db.get(AccessService,'tracearr').access_version
    journey=dict(mode='choices',browser_url='https://stats.example.test',nodes=[dict(id='statistics',kind='guide',title='My statistics',position=10,guide_id=gid)])
    published=post(client,'/admin/visual-howto/tracearr/publish',dict(payload=json.dumps(journey),version=version),'/admin')
    assert published.status_code==200,published.text
    html=client.get('/access/tracearr/guide/'+str(gid)).text
    assert 'Use your Tracearr account.' in html and 'private-token' not in html


def test_recreated_custom_link_does_not_adopt_an_orphaned_guide_identity(client):
    setup(client)
    assert post(client,'/admin/menu',dict(label='Old link',url='https://old.example.test',position='50',icon='link'),'/admin').status_code==303
    with SessionLocal() as db:ident=db.scalar(select(MenuItem.id).where(MenuItem.label=='Old link'))
    assert post(client,f'/admin/design/home/enable-howto/{ident}',{},'/admin').status_code==200
    with SessionLocal() as db:old_key=db.get(MenuItem,ident).access_service
    assert post(client,'/admin/menu/delete',dict(id=ident),'/admin').status_code==303
    assert post(client,'/admin/menu',dict(label='New link',url='https://new.example.test',position='50',icon='link'),'/admin').status_code==303
    with SessionLocal() as db:new_id=db.scalar(select(MenuItem.id).where(MenuItem.label=='New link'))
    assert post(client,f'/admin/design/home/enable-howto/{new_id}',{},'/admin').status_code==200
    with SessionLocal() as db:
        new_key=db.get(MenuItem,new_id).access_service
        assert new_key!=old_key
        assert db.get(AccessService,old_key).browser_url=='https://old.example.test'
        assert db.get(AccessService,new_key).browser_url=='https://new.example.test'
        assert 'access:'+old_key not in {a['key'] for a in applications.catalog(db,editor=True)}


def test_guide_origins_use_identity_and_publish_label(client):
    setup(client)
    editor=client.get('/admin/design/home/howto/tracearr').text
    assert '>Publish guide</button>' in editor
    assert '>Publish journey</button>' not in editor
    from types import SimpleNamespace
    for key,label in [('emby','Native application'),('tracearr','Native application'),('service-123','Custom application')]:
        descriptor=page_builder.descriptor(SimpleNamespace(id=123,system_key='guide:'+key,slug='example'),{'page_settings':{'title':'Tracearr'}})
        assert descriptor['guide_origin']==label
    pages=client.get('/admin/pages').text
    assert 'Native application</span>' in pages
    listing=client.get('/admin/pages').text
    assert '/admin/design/home/howto/tracearr' in listing
    legacy=client.get('/admin/access-guides',follow_redirects=False)
    assert legacy.status_code==303 and legacy.headers['location']=='/admin/pages'
