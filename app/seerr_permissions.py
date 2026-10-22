"""Verified Seerr permissions, stable media identity and role-scoped summaries."""
import json,time
from contextlib import contextmanager
from urllib.parse import quote
import httpx
from fastapi import APIRouter,Request,Depends,HTTPException
from sqlalchemy import select,update
from .models import User,SeerrPolicyState,SeerrSummary
from .mailer import config
from .security import decrypt,digest
from .integrations import request,normalized_id,SyncError

FLAGS={2:'Administrator',4:'Manage settings',8:'Manage users',16:'Manage requests',32:'Request',64:'Vote',128:'Auto approve',256:'Auto approve movies',512:'Auto approve series',1024:'Request 4K',2048:'Request 4K movies',4096:'Request 4K series',8192:'Advanced requests',16384:'View requests',32768:'Auto approve 4K',65536:'Auto approve 4K movies',131072:'Auto approve 4K series',262144:'Request movies',524288:'Request series',1048576:'Manage issues',2097152:'View issues',4194304:'Create issues',8388608:'Auto request',16777216:'Auto request movies',33554432:'Auto request series',67108864:'View recently added',134217728:'View watchlists',268435456:'Manage blocklist',1073741824:'View blocklist'}
CATEGORIES={bit:('admin' if bit in (2,4,8) else 'approval' if bit in (16,128,256,512,32768,65536,131072) else 'visibility' if bit in (64,16384,1048576,2097152,4194304,67108864,134217728,268435456,1073741824) else 'requests') for bit in FLAGS}
KNOWN=sum(FLAGS)
router=APIRouter()

def configured(db):return config(db,'seerr_enabled')=='true' and bool(config(db,'seerr_url') and config(db,'seerr_api_key'))
def fingerprint(db):return digest(config(db,'seerr_url')+'\n'+config(db,'seerr_api_key'))
@contextmanager
def connection(db,user):
    if not configured(db) or not user.emby_id:raise SyncError('configuration')
    with httpx.Client(base_url=config(db,'seerr_url').rstrip('/')+'/',headers={'X-Api-Key':decrypt(config(db,'seerr_api_key'))},timeout=5,follow_redirects=False,trust_env=False) as client:
        account=request(client,'GET','api/v1/user/jellyfin/'+quote(user.emby_id,safe=''))
        if not isinstance(account,dict) or not isinstance(account.get('id'),int) or normalized_id(account.get('jellyfinUserId',''))!=normalized_id(user.emby_id):raise SyncError('identity_mismatch')
        yield client,account['id']

def mask(value):
    if type(value) is not int or not 0<=value<=2147483647:raise SyncError('invalid_permissions')
    return value

def read_permissions(client,rid):
    data=request(client,'GET',f'api/v1/user/{rid}/settings/permissions')
    if not isinstance(data,dict):raise SyncError('invalid_permissions')
    return mask(data.get('permissions'))

def selected_permissions(data,unknown=0):
    result=unknown & ~KNOWN
    for value in data.getlist('seerr_permission'):
        try:bit=int(value)
        except ValueError:raise ValueError('Invalid Seerr permission')
        if bit not in FLAGS:raise ValueError('Invalid Seerr permission')
        result|=bit
    return result

def state(db,user):
    row=db.get(SeerrPolicyState,user.id)
    if not row:row=SeerrPolicyState(user_id=user.id,version=0,pending=False,error='',connection='');db.add(row);db.flush()
    return row

def observe(db,user,row,client,rid):
    current=read_permissions(client,rid)
    source=fingerprint(db)
    if row.connection and row.connection!=source:
        # Never apply an intention meant for a different Seerr installation.
        row.baseline=row.individual=row.desired=None;row.pending=False;row.version+=1
    row.connection=source
    if row.baseline is None:row.baseline=current
    if row.observed is not None and row.observed!=current and not row.pending:row.version+=1
    row.observed=current;row.checked_at=int(time.time())
    if row.desired is None or current==row.desired or row.error in ('Seerr unavailable, account not imported, or API permission denied','Seerr is not configured'):row.error=''
    return current

def inspect_user(db,user):
    row=state(db,user)
    if configured(db):
        try:
            with connection(db,user) as (c,rid):
                row.remote_owner=rid==1
                observe(db,user,row,c,rid)
        except (SyncError,httpx.HTTPError):row.error='Seerr unavailable, account not imported, or API permission denied'
    else:row.error='Seerr is not configured'
    db.commit();return row

def group_changed(db,user,group):
    from .seerr_quotas import group_changed as quotas_changed
    quotas_changed(db,user,group)
    row=state(db,user)
    access=json.loads(group.access_policy) if group else {}
    desired=access.get('seerr_permissions',row.individual)
    if desired is None and row.desired is not None:desired=row.baseline
    row.desired=desired;row.pending=desired is not None;row.version+=1;row.error=''

