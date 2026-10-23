"""Permission-filtered portal widgets; admin-only configuration and no browser API keys."""
import json,time
from datetime import datetime,timezone,timedelta
from collections import Counter
from sqlalchemy import select
from .models import PortalCache,GroupMember,LibraryPreference,LibraryEvent
from .mailer import config
from .security import digest
from .emby import emby,_ADMIN,EmbyError
from .integrations import SyncError,request
from . import tracearr
TYPES=('widget_media','widget_seerr','widget_tracearr','widget_library')
METRICS={'widget_media':{'movies':'Movies','series':'Series'},'widget_seerr':{'movies_left':'Movies left','series_left':'Seasons left','pending':'Awaiting approval','processing':'Processing','available':'Available','approved':'Approved','renewal':'Quota window (days)'},'widget_tracearr':{'watch_time':'Watch time','plays':'Sessions','favorite':'Most watched series','direct':'Direct play','transcoded':'Transcoded','bandwidth':'Estimated traffic','activity':'Daily activity','comparison':'Change from previous period'},'widget_library':{}}

def preference(db,user):
    row=db.get(LibraryPreference,user.id)
    if not row:row=LibraryPreference(user_id=user.id,seasons=True,email=False,statistics=True);db.add(row);db.flush()
    return row

def available(db,kind):
    from .seerr_permissions import configured as seerr_configured
    return bool(config(db,'emby_api_key')) if kind=='widget_media' else seerr_configured(db) if kind=='widget_seerr' else tracearr.configured(db) if kind=='widget_tracearr' else seerr_configured(db) or tracearr.configured(db)

def validate(block):
    kind=block['kind'];metrics=block.get('metrics',list(METRICS[kind])[:2]);groups=block.get('groups',[])
    if not isinstance(metrics,list) or any(m not in METRICS[kind] for m in metrics) or len(set(metrics))!=len(metrics):raise ValueError('Invalid widget metrics')
    if not isinstance(groups,list) or len(groups)>100 or any(type(g) is not int or g<=0 for g in groups):raise ValueError('Invalid widget audience')
    if type(block.get('show_logo',False)) is not bool:raise ValueError('Invalid widget logo setting')
    if block.get('period','week') not in ('week','month','30days'):raise ValueError('Invalid widget period')
    if type(block.get('priority',0)) is not int or not 0<=block.get('priority',0)<=100:raise ValueError('Invalid widget priority')
    ids=block.get('libraries',[])
    if not isinstance(ids,list) or len(ids)>200 or any(not isinstance(i,str) or not i or len(i)>128 for i in ids):raise ValueError('Invalid widget libraries')
    if block.get('retention','duration') not in ('duration','watched') or type(block.get('days',14)) is not int or not 1<=block.get('days',14)<=365:raise ValueError('Invalid widget retention')
    for field in ('requests','seasons'):
        if type(block.get(field,True)) is not bool:raise ValueError('Invalid widget setting')

def choose(db,blocks,user,editor=False):
    if not user:return set()
    group=db.scalar(select(GroupMember.group_id).where(GroupMember.user_id==user.id));chosen={}
    for b in blocks:
        if b['kind'] not in TYPES:continue
        v=b.get('visibility','everyone')
        if not editor and (not available(db,b['kind']) or (v=='admins' and not user.admin) or (v=='members' and user.admin) or (b.get('groups') and group not in b['groups'])):continue
        if not editor:
            parent=b.get('parent');index={x['id']:x for x in blocks};hidden=False
            while parent and parent in index:
                owner=index[parent];parent_visibility=owner.get('visibility','everyone')
                if (parent_visibility=='admins' and not user.admin) or (parent_visibility=='members' and user.admin):hidden=True;break
                parent=owner.get('parent')
            if hidden:continue
        rank=(2 if b.get('groups') else 1 if v!='everyone' else 0,b.get('priority',0),-b['order'])
        if editor or b['kind'] not in chosen or rank>chosen[b['kind']][0]:chosen[b['kind']]=(rank,b['id'])
    return {b['id'] for b in blocks if editor and b['kind'] in TYPES} if editor else {v[1] for v in chosen.values()}

def items(user,types,fields='',parent=None):
    params={'Recursive':'true','IncludeItemTypes':types,'Fields':fields,'Limit':200,'StartIndex':0}
    if parent:params['ParentId']=parent
    result=[]
    for _ in range(500):
        page=emby.request('GET','/Users/'+user.emby_id+'/Items',token=_ADMIN,params=params)
        if not isinstance(page,dict) or not isinstance(page.get('Items'),list):raise EmbyError('Invalid media response')
        result+=page['Items'];params['StartIndex']+=len(page['Items'])
        if not page['Items'] or params['StartIndex']>=page.get('TotalRecordCount',params['StartIndex']):return result
    raise EmbyError('Media pagination limit')

