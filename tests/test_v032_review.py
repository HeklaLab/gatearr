import json,re
from contextlib import contextmanager
from pathlib import Path
import httpx,pytest
from sqlalchemy import select
from app import main,default_journeys,portal,seerr_permissions as sp,seerr_quotas as sq
from app.models import Config,User,Guide,AccessService,ContentTranslation,PermissionGroup,GroupMember,SeerrQuotaState
from app.db import SessionLocal
from test_portal import setup,post,csrf
from test_permissions_bridge import policy_api


def test_factory_guides_icons_and_idempotent_seed(client):
    setup(client)
    with SessionLocal() as db:
        service=db.get(AccessService,'emby');nodes=json.loads(service.access_published)
        assert service.entry_mode=='structured'
        assert len({n['id'] for n in nodes})==len(nodes)
        assert {n['title'] for n in nodes if n['kind']=='guide'}=={'Mac','Windows','Linux','Android','iPhone','Smart TV'}
        assert db.get(AccessService,'seerr').entry_mode=='direct'
        count=len(list(db.scalars(select(Guide))));assert not default_journeys.seed(db,True)
        assert count==len(list(db.scalars(select(Guide))))
        for key in ('emby','seerr','radarr','sonarr','bazarr'):
            file=Path('app/static/services')/(key+'.png');assert file.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
        assert 'emby-theater-linux' in next(json.loads(g.draft) for g in db.scalars(select(Guide)) if 'Linux' in json.loads(g.draft)['title'])['steps'][0]['link_url']


def test_explicit_native_application_is_not_repeated_in_custom_links(client):
    setup(client)
    assert post(client,'/admin/menu',{'label':'Seerr','access_service':'seerr','url':'https://requests.example.com','icon':'link','position':10},'/admin').status_code==303
    page=client.get('/admin/integrations').text
    assert page.count('action="/admin/connections/emby"')==1
    assert '<h3><i class="fa-solid fa-grip-vertical"' not in page
    assert 'data-move=' not in page and 'application-editor' not in page
    assert '<h2>Custom application links</h2>' not in page
    assert post(client,'/admin/menu',{'label':'Custom guide app','url':'https://custom.example.com','icon':'link','position':20},'/admin').status_code==303
    with SessionLocal() as db:
        from app.models import MenuItem
        item=db.scalar(select(MenuItem).where(MenuItem.label=='Custom guide app'));item.access_service='custom-guide';db.commit()
    page=client.get('/admin/integrations').text
    assert page.count('application-editor')==1 and 'Custom guide app' in page
    assert post(client,'/admin/guides/service',{'key':'seerr','name':'Requests','browser_url':'https://new.example.com','icon':'link'},'/admin/integrations').status_code==303
    with SessionLocal() as db:
        from app.applications import catalog
        app=next(a for a in catalog(db,editor=True) if a['key']=='access:seerr');assert app['name']=='Requests' and 'new.example.com' in app['href']


def test_reset_retains_connections_accounts_and_invalidates_stale_editors(client):
    setup(client)
    with SessionLocal() as db:
        protected={k:main.config(db,k) for k in ('emby_url','emby_api_key','public_url','default_locale')}
        main.set_config(db,'smtp_host','smtp.local');main.set_config(db,'radarr_api_key','encrypted-sentinel');main.set_config(db,'ui_translation_en_custom','changed')
        main.set_config(db,'themes_published',json.dumps({'mode':'dark','dark':{'accent':'#aa00bb'}}));main.set_config(db,'portal_version','9')
        gids=set(db.scalars(select(Guide.id)));uids=list(db.scalars(select(User.id)));db.commit()
    token=csrf(client,'/admin/updates')
    assert client.post('/admin/updates/reset-content',data={'csrf':token,'confirm':'on','confirmation':'wrong'}).status_code==400
    response=client.post('/admin/updates/reset-content',data={'csrf':token,'confirm':'on','confirmation':'RESET'},follow_redirects=False)
    assert response.status_code==303
    with SessionLocal() as db:
        assert all(main.config(db,k)==v for k,v in protected.items())
        assert main.config(db,'smtp_host')=='smtp.local' and main.config(db,'radarr_api_key')=='encrypted-sentinel'
        assert not main.config(db,'ui_translation_en_custom')
        assert list(db.scalars(select(User.id)))==uids
        assert gids.isdisjoint(set(db.scalars(select(Guide.id))))
        assert main.config(db,'portal_version')=='10'
        assert db.get(AccessService,'emby').entry_mode=='structured' and db.get(AccessService,'seerr').entry_mode=='direct'
    assert client.post('/admin/design/home/save',data={'csrf':token,'payload':'{}','version':9}).status_code==403

