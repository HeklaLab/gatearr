"""Human editors, conflict protection and the two native media contracts."""
from copy import deepcopy
import json
from types import SimpleNamespace
import httpx
import pytest
from starlette.datastructures import FormData
from sqlalchemy import select
from app import permission_ui as ui,permissions as policies,admin_features,main
from app.emby import EmbyClient,JellyfinClient
from app.db import SessionLocal
from app.models import User,PolicyState
from app.permission_refresh import refresh_due as REAL_REFRESH
from test_portal import setup,post


def control(key,value,options=None):
    item={'key':key,'label':key,'value':value,'kind':'bool' if type(value) is bool else 'int' if type(value) is int else 'json','editable':True,'color':'neutral'}
    return ui.controls([item],options or {})[0]['fields'][0]


def test_typed_schedules_preserve_native_ids_and_reject_invalid_ranges():
    original=[{'Id':42,'UserId':'native-id','DayOfWeek':'Monday','StartHour':8,'EndHour':24}]
    field=control('AccessSchedules',original)
    data=FormData([('AccessSchedules_row','0'),('AccessSchedules_0_day','Weekend'),('AccessSchedules_0_start','09:30'),('AccessSchedules_0_end','24:00')])
    assert ui.parse(field,data)==[{'Id':42,'UserId':'native-id','DayOfWeek':'Weekend','StartHour':9.5,'EndHour':24}]
    with pytest.raises(ValueError):ui.parse(field,FormData([('AccessSchedules_row','1'),('AccessSchedules_1_day','Monday'),('AccessSchedules_1_start','23:00'),('AccessSchedules_1_end','08:00')]))
    assert original[0]['StartHour']==8
    assert ui.parse(field,FormData())==[]


def test_named_controls_fail_closed_and_preserve_unlisted_selection():
    field=control('EnabledDevices',['old-device'],{'devices':[{'Id':'device','Name':'Living room TV'}]})
    assert field['options'][1]['Name']=='Previously selected item 1 (unavailable)'
    assert ui.parse(field,FormData([('EnabledDevices','device'),('EnabledDevices','old-device')]))==['device','old-device']
    with pytest.raises(ValueError):ui.parse(field,FormData([('EnabledDevices','foreign')]))
    missing=control('EnabledDevices',[],{'devices':None})
    with pytest.raises(ValueError):ui.parse(missing,FormData())
    assert not any(x['Id']=='Game' for x in control('BlockUnratedItems',[])['options'])


def test_ratings_tags_and_bitrate_have_native_value_types():
    field=control('MaxParentalRating',None,{'ratings':[{'Id':13,'Name':'PG-13'}]})
    assert ui.parse(field,FormData({'MaxParentalRating':'13'}))==13
    assert ui.parse(field,FormData({'MaxParentalRating':''})) is None
    tags=control('BlockedTags',['old'])
    assert ui.parse(tags,FormData({'BlockedTags':'Horror\nViolence\nHorror'}))==['Horror','Violence']
    bitrate=control('RemoteClientBitrateLimit',1500000)
    assert bitrate['display_value']=='1.5'
    assert ui.parse(bitrate,FormData({'RemoteClientBitrateLimit':'4.25'}))==4250000
    with pytest.raises(ValueError):ui.parse(bitrate,FormData({'RemoteClientBitrateLimit':'NaN'}))


@pytest.mark.parametrize('cls,auth',[ (EmbyClient,'X-Emby-Token'),(JellyfinClient,'Authorization')])
def test_media_policy_contract_preserves_unrelated_fields_and_reads_back(client,monkeypatch,cls,auth):
    setup(client)
    client=cls('http://media.test','secret');store={'EnableMediaPlayback':True,'EnabledDevices':['tv'],'AccessSchedules':[],'NativeFutureField':{'kept':True}};calls=[]
    def request(method,path,**kwargs):
        calls.append((method,path,deepcopy(kwargs)))
        if method=='GET':return {'Id':'uid','Policy':deepcopy(store)}
        store.update(kwargs['json'])
    monkeypatch.setattr(client,'request',request)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'));user.emby_id='uid';db.commit()
        row=PolicyState(user_id=user.id,baseline=policies.encoded(store),observed=policies.encoded(store),overrides='{}',desired='{"EnableMediaPlayback":false}',confirmed='{}',version=0,pending=True,error='')
        db.add(row);db.commit()
        try:
            assert policies.apply(db,user,row,client,expected_current={'EnableMediaPlayback':True})
            assert store['NativeFutureField']=={'kept':True} and store['EnabledDevices']==['tv']
            assert [x[0] for x in calls]==['GET','POST','GET']
            assert calls[1][1]=='/Users/uid/Policy'
        finally:db.delete(row);db.commit()


