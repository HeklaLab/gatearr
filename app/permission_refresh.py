"""Bounded, read-only snapshots. An observation must never enqueue a write."""
import time
from sqlalchemy import select
from .db import SessionLocal
from .models import User,PolicyState
from .emby import emby,EmbyError
from .mailer import config
from .connections import emby_connection
from .permissions import observe
from .seerr_permissions import configured,inspect_user
from .seerr_quotas import inspect as inspect_quotas

INTERVAL=300

def refresh_due():
    from .main import set_config
    with SessionLocal() as db:
        base,key=emby_connection()
        media=bool(base and key);seerr=configured(db)
        if not media and not seerr:return
        now=int(time.time());remaining=2
        users=list(db.scalars(select(User).where(User.emby_id.is_not(None),User.emby_missing.is_(False))))
        attempts={user.id:int(config(db,'permission_refresh_attempt_'+str(user.id),'0')) for user in users}
        # Oldest observation first avoids starving users beyond the first batch.
        for user in sorted(users,key=lambda user:attempts[user.id]):
            attempt='permission_refresh_attempt_'+str(user.id)
            if now-attempts[user.id]<INTERVAL:continue
            set_config(db,attempt,str(now));db.commit()
            if media:
                try:
                    policy=emby.user(user.emby_id).get('Policy')
                    if not isinstance(policy,dict) or not policy:raise EmbyError('Invalid policy response')
                    observe(db,user,policy)
                except EmbyError:
                    row=db.get(PolicyState,user.id)
                    if row:row.error='Media server unreachable; showing the last observed permissions';db.commit()
            if seerr:
                inspect_user(db,user);inspect_quotas(db,user)
            remaining-=1
            if remaining==0:break
