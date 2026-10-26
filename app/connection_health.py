"""Read-only, authenticated probes. Store only safe diagnostics, never remote bodies."""
import time,json,socket,ssl,smtplib
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor
import httpx
from sqlalchemy import select
from .db import SessionLocal
from .models import ConnectionCheck,Config
from sqlalchemy.dialects.sqlite import insert
from .mailer import config
from .security import decrypt
from .connections import emby_connection,media_kind


def configured(db,service):
    if service=='emby':return bool(config(db,'emby_url') and config(db,'emby_api_key'))
    return config(db,service+'_enabled')=='true' and bool(config(db,service+'_url') and (service=='tdarr' or config(db,service+'_api_key')))


def probe(service,values):
    base,key=values['url'],values['key']
    if service=='tdarr':
        from .connections import tdarr_upstream_url
        base=tdarr_upstream_url(base)
    diagnostics=values.setdefault('diagnostics',{});diagnostics.update(host=urlsplit(base).hostname,reachable=False,api_valid=False,tls=urlsplit(base).scheme=='https');started=time.perf_counter()
    try:diagnostics['resolved_ips']=sorted({item[4][0] for item in socket.getaddrinfo(diagnostics['host'],None,type=socket.SOCK_STREAM)})[:4]
    except OSError:diagnostics['resolved_ips']=[]
    import ipaddress
    diagnostics['ip_types']={ip:('Private network' if ipaddress.ip_address(ip).is_private else 'Public network') for ip in diagnostics['resolved_ips']}
    headers={'X-Emby-Token':key} if service=='emby' else {'X-Api-Key':key}
    if service=='emby' and values['kind']=='jellyfin':headers={'Authorization':'MediaBrowser Client="Gatearr", Device="Portal", DeviceId="gatearr-portal", Version="1.0", Token="'+key+'"'}
    if service=='tracearr':headers={'Authorization':'Bearer '+key}
    path='/System/Info' if service=='emby' else '/api/v1/user?take=1&skip=0' if service=='seerr' else '/tools/'+service+'/app'+('/api/system/status' if service=='bazarr' else '/api/v3/system/status')
    if service=='tracearr':path='/api/v2/public/servers'
    if service=='tdarr':path='/';headers={}
    try:
        # Independent unauthenticated HTTP probe, then the authenticated API probe.
        server_started=time.perf_counter()
        try:
            with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as server_client:
                with server_client.stream('GET',base.rstrip('/')+'/') as server:
                    server_status=server.status_code
            diagnostics.update(reachable=True,server_http_status=server_status,server_response_ms=round((time.perf_counter()-server_started)*1000,1))
        except httpx.RequestError:
            diagnostics.update(server_response_ms=round((time.perf_counter()-server_started)*1000,1))
        if service=='tdarr':
            diagnostics['interface_only']=True
            diagnostics['api_valid']=False
            diagnostics['interface_valid']=diagnostics['reachable'] and 200<=diagnostics.get('server_http_status',0)<400
            return ('connected','Interface reachable; embedding must be verified in the browser') if diagnostics['interface_valid'] else ('error','Server unreachable')
        api_started=time.perf_counter()
        with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as client:response=client.get(base+path,headers=headers)
        diagnostics.update(api_http_status=response.status_code,api_response_ms=round((time.perf_counter()-api_started)*1000,1))
        diagnostics.update(reachable=True,http_status=response.status_code,response_ms=round((time.perf_counter()-started)*1000,1))
        try:diagnostics['resolved_ips']=sorted({item[4][0] for item in socket.getaddrinfo(diagnostics['host'],None,type=socket.SOCK_STREAM)})[:4]
        except OSError:diagnostics['resolved_ips']=[]
        if response.status_code in (401,403):return 'error','Authentication rejected'
        if response.status_code!=200:
            if service in ('radarr','sonarr','bazarr') and response.status_code==404:
                with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as client:
                    root=client.get(base+('/api/system/status' if service=='bazarr' else '/api/v3/system/status'),headers=headers)
                if root.status_code==200 and isinstance(root.json(),dict):return 'error','API available at the server root. Configure URL Base: /tools/'+service+'/app'
            return 'error','Server returned HTTP '+str(response.status_code)
        body=response.json()
        valid=isinstance(body,dict) and (bool(body.get('Id')) if service=='emby' else isinstance(body.get('results'),list) if service=='seerr' else isinstance(body.get('data'),list) if service=='tracearr' else bool(body))
        diagnostics['api_valid']=valid
        version=body.get('Version') or body.get('version') or body.get('tracearr_version')
        if isinstance(version,str) and len(version)<80:diagnostics['version']=version
        return ('connected','Authenticated API connection verified') if valid else ('error','Unexpected API response')
    except httpx.TimeoutException:return 'error','Connection timed out'
    except httpx.RequestError:return 'error','Server unreachable'
    except ValueError:return 'error','Unexpected API response'
    finally:diagnostics.setdefault('response_ms',round((time.perf_counter()-started)*1000,1))