@pytest.mark.parametrize('cls', [EmbyClient,JellyfinClient])
def test_native_metadata_auth_and_endpoints(monkeypatch,cls):
    import app.emby as module
    original=httpx.Client;seen=[]
    def handler(req):
        seen.append(req)
        if cls is JellyfinClient:assert 'Token="secret"' in req.headers['Authorization']
        else:assert req.headers['X-Emby-Token']=='secret'
        if req.url.path.endswith('SelectableMediaFolders'):return httpx.Response(200,json=[{'Guid':'guid','Name':'Movies','SubFolders':[{'Id':'path-id','Name':'Family','Path':'/private/path','IsUserAccessConfigurable':True}]}])
        if req.url.path.endswith('ParentalRatings'):return httpx.Response(200,json=[{'Name':'PG','Value':10}])
        return httpx.Response(200,json={'Items':[{'Id':'tv-id','Name':'Living room'}],'TotalRecordCount':1})
    monkeypatch.setattr(module.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    client=cls('http://media.test','secret')
    assert client.permission_options('devices')==[{'Id':'tv-id','Name':'Living room'}]
    assert client.permission_options('ratings')==[{'Id':10,'Name':'PG'}]
    folders=client.permission_options('folders')
    assert '/private/path' not in str(folders)
    assert seen[-1].url.path==('/Library/SelectableMediaFolders' if cls is EmbyClient else '/Library/MediaFolders')
    if cls is EmbyClient:assert folders==[{'Id':'guid_path-id','Name':'Movies / Family'}]


def test_category_ui_writes_typed_values_and_blocks_stale_forms(client,monkeypatch):
    setup(client)
    with SessionLocal() as db:uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
    store={'EnableMediaPlayback':True,'RemoteClientBitrateLimit':0,'AccessSchedules':[],'BlockedTags':[],'EnabledDevices':[],'EnableAllDevices':True,'AuthenticationProviderId':'secret-internal-id'};writes=[]
    api=SimpleNamespace(user=lambda uid:{'Id':uid,'Policy':deepcopy(store)},policy=lambda uid,p:(writes.append(deepcopy(p)),store.update(p)),libraries=lambda:[],users=lambda:[],copy_options=lambda:[],permission_options=lambda source:[{'Id':'tv','Name':'Living room TV'}])
    monkeypatch.setattr(policies,'emby',api);monkeypatch.setattr(admin_features,'emby',api)
    path=f'/admin/users/{uid}';page=client.get(path+'?tab=emby').text
    assert 'Structured value (JSON)' not in page and 'secret-internal-id' not in page
    assert 'Living room TV' in page and 'data-schedules="AccessSchedules"' in page
    payload={'category':'playback','version':0,'fields':['EnableMediaPlayback','RemoteClientBitrateLimit'],'hash_EnableMediaPlayback':policies.fingerprint(True),'hash_RemoteClientBitrateLimit':policies.fingerprint(0),'RemoteClientBitrateLimit':'5.5'}
    assert post(client,path+'/permissions/category',payload,path).status_code==303
    assert store['EnableMediaPlayback'] is False and store['RemoteClientBitrateLimit']==5500000
    assert store['AuthenticationProviderId']=='secret-internal-id'
    store['EnableMediaPlayback']=True
    assert post(client,path+'/permissions/category',payload,path).status_code==409
    assert len(writes)==1
    store_before=deepcopy(store)
    assert client.get(path+'?tab=emby').status_code==200 and store==store_before


def test_background_refresh_observes_external_edits_without_writes(client,monkeypatch):
    setup(client)
    from app import permission_refresh as refresh
    with SessionLocal() as db:uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
    calls=[]
    monkeypatch.setattr(refresh,'emby_connection',lambda:('http://media.test','key'))
    monkeypatch.setattr(refresh,'configured',lambda db:False)
    monkeypatch.setattr(refresh,'emby',SimpleNamespace(user=lambda uid:(calls.append(uid) or {'Policy':{'EnableMediaPlayback':False}})))
    REAL_REFRESH()
    with SessionLocal() as db:assert json.loads(db.get(PolicyState,uid).observed)['EnableMediaPlayback'] is False
    count=len(calls);REAL_REFRESH();assert len(calls)==count

# A scheduled observation must invalidate an already-open Seerr form too.
from test_v032 import seerr_api
from test_v032_review import quota_api
from app import seerr_permissions as sp,seerr_quotas as sq
from app.models import SeerrPolicyState,SeerrQuotaState


def test_observing_seerr_changes_invalidates_open_permission_form(client,seerr_api):
    uid,native,calls=seerr_api
    with SessionLocal() as db:version=sp.inspect_user(db,db.get(User,uid)).version
    native['permissions']=512
    with SessionLocal() as db:assert sp.inspect_user(db,db.get(User,uid)).version==version+1
    result=post(client,f'/admin/users/{uid}/seerr',{'version':version,'seerr_permission':['32']},'/admin/users')
    assert result.status_code==409 and native['permissions']==512
    assert not any(r.method=='POST' for r in calls)


def test_observing_seerr_changes_invalidates_open_quota_form(client,quota_api):
    uid,native,writes=quota_api
    with SessionLocal() as db:version=db.get(SeerrQuotaState,uid).version
    native['movieQuotaLimit']=99
    with SessionLocal() as db:assert sq.inspect(db,db.get(User,uid)).version==version+1
    result=post(client,f'/admin/users/{uid}/seerr/quotas',{'version':version,'manage_quotas':'on','movieQuotaLimit':2,'movieQuotaDays':7,'tvQuotaLimit':4,'tvQuotaDays':7},'/admin/users')
    assert result.status_code==409 and native['movieQuotaLimit']==99 and not writes
