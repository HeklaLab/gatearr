"""Explicit permission intent. Drift is reported; only explicit edits enqueue writes."""
import json,re,time
from copy import deepcopy
from fastapi import APIRouter,Request,Depends,HTTPException
from sqlalchemy import select,update,delete
from .models import User,PermissionGroup,GroupMember,PolicyState
from .db import SessionLocal
from .emby import emby,EmbyError
from .main import form,require_admin,render,redirect
from .security import digest
router=APIRouter()
READ_ONLY={'AuthenticationProviderId','PasswordResetProviderId','InvalidLoginAttemptCount','LoginAttemptsBeforeLockout','LockedOutDate','Password','PasswordHash'}
GROUP_EXCLUDED=READ_ONLY|{'IsAdministrator','IsDisabled'}
LIMITS={'SimultaneousStreamLimit','RemoteClientBitrateLimit','MaxParentalRating','MaxActiveSessions'}
DENY_LISTS={'BlockedTags','BlockUnratedItems','ExcludedSubFolders','RestrictedFeatures'}
GRANT_LISTS={'EnabledFolders','EnabledChannels','EnabledDevices','EnableContentDeletionFromFolders'}
LIBRARY_KEYS={'EnableAllFolders','EnabledFolders','ExcludedSubFolders'}

LABELS={'SimultaneousStreamLimit':'Maximum simultaneous streams (0 = unlimited)','EnableSubtitleDownloading':'Download subtitles','EnableSubtitleManagement':'Manage subtitles','EnableContentDownloading':'Download media','EnableMediaPlayback':'Play media','EnableRemoteAccess':'Allow remote access','EnableContentDeletion':'Delete media','RemoteClientBitrateLimit':'Remote bitrate limit (bits per second; 0 = unlimited)','IsAdministrator':'Media-server administrator','IsDisabled':'Account disabled','MaxParentalRating':'Maximum parental rating'}
def label(key):return LABELS.get(key,re.sub(r'(?<=[a-z0-9])(?=[A-Z])',' ',key))

def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'))
def fingerprint(value):return digest(encoded(value))
def normalize(key,value):
    if isinstance(value,list) and key!='AccessSchedules':
        return sorted([str(v).replace('-','').lower() for v in value]) if key in ('EnabledFolders','ExcludedSubFolders') else sorted(value,key=encoded)
    return value

def state(db,user,remote):
    row=db.get(PolicyState,user.id)
    if not row:
        row=PolicyState(user_id=user.id,baseline=encoded(remote),overrides='{}',desired='{}',observed=encoded(remote),confirmed='{}',version=0,pending=False,error='',checked_at=int(time.time()))
        db.add(row);db.flush()
    managed=json.loads(row.desired);baseline=json.loads(row.baseline)
    for key,value in remote.items():
        if key not in managed:baseline[key]=value
    row.baseline=encoded(baseline);row.observed=encoded(remote)
    return row

def safe_field(key,value,reference):
    if key in READ_ONLY or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,99}',key):raise ValueError('This field is managed by the media server')
    if key not in reference:raise ValueError('This permission is not supported by the connected server')
    old=reference[key]
    if old is not None and type(value) is not type(old):raise ValueError('Use the same value type as the media-server permission')
    if old is None and value is not None and type(value) not in (int,str,list,dict,bool):raise ValueError('Invalid permission value')
    if type(value) is int and not 0<=value<=2147483647:raise ValueError('Use a number between 0 and 2147483647')
    if isinstance(value,str) and len(value)>2000 or isinstance(value,(list,dict)) and len(encoded(value))>10000:raise ValueError('Permission value too large')
    if key=='MaxParentalRating' and value is not None and type(value) is not int:raise ValueError('Invalid parental rating')
    return value

def merge(groups):
    result={}
    for policy in groups:
        for key,value in policy.items():
            if key in GROUP_EXCLUDED:raise ValueError('Account security settings must be edited individually')
            if key not in result:result[key]=deepcopy(value);continue
            old=result[key]
            if old==value:continue
            if key=='EnableAllFolders':result[key]=bool(old or value)
            elif type(old) is bool and type(value) is bool:
                if key.startswith(('Enable','Allow')):result[key]=old and value
                elif key.startswith(('Block','IsHidden')):result[key]=old or value
                else:raise ValueError('Groups disagree on a permission; add an individual override')
            elif key in LIMITS:
                bounded=[n for n in (old,value) if n is not None and (key=='MaxParentalRating' or n!=0)]
                result[key]=min(bounded) if bounded else old
            elif key in DENY_LISTS|GRANT_LISTS and isinstance(old,list) and isinstance(value,list):
                result[key]=list({encoded(x):x for x in old+value}.values())
            else:raise ValueError('Groups disagree on a permission; add an individual override')
    return result

def recompute(db,user,row):
    overrides=json.loads(row.overrides)
    policies=[{k:v for k,v in json.loads(group.policy).items() if k not in overrides} for group in db.scalars(select(PermissionGroup).join(GroupMember).where(GroupMember.user_id==user.id).order_by(PermissionGroup.id))]
    desired=merge(policies);desired.update(overrides)
    previous=json.loads(row.desired);baseline=json.loads(row.baseline)
    for key in previous:
        if key not in desired and key in baseline:desired[key]=baseline[key]
    row.desired=encoded(desired);row.version+=1;row.pending=True;row.error=''

