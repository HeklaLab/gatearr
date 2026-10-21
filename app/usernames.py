"""Explicit username changes, with an independent durable Seerr retry queue."""
import json,time
import httpx
from sqlalchemy import select
from .models import Config,User
from .mailer import config
from .seerr_permissions import configured,connection,fingerprint
from .seerr_quotas import PRESERVE
from .integrations import request as remote,SyncError

PREFIX='username_sync_'

def status(db,uid):
    return json.loads(config(db,PREFIX+str(uid),'{}'))

def enqueue(db,user):
    from .main import set_config
    if not configured(db):return
    set_config(db,PREFIX+str(user.id),json.dumps({'name':user.name,'connection':fingerprint(db),'state':'Synchronization pending','checked_at':0}))
    db.commit()

def apply(db,user):
    row=db.get(Config,PREFIX+str(user.id))
    if not row:return
    original=row.value;value=json.loads(original)
    if value.get('state')=='Synchronized':return
    try:
        if value['name']!=user.name or value['connection']!=fingerprint(db):raise SyncError('configuration')
        with connection(db,user) as (client,rid):
            path=f'api/v1/user/{rid}/settings/main'
            current=remote(client,'GET',path)
            body={key:current[key] for key in PRESERVE if key in current}
            body['username']=user.name
            remote(client,'POST',path,json=body)
            if remote(client,'GET',path).get('username')!=user.name:raise SyncError('verification_failed')
        value['state']='Synchronized'
    except (SyncError,httpx.HTTPError):value['state']='failed — retry required'
    value['checked_at']=int(time.time())
    # A newer rename must not be overwritten by an older request's result.
    from sqlalchemy import update
    db.execute(update(Config).where(Config.key==row.key,Config.value==original).values(value=json.dumps(value)));db.commit()

def run_pending():
    from .db import SessionLocal
    with SessionLocal() as db:
        if not configured(db):return
        for row in db.scalars(select(Config).where(Config.key.startswith(PREFIX))):
            value=json.loads(row.value)
            if value.get('state')=='Synchronized' or time.time()-value.get('checked_at',0)<60:continue
            user=db.get(User,int(row.key[len(PREFIX):]))
            if user and user.active:apply(db,user)
