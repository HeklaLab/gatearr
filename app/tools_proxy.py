"""Origin-isolated, authenticated reverse proxy for explicitly configured admin tools.
Only configured upstreams are reachable; no request supplies a target URL or API key.
"""
import json,secrets,time
from urllib.parse import urlsplit,parse_qs
import httpx
from fastapi import APIRouter,Request,Depends,HTTPException
from fastapi.responses import Response,RedirectResponse,StreamingResponse
from sqlalchemy import select,delete,text
from .models import Config,Session,User,ToolGrant,SupportSession
from .db import SessionLocal
from .mailer import config
from .security import url_ok,origin,encrypt,decrypt,digest
from .main import form,require_admin,require_user,redirect,render,limit,set_config
router=APIRouter();TOOLS=('radarr','sonarr','bazarr')
HOP={'connection','keep-alive','proxy-authenticate','proxy-authorization','te','trailer','transfer-encoding','upgrade','host','content-length','cookie','authorization','x-api-key','x-emby-token','forwarded','x-forwarded-for','x-forwarded-host','x-forwarded-proto'}

def allowed_tools(db,user):
    grants=json.loads(user.tool_access) if user else []
    return [key for key in TOOLS if key in grants and config(db,key+'_enabled')=='true']

def configure_tools(request,data):
    require_admin(request);db=request.state.db;prepared={}
    for tool in TOOLS:
        active=data.get(tool+'_enabled')=='on'
        base=url_ok(str(data.get(tool+'_url','')),optional=not active)
        public=url_ok(str(data.get(tool+'_public_url','')),optional=not active)
        key=str(data.get(tool+'_api_key','')).strip() or decrypt(config(db,tool+'_api_key'))
        if active:
            if not key:raise ValueError('API key required')
            if urlsplit(base).path not in ('','/') or urlsplit(base).query or urlsplit(base).fragment:raise ValueError('Tool private URLs must use the domain root; clear the upstream URL Base setting')
            target=urlsplit(public)
            if target.path or target.query or target.fragment or origin(public)==origin(config(db,'public_url')):raise ValueError('Each tool needs a separate public hostname')
            if target.scheme!='https' and target.hostname not in ('localhost','127.0.0.1'):raise ValueError('Public tool URLs require HTTPS')
            if any(data.get(other+'_enabled')=='on' and origin(public)==origin(str(data.get(other+'_public_url',''))) for other in TOOLS if other!=tool):raise ValueError('Each tool needs a separate public hostname')
            path='/api/system/status' if tool=='bazarr' else '/api/v3/system/status'
            try:
                with httpx.Client(timeout=8,trust_env=False,follow_redirects=False) as client:r=client.get(base+path,headers={'X-Api-Key':key});r.raise_for_status();result=r.json()
                if not isinstance(result,dict) or not result:raise ValueError('Invalid connection response')
            except (httpx.HTTPError,ValueError):raise ValueError('Tool connection failed. Check its private URL and API key.')
            if data.get('proxy_acknowledge')!='on':raise ValueError('Confirm the private upstream and proxy authentication setup')
        prepared[tool]={'base':base,'public':public,'key':key,'active':active}
    for tool,v in prepared.items():
        for suffix,value in {'url':v['base'],'public_url':v['public'],'api_key':encrypt(v['key']) if v['key'] else '','enabled':'true' if v['active'] else 'false'}.items():set_config(db,tool+'_'+suffix,value)
    db.execute(delete(ToolGrant));db.commit()

@router.post('/admin/tools')
def save_tools(request:Request,data=Depends(form)):
    configure_tools(request,data);return redirect('/admin/integrations')

@router.get('/tools/{tool}')
def open_tool(request:Request,tool:str):
    user=require_user(request);db=request.state.db
    if tool not in allowed_tools(db,user):raise HTTPException(403,'Tool access denied')
    limit(request,'tool-launch',maximum=30)
    raw=secrets.token_urlsafe(32)
    db.execute(delete(ToolGrant).where(ToolGrant.expires<int(time.time())))
    db.add(ToolGrant(digest=digest(raw),session_digest=request.state.session.digest,user_id=user.id,tool=tool,expires=int(time.time())+60,redeemed=False));db.commit()
    return render(request,'tool.html',tool=tool,tool_public=config(db,tool+'_public_url'),handoff_ticket=raw)

def target_for_host(db,request):
    host=request.headers.get('host','').lower()
    return next((tool for tool in TOOLS if config(db,tool+'_enabled')=='true' and urlsplit(config(db,tool+'_public_url')).netloc.lower()==host),None)

def effective(db,session):
    user=db.get(User,session.user_id) if session else None
    if not user or not user.active or user.emby_missing or user.version!=session.version or session.expires<=int(time.time()):return None
    support=db.get(SupportSession,session.digest)
    if support:
        target=db.get(User,support.target_id)
        if not user.admin or support.expires<=int(time.time()) or not target or not target.active or target.version!=support.target_version:return None
        return target
    return user

def authorize(db,request,tool):
    raw=request.cookies.get('gatearr_tool_session','')
    grant=db.get(ToolGrant,digest(raw)) if raw else None
    if not grant or not grant.redeemed or grant.tool!=tool or grant.expires<=int(time.time()):return None
    session=db.get(Session,grant.session_digest);user=effective(db,session)
    if not user or user.id!=grant.user_id or tool not in allowed_tools(db,user):return None
    return grant

async def bounded_body(request,maximum):
    body=bytearray()
    async for chunk in request.stream():
        if len(body)+len(chunk)>maximum:raise HTTPException(413,'Request too large')
        body.extend(chunk)
    return bytes(body)

