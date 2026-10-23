"""Explicit permission intent. Drift is reported; only explicit edits enqueue writes."""
import json,re,time
from copy import deepcopy
from fastapi import APIRouter,Request,Depends,HTTPException
from sqlalchemy import select,update,delete,func
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
LABELS.update({'EnableAllFolders':'Access all libraries, including future ones','EnabledFolders':'Allowed libraries','ExcludedSubFolders':'Excluded subfolders','BlockedMediaFolders':'Blocked media folders','EnableAllDevices':'Allow all devices, including new ones','EnabledDevices':'Allowed devices','EnableAllChannels':'Access all channels','EnabledChannels':'Allowed channels','BlockedChannels':'Blocked channels','BlockUnratedItems':'Block unrated content','IncludeTags':'Only allow these tags','AllowedTags':'Only allow these tags','BlockedTags':'Blocked tags','EnableContentDeletionFromFolders':'Libraries allowing media deletion','AccessSchedules':'Allowed access times','EnableVideoPlaybackTranscoding':'Transcode video','EnableAudioPlaybackTranscoding':'Transcode audio','EnablePlaybackRemuxing':'Allow remuxing','MaxActiveSessions':'Maximum active sessions (0 = unlimited)','SyncPlayAccess':'Shared playback sessions','ForceRemoteSourceTranscoding':'Always transcode remote sources','IsHidden':'Hide from the sign-in screen','IsHiddenRemotely':'Hide from remote sign-in','IsHiddenFromUnusedDevices':'Hide on new devices','EnableLiveTvAccess':'Watch live TV','EnableLiveTvManagement':'Manage live TV recordings'})
def label(key):return LABELS.get(key,re.sub(r'(?<=[a-z0-9])(?=[A-Z])',' ',key))

def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'))
def fingerprint(value):return digest(encoded(value))
def normalize(key,value):
    if key=='AccessSchedules' and isinstance(value,list):
        return sorted([{k:v for k,v in slot.items() if k not in ('Id','UserId')} for slot in value],key=encoded)
    if isinstance(value,list):
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
    if key=='AccessSchedules':
        from .permission_ui import DAYS
        if not isinstance(value,list) or len(value)>50:raise ValueError('Invalid schedule')
        for slot in value:
            if not isinstance(slot,dict) or slot.get('DayOfWeek') not in DAYS or any(type(slot.get(k)) not in (int,float) for k in ('StartHour','EndHour')) or not 0<=slot['StartHour']<slot['EndHour']<=24:raise ValueError('Invalid schedule')
    if key in DENY_LISTS|GRANT_LISTS|{'IncludeTags','AllowedTags','BlockedChannels','BlockedMediaFolders'} and value is not None and (not isinstance(value,list) or any(not isinstance(v,str) for v in value)):raise ValueError('Invalid selection')
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
    from .group_access import group_for
    overrides={} if group_for(db,user) else json.loads(row.overrides)
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

def apply(db,user,row,api=None,write_keys=None,expected_current=None):
    api=api or emby;generation=row.version;desired=json.loads(row.desired)
    if write_keys is not None:desired={k:v for k,v in desired.items() if k in write_keys}
    try:
        guard(db,user,desired)
        current=api.user(user.emby_id).get('Policy',{})
        if not isinstance(current,dict) or not current:raise EmbyError('Invalid policy response')
        if expected_current is not None and any(k not in current or normalize(k,current[k])!=normalize(k,v) for k,v in expected_current.items()):raise ValueError('Permissions changed before writing')
        for k,v in desired.items():safe_field(k,v,current)
        target=deepcopy(current);target.update(desired)
        if 'EnabledFolders' in desired:
            available={x['Id'] for x in api.libraries()}
            if not set(desired['EnabledFolders'])<=available:raise ValueError('Unknown library. Reload the page.')
        api.policy(user.emby_id,target)
        confirmed=api.user(user.emby_id).get('Policy',{})
        if not isinstance(confirmed,dict):raise EmbyError('Invalid policy response')
        success=all(k in confirmed and normalize(k,confirmed[k])==normalize(k,v) for k,v in desired.items())
        db.execute(update(PolicyState).where(PolicyState.user_id==user.id,PolicyState.version==generation).values(observed=encoded(confirmed),confirmed=encoded(desired) if success else row.confirmed,pending=False,error='' if success else 'Remote verification failed',checked_at=int(time.time())))
        if success and 'IsDisabled' in desired and user.active==bool(desired['IsDisabled']):
            user.active=not desired['IsDisabled'] and not user.portal_disabled;user.version+=1
        db.commit();return success
    except (EmbyError,ValueError):
        db.execute(update(PolicyState).where(PolicyState.user_id==user.id,PolicyState.version==generation).values(pending=False,error='Permission synchronization failed',checked_at=int(time.time())))
        db.commit();return False

