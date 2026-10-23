import json
from contextlib import contextmanager
import pytest
from sqlalchemy import select,func
from app import permissions as p,seerr_permissions as sp,seerr_quotas as sq
from app.db import SessionLocal
from app.models import User,GroupMember,PolicyState,PermissionGroup
from test_portal import post,csrf,reviewed_post
from test_permissions_bridge import policy_api


def make_group(client):return post(client,'/admin/groups',{'name':'Review group'},'/admin/groups').headers['location']
def preview(client,path,data):return post(client,path,{**data,'review_only':'on'},path)


def test_review_readonly_native_diff_confirmation_and_baseline(client,policy_api):
    uid,store,writes,api=policy_api;path=make_group(client)
    data={'version':0,'members':[uid],'permission':['SimultaneousStreamLimit'],'value_SimultaneousStreamLimit':'2','library_mode':'selected','libraries':['11111111111111111111111111111111']}
    with SessionLocal() as db:before=db.scalar(select(func.count()).select_from(PolicyState))
    assert post(client,path,data,path).status_code==409
    response=preview(client,path,data);assert response.status_code==200,response.text
    review=response.json();diff=review['users'][0]['differences']
    assert any(x['label']=='Library · Movies' and x['before']=='No' and x['after']=='Yes' for x in diff)
    assert not any('Films' in x['label'] for x in diff)
    assert any('simultaneous' in x['label'] and x['before']=='0' and x['after']=='2' for x in diff)
    assert not writes
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PolicyState))==before
        assert db.scalar(select(func.count()).select_from(GroupMember))==0
    assert post(client,path,{**data,'review_token':review['review_token']},path).status_code==303


def test_review_rejects_remote_drift_and_payload_changes(client,policy_api):
    uid,store,writes,api=policy_api;path=make_group(client);data={'version':0,'members':[uid]}
    proof=preview(client,path,data).json()['review_token']
    assert post(client,path,{**data,'manage_tools':'on','tools':['radarr'],'review_token':proof},path).status_code==409
    store['user-1']['EnableRemoteAccess']=False
    assert post(client,path,{**data,'review_token':proof},path).status_code==409
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(GroupMember))==0


def test_single_user_assignment_requires_review_and_shows_no_differences(client,policy_api):
    uid,store,writes,api=policy_api;group_path=make_group(client);path=f'/admin/users/{uid}/group';page=f'/admin/users/{uid}?tab=access'
    data={'group_id':group_path.rsplit('/',1)[1]}
    assert post(client,path,data,page).status_code==409
    response=post(client,path,{**data,'review_only':'on'},page)
    assert response.json()['users'][0]['differences']==[]
    assert post(client,path,{**data,'review_token':response.json()['review_token']},page).status_code==303
    assert post(client,path,{**data,'review_only':'on'},page).json()=={'required':False}


def test_bulk_review_has_each_user_and_library_scope(client,policy_api):
    uid,store,writes,api=policy_api;path=make_group(client)
    with SessionLocal() as db:owner=db.scalar(select(User.id).where(User.admin.is_(True)))
    store['admin-1']['EnableAllFolders']=True
    response=preview(client,path,{'version':0,'members':[uid,owner],'library_mode':'selected','libraries':['11111111111111111111111111111111']})
    assert response.status_code==200,response.text
    users=response.json()['users'];assert len(users)==2
    owner_diff=next(u for u in users if u['id']==owner)['differences']
    assert any(d['label']=='Library · Films' and d['before']=='Yes' and d['after']=='No' for d in owner_diff)


