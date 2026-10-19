import re
from uuid import UUID
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from .main import form, require_admin, require_user, render, redirect, sync_users, set_config, limit
from .models import User, IntegrationJob
from .security import password_ok, url_ok, encrypt, email_ok
from .mailer import config
from .emby import emby
from . import portal
from .integrations import SERVICES, queue_all
from .settings import settings

router = APIRouter()

@router.get('/home')
def home(request: Request):
    require_user(request)
    return render(request, 'home.html', preview=False)

@router.get('/theme.css')
def theme_css(request: Request):
    draft = request.query_params.get('draft') == '1'
    if draft:
        require_admin(request)
    layout = portal.load(request.state.db, draft)
    from .themes import css
    return Response(css(request.state.db,request.state.user,draft),media_type='text/css')

@router.get('/admin/portal')
def builder(request: Request):
    require_admin(request)
    return render(request, 'builder.html', layout=portal.load(request.state.db, True), portal_version=portal.version(request.state.db))

@router.get('/admin/portal/preview')
def preview(request: Request):
    require_admin(request)
    return render(request, 'home.html', layout=portal.load(request.state.db, True), preview=True)

@router.post('/admin/portal/block')
def block_save(request: Request, data=Depends(form)):
    require_admin(request)
    draft = portal.load(request.state.db, True)
    block = portal.block_from_form(data)
    if data.get('block_id') and not any(item['id'] == block['id'] for item in draft['blocks']):
        raise HTTPException(404, 'Block not found')
    draft['blocks'] = [item for item in draft['blocks'] if item['id'] != block['id']] + [block]
    portal.save(request.state.db, draft, int(data['version']))
    return redirect('/admin/portal')

@router.post('/admin/portal/delete')
def block_delete(request: Request, data=Depends(form)):
    require_admin(request)
    draft = portal.load(request.state.db, True)
    draft['blocks'] = [item for item in draft['blocks'] if item['id'] != data['block_id']]
    portal.save(request.state.db, draft, int(data['version']))
    return redirect('/admin/portal')

@router.post('/admin/portal/move')
def block_move(request: Request, data=Depends(form)):
    require_admin(request)
    draft = portal.load(request.state.db, True)
    selected = next((b for b in draft['blocks'] if b['id'] == data['block_id']), None)
    if not selected or data['direction'] not in ('up','down'):
        raise ValueError('Invalid block')
    blocks = sorted([b for b in draft['blocks'] if b['region'] == selected['region']], key=lambda b: (b['order'], b['id']))
    index = blocks.index(selected)
    other = index-1 if data['direction'] == 'up' else index+1
    if 0 <= other < len(blocks):
        blocks[index], blocks[other] = blocks[other], blocks[index]
    for position, block in enumerate(blocks):
        block['order'] = (position+1)*10
    portal.save(request.state.db, draft, int(data['version']))
    return redirect('/admin/portal')

@router.post('/admin/portal/theme')
def theme_save(request: Request, data=Depends(form)):
    require_admin(request)
    draft = portal.load(request.state.db, True)
    draft['nav_position'] = data['nav_position']
    draft['sidebar_position'] = data.get('sidebar_position', draft.get('sidebar_position','left'))
    draft['theme'] = {key: data.get(key,draft['theme'].get(key,default)) for key,default in portal.DEFAULT['theme'].items()}
    portal.save(request.state.db, draft, int(data['version']))
    return redirect('/admin/portal')

@router.post('/admin/portal/publish')
def publish(request: Request, data=Depends(form)):
    require_admin(request)
    portal.save(request.state.db, portal.load(request.state.db, True), int(data['version']), publish=True)
    return redirect('/admin/portal')

@router.post('/admin/portal/reset')
def reset_draft(request: Request, data=Depends(form)):
    require_admin(request)
    portal.save(request.state.db, portal.load(request.state.db), int(data['version']))
    return redirect('/admin/portal')

@router.get('/admin/emby')
def emby_admin(request: Request):
    require_admin(request)
    return render(request, 'emby_admin.html', remote_users=emby.users(), options=emby.copy_options())

@router.post('/admin/emby/clone')
def clone(request: Request, data=Depends(form)):
    require_admin(request)
    limit(request, 'provision', maximum=10)
    password_ok(data['password'])
    name = str(data['name']).strip()
    if not name or len(name) > 100 or any(ord(c) < 32 for c in name):
        raise ValueError('Invalid name')
    source_id = data['source_id']
    emby.clone(source_id, name, data['password'], list(data.getlist('copy_options')))
    sync_users(request.state.db)
    log_message = 'User created. You can now assign libraries and send an email invitation.'
    return render(request, 'message.html', message=log_message)

