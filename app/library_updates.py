"""Personal library feed, incremental baselines and idempotent season email delivery."""
import json,time
from urllib.parse import quote
from sqlalchemy import select,delete
from fastapi import APIRouter,Request,Depends,HTTPException
from .models import User,LibraryEvent,LibraryPreference,PortalCache,MailJob
from .db import SessionLocal
from .mailer import config
from .security import digest,encrypt
from .emby import emby,_ADMIN,EmbyError
from .integrations import request,SyncError,normalized_id
from . import tracearr
router=APIRouter()

def source_fingerprint(db):return digest(config(db,'emby_url')+'\n'+config(db,'emby_api_key')+'\n'+config(db,'seerr_url')+'\n'+config(db,'seerr_api_key')+'\n'+tracearr.fingerprint(db))
def event_accessible(user,event):
    try:
        if emby.user(user.emby_id).get('Policy',{}).get('IsDisabled'):return False
        item=emby.request('GET','/Users/'+quote(user.emby_id,safe='')+'/Items/'+quote(event.item_id,safe=''),token=_ADMIN)
        return isinstance(item,dict) and str(item.get('Id'))==event.item_id
    except EmbyError:return False

def snapshot(db,key):
    row=db.get(PortalCache,digest(key))
    return json.loads(row.data) if row else None

def store(db,key,data):db.merge(PortalCache(key=digest(key),data=json.dumps(data),checked_at=int(time.time())))
def enqueue_season(db,user,event,pref):
    if event.watched or not (pref.seasons and pref.email and user.email and user.active and tracearr.configured(db) and config(db,'smtp_host') and event_accessible(user,event)):return
    data=json.loads(event.data)
    if data.get('email_queued'):return
    values={'app_name':config(db,'app_name','Gatearr'),'username':user.name,'title':event.title,'season':str(data.get('season','')),'link':config(db,'public_url')+'/library/open/'+event.key,'minutes':'30','_locale':__import__('app.i18n',fromlist=['user_language']).user_language(db,user)}
    payload={'notification':True,'purpose':'new_season','recipient':user.email,'values':values,'library_event':event.key,'user_id':user.id}
    now=int(time.time());db.add(MailJob(payload=encrypt(json.dumps(payload)),attempts=0,next_attempt=now,expires=now+86400));data['email_queued']=True;event.data=json.dumps(data)

def add_event(db,user,source,kind,item,title,data):
    key=digest(json.dumps([source,user.id,kind,item,data.get('request_id') if kind=='request' else None]))
    event=db.get(LibraryEvent,key)
    if event:return event
    event=LibraryEvent(key=key,user_id=user.id,source=source,kind=kind,item_id=str(item),title=title[:500],data=json.dumps(data),created_at=int(time.time()),watched=False);db.add(event);return event

def sync_user(db,user):
    from .widgets import preference,items
    from .group_access import seerr_allowed
    from .seerr_permissions import connection as seerr_connection,configured as seerr_configured
    pref=preference(db,user);source=source_fingerprint(db);history=[];trace_ready=False
    if tracearr.configured(db):
        try:
            with tracearr.connection(db) as client:history=tracearr.history(db,user,client)
            trace_ready=True
        except SyncError:pass # Request announcements do not depend on Tracearr availability.
    watched={normalized_id(r['rating_key']) for r in history if r.get('watched') and r.get('rating_key')}
    seen_series={normalized_id(r['grandparent_rating_key']) for r in history if r.get('grandparent_rating_key') and (r.get('duration_ms') or 0)>0}
    if trace_ready:
        seasons=items(user,'Season','DateCreated,SeriesInfo');current={str(s['Id']) for s in seasons if s.get('Id')};previous=snapshot(db,f'seasons:{source}:{user.id}')
        acknowledged=set(current)
        if previous is not None:
            for season in seasons:
                sid=str(season.get('Id',''));series=str(season.get('SeriesId',''));number=season.get('IndexNumber')
                if sid in previous or normalized_id(series) not in seen_series or type(number) is not int or number<1:continue
                episodes=items(user,'Episode',parent=sid)
                if not episodes:
                    acknowledged.discard(sid) # Retry when the scanner has populated the new season.
                    continue
                title=str(season.get('SeriesName') or season.get('Name','Series'))
                event=add_event(db,user,source,'season',sid,title,{'season':number,'episode_ids':[str(e['Id']) for e in episodes if e.get('Id')],'detail':str(number),'series_id':series})
                episode_ids=json.loads(event.data).get('episode_ids',[])
                if episode_ids and {normalized_id(i) for i in episode_ids}<=watched:event.watched=True
                enqueue_season(db,user,event,pref)
        store(db,f'seasons:{source}:{user.id}',sorted(acknowledged))
    db.commit()
    try:
        if seerr_configured(db) and seerr_allowed(db,user):
            with seerr_connection(db,user) as (client,rid):
                available=[]
                for skip in range(0,20000,100):
                    page=request(client,'GET','api/v1/request',params={'requestedBy':rid,'filter':'available','take':100,'skip':skip});rows=page.get('results')
                    if not isinstance(rows,list):raise SyncError('api_contract')
                    for row in rows:
                        if row.get('requestedBy',{}).get('id')!=rid:raise SyncError('identity_mismatch')
                    available+=rows
                    if len(rows)<100:break
                else:raise SyncError('pagination_limit')
            current={str(r['id']) for r in available if r.get('id')};previous=snapshot(db,f'requests:{source}:{user.id}')
            acknowledged=set(current) if previous is None else set(previous)&current
            if previous is not None:
                for row in available:
                    if str(row.get('id')) in previous:continue
                    media=row.get('media') or {};item_id=media.get('jellyfinMediaId')
                    if not item_id:continue
                    try:item=emby.request('GET','/Users/'+quote(user.emby_id,safe='')+'/Items/'+quote(str(item_id),safe=''),token=_ADMIN)
                    except EmbyError:continue
                    if not isinstance(item,dict) or str(item.get('Id'))!=str(item_id):continue
                    ids=[str(item_id)];season_numbers=[]
                    if item.get('Type')=='Series':
                        season_numbers=[s['seasonNumber'] for s in row.get('seasons',[]) if type(s.get('seasonNumber')) is int]
                        if not season_numbers:continue
                        ids=[]
                        for season in items(user,'Season',parent=str(item_id)):
                            if season.get('IndexNumber') in season_numbers:
                                ids.extend(str(e['Id']) for e in items(user,'Episode',parent=str(season['Id'])) if e.get('Id'))
                        if not ids:continue
                    elif item.get('Type')!='Movie':continue
                    acknowledged.add(str(row['id']))
                    add_event(db,user,source,'request',str(item_id),str(item.get('Name','Media')),{'request_id':row['id'],'episode_ids':ids,'requested_seasons':season_numbers,'detail':'Your request is now available.'})
            store(db,f'requests:{source}:{user.id}',sorted(acknowledged))
    except (SyncError,EmbyError):
        db.rollback() # A Seerr outage must not discard independently observed new seasons.
    for event in db.scalars(select(LibraryEvent).where(LibraryEvent.user_id==user.id,LibraryEvent.source==source)):
        ids=json.loads(event.data).get('episode_ids',[])
        if ids and {normalized_id(i) for i in ids}<=watched:event.watched=True
    db.commit()

