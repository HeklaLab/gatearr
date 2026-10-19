"""Opt-in session handoff on Seerr's own origin. Passwords are never retained."""
import json,logging,re,secrets,time
from urllib.parse import urlsplit,unquote
import httpx
from fastapi import APIRouter,Request,Depends,HTTPException
from fastapi.responses import RedirectResponse,PlainTextResponse
from sqlalchemy import select,delete
from .models import User,Session,SeerrSession,SeerrTicket,AccessService
from .db import SessionLocal
from .security import encrypt,decrypt,digest,url_ok
from .mailer import config
from .integrations import normalized_id
from .main import form,require_user,require_admin,render,redirect,set_config,limit
router=APIRouter();log=logging.getLogger('gatearr.seerr-login')

def public_url(db):
    value=config(db,'seerr_public_url')
    if not value:
        service=db.get(AccessService,'seerr');value=service.browser_url if service else ''
    return value

def enabled(db):return config(db,'seerr_portal_login')=='true' and config(db,'seerr_enabled')=='true' and bool(public_url(db))

def client(db,cookies=None):
    return httpx.Client(base_url=config(db,'seerr_url').rstrip('/')+'/',cookies=cookies,headers={'Origin':public_url(db)},timeout=8,trust_env=False,follow_redirects=False)

def csrf_headers(c):
    allowed={'_csrf','XSRF-TOKEN','connect.sid'}
    cookies={name:value for name,value in c.cookies.items() if name in allowed and not re.search(r'[\r\n;]',value)}
    headers={'Cookie':'; '.join(name+'='+value for name,value in cookies.items())}
    if cookies.get('XSRF-TOKEN'):headers['X-XSRF-TOKEN']=unquote(cookies['XSRF-TOKEN'])
    return headers

def capture(db,user,password,session_digest):
    if not enabled(db):return
    try:
        with client(db) as c:
            remote=c.get('api/v1/user/jellyfin/'+user.emby_id,headers={'X-Api-Key':decrypt(config(db,'seerr_api_key'))});remote.raise_for_status();account=remote.json()
            if not account.get('id') or normalized_id(account.get('jellyfinUserId',''))!=normalized_id(user.emby_id):raise ValueError('identity')
            c.get('api/v1/auth/me')
            auth=c.post('api/v1/auth/jellyfin',headers=csrf_headers(c),json={'username':user.name,'password':password});auth.raise_for_status()
            if auth.json().get('id')!=account['id']:raise ValueError('identity')
            verified=c.get('api/v1/auth/me',headers=csrf_headers(c));verified.raise_for_status()
            if verified.json().get('id')!=account['id']:raise ValueError('identity')
            cookie=c.cookies.get('connect.sid')
            if not cookie or len(cookie)>4096 or re.search(r'[\r\n;]',cookie):raise ValueError('cookie')
            session=db.get(Session,session_digest)
            db.merge(SeerrSession(session_digest=session_digest,user_id=user.id,payload=encrypt(json.dumps({'cookie':cookie,'remote_id':account['id'],'origin':public_url(db),'api':config(db,'seerr_url')})),expires=min(session.expires,int(time.time())+43200)))
            db.commit()
        log.info('Seerr login prepared user_id=%s',user.id)
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        log.warning('Seerr login unavailable user_id=%s',user.id)

def revoke(db,session_digest):
    row=db.get(SeerrSession,session_digest)
    if not row:return
    try:
        payload=json.loads(decrypt(row.payload))
        if payload['api']==config(db,'seerr_url'):
            with client(db,{'connect.sid':payload['cookie']}) as c:
                c.get('api/v1/auth/me',headers=csrf_headers(c))
                c.post('api/v1/auth/logout',headers=csrf_headers(c))
    except (httpx.HTTPError,ValueError,KeyError):pass
    db.delete(row);db.commit()

