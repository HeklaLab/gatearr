import json,re
from copy import deepcopy
from sqlalchemy import select
from app import main,permissions as p,admin_features
from app.db import SessionLocal
from app.models import User,PermissionGroup,PolicyState,Config
from test_portal import setup,post,csrf
from test_permissions_bridge import policy_api
from test_icon_uploads import png


def test_branding_uploaded_logo_name_and_full_browser_title(client):
    setup(client)
    data={'csrf':csrf(client,'/admin/branding'),'app_name':'Family media','login_text':'Welcome','public_url':'http://testserver','logo_url':'','emby_link':'','browser_title':'${app_name} — Welcome home','brand_display':'both'}
    response=client.post('/admin/settings',data=data,files={'icon_file':('logo.png',png(),'image/png')},follow_redirects=False)
    assert response.status_code==303,response.text
    with SessionLocal() as db:
        url=main.config(db,'logo_url');assert url.startswith('/media/icons/')
    assert client.get(url).content==png()
    for route in ('/home','/admin/branding','/admin/mail-editor'):
        page=client.get(route).text
        assert '<title>Family media — Welcome home</title>' in page
        assert f'src="{url}"' in page
        assert '/static/gatearr-logo.png' not in page
    # Old clients can still save the original identity fields and keep the custom title.
    assert post(client,'/admin/settings',{k:v for k,v in data.items() if k not in ('csrf','browser_title','brand_display')}|{'logo_url':url},'/admin/branding').status_code==303
    assert '<title>Family media — Welcome home</title>' in client.get('/home').text
    assert post(client,'/admin/settings',{k:v for k,v in data.items() if k!='csrf'}|{'logo_url':url,'browser_title':'','brand_display':'name'},'/admin/branding').status_code==303
    assert '<title>Family media · Your space</title>' in client.get('/home').text


def test_branding_rejects_unsafe_image_references_and_invalid_title(client):
    setup(client)
    data={'app_name':'Family','login_text':'Welcome','public_url':'http://testserver','logo_url':'javascript:alert(1)','emby_link':''}
    assert post(client,'/admin/settings',data,'/admin/branding').status_code==400
    assert post(client,'/admin/settings',data|{'logo_url':'/media/icons/'+'a'*64+'.png'},'/admin/branding').status_code==400
    assert post(client,'/admin/settings',data|{'logo_url':'','browser_title':'Bad\nTitle'},'/admin/branding').status_code==400
    assert post(client,'/admin/settings',data|{'logo_url':'','brand_display':'bad'},'/admin/branding').status_code==400


def test_groups_use_typed_controls_and_verify_native_schedules(client,policy_api,monkeypatch):
    uid,store,writes,api=policy_api
    for policy in store.values():policy.update(EnableAllDevices=False,EnabledDevices=[],MaxParentalRating=None)
    api.permission_options=lambda source:[{'Id':7,'Name':'PG-13'}] if source=='ratings' else [{'Id':'living-room','Name':'Living room TV'}] if source=='devices' else []
    path=post(client,'/admin/groups',{'name':'Family'},'/admin/groups').headers['location']
    page=client.get(path).text
    assert 'name="editor_format" value="human"' in page and 'Structured value (JSON)' not in page
    assert 'Living room TV' in page and 'data-schedules="value_AccessSchedules"' in page
    payload={'version':0,'editor_format':'human','members':[uid],'permission':['AccessSchedules','BlockedTags','EnabledDevices','MaxParentalRating'],'value_AccessSchedules_row':['0'],'value_AccessSchedules_0_day':'Weekday','value_AccessSchedules_0_start':'17:30','value_AccessSchedules_0_end':'22:00','value_BlockedTags':'Horror\nAdult','value_EnabledDevices':['living-room'],'value_MaxParentalRating':'7'}
    assert post(client,path,payload,path).status_code==303
    with SessionLocal() as db:
        row=db.get(PolicyState,uid);expected=json.loads(row.desired)
        assert expected['AccessSchedules']==[{'DayOfWeek':'Weekday','StartHour':17.5,'EndHour':22.0}]
        native_write=api.policy
        def policy_write(user_id,values):
            values=deepcopy(values)
            for slot in values.get('AccessSchedules',[]):slot.update(Id=123,UserId=user_id)
            native_write(user_id,values)
        monkeypatch.setattr(api,'policy',policy_write)
        assert p.apply(db,db.get(User,uid),row,api)
        db.refresh(row);assert not row.pending and not row.error
        assert json.loads(row.observed)['AccessSchedules'][0]['Id']==123
    assert store['user-1']['BlockedTags']==['Horror','Adult'] and store['user-1']['EnabledDevices']==['living-room']
    # Members already in this group must remain selectable.
    page=client.get(path).text
    member=re.search(r'<input[^>]*name="members"[^>]*value="'+str(uid)+r'"[^>]*>',page)[0]
    assert 'checked' in member and 'disabled' not in member