@router.get('/admin/users/{local_id}')
def emby_user(request: Request, local_id: int):
    require_admin(request)
    user = request.state.db.get(User, local_id)
    if not user or not user.emby_id:
        raise HTTPException(404, 'Emby account not found')
    from .permissions import observe,fields
    from .models import PolicyState
    from .emby import EmbyError
    try:
        remote=emby.user(user.emby_id);available=emby.libraries()
        remote_users=emby.users();options=emby.copy_options();policy_offline=False
    except EmbyError:
        cached=request.state.db.get(PolicyState,user.id)
        if not cached:raise
        remote={'Policy':__import__('json').loads(cached.observed)};available=[];remote_users=[];options=[];policy_offline=True
        cached.error='Media server unreachable; showing the last observed permissions';request.state.db.commit()
    normalize=lambda value:str(value).replace('-','').lower()
    selected={normalize(value) for value in remote.get('Policy',{}).get('EnabledFolders',[]) or []}
    if not policy_offline:remote.setdefault('Policy',{})['EnabledFolders']=[item['Id'] for item in available if normalize(item['Id']) in selected]
    from .permissions import observe,fields
    policy_state=cached if policy_offline else observe(request.state.db,user,remote.get('Policy',{}))
    return render(request,'emby_user.html',policy_state=policy_state,permission_fields=fields(remote.get('Policy',{}),policy_state),member=user,remote=remote,libraries=available,remote_users=remote_users,options=options)

@router.post('/admin/emby/libraries')
def libraries_save(request: Request, data=Depends(form)):
    require_admin(request)
    user = request.state.db.get(User, int(data['id']))
    if not user or not user.emby_id:
        raise HTTPException(404, 'Emby account not found')
    mode=data.get('access_mode')
    if mode is not None and mode not in ('all','selected'):
        raise ValueError('Invalid access mode')
    all_folders=mode=='all' if mode is not None else data.get('all_folders')=='on'
    selected=list(data.getlist('libraries'))
    if data.get('action')=='remove_all':
        selected=[]
        all_folders=False
    from .permissions import state,encoded,recompute,observe
    prior=emby.user(user.emby_id).get('Policy',{})
    row=state(request.state.db,user,prior)
    names={library['Id']:library['Name'] for library in emby.libraries()}
    describe=lambda full,ids:'All libraries' if full else ', '.join(names.get(identifier,identifier) for identifier in ids) or 'No libraries'
    request.state.audit_detail='Libraries: '+describe(prior.get('EnableAllFolders'),prior.get('EnabledFolders',[]) or [])+' → '+describe(all_folders,selected)
    emby.assign_libraries(user.emby_id,selected,all_folders)
    overrides=__import__('json').loads(row.overrides);overrides.update(EnableAllFolders=all_folders,EnabledFolders=sorted(set(selected)))
    row.overrides=encoded(overrides);recompute(request.state.db,user,row);row.pending=False
    observe(request.state.db,user,emby.user(user.emby_id).get('Policy',{}))
    return redirect('/admin/users/'+str(user.id)+'?saved=libraries')

@router.post('/admin/emby/copy')
def copy_existing(request: Request, data=Depends(form)):
    require_admin(request)
    user = request.state.db.get(User, int(data['id']))
    if not user or not user.emby_id:
        raise HTTPException(404, 'Emby account not found')
    if data.get('acknowledge') != 'on':
        raise ValueError('Confirm replacement of the selected settings.')
    emby.copy_to_existing(data['source_id'], user.emby_id, list(data.getlist('copy_options')))
    sync_users(request.state.db)
    return redirect('/admin/users/'+str(user.id))

@router.get('/admin/integrations')
def integrations(request: Request):
    require_admin(request)
    db = request.state.db
    jobs = list(db.scalars(select(IntegrationJob).order_by(IntegrationJob.updated_at.desc())))
    owners = {user.id: user for user in db.scalars(select(User))}
    from .connection_health import checks
    return render(request,'integrations.html',jobs=jobs,owners=owners,emby_connection_url=config(db,'emby_url'),emby_key_saved=bool(config(db,'emby_api_key')),connection_checks=checks(db))