def run_due():
    from .seerr_permissions import configured as seerr_configured
    with SessionLocal() as db:
        if not tracearr.configured(db) and not seerr_configured(db):return
        source=source_fingerprint(db);now=int(time.time())
        for user in db.scalars(select(User).where(User.active.is_(True),User.emby_missing.is_(False),User.emby_id.is_not(None)).order_by(User.id)):
            key=f'library-due:{source}:{user.id}';previous=snapshot(db,key) or 0
            if now-int(previous)<300:continue
            store(db,key,now);db.commit()
            try:sync_user(db,user)
            except (EmbyError,SyncError):db.rollback()
            break # Bound scheduler work: one account per cycle, five-minute refresh per account.
        db.execute(delete(PortalCache).where(PortalCache.checked_at<now-45*86400))
        db.execute(delete(LibraryEvent).where(LibraryEvent.created_at<now-366*86400));db.commit()

@router.post('/account/library-notifications')
def account_preference(request:Request,data=Depends(__import__('app.main',fromlist=['form']).form)):
    from .main import require_user,redirect
    return save_preference(request,require_user(request),data,'/account')

@router.post('/admin/users/{uid}/library-notifications')
def admin_preference(request:Request,uid:int,data=Depends(__import__('app.main',fromlist=['form']).form)):
    from .main import require_admin
    require_admin(request);user=request.state.db.get(User,uid)
    if not user:raise HTTPException(404,'User not found')
    return save_preference(request,user,data,'/admin/users/'+str(uid))

def save_preference(request,user,data,target):
    from .main import redirect
    from .widgets import preference
    db=request.state.db
    if not tracearr.configured(db):raise HTTPException(409,'Enable Tracearr first')
    if request.url.path=='/account/library-notifications' and (not user.email or not config(db,'smtp_host')):raise HTTPException(409,'Verify your email address before changing your preferences')
    row=preference(db,user);row.seasons=True;row.email=data.get('email')=='on' and bool(user.email) and bool(config(db,'smtp_host'))
    if request.url.path.startswith('/admin/users/'):row.statistics=data.get('statistics')=='on'
    db.commit();return redirect(target)

@router.get('/library/open/{key}')
def open_event(request:Request,key:str):
    from .main import require_user,redirect
    from .widgets import library_events
    from .models import AccessService
    from .connections import media_kind
    user=require_user(request);db=request.state.db;event=db.get(LibraryEvent,key)
    if not event or event.user_id!=user.id or event.source!=source_fingerprint(db) or not event_accessible(user,event):raise HTTPException(404,'Media unavailable')
    if event.kind=='season' and not tracearr.configured(db):raise HTTPException(404,'Media unavailable')
    if event.kind=='request':
        from .group_access import seerr_allowed
        if not seerr_allowed(db,user) or config(db,'seerr_enabled')!='true':raise HTTPException(404,'Media unavailable')
    service=db.get(AccessService,'emby');base=service.browser_url if service else ''
    if not base:raise HTTPException(409,'Configure the public media address')
    # Both native web clients support the details route; the item id is URL encoded.
    return redirect(base.rstrip('/')+('/web/#/details?id=' if media_kind(db)=='jellyfin' else '/web/index.html#!/item?id=')+quote(event.item_id,safe=''))