def media_metrics(db,user,block):
    # The native user-scoped query applies library and content restrictions.
    # Never sum views: they can overlap, and legacy admin selections are obsolete.
    counts={}
    for key,kind in [('movies','Movie'),('series','Series')]:
        if key not in block.get('metrics',['movies','series']):continue
        p=emby.request('GET','/Users/'+user.emby_id+'/Items',token=_ADMIN,params={'Recursive':'true','IncludeItemTypes':kind,'Limit':0})
        if not isinstance(p,dict) or type(p.get('TotalRecordCount')) is not int or p['TotalRecordCount']<0:raise EmbyError('Invalid media count')
        counts[key]=p['TotalRecordCount']
    return {'metrics':[{'label':METRICS[block['kind']][k],'value':v} for k,v in counts.items()]}

def seerr_metrics(db,user,block):
    from .group_access import seerr_allowed
    from .seerr_permissions import connection,read_permissions
    if not seerr_allowed(db,user):return None
    result=[]
    with connection(db,user) as (client,uid):
        flags=read_permissions(client,uid);can_manage=bool(flags&2 or flags&16);quota=None
        for key in block.get('metrics',['movies_left','series_left']):
            if key=='renewal':
                quota=quota or request(client,'GET',f'api/v1/user/{uid}/quota');q=quota.get('movie',{});value=q.get('days','—')
            elif key in ('movies_left','series_left'):
                quota=quota or request(client,'GET',f'api/v1/user/{uid}/quota');q=quota.get('movie' if key=='movies_left' else 'tv',{});value='∞' if q.get('limit')==0 else q.get('remaining','—')
            else:
                if key=='pending' and not can_manage:continue
                params={'take':1,'skip':0,'filter':key}
                if not (can_manage and user.admin):params['requestedBy']=uid
                value=request(client,'GET','api/v1/request',params=params).get('pageInfo',{}).get('results','—')
            result.append({'label':METRICS['widget_seerr'][key],'value':value})
    return {'metrics':result} if result else None