def run_pending():
    with SessionLocal() as db:
        for row in db.scalars(select(PolicyState).where(PolicyState.pending.is_(True)).limit(10)):
            user=db.get(User,row.user_id)
            if user and user.emby_id and not user.emby_missing and not user.portal_disabled:apply(db,user,row)

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
    from .group_access import unlocked
    unlocked(db,user)
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
    return redirect('/admin/users/'+str(uid)+'?tab=emby#permissions')

@router.get('/admin/users/{uid}/permissions/status')
def permission_status(request:Request,uid:int):
    require_admin(request);db=request.state.db;user=db.get(User,uid)
    if not user or not user.emby_id:raise HTTPException(404,'User not found')
    if request.query_params.get('service')=='seerr':
        from .models import SeerrPolicyState,SeerrQuotaState
        policy=db.get(SeerrPolicyState,uid);quota=db.get(SeerrQuotaState,uid)
        return {'hash':fingerprint([policy.observed if policy else None,quota.observed if quota else None]),'checked_at':policy.checked_at if policy else None}
    row=db.get(PolicyState,uid)
    return {'hash':fingerprint(json.loads(row.observed)) if row else '', 'checked_at':row.checked_at if row else None, 'error':row.error if row else ''}

@router.post('/admin/users/{uid}/permissions/category')
def save_category(request:Request,uid:int,data=Depends(form)):
    actor=require_admin(request);db=request.state.db;user=db.get(User,uid)
    if not user or not user.emby_id:raise HTTPException(404,'User not found')
    from .group_access import unlocked
    from .permission_ui import metadata,controls,parse
    unlocked(db,user)
    remote=emby.user(user.emby_id).get('Policy',{})
    row=state(db,user,remote)
    if row.version!=int(data.get('version','-1')):raise HTTPException(409,'Permissions changed. Reload this page.')
    meta=metadata(emby,remote,emby.libraries())
    groups=controls(fields(remote,row),meta)
    group=next((g for g in groups if g['id']==data.get('category')),None)
    if not group:raise ValueError('Unknown permission category')
    indexed={f['key']:f for f in group['fields']};changes={};overrides=json.loads(row.overrides);inherit=data.get('action')=='inherit'
    for key in data.getlist('fields'):
        if key not in indexed:raise ValueError('Unknown permission')
        if data.get('hash_'+key)!=fingerprint(remote[key]):raise HTTPException(409,'Permissions changed. Reload this page.')
        field=indexed[key]
        if inherit:
            if key in overrides:
                restored=json.loads(row.baseline).get(key)
                if key in ('IsAdministrator','IsDisabled') and restored!=remote[key]:
                    if data.get('confirm_sensitive')!='on':raise ValueError('Confirm the account security change')
                    if key=='IsDisabled' and restored and actor.id==uid:raise ValueError('You cannot disable your own account')
                changes[key]=remote[key]
            continue
        value=parse(field,data)
        safe_field(key,value,remote)
        if key in ('IsAdministrator','IsDisabled') and value!=remote[key]:
            if data.get('confirm_sensitive')!='on':raise ValueError('Confirm the account security change')
            if key=='IsDisabled' and value and actor.id==uid:raise ValueError('You cannot disable your own account')
        if normalize(key,value)!=normalize(key,remote[key]):changes[key]=value
    if not changes:return redirect('/admin/users/'+str(uid)+'?tab=emby#permissions')
    if inherit:
        for key in changes:overrides.pop(key,None)
    else:overrides.update(changes)
    row.overrides=encoded(overrides);recompute(db,user,row);guard(db,user,json.loads(row.desired));db.commit()
    request.state.audit_subject=uid;request.state.audit_detail='Permissions: '+', '.join(label(k) for k in changes)
    if not apply(db,user,row,write_keys=set(changes),expected_current={k:remote[k] for k in changes}):raise HTTPException(502,'Permission synchronization failed. No success was confirmed; refresh the server information.')
    return redirect('/admin/users/'+str(uid)+'?tab=emby&saved=permissions#permissions')

@router.post('/admin/users/{uid}/permissions/retry')
def retry(request:Request,uid:int,data=Depends(form)):
    require_admin(request);db=request.state.db;user=db.get(User,uid);row=db.get(PolicyState,uid)
    if not user or not row:raise HTTPException(404,'User not found')
    row.version+=1;row.pending=True;db.commit();apply(db,user,row)
    return redirect('/admin/users/'+str(uid)+'?tab=emby#permissions')