@pytest.fixture
def quota_api(client,monkeypatch):
    setup(client);settings={'username':'demo','email':'keep@example.com','locale':'fr','movieQuotaLimit':5,'movieQuotaDays':7,'tvQuotaLimit':10,'tvQuotaDays':7,'watchlistSyncMovies':True};writes=[]
    @contextmanager
    def connection(db,user):
        def handle(request):
            if request.method=='POST':
                values=json.loads(request.content);writes.append(values);settings.update(values)
            return httpx.Response(200,json=settings)
        with httpx.Client(base_url='http://seerr/',transport=httpx.MockTransport(handle)) as client:yield client,2
    monkeypatch.setattr(sq,'connection',connection);monkeypatch.setattr(sq,'configured',lambda db:True)
    with SessionLocal() as db:uid=db.scalar(select(User.id).where(User.emby_id=='user-1'));sq.inspect(db,db.get(User,uid))
    return uid,settings,writes


def test_individual_quotas_read_back_preserve_other_settings_and_can_restore(client,quota_api):
    uid,settings,writes=quota_api;path=f'/admin/users/{uid}/seerr/quotas'
    with SessionLocal() as db:version=db.get(SeerrQuotaState,uid).version
    data={'version':version,'manage_quotas':'on','movieQuotaLimit':2,'movieQuotaDays':14,'tvQuotaLimit':3,'tvQuotaDays':7}
    assert post(client,path,data,'/admin').status_code==303
    assert settings['movieQuotaLimit']==2 and settings['tvQuotaLimit']==3
    assert settings['email']=='keep@example.com' and settings['watchlistSyncMovies'] is True
    with SessionLocal() as db:
        state=db.get(SeerrQuotaState,uid);assert not state.pending and state.desired==state.observed;version=state.version
    assert post(client,path,{'version':version},'/admin').status_code==303
    assert settings['movieQuotaLimit']==5


def test_group_quotas_own_the_user_and_removal_restores_original(client,quota_api):
    uid,settings,writes=quota_api
    with SessionLocal() as db:
        group=PermissionGroup(name='Quota owners',policy='{}',access_policy=json.dumps({'seerr_quotas':{'movieQuotaLimit':1,'movieQuotaDays':7,'tvQuotaLimit':0,'tvQuotaDays':7}}));db.add(group);db.flush()
        user=db.get(User,uid);db.add(GroupMember(user_id=uid,group_id=group.id));sq.group_changed(db,user,group);db.commit();sq.apply(db,user)
    assert settings['movieQuotaLimit']==1
    assert post(client,f'/admin/users/{uid}/seerr/quotas',{'version':1,'manage_quotas':'on'},'/admin').status_code==409
    with SessionLocal() as db:
        user=db.get(User,uid);sq.group_changed(db,user,None);db.commit();sq.apply(db,user)
    assert settings['movieQuotaLimit']==5 and settings['tvQuotaLimit']==10


def test_counter_visibility_is_independent_and_hidden_makes_no_remote_call(client,monkeypatch):
    setup(client)
    assert post(client,'/admin/seerr-display',{'member':'on'},'/admin/integrations').status_code==303
    monkeypatch.setattr(sp,'configured',lambda db:True)
    def unexpected(*a):raise AssertionError('Hidden statistics must not contact Seerr')
    monkeypatch.setattr(sp,'connection',unexpected)
    with SessionLocal() as db:user=db.scalar(select(User).where(User.admin.is_(True)));assert sp.summary(db,user) is None
    assert 'Show counters for users' in client.get('/admin/integrations').text