def guard(db,user,desired):
    if desired.get('IsDisabled') and user.admin:
        others=db.scalar(select(User.id).where(User.admin.is_(True),User.active.is_(True),User.id!=user.id).limit(1))
        if not others:raise ValueError('The last active portal administrator cannot be disabled')

def apply(db,user,row,api=None,write_keys=None):
    api=api or emby;generation=row.version;desired=json.loads(row.desired)
    if write_keys is not None:desired={k:v for k,v in desired.items() if k in write_keys}
    try:
        guard(db,user,desired)
        current=api.user(user.emby_id).get('Policy',{})
        for k,v in desired.items():safe_field(k,v,current)
        target=deepcopy(current);target.update(desired)
        if 'EnabledFolders' in desired:
            available={x['Id'] for x in api.libraries()}
            if not set(desired['EnabledFolders'])<=available:raise ValueError('Unknown library. Reload the page.')
        api.policy(user.emby_id,target)
        confirmed=api.user(user.emby_id).get('Policy',{})
        success=all(k in confirmed and normalize(k,confirmed[k])==normalize(k,v) for k,v in desired.items())
        db.execute(update(PolicyState).where(PolicyState.user_id==user.id,PolicyState.version==generation).values(observed=encoded(confirmed),confirmed=encoded(desired) if success else row.confirmed,pending=False,error='' if success else 'Remote verification failed',checked_at=int(time.time())))
        if success and 'IsDisabled' in desired and user.active==bool(desired['IsDisabled']):
            user.active=not desired['IsDisabled'];user.version+=1
        db.commit();return success
    except (EmbyError,ValueError):
        db.execute(update(PolicyState).where(PolicyState.user_id==user.id,PolicyState.version==generation).values(pending=False,error='Permission synchronization failed',checked_at=int(time.time())))
        db.commit();return False

def run_pending():
    with SessionLocal() as db:
        for row in db.scalars(select(PolicyState).where(PolicyState.pending.is_(True)).limit(10)):
            user=db.get(User,row.user_id)
            if user and user.emby_id and not user.emby_missing:apply(db,user,row)

def observe(db,user,remote):
    row=state(db,user,remote);row.observed=encoded(remote);row.checked_at=int(time.time())
    desired=json.loads(row.desired)
    if not row.pending and all(k in remote and normalize(k,remote[k])==normalize(k,v) for k,v in desired.items()):row.error='';row.confirmed=encoded(desired)
    db.commit();return row

def fields(remote,row):
    desired=json.loads(row.desired);confirmed=json.loads(row.confirmed);items=[]
    for key,value in sorted(remote.items()):
        managed=key in desired
        matches=managed and normalize(key,value)==normalize(key,desired[key])
        color='red' if row.error and managed else 'green' if matches and not row.pending else 'orange' if managed else 'neutral'
        detail='Confirmed in media server' if color=='green' else 'Synchronization pending' if row.pending and managed else row.error if color=='red' else 'Different from saved permissions' if managed else 'Observed in media server; not managed by Gatearr'
        kind='bool' if type(value) is bool else 'int' if type(value) is int else 'str' if isinstance(value,str) else 'json'
        items.append({'key':key,'label':label(key),'value':value,'json':encoded(value),'kind':kind,'editable':key not in READ_ONLY,'color':color,'detail':detail,'hash':fingerprint(value),'desired':encoded(desired[key]) if managed else ''})
    return items

@router.post('/admin/users/{uid}/permission')
def save_permission(request:Request,uid:int,data=Depends(form)):
    actor=require_admin(request);db=request.state.db;user=db.get(User,uid)
    if not user or not user.emby_id:raise HTTPException(404,'User not found')
    remote=emby.user(user.emby_id).get('Policy',{});key=str(data.get('field',''))
    if key not in remote:raise ValueError('This permission is not supported by the connected server')
    row=state(db,user,remote)
    if row.version!=int(data.get('version','-1')) or data.get('hash')!=fingerprint(remote[key]):raise HTTPException(409,'Permissions changed. Reload this page.')
    value=str(data.get('value','')) if isinstance(remote[key],str) else json.loads(str(data.get('value','null')))
    safe_field(key,value,remote)
    if key in ('IsAdministrator','IsDisabled') and data.get('confirm_sensitive')!='on':raise ValueError('Confirm the account security change')
    if key=='IsDisabled' and value and actor.id==uid:raise ValueError('You cannot disable your own account')
    overrides=json.loads(row.overrides)
    if data.get('action')=='inherit':overrides.pop(key,None)
    else:overrides[key]=value
    request.state.audit_subject=uid
    request.state.audit_detail=label(key)+': '+encoded(remote[key])+' → '+('Inherited from groups' if data.get('action')=='inherit' else encoded(value))
    row.overrides=encoded(overrides);recompute(db,user,row);guard(db,user,json.loads(row.desired));db.commit();apply(db,user,row,write_keys={key})
    return redirect('/admin/users/'+str(uid)+'#permissions')

