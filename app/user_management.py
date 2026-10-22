"""Explicit administrative account changes with encrypted notification outbox."""
import json,time
from fastapi import APIRouter,Request,Depends,HTTPException
from sqlalchemy import select
from .models import User,MailJob
from .security import email_ok,password_ok,encrypt
from .mailer import config
from .main import require_admin,form,redirect,issue_token,enqueue_mail,invalidate,limit
from .integrations import queue_user
router=APIRouter()

def notification(db,user,recipient,purpose):
    if not recipient:return
    if not config(db,'smtp_host'):raise ValueError('Configure SMTP before changing account credentials')
    values={'app_name':config(db,'app_name','Gatearr'),'username':user.name,'link':config(db,'public_url'),'minutes':'30','_locale':user.locale}
    db.add(MailJob(payload=encrypt(json.dumps({'notification':True,'purpose':purpose,'recipient':recipient,'values':values})),attempts=0,next_attempt=int(time.time()),expires=int(time.time())+86400))

@router.post('/admin/users/{uid}/account')
def manage(request:Request,uid:int,data=Depends(form)):
    require_admin(request);db=request.state.db;user=db.get(User,uid)
    if not user or not user.emby_id or not user.active:raise HTTPException(404,'Active media account not found')
    limit(request,'manage-account',str(uid),maximum=10)
    action=data.get('action')
    request.state.audit_subject=uid
    if action in ('invite','reset','email','password','username'):request.state.audit_action='account.'+action
    if action=='username':
        from .main import emby
        from . import usernames
        name=str(data.get('name','')).strip()
        if not name or len(name)>100 or any(ord(c)<32 or ord(c)==127 for c in name):raise ValueError('Invalid name')
        if any(remote['Id']!=user.emby_id and remote.get('Name','').casefold()==name.casefold() for remote in emby.users()):raise ValueError('Username already in use')
        previous=user.name
        emby.rename(user.emby_id,name)
        user.name=name;db.commit()
        usernames.enqueue(db,user);usernames.apply(db,user)
        request.state.audit_detail='Username: '+previous+' → '+name
        invalidate(db,user)
        if request.state.user.id==uid:return redirect('/login')
    elif action=='invite':
        raw=issue_token(db,user,'verify',email_ok(data['email']));enqueue_mail(db,'invite',raw,email_ok(data['email']))
    elif action=='reset':
        if not user.email:raise ValueError('The user needs an email address')
        raw=issue_token(db,user,'reset');enqueue_mail(db,'reset',raw,user.email)
    elif action=='email':
        email=email_ok(data['email'])
        if db.scalar(select(User.id).where(User.email==email,User.id!=uid)):raise ValueError('Email address already in use')
        if not config(db,'smtp_host'):raise ValueError('Configure SMTP before changing account credentials')
        old=user.email
        for recipient in set(filter(None,(old,email))):notification(db,user,recipient,'email_changed')
        user.email=email;user.preferences_version+=1
        db.commit();invalidate(db,user);queue_user(db,user,force=True)
        if request.state.user.id==uid:return redirect('/login')
    elif action=='password':
        password_ok(data.get('password',''),db)
        if data.get('password')!=data.get('confirm'):raise ValueError('Passwords do not match')
        if not user.email:raise ValueError('The user needs an email address')
        if not config(db,'smtp_host'):raise ValueError('Configure SMTP before changing account credentials')
        # Commit notification only after the remote server accepts the password.
        from .main import emby
        emby.password(user.emby_id,data['password'])
        notification(db,user,user.email,'password_changed');db.commit();invalidate(db,user)
    else:raise ValueError('Invalid action')
    return redirect('/admin/users/'+str(uid)+'?saved=account')

@router.post('/admin/users/{uid}/activation')
def activation(request:Request,uid:int,data=Depends(form)):
    from sqlalchemy import func,update
    from .models import Token
    from .seerr_permissions import configured,connection
    from .integrations import request as remote_request,SyncError
    from .main import emby
    import secrets,httpx
    actor=require_admin(request);db=request.state.db;user=db.get(User,uid)
    if not user or not user.emby_id:raise HTTPException(404,'Media account not found')
    if data.get('confirm')!='on':raise ValueError('Confirm this account security change')
    if int(data.get('version','-1'))!=user.version:raise HTTPException(409,'Account changed. Reload the page.')
    limit(request,'account-activation',str(uid),maximum=10)
    request.state.audit_subject=uid
    if data.get('action')=='enable':
        if not user.portal_disabled:raise HTTPException(409,'The account is not disabled in Gatearr')
        if set(json.loads(user.disable_status))!={'emby','seerr'} or any(value not in ('changed','not configured','not imported') for value in json.loads(user.disable_status).values()):
            raise HTTPException(409,'Finish the password rotation before reactivating this account')
        remote=emby.user(user.emby_id)
        if remote.get('Policy',{}).get('IsDisabled'):raise HTTPException(409,'Enable the account in the media server first')
        user.portal_disabled=False;user.active=True;user.version+=1;db.commit()
        request.state.audit_action='account.reactivate'
        return redirect('/admin/users/'+str(uid)+'?saved=reactivated')
    if data.get('action')!='disable':raise ValueError('Invalid action')
    if user.id==actor.id:raise HTTPException(409,'You cannot deactivate your own account')
    if user.admin and user.active and db.scalar(select(func.count(User.id)).where(User.admin.is_(True),User.active.is_(True),User.emby_missing.is_(False)))<=1:raise HTTPException(409,'The last active administrator cannot be deactivated')
    # Fail closed locally before making either remote request. Sync/import must not undo this flag.
    status=json.loads(user.disable_status) if user.portal_disabled else {}
    status={key:status.get(key,"pending") for key in ("emby","seerr")}
    user.disable_status=json.dumps(status)
    user.portal_disabled=True;user.active=False;user.version+=1
    db.execute(update(Token).where(Token.user_id==uid).values(used=True))
    # Remove support/automatic-login sessions through the regular invalidation path.
    db.commit();invalidate(db,user)
    status=json.loads(user.disable_status)
    for service in ('emby','seerr'):
        if status.get(service)=='changed':continue
        random_password=secrets.token_urlsafe(96)+'Aa1!'
        try:
            if service=='emby':emby.password(user.emby_id,random_password)
            elif not configured(db):status[service]='not configured';continue
            else:
                with connection(db,user) as (client,rid):remote_request(client,'POST',f'api/v1/user/{rid}/settings/password',json={'newPassword':random_password})
            status[service]='changed'
        except (SyncError,httpx.HTTPError) as error:
            status[service]='not imported' if isinstance(error,SyncError) and error.code=='not_found' else 'failed — retry required'
        except Exception:
            status[service]='failed — retry required'
        finally:
            random_password=None
            user.disable_status=json.dumps(status);db.commit()
    request.state.audit_action='account.deactivate'
    request.state.audit_detail='Account disabled; Gatearr recovery blocked; password rotation: '+json.dumps(status)
    return redirect('/admin/users/'+str(uid)+'?saved=deactivated')