@router.get('/admin/groups')
def groups(request:Request):
    require_admin(request)
    db = request.state.db
    member_counts = dict(db.execute(select(GroupMember.group_id, func.count(GroupMember.user_id)).group_by(GroupMember.group_id)).all())
    return render(request,'groups.html',groups=list(db.scalars(select(PermissionGroup).order_by(PermissionGroup.name))),member_counts=member_counts)

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
    from .seerr_permissions import FLAGS,CATEGORIES
    from .permission_ui import metadata,controls,DAYS
    from types import SimpleNamespace
    from .group_access import group_for
    ownership={u.id:group_for(db,u) for u in users}
    libraries=emby.libraries()
    group_values={**reference,**{k:v for k,v in policy.items() if k in reference}}
    group_state=SimpleNamespace(desired=encoded(policy),confirmed=encoded(policy),pending=False,error='')
    categories=controls([f for f in fields(group_values,group_state) if f['key'] not in GROUP_EXCLUDED],metadata(emby,group_values,libraries))
    return render(request,'group_editor.html',group=group,membership_hash=membership_hash(db,gid),permission_categories=categories,permission_days=DAYS,seerr_categories=CATEGORIES,policy=policy,group_access=json.loads(group.access_policy),seerr_permissions=FLAGS,ownership=ownership,permission_keys=[k for k in sorted(reference) if k not in GROUP_EXCLUDED|LIBRARY_KEYS],reference_values=reference,reference_labels={k:label(k) for k in reference},members=set(db.scalars(select(GroupMember.user_id).where(GroupMember.group_id==gid))),group_users=users,libraries=libraries)

@router.post('/admin/groups/{gid}')
def save_group(request:Request,gid:int,data=Depends(form)):
    require_admin(request);db=request.state.db;group=db.get(PermissionGroup,gid)
    if not group:raise HTTPException(404,'Group not found')
    if group.version!=int(data.get('version','-1')):raise HTTPException(409,'Group changed. Reload this page.')
    users=list(db.scalars(select(User).where(User.emby_id.is_not(None))));indexed={u.id:u for u in users}
    members={int(v) for v in data.getlist('members')}
    if not members<=set(indexed):raise ValueError('Unknown group member')
    occupied=set(db.scalars(select(GroupMember.user_id).where(GroupMember.group_id!=gid,GroupMember.user_id.in_(members))))
    if occupied:raise HTTPException(409,'A user can belong to only one group. Remove the existing assignment first.')
    old_members=set(db.scalars(select(GroupMember.user_id).where(GroupMember.group_id==gid)))
    affected=members|old_members
    remotes={uid:emby.user(indexed[uid].emby_id).get('Policy',{}) for uid in sorted(affected)}
    reference=next(iter(remotes.values()),{})
    if not reference and users:reference=emby.user(users[0].emby_id).get('Policy',{})
    human=data.get('editor_format')=='human'
    controls_by_key={}
    if human:
        from .permission_ui import metadata,controls,parse
        from types import SimpleNamespace
        original=json.loads(group.policy)
        values={**reference,**{k:v for k,v in original.items() if k in reference}}
        group_state=SimpleNamespace(desired=encoded(original),confirmed=encoded(original),pending=False,error='')
        categories=controls(fields(values,group_state),metadata(emby,values,emby.libraries()))
        controls_by_key={field['key']:field for category in categories for field in category['fields']}
        # Unavailable controls cannot silently remove an existing group policy.
        policy={k:v for k,v in original.items() if k not in controls_by_key or not controls_by_key[k]['editable'] or controls_by_key[k]['unavailable']}
    else:policy={}
    for key in data.getlist('permission'):
        if key in GROUP_EXCLUDED or (not human and key in LIBRARY_KEYS):raise ValueError('Account security settings must be edited individually')
        if human:
            if key not in controls_by_key:raise ValueError('This permission is not supported by the connected server')
            value=parse(controls_by_key[key],data,prefix='value_')
        else:value=json.loads(str(data.get('value_'+key,'null')))
        if key=='AccessSchedules':value=[{k:v for k,v in slot.items() if k not in ('Id','UserId')} for slot in value]
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
    from .seerr_permissions import selected_permissions
    settings={}
    if data.get('manage_admin')=='on':settings['gatearr_admin']=data.get('gatearr_admin')=='on'
    if data.get('manage_tools')=='on':
        tools=sorted(set(data.getlist('tools')))
        if any(k not in ('radarr','sonarr','bazarr','tracearr','tdarr') for k in tools):raise ValueError('Invalid tool access')
        from .tools_proxy import retained_tools
        settings['tools']=retained_tools(db,json.loads(group.access_policy).get('tools',[]),tools)
    if data.get('manage_seerr_access')=='on':settings['seerr_access']=data.get('seerr_access')=='on'
    from .seerr_quotas import selected as quota_values
    quotas=quota_values(data)
    if quotas:settings['seerr_quotas']=quotas
    if data.get('manage_seerr_permissions')=='on':settings['seerr_permissions']=selected_permissions(data,json.loads(group.access_policy).get('seerr_permissions',0))
    from .group_review import review
    preview=review(request,data,group,[indexed[uid] for uid in members-old_members],policy,settings,remotes,emby)
    if preview is not None:return preview
    request.state.audit_detail='Group: '+group.name+'\nMembers: '+', '.join(indexed[uid].name for uid in sorted(members))+'\nPermissions: '+', '.join(label(key)+' = '+('Yes' if value is True else 'No' if value is False else str(value) if type(value) is int else 'Custom selection') for key,value in policy.items())
    affected=members|old_members
    states={}
    for uid in sorted(affected):states[uid]=state(db,indexed[uid],remotes[uid])
    result=db.execute(update(PermissionGroup).where(PermissionGroup.id==gid,PermissionGroup.version==int(data.get('version','-1'))).values(policy=encoded(policy),access_policy=encoded(settings),version=group.version+1))
    if result.rowcount!=1:db.rollback();raise HTTPException(409,'Group changed. Reload this page.')
    db.execute(delete(GroupMember).where(GroupMember.group_id==gid))
    db.add_all([GroupMember(group_id=gid,user_id=uid) for uid in members]);db.flush()
    from .group_access import apply_access,group_for
    # Grants first, then revocations, so moving the last administrator is checked atomically.
    order=sorted(affected,key=lambda uid:not settings.get('gatearr_admin',False) if uid in members else True)
    for uid in order:
        recompute(db,indexed[uid],states[uid]);guard(db,indexed[uid],json.loads(states[uid].desired));apply_access(db,indexed[uid],group_for(db,indexed[uid]))
    db.commit()
    active_tab=str(data.get('active_tab','members'))
    if active_tab not in ('members','emby','seerr','access'):active_tab='members'
    return redirect('/admin/groups/'+str(gid)+'?saved=1&tab='+active_tab)

