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
    if action in ('invite','reset','email','password'):request.state.audit_action='account.'+action
    if action=='invite':
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
    elif action=='password':
        password_ok(data.get('password',''))
        if data.get('password')!=data.get('confirm'):raise ValueError('Passwords do not match')
        if not user.email:raise ValueError('The user needs an email address')
        if not config(db,'smtp_host'):raise ValueError('Configure SMTP before changing account credentials')
        # Commit notification only after the remote server accepts the password.
        from .main import emby
        emby.password(user.emby_id,data['password'])
        notification(db,user,user.email,'password_changed');db.commit();invalidate(db,user)
    else:raise ValueError('Invalid action')
    return redirect('/admin/users/'+str(uid)+'?saved=account')