@router.get('/services/seerr/open')
def launch(request:Request):
    user=require_user(request);db=request.state.db
    if not enabled(db):
        url=public_url(db)
        if not url:raise HTTPException(404,'Configure the public Seerr URL in API connections')
        return redirect(url)
    limit(request,'seerr-launch',maximum=20)
    row=db.get(SeerrSession,request.state.session.digest)
    if not row or row.expires<=int(time.time()):
        return render(request,'message.html',message='Sign out and sign in to Gatearr again to prepare automatic Seerr login.')
    from .emby import emby
    if emby.user(user.emby_id).get('Policy',{}).get('IsDisabled'):raise HTTPException(403,'Account disabled')
    ticket=secrets.token_urlsafe(32)
    db.execute(delete(SeerrTicket).where(SeerrTicket.expires<int(time.time())))
    db.add(SeerrTicket(digest=digest(ticket),session_digest=row.session_digest,expires=int(time.time())+60));db.commit()
    return render(request,'seerr_handoff.html',handoff_url=public_url(db)+'/gatearr-login',handoff_ticket=ticket)

@router.post('/gatearr-login')
async def redeem(request:Request):
    # A top-level POST from Gatearr is the only accepted cross-origin operation.
    body=bytearray()
    async for chunk in request.stream():
        if len(body)+len(chunk)>2048:return PlainTextResponse('Invalid handoff',status_code=400)
        body.extend(chunk)
    from urllib.parse import parse_qs
    raw=parse_qs(body.decode(errors='replace')).get('ticket',[''])[0]
    if not re.fullmatch(r'[A-Za-z0-9_-]{40,100}',raw):return PlainTextResponse('Invalid handoff',status_code=403)
    with SessionLocal() as db:
        public=public_url(db)
        if not enabled(db):return PlainTextResponse('Login bridge disabled',status_code=403)
        source=urlsplit(config(db,'public_url'))
        origin=source.scheme+'://'+source.netloc
        target=urlsplit(public)
        from .security import origin as canonical_origin
        if canonical_origin(request.headers.get('origin',''))!=canonical_origin(origin) or canonical_origin(target.scheme+'://'+request.headers.get('host',''))!=canonical_origin(public):return PlainTextResponse('Invalid origin',status_code=403)
        db.execute(__import__('sqlalchemy').text('BEGIN IMMEDIATE'))
        ticket=db.get(SeerrTicket,digest(raw));now=int(time.time())
        if not ticket or ticket.expires<=now:return PlainTextResponse('Expired handoff',status_code=403)
        row=db.get(SeerrSession,ticket.session_digest);session=db.get(Session,ticket.session_digest)
        user=db.get(User,row.user_id) if row else None
        if not row or not session or not user or not user.active or user.emby_missing or session.version!=user.version or min(row.expires,session.expires)<=now:return PlainTextResponse('Session expired',status_code=403)
        payload=json.loads(decrypt(row.payload))
        if payload['origin']!=public or payload['api']!=config(db,'seerr_url'):return PlainTextResponse('Connection changed',status_code=403)
        db.delete(ticket);db.commit()
    response=RedirectResponse(public+'/',status_code=303)
    response.set_cookie('connect.sid',payload['cookie'],max_age=max(0,min(row.expires,session.expires)-now),httponly=True,secure=target.scheme=='https',samesite='lax',path='/')
    response.headers.update({'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'"})
    return response

@router.post('/admin/seerr-login')
def settings(request:Request,data=Depends(form)):
    require_admin(request);db=request.state.db;active=data.get('enabled')=='on'
    public=url_ok(str(data.get('public_url','')),optional=not active)
    if public:
        parsed=urlsplit(public)
        if parsed.path or parsed.query or parsed.fragment:raise ValueError('The public URL must be at the domain root')
        if parsed.scheme!='https' and parsed.hostname not in ('localhost','127.0.0.1'):raise ValueError('Automatic Seerr login requires HTTPS')
    if active and (not config(db,'seerr_api_key') or not config(db,'seerr_url')):raise ValueError('Configure the Seerr API first')
    set_config(db,'seerr_public_url',public);set_config(db,'seerr_portal_login','true' if active else 'false');db.execute(delete(SeerrSession));db.commit()
    service=db.get(AccessService,'seerr')
    if service and not service.browser_url:service.browser_url=public;db.commit()
    return redirect('/admin/integrations')