@router.post('/admin/users/{uid}/permissions/retry')
def retry(request:Request,uid:int,data=Depends(form)):
    require_admin(request);db=request.state.db;user=db.get(User,uid);row=db.get(PolicyState,uid)
    if not user or not row:raise HTTPException(404,'User not found')
    row.version+=1;row.pending=True;db.commit();apply(db,user,row)
    return redirect('/admin/users/'+str(uid)+'#permissions')

@router.get('/admin/groups')
def groups(request:Request):
    require_admin(request)
    return render(request,'groups.html',groups=list(request.state.db.scalars(select(PermissionGroup).order_by(PermissionGroup.name))))

@router.post('/admin/groups')
def create_group(request:Request,data=Depends(form)):
    require_admin(request);name=str(data.get('name','')).strip()
    if not name or len(name)>100:raise ValueError('Invalid name')
    if request.state.db.scalar(select(PermissionGroup.id).where(PermissionGroup.name==name)):raise ValueError('Group name already exists')
    row=PermissionGroup(name=name,policy='{}',version=0);request.state.db.add(row);request.state.db.commit()
    return redirect('/admin/groups/'+str(row.id))

@router.get('/admin/groups/{gid}')
def group_page(request:Request,gid:int):
    require_admin(request);db=request.state.db;group=db.get(PermissionGroup,gid)
    if not group:raise HTTPException(404,'Group not found')
    users=list(db.scalars(select(User).where(User.emby_id.is_not(None)).order_by(User.name)))
    template=next((u for u in users if u.active),None)
    reference=emby.user(template.emby_id).get('Policy',{}) if template else {}
    policy=json.loads(group.policy)
    return render(request,'group_editor.html',group=group,policy=policy,permission_keys=[k for k in sorted(reference) if k not in GROUP_EXCLUDED|LIBRARY_KEYS],reference_values=reference,reference_labels={k:label(k) for k in reference},members=set(db.scalars(select(GroupMember.user_id).where(GroupMember.group_id==gid))),group_users=users,libraries=emby.libraries())

@router.post('/admin/groups/{gid}')
def save_group(request:Request,gid:int,data=Depends(form)):
    require_admin(request);db=request.state.db;group=db.get(PermissionGroup,gid)
    if not group:raise HTTPException(404,'Group not found')
    if group.version!=int(data.get('version','-1')):raise HTTPException(409,'Group changed. Reload this page.')
    users=list(db.scalars(select(User).where(User.emby_id.is_not(None))));indexed={u.id:u for u in users}
    members={int(v) for v in data.getlist('members')}
    if not members<=set(indexed):raise ValueError('Unknown group member')
    old_members=set(db.scalars(select(GroupMember.user_id).where(GroupMember.group_id==gid)))
    affected=members|old_members
    remotes={uid:emby.user(indexed[uid].emby_id).get('Policy',{}) for uid in sorted(affected)}
    reference=next(iter(remotes.values()),{})
    if not reference and users:reference=emby.user(users[0].emby_id).get('Policy',{})
    policy={}
    for key in data.getlist('permission'):
        if key in GROUP_EXCLUDED|LIBRARY_KEYS:raise ValueError('Account security settings must be edited individually')
        value=json.loads(str(data.get('value_'+key,'null')))
        safe_field(key,value,reference)
        for uid in members:safe_field(key,value,remotes[uid])
        policy[key]=value
    mode=data.get('library_mode','inherit')
    if mode not in ('inherit','all','selected'):raise ValueError('Invalid access mode')
    if mode!='inherit':
        selected=sorted(set(data.getlist('libraries')));available={x['Id'] for x in emby.libraries()}
        if not set(selected)<=available:raise ValueError('Unknown library. Reload the page.')
        policy.update(EnableAllFolders=mode=='all',EnabledFolders=selected)
        if remotes and all('ExcludedSubFolders' in p for p in remotes.values()):policy['ExcludedSubFolders']=[]
    request.state.audit_detail='Group: '+group.name+'\nMembers: '+', '.join(indexed[uid].name for uid in sorted(members))+'\nPermissions: '+encoded(policy)
    affected=members|old_members
    states={}
    for uid in sorted(affected):states[uid]=state(db,indexed[uid],remotes[uid])
    result=db.execute(update(PermissionGroup).where(PermissionGroup.id==gid,PermissionGroup.version==int(data.get('version','-1'))).values(policy=encoded(policy),version=group.version+1))
    if result.rowcount!=1:db.rollback();raise HTTPException(409,'Group changed. Reload this page.')
    db.execute(delete(GroupMember).where(GroupMember.group_id==gid))
    db.add_all([GroupMember(group_id=gid,user_id=uid) for uid in members]);db.flush()
    for uid in affected:recompute(db,indexed[uid],states[uid]);guard(db,indexed[uid],json.loads(states[uid].desired))
    db.commit()
    return redirect('/admin/groups/'+str(gid)+'?saved=1')