@router.post('/admin/integrations')
def integrations_save(request: Request, data=Depends(form)):
    require_admin(request)
    service = data['service']
    if service not in SERVICES:
        raise ValueError('Invalid service')
    db = request.state.db
    active = data.get('enabled') == 'on'
    base = url_ok(data.get('url',''), optional=not active)
    if base and ('?' in base or '#' in base):
        raise ValueError('Invalid URL')
    set_config(db, service+'_url', base)
    if data.get('api_key'):
        set_config(db, service+'_api_key', encrypt(data['api_key']))
    if data.get('clear_key') == 'on':
        set_config(db, service+'_api_key', '')
    if active and not config(db, service+'_api_key'):
        raise ValueError('API key required')
    if service == 'seerr':
        mode = str(data.get('notification_mode', config(db,'seerr_notification_mode','unmanaged')))
        if mode not in ('unmanaged','optional','forced'):
            raise ValueError('Invalid notification mode')
        set_config(db,'seerr_notification_mode',mode)
    set_config(db, service+'_enabled', 'true' if active else 'false')
    from .connection_health import invalidate
    invalidate(db,service)
    db.commit()
    queue_all(db, force=True)
    return redirect('/admin/integrations')

@router.post('/admin/integrations/retry')
def retry_integrations(request: Request, data=Depends(form)):
    require_admin(request)
    limit(request, 'integration_retry')
    queue_all(request.state.db, force=True)
    return redirect('/admin/integrations')

@router.post('/admin/connections/emby')
def save_emby_connection(request: Request, data=Depends(form)):
    require_admin(request)
    db=request.state.db
    from .onboarding import connect_media
    connect_media(db,data)
    from .connection_health import invalidate
    invalidate(db,'emby')
    db.commit()
    return redirect('/admin/integrations')

@router.post('/admin/connections/test')
def test_connection(request: Request, data=Depends(form)):
    require_admin(request)
    limit(request,'connection_test',maximum=10)
    service=data.get('service')
    if service not in ('emby',*SERVICES):raise ValueError('Invalid service')
    from .connection_health import checks
    checks(request.state.db,refresh=True)
    return redirect('/admin/integrations')


# Earlier account-label settings were migrated to the single translation center.

@router.post('/admin/users/{local_id}/role')
def user_role(request:Request,local_id:int,data=Depends(form)):
    from sqlalchemy import text,delete,update,func
    from .models import Session,Token
    from .main import log
    actor_id=require_admin(request).id
    db=request.state.db
    db.rollback()
    db.execute(text('BEGIN IMMEDIATE'))
    actor=db.get(User,actor_id)
    if not actor or not actor.admin or not actor.active or not actor.emby_id:
        raise HTTPException(403,'Administrator access required')
    target=db.get(User,local_id)
    if not target or not target.emby_id:raise HTTPException(404,'Media account required')
    request.state.audit_subject=local_id
    request.state.audit_detail='Gatearr administrator: '+str(target.admin)+' → '+str(data.get('admin')=='on')+'\nTools: '+target.tool_access+' → '+str(data.getlist('tools'))
    grant=data.get('admin')=='on'
    if grant and (not target.active or target.emby_missing):raise HTTPException(400,'An active media account is required')
    import json
    tools=sorted(set(data.getlist('tools')))
    if any(t not in ('radarr','sonarr','bazarr') or config(db,t+'_enabled')!='true' for t in tools):raise ValueError('Invalid tool access')
    changed_tools=json.loads(target.tool_access)!=tools
    if target.admin==grant and not changed_tools:return redirect('/admin/users/'+str(local_id))
    target.tool_access=json.dumps(tools)
    if not grant and target.admin:
        count=db.scalar(select(func.count(User.id)).where(User.admin.is_(True),User.active.is_(True),User.emby_missing.is_(False),User.emby_id.is_not(None)))
        if target.active and not target.emby_missing and count<=1:
            raise HTTPException(409,'The last active administrator cannot be removed')
    target.admin=grant
    target.version+=1
    db.execute(delete(Session).where(Session.user_id==target.id))
    db.execute(update(Token).where(Token.user_id==target.id).values(used=True))
    db.commit()
    log.info('Portal role changed actor_id=%s user_id=%s admin=%s',actor_id,target.id,grant)
    return redirect('/login' if actor_id==target.id else '/admin/users/'+str(local_id)+'?saved=role')
