"""Session-protected, path-based reverse proxy for explicitly configured admin tools.
Only configured upstreams are reachable; no request supplies a target URL or API key.
"""
import json,time
from urllib.parse import urlsplit,urljoin,unquote
import httpx
from fastapi import APIRouter,Request,Depends,HTTPException
from fastapi.responses import Response,RedirectResponse,StreamingResponse
from sqlalchemy import delete
from .models import Session,User,ToolGrant,SupportSession
from .db import SessionLocal
from .mailer import config
from .security import url_ok,origin,encrypt,decrypt,digest
from .main import form,require_admin,require_user,redirect,render,set_config
router=APIRouter();PROXY_TOOLS=('radarr','sonarr','bazarr','tdarr');TOOLS=(*PROXY_TOOLS,'tracearr')
HOP={'connection','keep-alive','proxy-authenticate','proxy-authorization','te','trailer','transfer-encoding','upgrade','host','content-length','cookie','authorization','x-api-key','x-emby-token','forwarded','x-forwarded-for','x-forwarded-host','x-forwarded-proto'}


def tdarr_headers(incoming):
    """Only the native credentials scoped by this proxy may reach Tdarr."""
    from http.cookies import SimpleCookie
    result={}
    if incoming.get('authorization'):result['authorization']=incoming['authorization']
    cookies=SimpleCookie();cookies.load(incoming.get('cookie',''))
    namespace='gatearr_tdarr_native_'
    native='; '.join(name[len(namespace):]+'='+m.coded_value for name,m in cookies.items() if name.startswith(namespace) and len(name)>len(namespace))
    if native:result['cookie']=native
    return result


def allowed_tools(db,user):
    if not user:return []
    grants=json.loads(user.tool_access) if user else []
    return [key for key in TOOLS if key in grants and config(db,key+'_enabled')=='true' and (key not in ('tracearr','tdarr') or config(db,key+'_interface_enabled','true')=='true') and (key not in ('tracearr','tdarr') or user.admin)]

def configure_tools(request,data):
    require_admin(request);db=request.state.db;prepared={}
    for tool in ('radarr','sonarr','bazarr'):
        active=data.get(tool+'_enabled')=='on'
        entered=str(data.get(tool+'_url','')).strip()
        if not active:
            # An unused/partially filled optional service must not block another connection.
            prepared[tool]={'base':config(db,tool+'_url'),'key':decrypt(config(db,tool+'_api_key')),'active':False}
            continue
        title=tool.capitalize()
        try:base=url_ok(entered)
        except ValueError:raise HTTPException(400,title+': enter a complete private HTTP(S) URL, for example http://192.168.0.5:7878')
        parsed=urlsplit(base)
        if parsed.query or parsed.fragment or parsed.path.rstrip('/') not in ('',prefix(tool)):
            raise HTTPException(400,title+': use the private server root URL or its /tools/'+tool+'/app path, without query parameters')
        base=parsed.scheme+'://'+parsed.netloc
        key=str(data.get(tool+'_api_key','')).strip() or decrypt(config(db,tool+'_api_key'))
        if not key:raise HTTPException(400,title+': enter the API key')
        path='/api/system/status' if tool=='bazarr' else '/api/v3/system/status'
        try:
            with httpx.Client(timeout=8,trust_env=False,follow_redirects=False) as client:
                response=client.get(base+prefix(tool)+path,headers={'X-Api-Key':key})
                if response.status_code in (401,403):raise HTTPException(400,title+': API key rejected (HTTP '+str(response.status_code)+'). Check the key in the native application.')
                if response.status_code>=400:raise ValueError()
                result=response.json()
                if not isinstance(result,dict) or not result:raise ValueError()
        except httpx.RequestError:raise HTTPException(400,title+': server unreachable from Gatearr. Check its private address, port and firewall.')
        except ValueError:
            # Distinguish a working root API from a missing native URL Base.
            try:
                with httpx.Client(timeout=8,trust_env=False,follow_redirects=False) as client:
                    root=client.get(base+path,headers={'X-Api-Key':key})
                    reachable=root.status_code==200 and isinstance(root.json(),dict)
            except (httpx.HTTPError,ValueError):reachable=False
            if reachable:raise HTTPException(400,title+': server and API key are valid. Set URL Base in the native application to '+prefix(tool)+', restart it, then verify again.')
            raise HTTPException(400,title+': connection check failed (HTTP '+str(response.status_code)+'). Check the API key and native URL Base '+prefix(tool)+'.')
        if data.get('proxy_acknowledge')!='on':raise HTTPException(400,'Confirm the private upstream and proxy authentication setup')
        prepared[tool]={'base':base,'key':key,'active':active}
    for tool,v in prepared.items():
        for suffix,value in {'url':v['base'],'api_key':encrypt(v['key']) if v['key'] else '','enabled':'true' if v['active'] else 'false'}.items():set_config(db,tool+'_'+suffix,value)
    from .connection_health import invalidate
    for tool in TOOLS:invalidate(db,tool)
    db.execute(delete(ToolGrant));db.commit()

@router.post('/admin/tools')
def save_tools(request:Request,data=Depends(form)):
    configure_tools(request,data);return redirect('/admin/integrations')

