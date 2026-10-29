"""Fresh defaults, native photo contracts, setup preservation and destructive group guards."""
import base64,json,re,time
from copy import deepcopy
from types import SimpleNamespace
import httpx,pytest
from sqlalchemy import select
from app import main,portal,avatars,permissions,i18n
from app.db import SessionLocal
from app.models import User,UserPhoto,PermissionGroup,GroupMember,PolicyState,Config
from app.security import encrypt
from test_portal import setup,post,csrf,logout,login_user,smtp
from test_icon_uploads import png


def test_fresh_portal_defaults_are_conditional_and_never_replace_custom_content(client):
    setup(client,fresh_layout=True)
    with SessionLocal() as db:
        value=portal.load(db);blocks=value['blocks']
        assert [b['kind'] for b in blocks]==['welcome','applications','applications','page_menu']
        assert blocks[1]['applications']==['access:emby'] and blocks[-2]['applications']==['account'] and blocks[-2]['columns']==1
        for service in ('seerr','tracearr','radarr','sonarr','bazarr','tdarr'):
            for key,val in {'enabled':'true','url':'http://'+service,'api_key':encrypt('private'),'interface_enabled':'true'}.items():main.set_config(db,service+'_'+key,val)
        full=portal.initial_layout(db)
        assert next(b for b in full['blocks'] if b['id']=='main-applications')['information']=={'access:emby':{'enabled':True},'access:seerr':{'enabled':True}}
        assert next(b for b in full['blocks'] if b['id']=='main-applications')['applications']==['access:emby','access:seerr']
        tools=next(b for b in full['blocks'] if b['id']=='admin-applications')
        assert tools['visibility']=='admins' and tools['columns']==5
        saved=deepcopy(portal.load(db));assert portal.initialize(db) is False and portal.load(db)==saved

@pytest.mark.parametrize('seerr_enabled,tracearr_enabled',[(False,False),(True,False),(False,True),(True,True)])
def test_fresh_widgets_stay_under_their_application_when_tracearr_is_enabled(client,seerr_enabled,tracearr_enabled):
    setup(client,fresh_layout=True)
    with SessionLocal() as db:
        for service,enabled in [('seerr',seerr_enabled),('tracearr',tracearr_enabled)]:
            if enabled:
                for key,val in {'enabled':'true','url':'http://'+service,'api_key':encrypt('private')}.items():
                    main.set_config(db,service+'_'+key,val)
        blocks=portal.initial_layout(db)['blocks']
        apps=next(b for b in blocks if b['id']=='main-applications')
        assert apps['columns']==1+int(seerr_enabled)
        assert set(apps['information'])==set(apps['applications'])
        assert all(info['enabled'] for info in apps['information'].values())
        assert not any(b['kind'] in ('widget_media','widget_seerr') for b in blocks)
        activity=[b for b in blocks if b['kind']=='widget_tracearr']
        assert bool(activity)==tracearr_enabled
        assert 'tracearr' not in apps['applications']
        if activity:assert activity[0]['order']>apps['order']