async def handle(request,tool):
    with SessionLocal() as db:
        public=config(db,tool+'_public_url');portal=config(db,'public_url')
        if request.url.path=='/gatearr-tool-login':
            if request.method!='POST' or origin(request.headers.get('origin',''))!=origin(portal):return Response('Origin rejected',status_code=403)
            body=await bounded_body(request,2048)
            ticket=parse_qs(body.decode(errors='replace')).get('ticket',[''])[0]
            if len(ticket)!=43:return Response('Invalid ticket',status_code=403)
            db.execute(text('BEGIN IMMEDIATE'));grant=db.get(ToolGrant,digest(ticket))
            if not grant or grant.tool!=tool or grant.redeemed or grant.expires<=int(time.time()):return Response('Ticket expired',status_code=403)
            user=effective(db,db.get(Session,grant.session_digest))
            if not user or user.id!=grant.user_id or tool not in allowed_tools(db,user):return Response('Access revoked',status_code=403)
            # Exchange the one-use ticket for a different host-only cookie.
            db.delete(grant)
            raw=secrets.token_urlsafe(32);db.add(ToolGrant(digest=digest(raw),tool=tool,user_id=user.id,session_digest=grant.session_digest,redeemed=True,expires=min(int(time.time())+43200,db.get(Session,grant.session_digest).expires)));db.commit()
            response=RedirectResponse(public+'/',303)
            response.set_cookie('gatearr_tool_session',raw,httponly=True,secure=urlsplit(public).scheme=='https',samesite='lax',path='/')
            response.headers['Cache-Control']='no-store';return response
        grant=authorize(db,request,tool)
        if not grant:return Response('Open this tool from Gatearr to sign in.',status_code=401,headers={'Cache-Control':'no-store'})
        if request.method not in ('GET','HEAD','OPTIONS') and origin(request.headers.get('origin',''))!=origin(public):return Response('Origin rejected',status_code=403)
        base=config(db,tool+'_url');key=decrypt(config(db,tool+'_api_key'));actor=db.get(Session,grant.session_digest).user_id;subject=grant.user_id
    body=await bounded_body(request,32*1024*1024)
    # Preserve the raw escaped path/query. The fixed upstream cannot be replaced by //host or redirects.
    if request.url.path.startswith('//') or '\\' in request.url.path:return Response('Invalid path',400)
    url=base.rstrip('/')+request.scope['raw_path'].decode('ascii')
    if request.url.query:url+='?'+request.url.query
    headers={k:v for k,v in request.headers.items() if k.lower() not in HOP and not k.lower().startswith(('x-forwarded-','sec-'))}
    headers.update({'X-Api-Key':key,'Accept-Encoding':'identity'})
    client=httpx.AsyncClient(timeout=httpx.Timeout(60,connect=10),trust_env=False,follow_redirects=False)
    try:
        req=client.build_request(request.method,url,headers=headers,content=body)
        upstream=await client.send(req,stream=True)
    except httpx.HTTPError:
        await client.aclose();return Response('Tool unavailable',502)
    output={k:v for k,v in upstream.headers.items() if k.lower() not in HOP|{'set-cookie','content-security-policy','x-frame-options','content-encoding'}}
    location=output.get('location')
    if location:
        parsed=urlsplit(location)
        if parsed.netloc and origin(location)!=origin(base):
            await upstream.aclose();await client.aclose();return Response('External redirect refused',502)
        if parsed.netloc:output['location']=public+parsed.path+('?' + parsed.query if parsed.query else '')
    output.update({'Cache-Control':'no-store','Referrer-Policy':'same-origin','X-Content-Type-Options':'nosniff','Content-Security-Policy':"frame-ancestors "+urlsplit(portal).scheme+"://"+urlsplit(portal).netloc})
    from .audit import record
    record(actor,subject,'tool.'+tool+'.'+request.method,upstream.status_code)
    async def stream():
        try:
            async for chunk in upstream.aiter_bytes():yield chunk
        finally:await upstream.aclose();await client.aclose()
    return StreamingResponse(stream(),status_code=upstream.status_code,headers=output)

async def websocket_proxy(socket):
    import asyncio
    from websockets.asyncio.client import connect
    with SessionLocal() as db:
        tool=target_for_host(db,socket)
        if not tool or origin(socket.headers.get('origin',''))!=origin(config(db,tool+'_public_url')) or not authorize(db,socket,tool):
            await socket.close(code=1008);return
        base=config(db,tool+'_url');key=decrypt(config(db,tool+'_api_key'));public=config(db,tool+'_public_url')
    parsed=urlsplit(base);url=('wss' if parsed.scheme=='https' else 'ws')+'://'+parsed.netloc+parsed.path.rstrip('/')+socket.scope['raw_path'].decode('ascii')
    if socket.url.query:url+='?'+socket.url.query
    if socket.url.path.startswith('//') or '\\' in socket.url.path:await socket.close(code=1008);return
    try:
        async with connect(url,additional_headers={'X-Api-Key':key},origin=public,proxy=None,open_timeout=10,max_size=4*1024*1024) as upstream:
            await socket.accept()
            async def browser():
                while True:
                    message=await socket.receive()
                    if message['type']=='websocket.disconnect':return
                    await upstream.send(message.get('text') if message.get('text') is not None else message['bytes'])
            async def remote():
                async for message in upstream:
                    if isinstance(message,str):await socket.send_text(message)
                    else:await socket.send_bytes(message)
            async def guard():
                while True:
                    await asyncio.sleep(15)
                    with SessionLocal() as db:
                        if not authorize(db,socket,tool):return
            tasks=[asyncio.create_task(fn()) for fn in (browser,remote,guard)]
            try:await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
    except Exception:
        pass # Remote details may contain keys; audit only the service and result.
    finally:
        try:await socket.close()
        except RuntimeError:pass