def test_group_unavailable_metadata_preserves_existing_policy(client,policy_api):
    uid,store,writes,api=policy_api
    for policy in store.values():policy['EnabledDevices']=['existing-device']
    path=post(client,'/admin/groups',{'name':'Unavailable devices'},'/admin/groups').headers['location']
    gid=int(path.rsplit('/',1)[1])
    with SessionLocal() as db:
        group=db.get(PermissionGroup,gid);group.policy='{"EnabledDevices":["existing-device"]}';db.commit()
    assert post(client,path,{'version':0,'editor_format':'human','members':[uid]},path).status_code==303
    with SessionLocal() as db:assert json.loads(db.get(PermissionGroup,gid).policy)['EnabledDevices']==['existing-device']


def test_email_builder_reloads_existing_content_and_preserves_email_styles(client):
    setup(client)
    source='<h2>Your account</h2><img src="https://example.com/image.png" width="400" alt="Family" style="display:block;margin-left:auto;margin-right:auto"><a href="${link}" style="display:table;padding:10px 18px;border-radius:6px;background-color:#159eff">Confirm</a>'
    assert post(client,'/admin/mail-editor',{'purpose':'invite','mail_locale':'en','subject':'Welcome ${username}','html':source},'/admin/mail-editor').status_code==303
    page=client.get('/admin/mail-editor').text
    assert 'class="studio mail-studio"' in page and 'class="mail-workspace"' not in page
    assert 'data-mail-command="undo"' in page and 'data-mail-view="preview"' in page
    with SessionLocal() as db:
        html=main.config(db,'invite_html')
        assert 'margin-left:auto' in html and 'padding:10px 18px' in html and 'border-radius:6px' in html and '${link}' in html


def test_media_public_url_is_centralized_outside_branding(client):
    from app.models import AccessService
    from app.guides import service_url
    setup(client)
    with SessionLocal() as db:
        service=db.get(AccessService,'emby');service.browser_url='https://current.test'
        main.set_config(db,'emby_link','https://obsolete.test');db.commit()
    page=client.get('/admin/branding').text
    assert 'name="emby_link"' not in page
    assert post(client,'/admin/settings',{'app_name':'Family','login_text':'Welcome','public_url':'http://testserver','logo_url':''},'/admin/branding').status_code==303
    with SessionLocal() as db:
        service=db.get(AccessService,'emby')
        assert service.browser_url=='https://current.test'
        assert service_url(db,service)=='/services/emby/open'
        service.browser_url='';db.commit()
        assert service_url(db,service)==''


def test_legacy_media_url_migration_preserves_application_address(client,monkeypatch):
    import importlib
    from types import SimpleNamespace
    from app.models import AccessService
    migration=importlib.import_module('migrations.versions.0019_media_browser_url')
    with SessionLocal() as db:
        main.set_config(db,'emby_link','https://old.test');db.commit()
        monkeypatch.setattr(migration,'op',SimpleNamespace(get_bind=lambda:db.connection()))
        migration.upgrade();db.commit();db.expire_all()
        assert db.get(AccessService,'emby').browser_url=='https://old.test'
        assert db.get(Config,'emby_link') is None
        db.get(AccessService,'emby').browser_url='https://preferred.test'
        main.set_config(db,'emby_link','https://old.test');db.commit()
        migration.upgrade();db.commit();db.expire_all()
        assert db.get(AccessService,'emby').browser_url=='https://preferred.test'


def test_group_permission_tabs_keep_all_settings_and_selected_tab(client,policy_api):
    uid,store,writes,api=policy_api
    for policy in store.values():policy['EnableRemoteAccess']=False
    path=post(client,'/admin/groups',{'name':'Tabbed group'},'/admin/groups').headers['location']
    for tab in ('members','emby','seerr','access'):
        page=client.get(path+'?tab='+tab).text
        assert f'data-group-tab="{tab}" aria-current="page"' in page
        assert f'data-group-panel="{tab}" >' in page
    response=post(client,path,{'version':0,'editor_format':'human','active_tab':'seerr','members':[uid],'permission':['EnableRemoteAccess'],'value_EnableRemoteAccess':'on','manage_seerr_access':'on','seerr_access':'on','manage_tools':'on','tools':['radarr']},path)
    assert response.status_code==303,response.text
    assert response.headers['location']==path+'?saved=1&tab=seerr'
    with SessionLocal() as db:
        group=db.get(PermissionGroup,int(path.rsplit('/',1)[1]))
        assert json.loads(group.policy)['EnableRemoteAccess'] is True
        assert json.loads(group.access_policy)['tools']==['radarr']
        assert json.loads(group.access_policy)['seerr_access'] is True
    with SessionLocal() as db:main.set_config(db,'media_server','jellyfin');db.commit()
    assert 'Jellyfin Permissions' in client.get(path+'?tab=emby').text
