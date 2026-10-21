"""Seerr quota ownership and read-back verification, with safe settings preservation."""
import json,time
from fastapi import APIRouter,Request,Depends,HTTPException
from sqlalchemy import select,update,delete
import httpx
from .models import User,SeerrQuotaState,SeerrSummary
from .seerr_permissions import connection,configured,fingerprint
from .integrations import request as remote,SyncError
router=APIRouter()
FIELDS={'movieQuotaLimit':'Movie requests','movieQuotaDays':'Movie period (days)','tvQuotaLimit':'Season requests','tvQuotaDays':'Season period (days)'}
PRESERVE=('username','email','locale','discoverRegion','streamingRegion','originalLanguage','movieQuotaLimit','movieQuotaDays','tvQuotaLimit','tvQuotaDays','watchlistSyncMovies','watchlistSyncTv')

def selected(data):
    if data.get('manage_quotas')!='on':return {}
    values={}
    for key in FIELDS:
        raw=str(data.get(key,'')).strip()
        value=int(raw) if raw else None
        if value is not None and not (1 if key.endswith('Days') else 0)<=value<=(3650 if key.endswith('Days') else 100000):raise ValueError('Invalid request quota')
        values[key]=value
    return values

def state(db,user):
    row=db.get(SeerrQuotaState,user.id)
    if not row:
        row=SeerrQuotaState(user_id=user.id,baseline='{}',individual='{}',desired='{}',observed='{}',version=0,pending=False,error='',connection='');db.add(row);db.flush()
    return row

def read(client,rid):
    data=remote(client,'GET',f'api/v1/user/{rid}/settings/main')
    if not isinstance(data,dict):raise SyncError('invalid_response')
    values={k:data.get(k) for k in FIELDS}
    if any(v is not None and (type(v) is not int or v<0) for v in values.values()):raise SyncError('invalid_response')
    return data,values

def inspect(db,user):
    row=state(db,user)
    if not configured(db):row.error='Seerr is not configured';db.commit();return row
    try:
        with connection(db,user) as (client,rid):_,values=read(client,rid)
        current=fingerprint(db)
        if row.connection and row.connection!=current:
            row.baseline=row.individual=row.desired='{}';row.pending=False;row.version+=1
        row.connection=current;row.observed=json.dumps(values)
        if row.baseline=='{}':row.baseline=row.observed
        row.checked_at=int(time.time());row.error=''
    except (SyncError,httpx.HTTPError):row.error='Seerr unavailable, account not imported, or API permission denied'
    db.commit();return row

def group_changed(db,user,group):
    row=state(db,user);policy=json.loads(group.access_policy) if group else {}
    values=policy.get('seerr_quotas',json.loads(row.individual))
    if not values and row.desired!='{}':values=json.loads(row.baseline)
    row.desired=json.dumps(values);row.pending=bool(values);row.version+=1

def apply(db,user):
    row=state(db,user);expected=json.loads(row.desired);generation=row.version
    if not expected:return
    changes={'checked_at':int(time.time())}
    try:
        source=fingerprint(db)
        if row.connection and row.connection!=source:raise SyncError('configuration')
        with connection(db,user) as (client,rid):
            original,current=read(client,rid)
            if row.baseline=='{}':changes['baseline']=json.dumps(current)
            changes['connection']=source
            if current!=expected:
                payload={k:original.get(k) for k in PRESERVE};payload.update(expected)
                remote(client,'POST',f'api/v1/user/{rid}/settings/main',json=payload)
            _,actual=read(client,rid);changes['observed']=json.dumps(actual)
            if actual!=expected:raise SyncError('Seerr did not apply these quotas. Check the account permissions.')
        changes.update(pending=False,error='')
    except (SyncError,httpx.HTTPError) as error:changes.update(pending=True,error=error.code if isinstance(error,SyncError) else 'unavailable')
    db.execute(update(SeerrQuotaState).where(SeerrQuotaState.user_id==user.id,SeerrQuotaState.version==generation).values(**changes));db.commit()

def run_pending():
    from .db import SessionLocal
    with SessionLocal() as db:
        if not configured(db):return
        rows=list(db.scalars(select(SeerrQuotaState).join(User).where(SeerrQuotaState.pending.is_(True),User.active.is_(True),(SeerrQuotaState.checked_at.is_(None))|(SeerrQuotaState.checked_at<int(time.time())-60)).limit(5)))
        for row in rows:apply(db,db.get(User,row.user_id))

from .main import require_admin,form,redirect
@router.post('/admin/users/{uid}/seerr/quotas')
def save(request:Request,uid:int,data=Depends(form)):
    require_admin(request);db=request.state.db;user=db.get(User,uid)
    if not user:raise HTTPException(404,'User not found')
    from .group_access import unlocked
    unlocked(db,user);row=state(db,user)
    if row.version!=int(data.get('version','-1')):raise HTTPException(409,'Permissions changed. Reload the page.')
    previous=row.observed;row=inspect(db,user)
    if row.error:raise HTTPException(409,row.error)
    if row.observed!=previous:raise HTTPException(409,'Seerr permissions changed. Reload the page.')
    values=selected(data)
    result=db.execute(update(SeerrQuotaState).where(SeerrQuotaState.user_id==uid,SeerrQuotaState.version==int(data['version'])).values(individual=json.dumps(values),desired=json.dumps(values) if values else row.baseline,pending=True,version=row.version+1))
    if result.rowcount!=1:db.rollback();raise HTTPException(409,'Permissions changed. Reload the page.')
    db.commit();apply(db,user);request.state.audit_subject=uid;request.state.audit_action='seerr.quotas'
    return redirect('/admin/users/'+str(uid)+'?tab=seerr&saved=quotas')
