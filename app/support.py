"""Audited administrator assistance using a live, identity-matched member session."""
import json,secrets,time
from urllib.parse import urlencode
from fastapi import APIRouter,Request,Depends,HTTPException
from sqlalchemy import select,delete
from .models import User,Session,MediaSession,SupportSession,SeerrSession,ToolGrant
from .security import encrypt,decrypt
from .main import require_admin,require_user,form,redirect,render,limit
from .mailer import config
router=APIRouter()

def capture(db,user,result,session_digest):
    token=result.get('AccessToken');server=result.get('ServerId') or result.get('User',{}).get('ServerId') or config(db,'media_server_id')
    if not token or not server:return
    session=db.get(Session,session_digest)
    db.merge(MediaSession(session_digest=session_digest,user_id=user.id,payload=encrypt(json.dumps({'token':token,'server':server,'url':config(db,'emby_url')})),expires=session.expires));db.commit()

def source_digest(request):
    support=getattr(request.state,'support',None)
    return support.source_digest if support else request.state.session.digest

def resolve(db,session,actor):
    row=db.get(SupportSession,session.digest)
    if not row:return None,None
    target=db.get(User,row.target_id)
    if not actor or not actor.admin or not target or not target.active or target.emby_missing or target.version!=row.target_version or row.expires<=int(time.time()):
        db.delete(row);db.commit();return None,None
    return row,target

@router.post('/admin/users/{uid}/assist')
def start(request:Request,uid:int,data=Depends(form)):
    actor=require_admin(request);db=request.state.db;target=db.get(User,uid)
    if not target or not target.active or target.emby_missing or not target.emby_id:raise HTTPException(400,'An active media account is required')
    if target.id==actor.id:return redirect('/home')
    limit(request,'assistance',str(uid),maximum=20)
    live=db.scalar(select(Session).where(Session.user_id==uid,Session.version==target.version,Session.expires>int(time.time())).order_by(Session.expires.desc()))
    db.merge(SupportSession(session_digest=request.state.session.digest,source_digest=live.digest if live else request.state.session.digest,target_id=uid,target_version=target.version,expires=min(request.state.session.expires,int(time.time())+1800)));db.commit()
    from .audit import record
    record(actor.id,uid,'assistance.start',200)
    return redirect('/home')

@router.post('/support/stop')
def stop(request:Request,data=Depends(form)):
    db=request.state.db;row=db.get(SupportSession,request.state.session.digest)
    if row:
        from .audit import record
        record(request.state.actor.id,row.target_id,'assistance.stop',200)
        db.delete(row);db.execute(delete(ToolGrant).where(ToolGrant.session_digest==request.state.session.digest));db.commit()
    return redirect('/home')

@router.get('/services/emby/open')
def open_media(request:Request):
    user=require_user(request);db=request.state.db
    row=db.get(MediaSession,source_digest(request));session=db.get(Session,row.session_digest) if row else None
    if not row or row.user_id!=user.id or row.expires<=int(time.time()) or not session or session.version!=user.version or session.expires<=int(time.time()):
        return render(request,'message.html',message='Automatic login unavailable. This user must sign in to Gatearr again.')
    value=json.loads(decrypt(row.payload))
    if value.get('url')!=config(db,'emby_url'):raise HTTPException(403,'Connection changed')
    from .emby import emby
    verified=emby.request('GET','/Users/'+user.emby_id,token=value['token'])
    if verified.get('Id')!=user.emby_id or verified.get('Policy',{}).get('IsDisabled'):raise HTTPException(403,'Media session expired')
    base=config(db,'emby_link')
    if not base:raise HTTPException(400,'Configure the public media URL')
    from .connections import media_kind
    if media_kind(db)=='jellyfin':
        return render(request,'message.html',message='Automatic browser login is not supported by this Jellyfin web client. Open the media service and sign in.')
    base=base.rstrip('/')
    page=base if base.endswith('/web/index.html') else base+'/index.html' if base.endswith('/web') else base+'/web/index.html'
    url=page+'?'+urlencode({'serverId':value['server'],'userId':user.emby_id,'accessToken':value['token'],'e':'1'})
    response=redirect(url);response.headers['Referrer-Policy']='no-referrer';return response


def revoke(db,session_digest):
    row=db.get(MediaSession,session_digest)
    if not row:return
    try:
        payload=json.loads(decrypt(row.payload))
        if payload.get('url')==config(db,'emby_url'):
            from .main import emby
            emby.request('POST','/Sessions/Logout',token=payload['token'])
    except Exception:pass
    db.delete(row);db.commit()
