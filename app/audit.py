"""Bounded audit metadata: never request bodies, query strings, headers or credentials."""
import time,json,logging
from fastapi import APIRouter,Request
from sqlalchemy import select,delete
from .models import AuditEvent
from .db import SessionLocal
log=logging.getLogger('gatearr.audit')
router=APIRouter()
def record(actor,subject,action,outcome,detail=''):
    with SessionLocal() as db:
        db.add(AuditEvent(at=int(time.time()),actor_id=actor,subject_id=subject,action=action[:200],outcome=outcome,detail=detail[:1000]))
        db.execute(delete(AuditEvent).where(AuditEvent.at<int(time.time())-90*86400))
        cutoff=db.scalar(select(AuditEvent.id).order_by(AuditEvent.id.desc()).offset(99999).limit(1))
        if cutoff:db.execute(delete(AuditEvent).where(AuditEvent.id<cutoff))
        db.commit()
    log.info('action=%s actor_id=%s subject_id=%s status=%s',action,actor,subject,outcome)

@router.get('/admin/activity')
def activity(request:Request):
    from .main import require_admin,render
    require_admin(request)
    before=int(request.query_params.get('before','2147483647'))
    query=select(AuditEvent).where(AuditEvent.id<before).order_by(AuditEvent.id.desc()).limit(100)
    events=list(request.state.db.scalars(query))
    return render(request,'activity.html',events=events)
