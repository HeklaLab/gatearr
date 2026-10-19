"""Authenticated, resumable first-run setup. Media connection is mandatory."""
from urllib.parse import urlsplit
from fastapi import APIRouter,Depends,HTTPException,Request
import httpx
from sqlalchemy import select
from .main import form,require_admin,render,redirect,set_config,sync_users,limit
from .mailer import config
from .security import url_ok,encrypt,decrypt
from .models import AccessService,User
from .settings import settings
from .connections import media_kind
from .emby import client_for,EmbyError,_ADMIN
from .integrations import request as remote_request,tracearr_login

router=APIRouter()
STEPS=('media','seerr','tracearr','smtp','finish')

def probe_media(kind,base,key):
    client=client_for(kind,base,key)
    info=client.request('GET','/System/Info',token=_ADMIN)
    users=client.users()
    if not isinstance(info,dict) or not info.get('Id') or not isinstance(users,list) or any(not isinstance(user,dict) or not user.get('Id') or not user.get('Name') for user in users):
        raise EmbyError('Réponse de synchronisation invalide')
    product=str(info.get('ProductName','')).lower()
    if product and kind not in product:
        raise ValueError('The selected server type does not match the contacted server')
    return {'id':str(info['Id']),'name':str(info.get('ServerName') or kind),'count':len(users)}

def check_base(value):
    base=url_ok(str(value))
    parsed=urlsplit(base)
    if parsed.query or parsed.fragment:raise ValueError('Invalid URL')
    parsed.port
    return base

def connect_media(db,data):
    kind=str(data.get('media_server','emby'))
    if kind not in ('emby','jellyfin'):raise ValueError('Invalid media server')
    if kind!=media_kind(db) and db.scalar(select(User.id).where(User.emby_id.is_not(None)).limit(1)):
        raise ValueError('Choose your server type before importing users')
    base=check_base(data.get('url',''))
    encoded=config(db,'emby_api_key')
    key=str(data.get('api_key','')).strip() or (decrypt(encoded) if encoded else '')
    if not key:raise ValueError('API key required')
    result=probe_media(kind,base,key)
    old_id=config(db,'media_server_id')
    if old_id and old_id!=result['id'] and db.scalar(select(User.id).where(User.emby_id.is_not(None)).limit(1)):
        raise ValueError('This portal is already linked to another media server')
    browser=url_ok(str(data.get('browser_url','')),optional=True)
    for name,value in {'media_server':kind,'emby_url':base,'emby_api_key':encrypt(key),'media_server_id':result['id'],'media_server_name':result['name'],'emby_link':browser}.items():set_config(db,name,value)
    service=db.get(AccessService,'emby')
    if service and service.name in ('Emby','Jellyfin'):
        service.name='Jellyfin' if kind=='jellyfin' else 'Emby'
    if service and browser:
        service.browser_url=browser
        service.server_url=browser
    from .default_journeys import seed,seed_seerr
    seed(db, activate=True)
    seed_seerr(db)
    db.commit()
    sync_users(db)
    set_config(db,'onboarding_media_verified','true')

@router.get('/admin/setup')
def start(request:Request):
    require_admin(request)
    if config(request.state.db,'onboarding_required')!='true':return redirect('/admin/integrations')
    step=config(request.state.db,'onboarding_step','media')
    return redirect('/admin/setup/'+(step if step in STEPS else 'media'))

@router.get('/admin/setup/{step}')
def page(request:Request,step:str):
    require_admin(request)
    if step not in STEPS:raise HTTPException(404,'Step not found')
    db=request.state.db
    if config(db,'onboarding_required')!='true':return redirect('/admin/integrations')
    return render(request,'onboarding.html',step=step,steps=STEPS,step_number=1 if step=='media' else STEPS.index(step)+2,media_url=config(db,'emby_url'),media_key_saved=bool(config(db,'emby_api_key') or ''),selected_media=media_kind(db),media_verified=config(db,'onboarding_media_verified')=='true')

@router.post('/admin/setup/{step}')
def save(request:Request,step:str,data=Depends(form)):
    require_admin(request)
    if step not in STEPS:raise HTTPException(404,'Step not found')
    db=request.state.db
    if config(db,'onboarding_required')!='true':raise HTTPException(403,'Setup already completed')
    if data.get('action')=='skip':
        if step in ('media','finish'):raise HTTPException(400,'A media server connection is required')
    elif step=='media':
        limit(request,'onboarding_connection',maximum=15)
        connect_media(db,data)
    elif step in ('seerr','tracearr'):
        limit(request,'onboarding_connection',maximum=15)
        from .admin_features import integrations_save
        from starlette.datastructures import FormData
        from .integrations import SyncError
        from .security import email_ok
        from uuid import UUID
        base=check_base(data.get('url',''))
        key=str(data.get('api_key','')).strip() or decrypt(config(db,step+'_api_key'))
        if not key:raise ValueError('API key required')
        try:
            with httpx.Client(base_url=base+'/',timeout=15,trust_env=False,follow_redirects=False) as client:
                if step=='seerr':
                    result=remote_request(client,'GET','api/v1/user',headers={'X-Api-Key':key},params={'take':1,'skip':0})
                    if not isinstance(result,dict) or not isinstance(result.get('results'),list):raise ValueError('Invalid connection response')
                else:
                    UUID(str(data.get('server_id','')))
                    owner=email_ok(str(data.get('owner_email','')))
                    password=str(data.get('owner_password','')) or decrypt(config(db,'tracearr_owner_password'))
                    if not password or data.get('internal_api')!='on':raise ValueError('Tracearr requires an owner account and its internal API.')
                    result=remote_request(client,'GET','api/v2/public/users',headers={'Authorization':'Bearer '+key},params={'pageSize':1})
                    if not isinstance(result,dict) or not isinstance(result.get('data'),list):raise ValueError('Invalid connection response')
                    parsed=urlsplit(base)
                    client.headers['Origin']=parsed.scheme+'://'+parsed.netloc
                    remote_request(client,'POST','api/v1/auth/sign-in/email',json={'email':owner,'password':password,'rememberMe':False})
                    if not client.cookies:raise SyncError('authentication')
                    try:remote_request(client,'GET','api/v1/email/suppressions')
                    finally:remote_request(client,'POST','api/v1/auth/sign-out',json={})
        except SyncError:
            raise HTTPException(502,'Connection refused or service unavailable. Check the settings and try again.')
        integrations_save(request,FormData({**dict(data),'service':step,'enabled':'on'}))
    elif step=='smtp':
        from .main import admin_smtp
        admin_smtp(request,data)
    elif step=='finish':
        if config(db,'onboarding_media_verified')!='true':
            raise HTTPException(400,'A media server connection is required')
        set_config(db,'onboarding_required','false')
        set_config(db,'onboarding_step','finish')
        db.commit()
        return redirect('/home')
    else:raise ValueError('Invalid action')
    next_step=STEPS[STEPS.index(step)+1]
    set_config(db,'onboarding_step',next_step)
    db.commit()
    return redirect('/admin/setup/'+next_step)