def test_spacing_is_validated_and_guide_navigation_is_separate(client):
    setup(client)
    with SessionLocal() as db:value=portal.load(db,True)
    value['blocks'].append({'id':'gap','kind':'spacer','region':'main','order':90,'span':12,'size':148})
    response=post(client,'/admin/design/home/preview',{'payload':json.dumps(value)},'/admin/portal')
    assert response.status_code==200 and 'height:148px' in response.text
    value['blocks'][-1]['size']='injection'
    assert post(client,'/admin/design/home/preview',{'payload':json.dumps(value)},'/admin/portal').status_code==400
    page=client.get('/admin/portal').text
    assert page.index('data-command="page-settings"')<page.index('id="studio-palette"')
    assert 'builder-howtos' not in page and '/admin/access-guides' in page
    assert client.get('/admin/access-guides').status_code==200


def test_builder_logs_are_readable_and_reset_requires_admin_and_csrf(client):
    setup(client)
    from app.visual_builder import load
    with SessionLocal() as db:layout=load(db,'login',True)
    assert post(client,'/admin/design/login/save',{'payload':json.dumps(layout),'version':0},'/admin/portal').status_code==200
    page=client.get('/admin/activity').text
    assert 'Login screen · Draft saved' in page and 'POST /admin/design/login/save' not in page
    assert client.post('/admin/updates/reset-content',data={'csrf':'wrong','confirm':'on','confirmation':'RESET'}).status_code==403


def test_review_navigation_group_counts_and_admin_tools(client):
    setup(client)
    page=client.get('/admin/access-guides').text
    tabs=re.search(r'<div class="admin-sidebar-children">(.*?)</div>',page,re.S).group(1)
    assert 'Access guide' not in tabs and 'Footer' not in tabs
    assert tabs.count('aria-current="page"')==1 and 'Portal builder' in tabs
    with SessionLocal() as db:
        uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
        empty=PermissionGroup(name='Empty group');populated=PermissionGroup(name='Populated group')
        db.add_all([empty,populated]);db.flush();db.add(GroupMember(group_id=populated.id,user_id=uid));db.commit()
    page=client.get('/admin/groups').text
    assert 'Members: 0' in page and 'Members: 1' in page
    page=client.get(f'/admin/users/{uid}?tab=access').text
    assert 'Minimum characters:' not in page
    for tool in ('radarr','sonarr','bazarr'):
        assert f'name="tools" value="{tool}"' in page
    # A permission can be prepared before connecting a tool; the tool stays inaccessible.
    assert post(client,f'/admin/users/{uid}/role',{'tools':['radarr']},'/admin').status_code==409  # group ownership
    with SessionLocal() as db:
        from sqlalchemy import delete
        db.execute(delete(GroupMember).where(GroupMember.user_id==uid));db.commit()
    assert post(client,f'/admin/users/{uid}/role',{'tools':['radarr']},'/admin').status_code==400
    with SessionLocal() as db:assert json.loads(db.get(User,uid).tool_access)==[]
    assert client.get('/tools/radarr').status_code in (403,404)
    assert post(client,f'/admin/users/{uid}/role',{'tools':['unknown']},'/admin').status_code==400


def test_application_capacity_and_preview_after_reset(client):
    setup(client)
    from copy import deepcopy
    from app.applications import normalize
    with SessionLocal() as db:
        main.set_config(db,'seerr_enabled','true');db.commit()
        layout=portal.load(db)
        row=next(b for b in layout['blocks'] if b['kind']=='applications')
        assert 'access:seerr' in row['applications']
        assert 'access:seerr' not in {a['key'] for r in portal.for_display(layout,'en',db.scalar(select(User)),db).values() for b in r for a in b.get('cards',[])}
        assert 'access:seerr' in {a['key'] for r in portal.for_display(layout,'en',db.scalar(select(User)),db,editor=True).values() for b in r for a in b.get('cards',[])}
        row['columns']=2;row['applications']=['access:emby','access:seerr','account']
        with pytest.raises(ValueError,match='configured number'):portal.validate(layout)
        upgraded=normalize(deepcopy(layout),db)
        rows=[b for b in upgraded['blocks'] if b['kind']=='applications']
        assert [b['applications'] for b in rows]==[['access:emby','access:seerr'],['account']]
        assert normalize(upgraded,db)==upgraded
        portal.validate(upgraded)
    # Reset preserves the public address formerly held only by a legacy menu row.
    assert post(client,'/admin/menu',{'label':'Seerr','url':'https://requests.example.com','icon':'link','position':10},'/admin').status_code==303
    assert post(client,'/admin/updates/reset-content',{'confirm':'on','confirmation':'RESET'},'/admin/updates').status_code==303
    with SessionLocal() as db:
        assert db.get(AccessService,'seerr').browser_url=='https://requests.example.com'
        from app.applications import catalog
        assert next(a for a in catalog(db,db.scalar(select(User))) if a['key']=='access:seerr')['href']=='https://requests.example.com'


