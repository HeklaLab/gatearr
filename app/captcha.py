"""Embedded Cap with scoped single-use challenges and aggregate-only statistics."""
import json,os,time,threading,subprocess,select as io_select
from pathlib import Path
from collections import defaultdict
from fastapi import APIRouter,Request,Depends,HTTPException
from sqlalchemy import select,delete,update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError
from .models import CaptchaToken,CaptchaMetric
from .mailer import config
from .security import digest
from .settings import settings
router=APIRouter();_lock=threading.Lock();_process=None

def enabled(db,purpose):return purpose in ('login','forgot') and config(db,'captcha_'+purpose,'true')=='true'
def call(action,scope,body=None):
    global _process
    with _lock:
        try:
            if _process is None or _process.poll() is not None:
                env={**os.environ,'GATEARR_CAP_SECRET':digest('gatearr-cap:'+settings.secret_key)}
                _process=subprocess.Popen([os.getenv('CAP_NODE','node'),str(Path(__file__).with_name('cap')/'worker.mjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1,env=env)
            _process.stdin.write(json.dumps({'action':action,'scope':scope,'body':body})+'\n');_process.stdin.flush()
            if not io_select.select([_process.stdout],[],[],10)[0]:raise TimeoutError()
            value=json.loads(_process.stdout.readline())
            if not isinstance(value,dict):raise ValueError()
            return value
        except (OSError,ValueError,TimeoutError):
            if _process:
                _process.kill();_process.wait();_process=None
            raise HTTPException(503,'Captcha unavailable. Please try again shortly.')

def record(db,purpose,outcome):
    day=int(time.time())//86400*86400
    stmt=insert(CaptchaMetric).values(day=day,form=purpose,outcome=outcome,count=1)
    db.execute(stmt.on_conflict_do_update(index_elements=['day','form','outcome'],set_={'count':CaptchaMetric.count+1}));db.commit()

def verify(request,data,purpose):
    db=request.state.db
    if not enabled(db,purpose):return
    raw=str(data.get('cap-token',''));scope=purpose+':'+request.state.session.digest
    result=db.execute(update(CaptchaToken).where(CaptchaToken.key==digest(raw),CaptchaToken.scope==scope,CaptchaToken.used.is_(False),CaptchaToken.expires>int(time.time())).values(used=True)) if raw else None
    db.commit()
    if not result or result.rowcount!=1:
        record(db,purpose,'rejected');raise HTTPException(400,'Complete the captcha verification again.')

@router.post('/captcha/{purpose}/{action}')
async def endpoint(request:Request,purpose:str,action:str):
    from .main import limit
    from .security import origin
    db=request.state.db
    if action not in ('challenge','redeem') or not enabled(db,purpose):raise HTTPException(404,'Captcha not available')
    if origin(request.headers.get('origin',''))!=origin(config(db,'public_url',settings.public_url)):raise HTTPException(403,'Origin rejected')
    limit(request,'captcha_'+action,maximum=30,window=60)
    scope=purpose+':'+request.state.session.digest
    from starlette.concurrency import run_in_threadpool
    if action=='challenge':return await run_in_threadpool(call,'challenge',scope)
    from .tools_proxy import bounded_body
    try:body=json.loads(await bounded_body(request,32768))
    except (ValueError,UnicodeError):raise HTTPException(400,'Invalid captcha')
    result=await run_in_threadpool(call,'redeem',scope,body)
    if not result.get('success'):
        record(db,purpose,'expired' if result.get('reason')=='expired' else 'rejected');return {'success':False}
    if not result.get('nonce') or not result.get('token'):raise HTTPException(503,'Captcha unavailable')
    now=int(time.time())
    try:
        db.add(CaptchaToken(key=result['nonce'],scope=scope,expires=now+600,used=True))
        db.add(CaptchaToken(key=digest(result['token']),scope=scope,expires=min(int(result['expires']/1000),now+300),used=False));db.commit()
    except IntegrityError:
        db.rollback();record(db,purpose,'rejected');return {'success':False}
    record(db,purpose,'solved');return {'success':True,'token':result['token'],'expires':result['expires']}

def stats(db,days):
    now=int(time.time());totals=defaultdict(int);series=[]
    for row in db.scalars(select(CaptchaMetric).where(CaptchaMetric.day>=now//86400*86400-(days-1)*86400)):
        totals[row.outcome]+=row.count
    for day in range(now//86400*86400-(days-1)*86400,now+1,86400):
        count=sum(x.count for x in db.scalars(select(CaptchaMetric).where(CaptchaMetric.day==day,CaptchaMetric.outcome=='solved')))
        series.append({'label':time.strftime('%d/%m',time.gmtime(day)),'count':count})
    return dict(totals),series

def cleanup(db):
    now=int(time.time());db.execute(delete(CaptchaToken).where(CaptchaToken.expires<now));db.execute(delete(CaptchaMetric).where(CaptchaMetric.day<now-int(config(db,'captcha_retention','30'))*86400));db.commit()

@router.get('/admin/security/captcha')
def page(request:Request):
    from .main import require_admin,render
    require_admin(request);days=int(request.query_params.get('days','7'));days=days if days in (1,7,30) else 7
    totals,series=stats(request.state.db,days)
    return render(request,'captcha_settings.html',captcha_totals=totals,captcha_series=series,captcha_days=days)

@router.post('/admin/security/captcha')
def save(request:Request,data=Depends(__import__('app.main',fromlist=['form']).form)):
    from .main import require_admin,redirect,set_config,limit
    require_admin(request);db=request.state.db
    if data.get('action')=='test':
        limit(request,'captcha_test',maximum=10)
        value=call('challenge','admin-test:'+request.state.session.digest)
        set_config(db,'captcha_health','ok' if value.get('token') else 'error')
    else:
        for purpose in ('login','forgot'):set_config(db,'captcha_'+purpose,'true' if data.get(purpose)=='on' else 'false')
        days=int(data.get('retention','30'))
        if days not in (7,30,90):raise ValueError('Invalid retention')
        set_config(db,'captcha_retention',str(days))
    db.commit();return redirect('/admin/security/captcha')

@router.get('/captcha/frame')
def instrumentation_frame(request:Request):
    from html import escape
    from fastapi.responses import HTMLResponse
    from urllib.parse import urlsplit
    public=urlsplit(config(request.state.db,'public_url',settings.public_url))
    origin=public.scheme+'://'+public.netloc
    return HTMLResponse('<!doctype html><html><head><meta charset="utf-8"></head><body><script src="/static/cap-frame.js" nonce="'+escape(request.state.csp_nonce,quote=True)+'" data-origin="'+escape(origin,quote=True)+'"></script></body></html>')


def shutdown():
    global _process
    with _lock:
        if _process and _process.poll() is None:
            _process.terminate()
            try:_process.wait(timeout=3)
            except subprocess.TimeoutExpired:_process.kill();_process.wait()
        _process=None