@router.get('/tools/{tool}')
def open_tool(request:Request,tool:str):
    user=require_user(request);db=request.state.db
    if tool not in allowed_tools(db,user):raise HTTPException(403,'Tool access denied')
    external=config(db,tool+'_public_url') if tool=='tracearr' else ''
    if tool=='tracearr' and not external:raise HTTPException(409,'Configure the public interface address first')
    return render(request,'tool.html',tool=tool,tool_external=external)

def prefix(tool):return '/tools/'+tool+'/app'+('/tdarr' if tool=='tdarr' else '')

def target_for_host(db,request):
    # Kept as an internal dispatch name for compatibility; hostnames never select a tool.
    path=request.url.path
    return next((tool for tool in PROXY_TOOLS if path==prefix(tool) or path.startswith(prefix(tool)+'/')),None)

def effective(db,session):
    user=db.get(User,session.user_id) if session else None
    if not user or not user.active or user.emby_missing or user.version!=session.version or session.expires<=int(time.time()):return None
    support=db.get(SupportSession,session.digest)
    if support:
        target=db.get(User,support.target_id)
        if not user.admin or support.expires<=int(time.time()) or not target or not target.active or target.emby_missing or target.version!=support.target_version:return None
        return target
    return user

def authorize(db,request,tool):
    raw=request.cookies.get('gatearr_session','')
    session=db.get(Session,digest(raw)) if raw else None
    # A native admin UI cannot be made read-only by Gatearr's assistance mode.
    if session and db.get(SupportSession,session.digest):return None
    user=effective(db,session)
    if not user or tool not in allowed_tools(db,user):return None
    from .main import emby,invalidate
    from .emby import EmbyError
    # Proxy requests bypass the portal middleware; enforce native revocation here too.
    try:remote=emby.user(user.emby_id)
    except EmbyError:return None
    if remote.get('Policy',{}).get('IsDisabled') or remote.get('HasPassword') is False:
        user.active=False;invalidate(db,user);return None
    return type('ProxyAccess',(),{'session_digest':session.digest,'user_id':user.id})()

async def bounded_body(request,maximum):
    body=bytearray()
    async for chunk in request.stream():
        if len(body)+len(chunk)>maximum:raise HTTPException(413,'Request too large')
        body.extend(chunk)
    return bytes(body)

def safe_path(request,tool):
    # Reject ambiguous encodings before any upstream receives its injected API key.
    try:path=request.scope['raw_path'].decode('ascii')
    except (UnicodeError,KeyError):return False
    for _ in range(8):
        if not (path==prefix(tool) or path.startswith(prefix(tool)+'/')):return False
        if '\\' in path or any(ord(c)<32 or ord(c)==127 for c in path):return False
        if any(part in ('.','..') for part in path.split('/')):return False
        decoded=unquote(path)
        if decoded==path:return True
        path=decoded
    return False

