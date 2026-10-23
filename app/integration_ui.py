"""Uniform connection settings; tests remain read-only and separate from saving."""
from urllib.parse import urlsplit
from fastapi import APIRouter,Request,Depends,HTTPException
from .main import form,require_admin,set_config,redirect
from .mailer import config
from .security import url_ok,encrypt
from .models import AccessService
SERVICES=('emby','seerr','radarr','sonarr','bazarr','tracearr','tdarr')
router=APIRouter()
@router.post('/admin/connections/{service}/save')
def save(request:Request,service:str,data=Depends(form)):
    require_admin(request)
    if service not in SERVICES:raise HTTPException(404,'Invalid service')
    db=request.state.db
    if service=='emby':
        from .onboarding import connect_media
        connect_media(db,data)
    else:
        active=data.get('enabled')=='on';base=url_ok(data.get('url',''),optional=not active)
        if base and (urlsplit(base).query or urlsplit(base).fragment):raise ValueError('Invalid URL')
        if service in ('radarr','sonarr','bazarr') and base:
            parsed=urlsplit(base)
            if parsed.path.rstrip('/') not in ('','/tools/'+service+'/app'):raise ValueError('Use the private server root URL or its Gatearr URL Base')
            base=parsed.scheme+'://'+parsed.netloc
        if service in ('radarr','sonarr','bazarr') and active and data.get('proxy_acknowledge')!='on':raise ValueError('Confirm the private upstream and proxy authentication setup')
        set_config(db,service+'_url',base)
        if data.get('api_key'):set_config(db,service+'_api_key',encrypt(data['api_key']))
        if data.get('clear_key')=='on':set_config(db,service+'_api_key','')
        if service!='tdarr' and active and not config(db,service+'_api_key'):raise ValueError('API key required')
        set_config(db,service+'_enabled','true' if active else 'false')
        if service in ('tracearr','tdarr') and data.get('interface_enabled')=='on' and not data.get('public_url'):raise ValueError('Public interface address required')
        set_config(db,service+'_interface_enabled','true' if data.get('interface_enabled')=='on' else 'false')
    if service=='tracearr':
        import uuid
        server=str(data.get('tracearr_server_id','')).strip()
        if server:uuid.UUID(server)
        set_config(db,'tracearr_server_id',server)
    existing=db.get(AccessService,service) if service in ('emby','seerr') else None
    public=url_ok(data.get('public_url',existing.browser_url if existing else config(db,service+'_public_url')),optional=True)
    set_config(db,service+'_public_url',public)
    if service in ('emby','seerr'):
        row=db.get(AccessService,service)
        if not row:row=AccessService(key=service,name=service.capitalize(),browser_url=public,server_url=public);db.add(row)
        row.browser_url=public
        if 'name' in data:
            name=str(data.get('name','')).strip()
            if not name or len(name)>100:raise ValueError('Invalid service name')
            row.name=name
        if 'server_url' in data:row.server_url=url_ok(data['server_url'],optional=True)
        if 'icon' in data:
            from .icons import local_icon_value,font_icon
            row.icon_url=local_icon_value(db,data);row.icon=font_icon(data.get('icon','link'))
    if service=='seerr':
        mode=data.get('notification_mode','unmanaged')
        if mode not in ('unmanaged','optional','forced'):raise ValueError('Invalid notification mode')
        set_config(db,'seerr_notification_mode',mode)
    from .connection_health import invalidate
    invalidate(db,service);db.commit()
    return redirect('/admin/integrations?connection='+service+'#connection-'+service)
