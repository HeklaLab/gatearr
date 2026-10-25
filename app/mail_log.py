"""SMTP attempt metadata that survives caller and preview-savepoint rollbacks."""
import logging
import re
import time
from urllib.parse import parse_qs,urlsplit
from fastapi import APIRouter,Request,Query
from sqlalchemy import event,insert,select
from sqlalchemy.orm import Session
from .models import MailDelivery

router=APIRouter()
log=logging.getLogger('gatearr.mail')
PENDING='gatearr_mail_deliveries'
PURPOSES={'invite':'Invitation','reset':'Password recovery','verify':'Email verification','email_changed':'Email address changed','password_changed':'Password changed','new_season':'New season'}
CONTEXTS={'smtp_test':'SMTP test','template_test':'Template test','notification':'Notification','transactional':'Account email'}
ERRORS={'authentication':'SMTP authentication failed','recipients':'Recipient rejected','sender':'Sender rejected','data':'SMTP message rejected','configuration':'SMTP configuration error','connection':'SMTP connection failed','other':'Email sending failed'}


def safe_subject(subject,values):
    value=str(subject)
    # Subjects may be customized with ${link}; never retain recovery/verification secrets.
    for key,secret in values.items():
        if not isinstance(secret,str) or not secret:continue
        if key=='link' or re.search(r'password|token|secret|api_key',key,re.I):value=value.replace(secret,'[private]')
        if key=='link':
            try:query=parse_qs(urlsplit(secret).query)
            except ValueError:query={}
            for name,parts in query.items():
                if re.search(r'token|password|secret|key|ticket',name,re.I):
                    for part in parts:
                        if part:value=value.replace(part,'[private]')
    return re.sub(r'[\r\n]+',' ',value)[:1000]


def persist(db):
    rows=db.info.pop(PENDING,[])
    if not rows:return
    try:
        # The caller's outer transaction has ended, releasing SQLite's writer lock.
        with db.get_bind().begin() as connection:connection.execute(insert(MailDelivery),rows)
    except Exception as exc:
        # SMTP may already have accepted a message: never cause a duplicate retry.
        log.error('Unable to persist SMTP delivery metadata (%s)',type(exc).__name__)


@event.listens_for(Session,'after_transaction_end')
def transaction_finished(db,transaction):
    if transaction.parent is None:persist(db)


def record(db,recipient,purpose,subject,values,state,error=''):
    context=values.get('_mail_context')
    if context not in CONTEXTS:context='notification' if purpose=='new_season' else 'transactional'
    db.info.setdefault(PENDING,[]).append(dict(at=int(time.time()),recipient=re.sub(r'[\r\n]+',' ',str(recipient))[:320],subject=safe_subject(subject,values),purpose=purpose[:60],context=context,state=state,error=error))
    if not db.in_transaction():persist(db)


@router.get('/admin/activity/mail')
def mail_activity(request:Request,before:int|None=Query(default=None,ge=1)):
    from .main import require_admin,render
    require_admin(request)
    query=select(MailDelivery).order_by(MailDelivery.id.desc()).limit(51)
    if before is not None:query=query.where(MailDelivery.id<before)
    rows=list(request.state.db.scalars(query));more=len(rows)>50
    return render(request,'mail_log.html',deliveries=rows[:50],has_older=more,mail_purposes=PURPOSES,mail_contexts=CONTEXTS,mail_errors=ERRORS)