@router.post('/admin/users/{uid}/group')
def assign_group(request:Request,uid:int,data=Depends(form)):
    require_admin(request);db=request.state.db;user=db.get(User,uid)
    if not user or not user.emby_id:raise HTTPException(404,'User not found')
    gid=int(data.get('group_id') or '0');group=db.get(PermissionGroup,gid) if gid else None
    if gid and not group:raise HTTPException(404,'Group not found')
    remote=emby.user(user.emby_id).get('Policy',{})
    from .group_access import group_for
    from .group_review import review
    old=group_for(db,user)
    preview=review(request,data,group,[user] if group and (not old or old.id!=gid) else [],json.loads(group.policy) if group else {},json.loads(group.access_policy) if group else {},{uid:remote},emby)
    if preview is not None:return preview
    row=state(db,user,remote)
    db.execute(delete(GroupMember).where(GroupMember.user_id==uid))
    if group:db.add(GroupMember(user_id=uid,group_id=gid))
    db.flush();recompute(db,user,row);guard(db,user,json.loads(row.desired))
    from .group_access import apply_access
    apply_access(db,user,group);db.commit()
    request.state.audit_subject=uid;request.state.audit_detail='Owning group: '+(group.name if group else 'None')
    return redirect('/admin/users/'+str(uid)+'?tab=access')


def membership_hash(db,gid):
    return fingerprint(sorted(db.scalars(select(GroupMember.user_id).where(GroupMember.group_id==gid))))

@router.post('/admin/groups/{gid}/rename')
def rename_group(request:Request,gid:int,data=Depends(form)):
    require_admin(request);db=request.state.db;group=db.get(PermissionGroup,gid)
    if not group:raise HTTPException(404,'Group not found')
    name=str(data.get('name','')).strip()
    if not name or len(name)>100:raise ValueError('Invalid name')
    if db.scalar(select(PermissionGroup.id).where(PermissionGroup.name==name,PermissionGroup.id!=gid)):raise ValueError('Group name already exists')
    result=db.execute(update(PermissionGroup).where(PermissionGroup.id==gid,PermissionGroup.version==int(data.get('version','-1'))).values(name=name,version=PermissionGroup.version+1))
    if result.rowcount!=1:raise HTTPException(409,'Group changed. Reload this page.')
    db.commit();request.state.audit_detail='Group renamed: '+name
    return redirect('/admin/groups/'+str(gid))


