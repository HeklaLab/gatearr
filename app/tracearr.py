"""Tracearr public v2 contract. Identities match native IDs plus server IDs, never names."""
from contextlib import contextmanager
from urllib.parse import quote
import httpx,time
from .mailer import config
from .security import decrypt,digest
from .connections import media_kind
from .integrations import SyncError,normalized_id,request

def configured(db):return config(db,'tracearr_enabled')=='true' and bool(config(db,'tracearr_url') and config(db,'tracearr_api_key'))
def fingerprint(db):return digest(config(db,'tracearr_url')+'\n'+config(db,'tracearr_api_key')+'\n'+config(db,'tracearr_server_id'))
@contextmanager
def connection(db):
    if not configured(db):raise SyncError('configuration')
    with httpx.Client(base_url=config(db,'tracearr_url').rstrip('/')+'/',headers={'Authorization':'Bearer '+decrypt(config(db,'tracearr_api_key'))},timeout=8,trust_env=False,follow_redirects=False) as client:yield client

def rows(client,path,params=None):
    params={**(params or {}),'pageSize':100};result=[];seen=set();deadline=time.monotonic()+20
    for _ in range(200):
        if time.monotonic()>deadline:raise SyncError('pagination_timeout')
        page=request(client,'GET','api/v2/public/'+path,params=params)
        if not isinstance(page,dict) or not isinstance(page.get('data'),list):raise SyncError('api_contract')
        if any(not isinstance(row,dict) for row in page['data']):raise SyncError('api_contract')
        result.extend(page['data']);cursor=page.get('meta',{}).get('nextCursor')
        if not cursor:return result
        if cursor in seen:raise SyncError('pagination')
        seen.add(cursor);params['cursor']=cursor
    raise SyncError('pagination_limit')

def identity(db,user,client):
    if not user or not user.emby_id:raise SyncError('identity_mismatch')
    server=config(db,'tracearr_server_id')
    if not server:
        servers=rows(client,'servers');matching=[s['server_id'] for s in servers if s.get('server_type')==media_kind(db) and not s.get('historical')]
        if len(matching)!=1:raise SyncError('Select the matching media server in Tracearr settings')
        server=matching[0]
    matches=[]
    for item in rows(client,'users'):
        if any(a.get('server_id')==server and a.get('server_type')==media_kind(db) and not a.get('removed_at') and normalized_id(a.get('external_user_id',''))==normalized_id(user.emby_id) for a in item.get('accounts',[])):matches.append(item)
    if len(matches)!=1:raise SyncError('identity_mismatch')
    return matches[0]['id'],server

def history(db,user,client,params=None):
    uid,server=identity(db,user,client)
    rows_=rows(client,'history',{'user_id':uid,'server_id':server,**(params or {})})
    if any(not isinstance(row.get('user'),dict) or row['user'].get('id')!=uid or row.get('server_id')!=server for row in rows_):raise SyncError('identity_mismatch')
    if any(any(row.get(k) is not None and type(row[k]) not in (int,float) for k in ('duration_ms','bitrate')) for row in rows_):raise SyncError('api_contract')
    return rows_