@pytest.mark.parametrize('kind,path',[('emby','/emby/Users/user-1/Images/Primary'),('jellyfin','/emby/UserImage')])
def test_photo_native_upload_uses_correct_identity_body_and_private_credentials(client,monkeypatch,kind,path):
    setup(client);raw=png();calls=[];real=httpx.Client
    def handler(req):
        calls.append(req);return httpx.Response(204) if req.method=='POST' else httpx.Response(200,content=raw)
    monkeypatch.setattr(avatars.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    with SessionLocal() as db:
        main.set_config(db,'media_server',kind);user=db.scalar(select(User).where(User.emby_id=='user-1'))
        avatars.native(db,user,'POST',raw,'image/png');assert calls[-1].url.path==path
        assert base64.b64decode(calls[-1].content)==raw
        assert 'test-api-key' in (calls[-1].headers.get('authorization','')+calls[-1].headers.get('x-emby-token',''))
        if kind=='jellyfin':assert calls[-1].url.params['userId']=='user-1'
        assert avatars.native(db,user,'GET')[0]==raw


def test_photo_cache_invalidates_on_native_change_and_removed_image(client):
    setup(client)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'))
        avatars.observe(db,user,{'PrimaryImageTag':'one'});db.flush();row=db.get(UserPhoto,user.id);row.content=png();old=avatars.url(db,user)
        avatars.observe(db,user,{'PrimaryImageTag':'two'});assert row.content is None and avatars.url(db,user)!=old
        avatars.observe(db,user,{});assert avatars.url(db,user)=='' and row.content is None


def test_photo_access_and_upload_guards(client,fake,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)));uid=db.scalar(select(User.id).where(User.emby_id=='user-1'));owner_id=owner.id
        avatars.observe(db,owner,{'PrimaryImageTag':'owner'});db.get(UserPhoto,owner.id).content=png();db.commit()
    logout(client);login_user(client)
    assert client.get('/avatars/'+str(owner_id)).status_code==404
    assert client.post('/account/photo',data={'csrf':'wrong'},files={'icon_file':('a.png',png(),'image/png')}).status_code==403
    assert client.post('/account/photo',data={'csrf':csrf(client,'/account')},files={'icon_file':('a.svg',b'<svg/>','image/svg+xml')}).status_code==400
    assert client.post('/admin/users/'+str(owner_id)+'/photo',data={'csrf':csrf(client,'/account')},files={'icon_file':('a.png',png(),'image/png')}).status_code==403


def group_fixture(client,monkeypatch):
    setup(client)
    remote={'user-1':{'Id':'user-1','Name':'demo','Policy':{'EnableAllFolders':False,'EnabledFolders':[],'IsDisabled':False,'IsAdministrator':False}}}
    writes=[]
    api=SimpleNamespace(user=lambda uid:deepcopy(remote[uid]),users=lambda:list(deepcopy(remote).values()),libraries=lambda:[],policy=lambda uid,p:(writes.append(deepcopy(p)),remote[uid].update(Policy=p)),request=lambda method,path,**kw:remote.pop(path.split('/')[-1]))
    monkeypatch.setattr(permissions,'emby',api)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'));group=PermissionGroup(name='Members',policy='{}',version=0);db.add(group);db.flush();db.add(GroupMember(user_id=user.id,group_id=group.id));db.commit();gid=group.id;uid=user.id
        data={'version':'0','membership':permissions.membership_hash(db,gid)}
    return gid,uid,data,remote,writes


def test_group_rename_conflict_and_delete_without_users(client,monkeypatch):
    gid,uid,data,remote,writes=group_fixture(client,monkeypatch)
    assert post(client,f'/admin/groups/{gid}/rename',{'version':'-1','name':'Renamed'},'/admin').status_code==409
    assert post(client,f'/admin/groups/{gid}/rename',{'version':'0','name':'Renamed'},'/admin').status_code==303
    data.update(version='1',mode='group')
    assert post(client,f'/admin/groups/{gid}/delete',data,'/admin').status_code==303
    with SessionLocal() as db:assert db.get(User,uid) and not db.get(PermissionGroup,gid) and not db.get(GroupMember,(gid,uid))
    assert 'user-1' in remote


def test_group_and_native_users_require_two_confirmations_and_current_membership(client,monkeypatch):
    gid,uid,data,remote,writes=group_fixture(client,monkeypatch);data['mode']='users'
    assert post(client,f'/admin/groups/{gid}/delete',data,'/admin').status_code==400
    data.update(confirm_delete='on',confirmation='DELETE')
    assert post(client,f'/admin/groups/{gid}/delete',{**data,'membership':'stale'},'/admin').status_code==409
    assert uid and 'user-1' in remote
    assert post(client,f'/admin/groups/{gid}/delete',data,'/admin').status_code==303
    with SessionLocal() as db:assert not db.get(User,uid) and not db.get(PermissionGroup,gid)
    assert not remote