def test_seerr_checked_live_and_unavailable_blocks_membership(client,policy_api,monkeypatch):
    uid,store,writes,api=policy_api;path=make_group(client)
    monkeypatch.setattr(sp,'configured',lambda db:True)
    @contextmanager
    def connection(db,user):yield None,2
    monkeypatch.setattr(sp,'connection',connection)
    monkeypatch.setattr(sp,'read_permissions',lambda c,rid:32|16)
    monkeypatch.setattr(sq,'read',lambda c,rid:({},dict.fromkeys(sq.FIELDS,None)))
    data={'version':0,'members':[uid],'manage_seerr_permissions':'on','seerr_permission':['32']}
    response=preview(client,path,data);assert response.status_code==200,response.text
    assert any(d['service']=='Seerr' and d['label']=='Manage requests' and d['before']=='Yes' and d['after']=='No' for d in response.json()['users'][0]['differences'])
    from app.integrations import SyncError
    def unavailable(c,rid):raise SyncError('unavailable')
    monkeypatch.setattr(sp,'read_permissions',unavailable)
    assert post(client,path,{**data,'review_token':response.json()['review_token']},path).status_code==502
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(GroupMember))==0


def test_expired_token_csrf_and_state_restore(client,policy_api,monkeypatch):
    uid,store,writes,api=policy_api;path=make_group(client)
    with SessionLocal() as db:
        db.add(PolicyState(user_id=uid,baseline=json.dumps({'EnableSubtitleDownloading':True}),desired=json.dumps({'EnableSubtitleDownloading':False}),overrides='{}',observed='{}',confirmed='{}',version=0,pending=False,error=''));db.commit()
    store['user-1']['EnableSubtitleDownloading']=False
    response=preview(client,path,{'version':0,'members':[uid]});assert response.status_code==200,response.text
    assert any(d['label']=='Download subtitles' and d['after']=='Yes' for d in response.json()['users'][0]['differences'])
    assert client.post(path,data={'csrf':'bad','review_only':'on','version':0,'members':[uid]}).status_code==403
    from app import group_review
    now=group_review.time.time();monkeypatch.setattr(group_review.time,'time',lambda:now+301)
    assert post(client,path,{'version':0,'members':[uid],'review_token':response.json()['review_token']},path).status_code==409


def test_languages_and_removed_assistance_copy(client,policy_api):
    uid,*_=policy_api
    html=client.get('/admin/translations').text
    assert 'language-row' in html and '🇬🇧' in html and 'language-settings' in html
    assert 'Assistance lasts 30 minutes' not in client.get(f'/admin/users/{uid}').text


def test_unconfigured_seerr_cannot_preview_managed_native_rights(client,policy_api):
    uid,*_=policy_api;path=make_group(client)
    response=preview(client,path,{'version':0,'members':[uid],'manage_seerr_permissions':'on','seerr_permission':['32']})
    assert response.status_code==409
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(GroupMember))==0


def test_review_proof_cannot_cross_assignment_route_or_group(client,policy_api):
    uid,*_=policy_api;path=make_group(client);data={'version':0,'members':[uid]}
    proof=preview(client,path,data).json()['review_token']
    target=f'/admin/users/{uid}/group'
    assert post(client,target,{'group_id':path.rsplit('/',1)[1],'review_token':proof},f'/admin/users/{uid}?tab=access').status_code==409
    with SessionLocal() as db:
        group=db.get(PermissionGroup,int(path.rsplit('/',1)[1]));group.version+=1;db.commit()
    assert post(client,path,{**data,'version':1,'review_token':proof},path).status_code==409


def test_review_hides_internal_policy_metadata_and_lists_security_restoration(client,policy_api):
    uid,store,*_=policy_api;path=make_group(client)
    store['user-1'].update(IsAdministrator=True,AuthenticationProviderId='PRIVATE_NATIVE_METADATA')
    with SessionLocal() as db:
        db.add(PolicyState(user_id=uid,baseline=json.dumps({'IsAdministrator':False}),desired=json.dumps({'IsAdministrator':True}),overrides='{}',observed='{}',confirmed='{}',version=0,pending=False,error=''));db.commit()
    response=preview(client,path,{'version':0,'members':[uid]})
    assert response.status_code==200,response.text
    assert 'PRIVATE_NATIVE_METADATA' not in response.text
    assert any(d['label']=='Media-server administrator' and d['before']=='Yes' and d['after']=='No' for d in response.json()['users'][0]['differences'])
