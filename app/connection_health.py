"""Read-only, authenticated probes. Store only safe diagnostics, never remote bodies."""
import time
from concurrent.futures import ThreadPoolExecutor
import httpx
from sqlalchemy import select
from .db import SessionLocal
from .models import ConnectionCheck
from .mailer import config
from .security import decrypt
from .connections import emby_connection,media_kind


def configured(db,service):
    if service=='emby':return bool(config(db,'emby_url') and config(db,'emby_api_key'))
    return config(db,service+'_enabled')=='true' and bool(config(db,service+'_url') and config(db,service+'_api_key'))


def probe(service,values):
    base,key=values['url'],values['key']
    headers={'X-Emby-Token':key} if service=='emby' else {'X-Api-Key':key}
    if service=='emby' and values['kind']=='jellyfin':headers={'Authorization':'MediaBrowser Client="Gatearr", Device="Portal", DeviceId="gatearr-portal", Version="1.0", Token="'+key+'"'}
    path='/System/Info' if service=='emby' else '/api/v1/user?take=1&skip=0' if service=='seerr' else '/tools/'+service+'/app'+('/api/system/status' if service=='bazarr' else '/api/v3/system/status')
    try:
        with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as client:response=client.get(base+path,headers=headers)
        if response.status_code in (401,403):return 'error','Authentication rejected'
        if response.status_code!=200:return 'error','Server returned HTTP '+str(response.status_code)
        body=response.json()
        valid=isinstance(body,dict) and (bool(body.get('Id')) if service=='emby' else isinstance(body.get('results'),list) if service=='seerr' else bool(body))
        return ('connected','Authenticated API connection verified') if valid else ('error','Unexpected API response')
    except httpx.TimeoutException:return 'error','Connection timed out'
    except httpx.RequestError:return 'error','Server unreachable'
    except ValueError:return 'error','Unexpected API response'


def checks(db,refresh=False):
    current=int(time.time());pending={};result={}
    for service in ('emby','seerr','radarr','sonarr','bazarr'):
        row=db.get(ConnectionCheck,service)
        if not configured(db,service):
            result[service]={'state':'unconfigured','detail':'Connection not configured','checked_at':None};continue
        if refresh or not row or current-row.checked_at>60:
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
            result[service]={'state':state,'detail':detail,'checked_at':current}
        db.commit()
    for check in result.values():check['checked_label']=time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime(check['checked_at'])) if check['checked_at'] else ''
    return result


def invalidate(db,service):
    row=db.get(ConnectionCheck,service)
    if row:db.delete(row)
