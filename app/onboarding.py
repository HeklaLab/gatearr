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
from .integrations import request as remote_request

router=APIRouter()
STEPS=('media','applications','smtp','finish')
LEGACY={'seerr':'applications','tools':'applications'}

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
    for name,value in {'media_server':kind,'emby_url':base,'emby_api_key':encrypt(key),'media_server_id':result['id'],'media_server_name':result['name']}.items():set_config(db,name,value)
    service=db.get(AccessService,'emby')
    if service and service.name in ('Emby','Jellyfin'):
        service.name='Jellyfin' if kind=='jellyfin' else 'Emby'
    if service:
        service.browser_url=browser
        if browser:service.server_url=browser
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
    step=LEGACY.get(config(request.state.db,'onboarding_step','media'),config(request.state.db,'onboarding_step','media'))
    return redirect('/admin/setup/'+(step if step in STEPS else 'media'))

@router.get('/admin/setup/{step}')
def page(request:Request,step:str):
    require_admin(request)
    step=LEGACY.get(step,step)
    if step not in STEPS:raise HTTPException(404,'Step not found')
    db=request.state.db
    if config(db,'onboarding_required')!='true':return redirect('/admin/integrations')
    request.state.setup_context=dict(step=step,steps=STEPS,step_number=1 if step=='media' else STEPS.index(step)+2,media_url=getattr(request.state,'form_values',{}).get('url',config(db,'emby_url')),media_key_saved=bool(config(db,'emby_api_key') or ''),selected_media=getattr(request.state,'form_values',{}).get('media_server',media_kind(db)),media_verified=config(db,'onboarding_media_verified')=='true')
    return render(request,'onboarding.html',**request.state.setup_context)

@router.post('/admin/setup/{step}')
def save(request:Request,step:str,data=Depends(form)):
    require_admin(request)
    legacy=step
    step=LEGACY.get(step,step)
    if step not in STEPS:raise HTTPException(404,'Step not found')
    db=request.state.db
    if config(db,'onboarding_required')!='true':raise HTTPException(403,'Setup already completed')
    if legacy=='seerr' and data.get('action')!='skip':return application_save(request,'seerr',data)
    if data.get('action')=='skip':
        if step in ('media','finish'):raise HTTPException(400,'A media server connection is required')
    elif step=='media':
        limit(request,'onboarding_connection',maximum=15)
        connect_media(db,data)
    elif step=='applications':
        pass
    elif step=='smtp':
        from .main import admin_smtp
        admin_smtp(request,data)
    elif step=='finish':
        if config(db,'onboarding_media_verified')!='true':
            raise HTTPException(400,'A media server connection is required')
        from .portal import initialize
        initialize(db,request.state.user)
        set_config(db,'onboarding_required','false')
        set_config(db,'onboarding_step','finish')
        db.commit()
        return redirect('/home')
    else:raise ValueError('Invalid action')
    next_step=STEPS[STEPS.index(step)+1]
    set_config(db,'onboarding_step',next_step)
    db.commit()
    return redirect('/admin/setup/'+next_step)


@router.post('/admin/setup/applications/{service}/save')
def application_save(request:Request,service:str,data=Depends(form)):
    require_admin(request)
    if config(request.state.db,'onboarding_required')!='true':raise HTTPException(403,'Setup already completed')
    from .integration_ui import save,SERVICES
    if service not in SERVICES:raise HTTPException(404,'Invalid service')
    if data.get('enabled')=='on':
        result=application_test(request,service,data)
        if result['state']!='connected':raise HTTPException(502,result['detail'])
    save(request,service,data)
    return redirect('/admin/setup/applications?saved='+service+'#service-'+service)

@router.post('/admin/setup/applications/{service}/test')
def application_test(request:Request,service:str,data=Depends(form)):
    require_admin(request);limit(request,'onboarding_connection',maximum=30)
    from .integration_ui import SERVICES
    from .connection_health import probe
    if service not in SERVICES:raise HTTPException(404,'Invalid service')
    base=check_base(data.get('url',''))
    encoded=config(request.state.db,service+'_api_key')
    key=str(data.get('api_key','')).strip() or (decrypt(encoded) if encoded else '')
    values={'url':base,'key':key,'kind':media_kind(request.state.db)}
    state,detail=probe(service,values)
    return {'state':state,'detail':detail,'diagnostics':values.get('diagnostics',{})}


@router.post('/admin/setup/smtp/test')
def email_test(request:Request,data=Depends(form)):
    require_admin(request);limit(request,'onboarding_connection',maximum=30)
    from .connection_health import smtp_probe
    if data.get('smtp_mode') not in ('ssl','starttls','plain'):raise ValueError('Invalid SMTP mode')
    if not 1<=int(data.get('smtp_port','0'))<=65535:raise ValueError('Invalid SMTP port')
    values={k:str(data[k]) for k in ('smtp_host','smtp_port','smtp_mode','smtp_username','smtp_password') if k in data and (k!='smtp_password' or data[k])}
    result=smtp_probe(request.state.db,values)
    from .i18n import translate
    result['detail']=translate(result['detail'],request.state.locale)
    return result
