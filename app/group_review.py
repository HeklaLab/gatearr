"""Read-only membership preview, bound to a short-lived, session-specific proof."""
import hashlib,hmac,json,time
import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from .models import GroupMember,PolicyState,GroupBaseline,SeerrPolicyState,SeerrQuotaState
from .settings import settings
from . import i18n,seerr_permissions as sp,seerr_quotas as sq
from .integrations import SyncError
from .group_access import group_for,seerr_allowed,access_values
from .connections import media_kind


def review(request,data,group,users,policy,access,remotes,api):
    if not users:
        return JSONResponse({'required':False}) if data.get('review_only')=='on' else None
    from .permissions import encoded,normalize,label,READ_ONLY
    db=request.state.db
    translations=i18n.overrides(db,request.state.locale)
    t=lambda message:i18n.translate(message,request.state.locale,overrides=translations)
    def display(value):
        if type(value) is bool:return t('Yes') if value else t('No')
        if value is None:return '—'
        if isinstance(value,(dict,list)):return json.dumps(value,ensure_ascii=False)
        return str(value)
    libraries=api.libraries()
    def ident(value):return str(value).replace('-','').lower()
    payload=[];snapshots=[]
    for user in sorted(users,key=lambda u:u.id):
        current=remotes[user.id]
        if not isinstance(current,dict) or not current:raise HTTPException(502,'Could not verify current permissions. Try again.')
        row=db.get(PolicyState,user.id)
        baseline=json.loads(row.baseline) if row else dict(current)
        previous=json.loads(row.desired) if row else {}
        baseline.update({k:v for k,v in current.items() if k not in previous})
        desired={k:baseline[k] for k in previous if k not in policy and k in baseline};desired.update(policy)
        target={**current,**desired};diff=[]
        def add(service,name,before,after):
            if before!=after:diff.append({'service':service,'label':t(name),'before':display(before),'after':display(after)})
        media='Jellyfin' if media_kind(db)=='jellyfin' else 'Emby'
        from .permission_ui import metadata,LIST_SOURCES,hour_text
        meta=metadata(api,{k:v for k,v in target.items() if k in desired},libraries)
        def human(key,value):
            if key=='AccessSchedules':return '; '.join(t(slot['DayOfWeek'])+' '+hour_text(slot['StartHour'])+'–'+hour_text(slot['EndHour']) for slot in value or []) or '—'
            if key in LIST_SOURCES:
                names={ident(item['Id']):item['Name'] for item in meta.get(LIST_SOURCES[key]) or []}
                return ', '.join(names.get(ident(item),t('Previously selected item (unavailable)')) for item in value or []) or '—'
            if isinstance(value,list):return ', '.join(t(item) for item in value) if all(isinstance(item,str) for item in value) else t('Custom selection')
            if isinstance(value,dict):return t('Custom selection')
            return value
        for key in sorted(desired):
            if key in READ_ONLY or key=='EnabledFolders':continue
            if normalize(key,current.get(key))!=normalize(key,target.get(key)):
                # Schedule IDs are server metadata, not part of an administrator's intent.
                add(media,label(key),human(key,current.get(key)),human(key,target.get(key)))
        if any(k in desired for k in ('EnableAllFolders','EnabledFolders')):
            for library in libraries:
                def allowed(values):return bool(values.get('EnableAllFolders')) or ident(library['Id']) in {ident(v) for v in values.get('EnabledFolders',[])}
                add(media,t('Library')+' · '+library['Name'],allowed(current),allowed(target))
        local=db.get(GroupBaseline,user.id)
        old=group_for(db,user)
        local_target={**(json.loads(local.values) if local else access_values(user)),**access}
        add('Gatearr','Admin Gatearr',user.admin,local_target['gatearr_admin'])
        before_tools=set(json.loads(user.tool_access));after_tools=set(local_target['tools'])
        for tool in sorted(before_tools|after_tools):add('Gatearr',tool.capitalize(),tool in before_tools,tool in after_tools)
        add('Seerr','Access',seerr_allowed(db,user),access.get('seerr_access',True))
        sr=db.get(SeerrPolicyState,user.id);qr=db.get(SeerrQuotaState,user.id)
        permission_target=access.get('seerr_permissions',sr.individual if sr else None)
        if permission_target is None and sr and sr.desired is not None:permission_target=sr.baseline
        quota_target=access.get('seerr_quotas',json.loads(qr.individual) if qr else {})
        if not quota_target and qr and qr.desired!='{}':quota_target=json.loads(qr.baseline)
        native=None
        if sp.configured(db):
            try:
                with sp.connection(db,user) as (client,rid):
                    mask=sp.read_permissions(client,rid);_,quotas=sq.read(client,rid)
                native={'mask':mask,'quotas':quotas,'id':rid,'connection':sp.fingerprint(db)}
                if (permission_target is not None and sr and sr.connection and sr.connection!=native['connection']) or (quota_target and qr and qr.connection and qr.connection!=native['connection']):
                    raise HTTPException(409,'Seerr connection changed. Refresh the user permissions before assigning a group.')
                if permission_target is not None:
                    if rid==1:raise HTTPException(409,'Seerr owner permissions cannot be changed')
                    for bit,name in sp.FLAGS.items():add('Seerr',name,bool(mask&bit),bool(permission_target&bit))
                for key,value in quota_target.items():add('Seerr',sq.FIELDS[key],quotas.get(key),value)
            except (SyncError,httpx.HTTPError):raise HTTPException(502,'Could not verify current Seerr permissions. Check the connection and account import, then try again.')
        elif permission_target is not None or quota_target:
            raise HTTPException(409,'Configure Seerr before applying Seerr permissions or quotas.')
        def state_values(obj):return {col.key:getattr(obj,col.key) for col in obj.__table__.columns if col.key not in ('observed','checked_at','error','confirmed')} if obj else None
        snapshots.append({'id':user.id,'version':user.version,'group':old.id if old else None,'current':current,'native':native,'local':access_values(user),'policy':state_values(row),'baseline':state_values(local),'seerr':state_values(sr),'quota':state_values(qr)})
        payload.append({'id':user.id,'name':user.name,'differences':diff})
    intent=sorted((str(k),str(v)) for k,v in data.multi_items() if k not in ('csrf','review_only','review_token'))
    snapshot=encoded({'actor':request.state.user.id,'csrf':request.state.session.csrf,'route':request.url.path,'group':[group.id,group.version,sorted(db.scalars(select(GroupMember.user_id).where(GroupMember.group_id==group.id)))],'policy':policy,'access':access,'intent':intent,'users':snapshots})
    def signature(issued):return hmac.new(settings.secret_key.encode(),('group-review\n'+str(issued)+'\n'+snapshot).encode(),hashlib.sha256).hexdigest()
    if data.get('review_only')=='on':
        issued=int(time.time())
        return JSONResponse({'required':True,'group':group.name,'users':payload,'review_token':str(issued)+'.'+signature(issued)})
    token=str(data.get('review_token',''))
    try:issued,supplied=token.split('.');issued=int(issued)
    except (ValueError,TypeError):raise HTTPException(409,'Review the current permissions before confirming the group assignment.')
    if not 0<=time.time()-issued<=300 or not hmac.compare_digest(supplied,signature(issued)):
        raise HTTPException(409,'Permissions or group settings changed. Review the differences again.')