def tracearr_period(period,current=None):
    current=current or datetime.now(timezone.utc)
    start=current-timedelta(days=30) if period=='30days' else current.replace(day=1,hour=0,minute=0,second=0,microsecond=0) if period=='month' else (current-timedelta(days=current.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
    return start,current

def tracearr_metrics(db,user,block):
    if not preference(db,user).statistics:return None
    period=block.get('period','week');start,current=tracearr_period(period)
    with tracearr.connection(db) as c:
        history=tracearr.history(db,user,c,{'since':start.isoformat()})
        previous=[]
        if 'comparison' in block.get('metrics',[]):
            before=start-timedelta(days=7) if period=='week' else (start-timedelta(days=1)).replace(day=1) if period=='month' else start-timedelta(days=30)
            previous=tracearr.history(db,user,c,{'since':before.isoformat(),'until':start.isoformat()})
    watch=sum(max(0,r.get('duration_ms') or 0) for r in history);minutes=watch//60000
    shows=Counter()
    for r in history:
        if r.get('show_title'):shows[r['show_title']]+=max(0,r.get('duration_ms') or 0)
    favorite=shows.most_common(1)
    bandwidth=sum((r.get('bitrate') or 0)*max(0,r.get('duration_ms') or 0)/8 for r in history)
    values={'watch_time':f'{minutes//60} h {minutes%60:02d}','plays':len(history),'favorite':favorite[0][0] if favorite else '—','direct':sum(not bool(r.get('is_transcode')) for r in history),'transcoded':sum(bool(r.get('is_transcode')) for r in history),'bandwidth':f'{bandwidth/1e9:.2f} GB','comparison':f"{(watch-sum(max(0,r.get('duration_ms') or 0) for r in previous))/3600000:+.1f} h"}
    daily=Counter()
    for r in history:daily[str(r.get('started_at',''))[:10]]+=max(0,r.get('duration_ms') or 0)/3600000
    chart=[{'day':k,'hours':round(v,2)} for k,v in sorted(daily.items())] if 'activity' in block.get('metrics',[]) else []
    return {'period_start':start.date().isoformat(),'period_end':current.date().isoformat(),'chart':chart,'metrics':[{'label':METRICS['widget_tracearr'][k],'value':values[k]} for k in block.get('metrics',['watch_time','favorite']) if k!='activity' and (k!='bandwidth' or all(type(r.get('bitrate')) in (int,float) for r in history))]}

def library_events(db,user,block):
    from .library_updates import source_fingerprint,event_accessible
    from .group_access import seerr_allowed
    pref=preference(db,user);now=int(time.time());result=[]
    if block.get('retention','duration')=='watched' and not tracearr.configured(db):return None
    for e in db.scalars(select(LibraryEvent).where(LibraryEvent.user_id==user.id,LibraryEvent.source==source_fingerprint(db)).order_by(LibraryEvent.created_at.desc()).limit(100)):
        if e.kind=='season' and (not block.get('seasons',True) or not tracearr.configured(db)):continue
        if e.kind=='request' and (not block.get('requests',True) or config(db,'seerr_enabled')!='true' or not seerr_allowed(db,user)):continue
        if block.get('retention','duration')=='duration' and now-e.created_at>block.get('days',14)*86400:continue
        if block.get('retention')=='watched' and e.watched:continue
        if not event_accessible(user,e):continue
        result.append({'title':e.title,'kind':e.kind,'detail':json.loads(e.data).get('detail',''),'href':'/library/open/'+e.key})
        if len(result)>=10:break
    return {'events':result}

def display(db,user,block,editor=False):
    if editor:
        sample={'widget_media':[('Movies',1302),('Series',284)],'widget_seerr':[('Movies left','3 / 5'),('Seasons left','2 / 3')],'widget_tracearr':[('Watch time','12 h 40'),('Most watched series','Severance')],'widget_library':[]}
        start,end=tracearr_period(block.get('period','week'))
        return {'period_start':start.date().isoformat(),'period_end':end.date().isoformat(),'metrics':[{'label':k,'value':v} for k,v in sample[block['kind']]],'events':[{'title':'The Batman','detail':'Your request is now available.','href':'#','kind':'request'}] if block['kind']=='widget_library' else [],'preview':True}
    if not user or not user.active or user.emby_missing:return None
    try:
        policy=emby.user(user.emby_id).get('Policy',{})
        if policy.get('IsDisabled'):return None
        if block['kind']=='widget_seerr':
            from .group_access import seerr_allowed
            if not seerr_allowed(db,user):return None
            return seerr_metrics(db,user,block)
        if block['kind']=='widget_library':return library_events(db,user,block)
        # Check the actual native policy before reading a cached aggregate.
        key=digest(json.dumps(['authorized-counts-v3-period',tracearr_period(block.get('period','week'))[0].date().isoformat() if block['kind']=='widget_tracearr' else '',user.id,user.admin,user.version,user.emby_id,policy,block,tracearr.fingerprint(db),config(db,'emby_url'),config(db,'emby_api_key'),config(db,'seerr_url'),config(db,'seerr_api_key'),config(db,'seerr_access_'+str(user.id))],sort_keys=True))
        if block['kind']=='widget_tracearr' and not preference(db,user).statistics:return None
        row=db.get(PortalCache,key);now=int(time.time())
        if row and now-row.checked_at<60:return json.loads(row.data)
        result={'widget_media':media_metrics,'widget_seerr':seerr_metrics,'widget_tracearr':tracearr_metrics}[block['kind']](db,user,block)
        db.merge(PortalCache(key=key,data=json.dumps(result),checked_at=now));db.commit();return result
    except (EmbyError,SyncError):return {'metrics':[],'message':'Statistics temporarily unavailable.'}

def builder_data(db):
    from .models import PermissionGroup
    from .connections import media_kind
    from .connection_health import checks
    from .service_assets import default_icon
    health=checks(db)
    connected=lambda key:health.get(key,{}).get('state')=='connected'
    enabled={'widget_media':connected('emby'),'widget_seerr':available(db,'widget_seerr') and connected('seerr'),'widget_tracearr':available(db,'widget_tracearr') and connected('tracearr')}
    enabled['widget_library']=enabled['widget_seerr'] or enabled['widget_tracearr']
    return {'types':list(TYPES),'enabled':enabled,'icons':{k:default_icon({'widget_media':'emby','widget_seerr':'seerr','widget_tracearr':'tracearr','widget_library':'emby'}[k],media_kind(db)) for k in TYPES},'metrics':METRICS,'groups':[{'id':g.id,'name':g.name} for g in db.scalars(select(PermissionGroup))],'tracearr':tracearr.configured(db),'seerr':__import__('app.seerr_permissions',fromlist=['configured']).configured(db)}

def conflicts(blocks):
    widgets=[b for b in blocks if b['kind'] in TYPES]
    for i,a in enumerate(widgets):
        for b in widgets[i+1:]:
            if a['kind']!=b['kind'] or a.get('priority',0)!=b.get('priority',0):continue
            ga,gb=set(a.get('groups',[])),set(b.get('groups',[]));va,vb=a.get('visibility','everyone'),b.get('visibility','everyone')
            if ga and gb and ga&gb and (va==vb or 'everyone' in (va,vb)):return True
            if not ga and not gb and va==vb:return True
    return False