def delete_local_user(db,user):
    from .models import Base,Config
    # Delete dependent rows before the user; session children use FK cascades.
    for table in reversed(Base.metadata.sorted_tables):
        if table.name=='users':continue
        for column in table.columns:
            if any(f.target_fullname=='users.id' for f in column.foreign_keys):db.execute(delete(table).where(column==user.id))
    db.execute(delete(Config).where(Config.key=='seerr_access_'+str(user.id)))
    db.delete(user)

@router.post('/admin/groups/{gid}/delete')
def delete_group(request:Request,gid:int,data=Depends(form)):
    actor=require_admin(request);db=request.state.db
    from sqlalchemy import text
    db.rollback();db.execute(text('BEGIN IMMEDIATE'))
    group=db.get(PermissionGroup,gid)
    if not group:raise HTTPException(404,'Group not found')
    if group.version!=int(data.get('version','-1')) or data.get('membership')!=membership_hash(db,gid):raise HTTPException(409,'Group changed. Reload this page.')
    mode=str(data.get('mode',''))
    if mode not in ('group','users'):raise ValueError('Choose what to delete')
    members=list(db.scalars(select(User).join(GroupMember).where(GroupMember.group_id==gid).order_by(User.id)))
    if mode=='users':
        if data.get('confirm_delete')!='on' or data.get('confirmation')!='DELETE':raise ValueError('Check the confirmation box and type DELETE')
        # Preflight the whole selection before any irreversible request.
        remotes={u['Id']:u for u in emby.users()}
        for member in members:
            if member.id==actor.id or member.admin or remotes.get(member.emby_id,{}).get('Policy',{}).get('IsAdministrator'):raise HTTPException(409,'Administrators and your own account cannot be deleted with a group')
        from .seerr_permissions import configured,connection,read_permissions
        from .integrations import SyncError,request as remote_request
        if configured(db):
            for member in members:
                resolved=False
                try:
                    with connection(db,member) as (client,rid):
                        resolved=True
                        if rid==1 or read_permissions(client,rid)&2:raise HTTPException(409,'Administrators cannot be deleted with a group')
                except SyncError as exc:
                    if resolved or exc.code!='not_found':raise HTTPException(502,'Linked account verification failed. No deletion was started.')
        removed=0
        expected_members={member.id for member in members}
        for member in members:
            try:
                if configured(db):
                    resolved=False
                    try:
                        with connection(db,member) as (client,rid):
                            resolved=True
                            if rid==1 or read_permissions(client,rid)&2:raise HTTPException(409,'Administrators cannot be deleted with a group')
                            remote_request(client,'DELETE',f'api/v1/user/{rid}')
                    except SyncError as exc:
                        if resolved or exc.code!='not_found':raise
                if member.emby_id in remotes:
                    from .emby import _ADMIN
                    from urllib.parse import quote
                    emby.request('DELETE','/Users/'+quote(member.emby_id,safe=''),token=_ADMIN)
                    if any(u['Id']==member.emby_id for u in emby.users()):raise EmbyError('Deletion not verified')
                expected_members.remove(member.id)
                delete_local_user(db,member);db.commit();removed+=1
                db.execute(text('BEGIN IMMEDIATE'));db.expire_all()
                current=db.get(PermissionGroup,gid)
                if not current or current.version!=int(data.get('version','-1')) or membership_hash(db,gid)!=fingerprint(sorted(expected_members)):
                    raise HTTPException(409,'Group changed during deletion; refresh before retrying')
            except (EmbyError,SyncError,HTTPException):
                db.rollback()
                raise HTTPException(502,f'Deletion stopped after {removed} complete account deletion(s). Some linked accounts or requests may already be deleted. Remaining group members were kept; refresh and check the servers before retrying.')
    else:
        from .group_access import apply_access
        states={u.id:state(db,u,emby.user(u.emby_id).get('Policy',{})) for u in members}
        db.execute(delete(GroupMember).where(GroupMember.group_id==gid));db.flush()
        for member in members:
            recompute(db,member,states[member.id]);guard(db,member,json.loads(states[member.id].desired));apply_access(db,member,None)
    db.delete(group);db.commit();request.state.audit_detail='Group deleted; mode='+mode
    return redirect('/admin/groups')