async def handle(request,tool):
    with SessionLocal() as db:
        portal=config(db,'public_url');public=portal.rstrip('/')+prefix(tool)
        grant=authorize(db,request,tool)
        if not grant:return Response('Open this tool from Gatearr to sign in.',status_code=401,headers={'Cache-Control':'no-store'})
        if request.method not in ('GET','HEAD','OPTIONS') and origin(request.headers.get('origin',''))!=origin(portal):return Response('Origin rejected',status_code=403)
        base=config(db,tool+'_url');key=decrypt(config(db,tool+'_api_key'));actor=db.get(Session,grant.session_digest).user_id;subject=grant.user_id
    body=await bounded_body(request,32*1024*1024)
    # Preserve the raw escaped path/query. The fixed upstream cannot be replaced by //host or redirects.
    if not safe_path(request,tool):return Response('Invalid path',400)
    upstream_path=request.scope['raw_path'].decode('ascii')
    if tool=='tdarr':upstream_path=upstream_path[len(prefix(tool)):] or '/'
    url=base.rstrip('/')+upstream_path
    if request.url.query:url+='?'+request.url.query
    headers={k:v for k,v in request.headers.items() if k.lower() not in HOP and not k.lower().startswith(('x-forwarded-','sec-'))}
    # Replace the lowercase browser header: mixed-case duplicates are combined by HTTPX.
    headers['accept-encoding']='identity'
    if tool!='tdarr':headers['X-Api-Key']=key
    else:headers.update(tdarr_headers(request.headers))
    client=httpx.AsyncClient(timeout=httpx.Timeout(60,connect=10),trust_env=False,follow_redirects=False)
    try:
        req=client.build_request(request.method,url,headers=headers,content=body)
        upstream=await client.send(req,stream=True)
    except httpx.HTTPError:
        await client.aclose();return Response('Tool unavailable',502)
    output={k:v for k,v in upstream.headers.items() if k.lower() not in HOP|{'set-cookie','content-security-policy','x-frame-options'}}
    native_cookies=[]
    if tool=='tdarr':
        from http.cookies import SimpleCookie
        for raw in upstream.headers.get_list('set-cookie'):
            cookies=SimpleCookie();cookies.load(raw)
            for name,morsel in cookies.items():
                if name.startswith('gatearr_'):continue
                scoped=SimpleCookie();scoped['gatearr_tdarr_native_'+name]=morsel.value
                local=scoped['gatearr_tdarr_native_'+name]
                for attr in ('expires','max-age','secure','httponly','samesite'):
                    if morsel[attr]:local[attr]=morsel[attr]
                local['path']=prefix(tool)+'/'
                if portal.startswith('https://'):local['secure']=True
                native_cookies.append(local.OutputString())
    def with_cookies(response):
        for cookie in native_cookies:response.headers.append('set-cookie',cookie)
        return response
    location=output.get('location')
    if location:
        parsed=urlsplit(urljoin(str(upstream.request.url),location))
        root=parsed.scheme+'://'+parsed.netloc
        if origin(root)!=origin(base) or (tool!='tdarr' and not (parsed.path==prefix(tool) or parsed.path.startswith(prefix(tool)+'/'))):
            await upstream.aclose();await client.aclose();return Response('External redirect refused or upstream URL Base is incorrect',502)
        output['location']=portal.rstrip('/')+(prefix(tool) if tool=='tdarr' else '')+parsed.path+('?' + parsed.query if parsed.query else '')
    output.update({'Cache-Control':'no-store','Referrer-Policy':'same-origin','X-Content-Type-Options':'nosniff','Content-Security-Policy':"frame-ancestors "+"'self'"})
    from .audit import record
    record(actor,subject,'tool.'+tool+'.'+request.method,upstream.status_code)
    content_type=upstream.headers.get('content-type','')
    if tool=='tdarr' and any(kind in content_type for kind in ('text/html','text/css')) and request.method=='GET':
        import re
        raw=bytearray()
        try:
            async for chunk in upstream.aiter_bytes():
                raw.extend(chunk)
                if len(raw)>4*1024*1024:return Response('Tdarr page is too large',502)
            html=raw.decode('utf-8')
            base_path=prefix(tool)+'/'
            if 'text/css' in content_type:
                html=re.sub(r'(url\(\s*[\"\']?)/(?!/|tools/tdarr/app/)',lambda m:m[1]+base_path,html,flags=re.I)
                html=re.sub(r'(@import\s+[\"\'])/(?!/|tools/tdarr/app/)',lambda m:m[1]+base_path,html,flags=re.I)
            else:
                html=re.sub(r'<base\b[^>]*>','',html,flags=re.I)
                html=re.sub(r'((?:src|href|action)=[\"\'])/(?!/|tools/tdarr/app/)',lambda m:m[1]+base_path,html,flags=re.I)
                # Execute before native bundles, without rewriting their JavaScript.
                bridge='<base href="'+base_path+'"><script src="/static/tdarr-proxy.js" data-proxy-base="'+base_path+'"></script>'
                html,inserted=re.subn(r'(<head[^>]*>)',lambda m:m[0]+bridge,html,count=1,flags=re.I)
                if not inserted:html=bridge+html
            output.pop('content-length',None);output.pop('content-encoding',None)
            return with_cookies(Response(html,status_code=upstream.status_code,headers=output))
        finally:await upstream.aclose();await client.aclose()

    async def stream():
        try:
            # Forward wire bytes and Content-Encoding together, including formats
            # HTTPX cannot decode (e.g. Brotli or Zstandard without optional extras).
            async for chunk in upstream.aiter_raw():yield chunk
        finally:await upstream.aclose();await client.aclose()
    return with_cookies(StreamingResponse(stream(),status_code=upstream.status_code,headers=output))

async def websocket_proxy(socket):
    import asyncio
    from websockets.asyncio.client import connect
    with SessionLocal() as db:
        tool=target_for_host(db,socket)
        if not tool or origin(socket.headers.get('origin',''))!=origin(config(db,'public_url')) or not authorize(db,socket,tool):
            await socket.close(code=1008);return
        base=config(db,tool+'_url');key=decrypt(config(db,tool+'_api_key'));public=config(db,'public_url')
    parsed=urlsplit(base);path=socket.scope['raw_path'].decode('ascii')
    if tool=='tdarr':path=path[len(prefix(tool)):] or '/'
    url=('wss' if parsed.scheme=='https' else 'ws')+'://'+parsed.netloc+parsed.path.rstrip('/')+path
    if socket.url.query:url+='?'+socket.url.query
    if not safe_path(socket,tool):await socket.close(code=1008);return
    try:
        async with connect(url,additional_headers={'X-Api-Key':key} if tool!='tdarr' else tdarr_headers(socket.headers),origin=public,proxy=None,open_timeout=10,max_size=4*1024*1024) as upstream:
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


def editable_tools(db):
    from .connection_health import configured
    return {tool for tool in TOOLS if configured(db,tool) and (tool not in ('tracearr','tdarr') or config(db,tool+'_interface_enabled','true')=='true')}


def retained_tools(db,previous,submitted):
    available=editable_tools(db);previous=set(previous);submitted=set(submitted)
    if submitted-available-previous:raise ValueError('Configure this tool in Applications & API before granting access')
    return sorted((submitted&available)|(previous-available))