def test_username_rename_updates_media_then_retries_seerr_without_losing_settings(client,fake,monkeypatch):
    from app import usernames
    setup(client)
    with SessionLocal() as db:
        uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
        main.set_config(db,'seerr_enabled','true');main.set_config(db,'seerr_url','https://seerr.example.com');main.set_config(db,'seerr_api_key','test-key');db.commit()
    renamed=[]
    monkeypatch.setattr(fake,'rename',lambda rid,name:renamed.append((rid,name)),raising=False)
    values={'username':'demo','email':'retained@example.com','locale':'fr','movieQuotaLimit':2,'tvQuotaDays':7};writes=[]
    offline=[True]
    @contextmanager
    def connection(db,user):
        if offline[0]:raise sq.SyncError('unavailable')
        def handle(request):
            if request.method=='POST':
                data=json.loads(request.content);writes.append(data);values.update(data)
            return httpx.Response(200,json=values)
        with httpx.Client(base_url='https://seerr.example.com/',transport=httpx.MockTransport(handle)) as remote:yield remote,2
    monkeypatch.setattr(usernames,'connection',connection)
    path=f'/admin/users/{uid}/account'
    assert post(client,path,{'action':'username','name':'owner'},'/admin').status_code==400
    assert not renamed
    assert post(client,path,{'action':'username','name':'New demo'},'/admin').status_code==303
    assert renamed==[('user-1','New demo')]
    with SessionLocal() as db:
        user=db.get(User,uid);assert user.name=='New demo'
        assert usernames.status(db,uid)['state']=='failed — retry required'
        offline[0]=False;usernames.apply(db,user)
        assert usernames.status(db,uid)['state']=='Synchronized'
    assert values['username']=='New demo' and values['email']=='retained@example.com' and values['movieQuotaLimit']==2
    assert len(writes)==1


def test_media_rename_contract_preserves_policy_and_checks_readback(monkeypatch):
    from app.emby import EmbyClient,EmbyError
    api=EmbyClient();current={'Id':'u-1','Name':'Old','Policy':{'EnableAllFolders':False}};writes=[]
    monkeypatch.setattr(api,'user',lambda uid:dict(current))
    def request(method,path,**kwargs):
        writes.append(kwargs['json']);current.update(kwargs['json'])
    monkeypatch.setattr(api,'request',request)
    api.rename('u-1','New')
    assert current['Name']=='New' and writes[0]['Policy']=={'EnableAllFolders':False}
    monkeypatch.setattr(api,'request',lambda *a,**k:None)
    with pytest.raises(EmbyError):api.rename('u-1','Ignored')


def test_username_and_verified_email_login_resolve_same_identity(client,fake,monkeypatch):
    from test_portal import logout
    setup(client)
    with SessionLocal() as db:
        member=db.scalar(select(User).where(User.emby_id=='user-1'));uid=member.id;member.email='demo@example.com';db.commit()
    logout(client)
    for identity in ('demo','demo@example.com',' DEMO@EXAMPLE.COM '):
        assert post(client,'/login',{'name':identity,'password':'DemoPassword123!'},'/login').status_code==303
        assert client.get('/account').status_code==200
        logout(client)
    assert post(client,'/login',{'name':'demo@example.com','password':'wrong'},'/login').status_code==401
    # A valid password on another native account must never satisfy an email alias.
    original=fake.authenticate
    monkeypatch.setattr(fake,'authenticate',lambda name,password:{'User':fake.owner(),'AccessToken':'owner-token'})
    assert post(client,'/login',{'name':'demo@example.com','password':'DemoPassword123!'},'/login').status_code==401
    monkeypatch.setattr(fake,'authenticate',original)
    with SessionLocal() as db:
        member=db.get(User,uid);member.portal_disabled=True;db.commit()
    assert post(client,'/login',{'name':'demo@example.com','password':'DemoPassword123!'},'/login').status_code==401
    assert post(client,'/login',{'name':'demo','password':'DemoPassword123!'},'/login').status_code==401