def apply(db,user,expected_observed=None):
    row=state(db,user)
    if row.desired is None:return
    expected=mask(row.desired);generation=row.version;source=fingerprint(db)
    values={'checked_at':int(time.time())}
    try:
        if row.connection and row.connection!=source:raise SyncError('configuration')
        with connection(db,user) as (c,rid):
            current=read_permissions(c,rid)
            if expected_observed is not None and current!=expected_observed:raise SyncError('Permissions changed before writing')
            expected=(expected & KNOWN)|(current & ~KNOWN)
            if rid==1:raise SyncError('Seerr owner permissions cannot be changed')
            values.update(baseline=row.baseline if row.baseline is not None else current,connection=source)
            if current!=expected:request(c,'POST',f'api/v1/user/{rid}/settings/permissions',json={'permissions':expected})
            actual=read_permissions(c,rid)
            values['observed']=actual
            if actual!=expected:raise SyncError('verification_failed')
        values.update(pending=False,error='',desired=expected)
    except (SyncError,httpx.HTTPError) as exc:
        values.update(error=exc.code if isinstance(exc,SyncError) else 'unavailable',pending=not (isinstance(exc,SyncError) and exc.code=='Permissions changed before writing'))
    # A newer group edit must retain its pending state while this request finishes.
    db.execute(update(SeerrPolicyState).where(SeerrPolicyState.user_id==user.id,SeerrPolicyState.version==generation).values(**values))
    db.commit()

def run_pending():
    from .db import SessionLocal
    with SessionLocal() as db:
        if not configured(db):return
        ids=list(db.scalars(select(SeerrPolicyState.user_id).join(User).where(SeerrPolicyState.pending.is_(True),User.active.is_(True), (SeerrPolicyState.checked_at.is_(None)) | (SeerrPolicyState.checked_at<int(time.time())-60)).limit(5)))
        for uid in ids:apply(db,db.get(User,uid))

def summary(db,user):
    from .group_access import seerr_allowed
    if not configured(db) or not seerr_allowed(db,user):return None
    role='admin' if user.admin else 'member'
    if config(db,'seerr_counts_'+role,'true')!='true':return None
    source=fingerprint(db);row=db.get(SeerrSummary,(user.id,role));now=int(time.time())
    if row and row.connection==source and now-row.checked_at<60:return json.loads(row.data)
    labels=['Processing','Awaiting approval'] if user.admin else ['Movies left','Seasons left','Approved','Available']
    values=['—']*len(labels)
    try:
        with connection(db,user) as (c,rid):
            def count(kind):
                params={'take':1,'skip':0,'filter':kind}
                if not user.admin:params['requestedBy']=rid
                value=request(c,'GET','api/v1/request',params=params).get('pageInfo',{}).get('results')
                if type(value) is not int or value<0:raise SyncError('invalid_counts')
                return value
            if user.admin:values=[count('processing'),count('pending')]
            else:
                quota=request(c,'GET',f'api/v1/user/{rid}/quota')
                def remaining(key):
                    q=quota.get(key,{})
                    if q.get('limit')==0:return '∞'
                    n=q.get('remaining')
                    return max(0,n) if type(n) is int else '—'
                values=[remaining('movie'),remaining('tv'),count('approved'),count('available')]
    except (SyncError,httpx.HTTPError):pass
    data=list(zip(labels,values));db.merge(SeerrSummary(user_id=user.id,role=role,data=json.dumps(data),checked_at=now,connection=source));db.commit();return data

from .main import require_admin,form,redirect
@router.post('/admin/users/{uid}/seerr')
def save(request:Request,uid:int,data=Depends(form)):
    require_admin(request);db=request.state.db;user=db.get(User,uid)
    if not user:raise HTTPException(404,'User not found')
    from .group_access import unlocked
    unlocked(db,user);row=state(db,user)
    if int(data.get('version','-1'))!=row.version:raise HTTPException(409,'Permissions changed. Reload the page.')
    with connection(db,user) as (c,rid):
        previous=row.observed;actual=observe(db,user,row,c,rid)
        if actual!=previous:db.commit();raise HTTPException(409,'Seerr permissions changed. Reload the page.')
        if rid==1:raise HTTPException(409,'Seerr owner permissions cannot be changed')
    individual=None if data.get('action')=='inherit' else selected_permissions(data,actual)
    result=db.execute(update(SeerrPolicyState).where(SeerrPolicyState.user_id==uid,SeerrPolicyState.version==int(data['version'])).values(individual=individual,desired=individual if individual is not None else row.baseline,version=row.version+1,pending=True))
    if result.rowcount!=1:db.rollback();raise HTTPException(409,'Permissions changed. Reload the page.')
    from .main import set_config
    set_config(db,'seerr_access_'+str(uid),'true' if data.get('seerr_access')=='on' else 'false')
    db.commit();apply(db,user,expected_observed=actual)
    db.refresh(row)
    if row.pending or row.error:raise HTTPException(502,'Seerr did not confirm the requested permissions. Refresh and check the synchronization status.')
    request.state.audit_subject=uid;request.state.audit_action='permissions.seerr'
    return redirect('/admin/users/'+str(uid)+'?tab=seerr&saved=permissions')

@router.post('/admin/users/{uid}/seerr/retry')
def retry(request:Request,uid:int,data=Depends(form)):
    require_admin(request);db=request.state.db;user=db.get(User,uid)
    if not user:raise HTTPException(404,'User not found')
    row=db.get(SeerrPolicyState,uid)
    if not row or row.desired is None:raise HTTPException(409,'Permissions are read from Seerr until explicitly managed in Gatearr. Seerr owner permissions cannot be edited.')
    row.pending=True;row.checked_at=None;db.commit();apply(db,user)
    request.state.audit_subject=uid;request.state.audit_action='permissions.seerr'
    return redirect('/admin/users/'+str(uid)+'?tab=seerr')

@router.post('/admin/seerr-display')
def display_settings(request:Request,data=Depends(form)):
    require_admin(request);db=request.state.db
    from .main import set_config
    for role in ('admin','member'):set_config(db,'seerr_counts_'+role,'true' if data.get(role)=='on' else 'false')
    db.commit();return redirect('/admin/integrations?saved=display')