def test_group_bulk_delete_refuses_administrators_before_writes(client,monkeypatch):
    gid,uid,data,remote,writes=group_fixture(client,monkeypatch);remote['user-1']['Policy']['IsAdministrator']=True
    assert post(client,f'/admin/groups/{gid}/delete',{**data,'mode':'users','confirm_delete':'on','confirmation':'DELETE'},'/admin').status_code==409
    assert 'user-1' in remote


def test_notifications_depend_on_email_services_and_never_control_widget_visibility(client):
    setup(client)
    with SessionLocal() as db:
        for key,value in {'tracearr_enabled':'true','tracearr_url':'http://tracearr','tracearr_api_key':encrypt('secret')}.items():main.set_config(db,key,value)
        db.commit()
    assert 'id="notification-settings"' not in client.get('/account').text
    assert post(client,'/account/notifications',{'seasons_email':'on'},'/account').status_code==409
    smtp(client);page=client.get('/account').text
    section=page.split('id="notification-settings"')[1].split('</section>')[0]
    assert 'SMTP' not in section and 'Tracearr' not in section and 'Seerr' not in section and 'name="seasons"' not in section


def test_wizard_language_preview_translates_without_sign_in_or_admin_navigation(client):
    page=client.get('/setup?locale=fr').text
    assert '<html lang="fr"' in page and 'Langue par défaut' in page
    assert 'src="/static/gatearr-logo.png"' in page and 'Blue Boréal' in page
    assert 'class="admin-navigation"' not in page and 'href="/login"' not in page
    assert '/static/setup-wizard.js' in page
    assert page.index('name="app_name"')<page.index('name="icon_file"')


def test_group_delete_stops_before_native_write_when_linked_permissions_cannot_be_verified(client,monkeypatch):
    from contextlib import contextmanager
    from app import seerr_permissions
    from app.integrations import SyncError
    gid,uid,data,remote,writes=group_fixture(client,monkeypatch)
    @contextmanager
    def linked(db,user):yield object(),2
    def unavailable(*args):raise SyncError('not_found')
    monkeypatch.setattr(seerr_permissions,'configured',lambda db:True)
    monkeypatch.setattr(seerr_permissions,'connection',linked)
    monkeypatch.setattr(seerr_permissions,'read_permissions',unavailable)
    response=post(client,f'/admin/groups/{gid}/delete',{**data,'mode':'users','confirm_delete':'on','confirmation':'DELETE'},'/admin')
    assert response.status_code==502 and 'user-1' in remote
    with SessionLocal() as db:assert db.get(User,uid) and db.get(PermissionGroup,gid)


def test_partial_group_deletion_keeps_remaining_members_for_review(client,monkeypatch):
    from app.emby import EmbyError
    gid,uid,data,remote,writes=group_fixture(client,monkeypatch)
    with SessionLocal() as db:
        other=User(emby_id='other-2',name='Other',active=True,admin=False,version=0,locale='en');db.add(other);db.flush();oid=other.id
        db.add(GroupMember(group_id=gid,user_id=oid));db.commit();data['membership']=permissions.membership_hash(db,gid)
    remote['other-2']={'Id':'other-2','Name':'Other','Policy':{'IsAdministrator':False}}
    def remove(method,path,**kwargs):
        if path.endswith('/other-2'):raise EmbyError('unavailable')
        remote.pop(path.split('/')[-1])
    monkeypatch.setattr(permissions.emby,'request',remove)
    result=post(client,f'/admin/groups/{gid}/delete',{**data,'mode':'users','confirm_delete':'on','confirmation':'DELETE'},'/admin')
    assert result.status_code==502 and 'Some linked accounts' in result.text
    with SessionLocal() as db:assert not db.get(User,uid) and db.get(User,oid) and db.get(GroupMember,(gid,oid)) and db.get(PermissionGroup,gid)