def checks(db,refresh=False):
    current=int(time.time());pending={};result={}
    for service in ('emby','seerr','radarr','sonarr','bazarr','tracearr','tdarr'):
        row=db.get(ConnectionCheck,service)
        if not configured(db,service):
            result[service]={'state':'unconfigured','detail':'Connection not configured','checked_at':None};continue
        if refresh is True or refresh==service or not row or current-row.checked_at>60:
            base,key=emby_connection() if service=='emby' else (config(db,service+'_url'),decrypt(config(db,service+'_api_key')))
            pending[service]={'url':base,'key':key,'kind':media_kind(db)}
        else:result[service]={'state':row.state,'detail':row.detail,'checked_at':row.checked_at}
    # Network calls do not share the ORM session and run concurrently with bounded timeouts.
    if pending:
        with ThreadPoolExecutor(max_workers=3) as pool:
            outcomes=list(pool.map(lambda item:(item[0],probe(*item)),pending.items()))
        for service,(state,detail) in outcomes:
            row=db.get(ConnectionCheck,service)
            if not row:row=ConnectionCheck(service=service);db.add(row)
            row.state=state;row.detail=detail;row.checked_at=current
            diagnostics=pending[service].get('diagnostics',{})
            db.execute(insert(Config).values(key='connection_diagnostics_'+service,value=json.dumps(diagnostics)).on_conflict_do_update(index_elements=[Config.key],set_={'value':json.dumps(diagnostics)}))
            result[service]={'state':state,'detail':detail,'checked_at':current}
        db.commit()
    for service,check in result.items():check['diagnostics']=read_diagnostics(db,'connection_diagnostics_'+service) if check['state']!='unconfigured' else {}
    for check in result.values():check['checked_label']=time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime(check['checked_at'])) if check['checked_at'] else ''
    return result


def invalidate(db,service):
    row=db.get(ConnectionCheck,service)
    if row:db.delete(row)
    diagnostic=db.get(Config,'connection_diagnostics_'+service)
    if diagnostic:db.delete(diagnostic)


def read_diagnostics(db,key):
    try:return json.loads(config(db,key,'{}'))
    except (ValueError,TypeError):return {}


def smtp_probe(db,values=None):
    def setting(key,default=""):
        if values is not None and key in values:
            value=values[key]
            return __import__("app.security",fromlist=["encrypt"]).encrypt(value) if key=="smtp_password" and value else value
        return config(db,key,default)
    host=setting('smtp_host');mode=setting('smtp_mode','starttls')
    result={'host':host,'reachable':False,'tls':False,'authenticated':False,'checked_at':time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime()),'state':'error','detail':'SMTP connection failed'}
    started=time.perf_counter()
    try:
        if not host:result['detail']='SMTP not configured';return result
        if mode=='plain' and setting('smtp_username'):result['detail']='SMTP authentication requires TLS';return result
        port=int(setting('smtp_port','587'));result['port']=port
        result['resolved_ips']=sorted({item[4][0] for item in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)})[:4]
        connection=smtplib.SMTP_SSL(host,port,timeout=5,context=ssl.create_default_context()) if mode=='ssl' else smtplib.SMTP(host,port,timeout=5)
        with connection as smtp:
            result['reachable']=True;code,_=smtp.ehlo();result['smtp_status']=code
            if code!=250:result['detail']='SMTP greeting rejected';return result
            if mode=='starttls':smtp.starttls(context=ssl.create_default_context());smtp.ehlo()
            result['tls']=mode in ('ssl','starttls')
            username=setting('smtp_username');result['authentication_required']=bool(username)
            if username:smtp.login(username,decrypt(setting('smtp_password')));result['authenticated']=True
            result.update(state='connected',detail='SMTP connection verified')
    except smtplib.SMTPAuthenticationError:result['detail']='Authentication rejected'
    except (ssl.SSLError,smtplib.SMTPNotSupportedError):result['detail']='SMTP TLS negotiation failed'
    except (OSError,smtplib.SMTPException,ValueError):result['detail']='SMTP connection failed'
    finally:result['response_ms']=round((time.perf_counter()-started)*1000,1)
    return result
