import asyncio
import logging
import json
import re
import secrets
import time
from contextlib import asynccontextmanager
from string import Template
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, delete, update, text, case
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from .db import SessionLocal
from .models import User, Session, Token, Config, MenuItem, RateBucket, MailJob, AccessService
from .settings import settings
from .security import digest, password_ok, email_ok, url_ok, encrypt, decrypt, origin as url_origin
from .emby import emby, EmbyError
from .mailer import config, send, DEFAULTS, mail_template
from . import rich_mail
from .integrations import SECRET_CONFIG, queue_user, queue_all, run_jobs
from . import portal, i18n

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("gatearr")
logging.getLogger("httpx").setLevel(logging.WARNING)
templates = Jinja2Templates(directory="app/templates")

def now():
    return int(time.time())

def set_config(db, key, value):
    row = db.get(Config, key)
    if row:
        row.value = value
    else:
        db.add(Config(key=key, value=value))

def sync_users(db):
    try:
        remote = emby.users()
        if any(not isinstance(u, dict) or not u.get("Id") or not u.get("Name") for u in remote):
            raise EmbyError("Liste Emby invalide")
    except EmbyError:
        set_config(db, "emby_sync_error", 'unavailable')
        set_config(db, "emby_sync_attempt_at", str(now()))
        db.commit()
        raise
    if any(not isinstance(u, dict) or not u.get("Id") or not u.get("Name") for u in remote):
        raise EmbyError("Liste Emby invalide")
    sync_time = now()
    ids = set()
    for item in remote:
        ids.add(item["Id"])
        row = db.scalar(select(User).where(User.emby_id == item["Id"]))
        if not row:
            row = User(emby_id=item["Id"], name=item["Name"], admin=False, active=True, version=0)
            db.add(row)
        row.emby_missing = False
        row.emby_seen_at = sync_time
        row.name = item["Name"]
        active = not item.get("Policy", {}).get("IsDisabled", False)
        if row.active and not active:
            row.version += 1
        row.active = active
    for row in db.scalars(select(User).where(User.emby_id.is_not(None))):
        if row.emby_id not in ids:
            row.emby_missing = True
            if row.active:
                row.version += 1
            row.active = False
    set_config(db, "emby_sync_error", "")
    set_config(db, "emby_sync_at", str(sync_time))
    set_config(db, "emby_sync_attempt_at", str(now()))
    set_config(db, "last_sync", time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()))
    db.commit()
    queue_all(db)
    log.info("Emby sync completed count=%d", len(remote))
    return len(remote)

def maintenance():
    with SessionLocal() as db:
        for model in (Session, Token, RateBucket):
            db.execute(delete(model).where(model.expires < now()))
        db.commit()
        if config(db, "emby_api_key"):
            try:
                sync_users(db)
            except (EmbyError, IntegrityError):
                db.rollback()
                log.warning("Scheduled Emby sync failed")
        queue_all(db, force=True)

def deliver_mail():
    with SessionLocal() as db:
        jobs = list(db.scalars(select(MailJob).where(MailJob.next_attempt <= now()).order_by(MailJob.id).limit(10)))
        for job in jobs:
            try:
                payload = json.loads(decrypt(job.payload))
                token = db.get(Token, digest(payload["token"]))
                owner = db.get(User, token.user_id) if token else None
                if job.expires <= now() or not token or token.used or not owner or not owner.active or token.version != owner.version:
                    db.delete(job)
                    db.commit()
                    continue
                mail_token(db, owner, payload["purpose"], payload["token"], payload["recipient"])
                db.delete(job)
                log.info("Mail delivered job_id=%s", job.id)
            except Exception:
                job.attempts += 1
                job.next_attempt = now() + min(300, 30 * 2 ** job.attempts)
                log.warning("Mail delivery failed job_id=%s attempt=%s", job.id, job.attempts)
                if job.attempts >= 5:
                    db.delete(job)
            db.commit()

def enqueue_mail(db, purpose, raw, recipient):
    if not config(db, "smtp_host"):
        raise ValueError('SMTP not configured')
    payload = encrypt(json.dumps({"purpose": purpose, "token": raw, "recipient": recipient}))
    db.add(MailJob(payload=payload, attempts=0, next_attempt=now(), expires=now()+1800))
    db.commit()

async def scheduled():
    next_sync = now()
    while True:
        await asyncio.sleep(5)
        await run_in_threadpool(deliver_mail)
        await run_in_threadpool(run_jobs)
        if now() >= next_sync:
            await run_in_threadpool(maintenance)
            next_sync = now() + max(1, settings.sync_minutes) * 60

@asynccontextmanager
async def lifespan(app):
    if len(settings.secret_key) < 32 or settings.secret_key.startswith("replace-"):
        raise RuntimeError("SECRET_KEY must contain at least 32 characters")
    url_ok(settings.public_url)
    public = urlsplit(settings.public_url)
    if public.path not in ("", "/") or public.query or public.fragment:
        raise RuntimeError("PUBLIC_URL doit désigner la racine d'un domaine, sans query string")
    if not settings.database_url.startswith("sqlite"):
        raise RuntimeError("Cette version utilise SQLite ; un seul processus applicatif est requis")
    if settings.secure_cookie and urlsplit(settings.public_url).scheme != "https":
        raise RuntimeError("COOKIE_SECURE=true nécessite une PUBLIC_URL HTTPS")
    task = asyncio.create_task(scheduled())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="Gatearr", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.state.public_url = settings.public_url
app.mount("/static", StaticFiles(directory="app/static"), name="static")

def cookie(response, value, secure=None):
    response.set_cookie("gatearr_session", value, max_age=43200, httponly=True, secure=settings.secure_cookie if secure is None else secure, samesite="lax", path="/")

@app.middleware("http")
async def context(request: Request, call_next):
    # Ignore arbitrary Host / forwarded headers for links: the configured public URL is authoritative.
    if request.url.path == "/healthz" or (request.url.path.startswith("/static/") or re.fullmatch(r"/media/icons/[a-f0-9]{64}\.png",request.url.path)):
        return await call_next(request)
    with SessionLocal() as db:
        raw = request.cookies.get("gatearr_session", "")
        session = db.get(Session, digest(raw)) if raw else None
        if session and session.expires <= now():
            db.delete(session)
            db.commit()
            session = None
        fresh = session is None
        if fresh:
            raw = secrets.token_urlsafe(32)
            session = Session(digest=digest(raw), csrf=secrets.token_urlsafe(32), expires=now()+43200, version=0)
            db.add(session)
            db.commit()
        user = db.get(User, session.user_id) if session.user_id else None
        if user and (not user.active or user.version != session.version):
            session.user_id = None
            db.commit()
            user = None
        request.state.db, request.state.session, request.state.user = db, session, user
        request.state.locale = i18n.resolve(request, user)
        request.state.rotated = False
        request.state.cookie_secure = settings.secure_cookie or urlsplit(config(db,"public_url",settings.public_url)).scheme=="https"
        response = await call_next(request)
        if fresh and not request.state.rotated:
            cookie(response, raw,request.state.cookie_secure)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if request.state.cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; img-src 'self' https: http:; script-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if request.url.path=="/admin/mail-editor":
            response.headers["Content-Security-Policy"]=response.headers["Content-Security-Policy"].replace("script-src 'none'","script-src 'self'").replace("style-src 'self'","style-src 'self' 'unsafe-inline'")
        return response

async def form(request: Request):
    # Starlette bounds multipart fields; also limit body size for urlencoded forms.
    accepts_icon=request.url.path in ("/admin/menu","/admin/guides/service")
    chunks, length = [], 0
    async for chunk in request.stream():
        length += len(chunk)
        if length > (2*1024*1024+65536 if accepts_icon else 65536):
            raise HTTPException(413, 'Form too large')
        chunks.append(chunk)
    # Preserve the bounded body for Starlette's form parser after streaming it once.
    request._body = b"".join(chunks)
    data = await request.form(max_fields=400 if request.url.path.startswith(("/admin/guides/", "/admin/access/")) else 100, max_files=1 if accepts_icon else 0)
    supplied = str(data.get("csrf", ""))
    if not secrets.compare_digest(supplied, request.state.session.csrf):
        raise HTTPException(403, 'Form expired. Reload the page.')
    required = {
        "/setup": (),
        "/login": ("name", "password"),
        "/account/password": ("current", "password", "confirm"),
        "/account/email": ("current", "email"),
        "/forgot": ("email",),
        "/reset": ("token", "password", "confirm"),
        "/verify-email": ("token",),
        "/admin/settings": ("app_name", "public_url", "login_text", "logo_url", "emby_link"),
        "/admin/smtp": ("smtp_host", "smtp_port", "smtp_mode", "smtp_from"),
        "/admin/mail-templates": ("reset_subject", "reset_body", "verify_subject", "verify_body"),
        "/admin/menu": ("label", "url", "icon", "position"),
        "/admin/menu/delete": ("id",),
        "/admin/user-email": ("id", "email"),
        "/language": ("locale",),
        "/admin/emby/clone": ("source_id", "name", "password"),
        "/admin/emby/libraries": ("id",),
        "/admin/emby/copy": ("id", "source_id"),
        "/admin/integrations": ("service",),
        "/admin/portal/block": ("version", "kind", "region", "order", "span"),
        "/admin/portal/delete": ("version", "block_id"),
        "/admin/portal/move": ("version", "block_id", "direction"),
        "/admin/portal/theme": ("version", "nav_position", "accent", "bg", "surface", "text", "muted"),
        "/admin/portal/publish": ("version",),
        "/admin/portal/reset": ("version",),
    }.get(request.url.path, ())
    if any(key not in data for key in required):
        raise HTTPException(400, 'Incomplete form')
    from starlette.datastructures import UploadFile
    if any((key!='icon_file' or not accepts_icon) if isinstance(value,UploadFile) else (not isinstance(value,str) or len(value)>10000) for key,value in data.multi_items()):
        raise HTTPException(400, 'Invalid or oversized field')
    if any(len(str(data.get(key, ""))) > 256 for key in ("current", "password", "confirm", "smtp_password")):
        raise HTTPException(400, 'Password too long')
    origin = request.headers.get("origin")
    expected = urlsplit(config(request.state.db, "public_url", settings.public_url))
    initial_setup=request.url.path in ('/setup','/setup/admin') and not request.state.db.get(Config,'setup_complete')
    initial_origin=str(request.base_url).rstrip('/')
    if origin and (url_origin(origin) is None or (url_origin(origin)!=url_origin(expected.geturl()) and not (initial_setup and url_origin(origin)==url_origin(initial_origin)))):
        log.warning("Rejected form origin=%r expected=%r", origin[:200], f"{expected.scheme}://{expected.netloc}")
        raise HTTPException(403, 'Origin rejected')
    return data

def limit(request, action, identity="", maximum=5, window=900):
    db = request.state.db
    ip = request.client.host if request.client else "unknown"
    keys = [digest(action + ":ip:" + ip)]
    if identity:
        keys.append(digest(action + ":identity:" + identity.casefold()))
    for key in keys:
        stmt = insert(RateBucket).values(key=key, count=1, expires=now()+window)
        db.execute(stmt.on_conflict_do_update(index_elements=[RateBucket.key], set_={
            "count": case((RateBucket.expires < now(), 1), else_=RateBucket.count + 1),
            "expires": case((RateBucket.expires < now(), now()+window), else_=RateBucket.expires),
        }))
    db.commit()
    if any(db.get(RateBucket, key).count > maximum for key in keys):
        raise HTTPException(429, 'Too many attempts. Try again in a few minutes.', headers={"Retry-After": str(window)})

def require_user(request):
    if not request.state.user:
        raise HTTPException(401, 'Sign in to access this page.')
    return request.state.user

def require_admin(request):
    user = require_user(request)
    if not user.admin or not user.emby_id:
        raise HTTPException(403, 'Administrator access required')
    return user

def render(request, template, **kwargs):
    db = request.state.db
    locale = request.state.locale
    custom_translations = i18n.overrides(db,locale)
    base_translations = i18n.overrides(db,"en")
    from .connections import media_kind
    media_name="Jellyfin" if media_kind(db)=="jellyfin" else "Emby"
    values = {row.key: row.value for row in db.scalars(select(Config)) if row.key not in SECRET_CONFIG and row.key != "setup_owner_digest" and not row.key.startswith(("portal_","ui_translation_","_i18n_"))}
    values["login_source"]=config(db,"login_text", "Access your services and manage your account with ease.")
    values["login_text"] = i18n.content(db,'branding:login_text',config(db,'login_text','Access your services and manage your account with ease.'),locale)
    layout = kwargs.pop("layout", None) or portal.load(db)
    menus = {}
    for item in db.scalars(select(MenuItem).order_by(MenuItem.position, MenuItem.id)):
        menus.setdefault(item.menu_key, []).append(item)
    mail_locale = request.query_params.get("mail_locale", locale)
    if mail_locale not in i18n.languages(db):
        mail_locale = locale
    for key in DEFAULTS:
        values[key] = mail_template(db,*key.rsplit("_",1),mail_locale)
    from .guides import access_href
    def translator(message,**params):
        result=i18n.translate(message,locale,overrides=custom_translations,base_overrides=base_translations,**params)
        if media_name=='Jellyfin' and message not in custom_translations:
            result=result.replace('Emby','Jellyfin')
            if message=='EMBY':result='JELLYFIN'
        return result
    return templates.TemplateResponse(request=request, name=template, context={
        "asset_version":str(max(Path("app/static/style.css").stat().st_mtime_ns,Path("app/static/mail-editor.js").stat().st_mtime_ns)), "user": request.state.user, "csrf": request.state.session.csrf, "cfg": values,
        "media_name": media_name, "app_name": i18n.content(db,"branding:app_name",values.get("app_name",settings.app_name),locale), "app_name_source":values.get("app_name",settings.app_name), "locale": locale, "languages": i18n.languages(db), "language_names": i18n.languages(db), "_": translator,
        "account_label_defaults": i18n.ACCOUNT_LABEL_DEFAULTS, "account_labels": {key: translator(i18n.ACCOUNT_LABEL_KEYS[key]) for key,default in i18n.ACCOUNT_LABEL_DEFAULTS.get(locale,i18n.ACCOUNT_LABEL_DEFAULTS["en"]).items()},
        "seerr_notification_mode": config(db, "seerr_notification_mode", "unmanaged"), "newsletter_available": config(db,"tracearr_enabled") == "true",
        "service_icon": lambda key: (db.get(AccessService,key).icon_url if db.get(AccessService,key) else ""), "access_href": lambda key: access_href(db, key), "access_services": list(db.scalars(select(AccessService).order_by(AccessService.name))),
        "layout": layout, "regions": portal.for_display(layout, locale, request.state.user,db), "menus": menus, "mail_locale": mail_locale,
        "content": lambda key,source:i18n.content(db,key,source,locale), "message": translator(kwargs.pop("message", "")), **kwargs})

@app.exception_handler(HTTPException)
def http_error(request, exc):
    response = render(request, "error.html", message=exc.detail)
    response.status_code = exc.status_code
    response.headers.update(exc.headers or {})
    return response

@app.exception_handler(ValueError)
def validation_error(request, exc):
    response = render(request, "error.html", message=str(exc) if i18n.canonical(str(exc)) in i18n.CATALOGS["en"] else 'Invalid value.')
    response.status_code = 400
    return response

@app.exception_handler(EmbyError)
def emby_error(request, exc):
    log.warning("Emby operation failed: %s", exc)
    response = render(request, "error.html", message='Emby is unavailable or rejected the operation. Check its configuration and try again.')
    response.status_code = 502
    return response

def redirect(path):
    return RedirectResponse(path, status_code=303)

def rotate(request, user, destination=None):
    db = request.state.db
    db.delete(request.state.session)
    raw = secrets.token_urlsafe(32)
    db.add(Session(digest=digest(raw), user_id=user.id, csrf=secrets.token_urlsafe(32), expires=now()+43200, version=user.version))
    db.commit()
    pending=user.admin and config(db,"onboarding_required")=="true"
    response = redirect(destination or ("/admin/setup" if pending else "/home"))
    cookie(response, raw,settings.secure_cookie or urlsplit(config(db,"public_url",settings.public_url)).scheme=="https")
    request.state.rotated = True
    return response

def invalidate(db, user):
    db.execute(update(User).where(User.id == user.id).values(version=User.version + 1))
    db.execute(delete(Session).where(Session.user_id == user.id))
    db.execute(update(Token).where(Token.user_id == user.id).values(used=True))
    db.commit()

@app.get('/media/icons/{filename}')
def uploaded_icon(filename:str):
    from .models import IconAsset
    if not re.fullmatch(r'[a-f0-9]{64}\.png',filename):raise HTTPException(404,'Icon not found')
    with SessionLocal() as db:
        asset=db.get(IconAsset,filename[:-4])
        if not asset:return Response(status_code=404)
        return Response(content=asset.content,media_type='image/png',headers={'X-Content-Type-Options':'nosniff','Cache-Control':'public, max-age=31536000, immutable','Content-Security-Policy':"default-src 'none'; sandbox"})

@app.get("/healthz")
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1 FROM alembic_version"))
    return {"status": "ok"}

@app.get("/")
def index(request: Request):
    return redirect("/home" if request.state.user else "/login")

@app.get("/setup")
def setup_page(request: Request):
    from .first_run import page
    return page(request)

@app.post("/setup")
def setup(request: Request, data=Depends(form)):
    from .first_run import connect
    return connect(request,data)

@app.get("/setup/admin")
def setup_admin_page(request: Request):
    from .first_run import administrator_page
    return administrator_page(request)

@app.post("/setup/admin")
def setup_admin(request: Request, data=Depends(form)):
    from .first_run import claim
    return claim(request,data)

@app.get("/login")
def login_page(request: Request):
    if not request.state.db.get(Config, "setup_complete"):
        return redirect("/setup")
    return render(request, "login.html")

@app.post("/login")
def login(request: Request, data=Depends(form)):
    name, password = str(data.get("name", "")).strip(), str(data.get("password", ""))
    if len(name) > 320 or len(password) > 256:
        raise HTTPException(400, 'Credentials too long')
    limit(request, "login", name, maximum=10)
    db = request.state.db
    if not db.get(Config,"setup_complete"):
        raise HTTPException(403, 'Complete the initial setup first')
    try:
        result = emby.authenticate(name, password)
    except EmbyError:
        raise HTTPException(401, 'Invalid credentials or Emby unavailable')
    remote = result["User"]
    if remote.get("Policy", {}).get("IsDisabled"):
        raise HTTPException(401, 'Invalid credentials')
    user = db.scalar(select(User).where(User.emby_id == remote["Id"]))
    if config(db,'onboarding_required')=='true' and (not user or not user.admin):
        raise HTTPException(403,'Le portail est en cours de configuration')
    if not user:
        user = User(emby_id=remote["Id"], name=remote["Name"], admin=False, active=True, locale=request.state.locale)
        db.add(user)
    user.name, user.active, user.emby_missing = remote["Name"], True, False
    db.commit()
    if request.cookies.get("gatearr_language") in i18n.languages(db):
        user.locale = request.cookies["gatearr_language"]
        db.commit()
    return rotate(request, user)

@app.post("/logout")
def logout(request: Request, data=Depends(form)):
    request.state.db.delete(request.state.session)
    request.state.db.commit()
    response = redirect("/login")
    response.delete_cookie("gatearr_session", path="/")
    request.state.rotated = True
    return response

@app.get("/account")
def account(request: Request):
    user = require_user(request)
    items = list(request.state.db.scalars(select(MenuItem).order_by(MenuItem.position, MenuItem.id)))
    return render(request, "account.html", items=items)

@app.post("/account/password")
def change_password(request: Request, data=Depends(form)):
    user = require_user(request)
    limit(request, "password", str(user.id))
    password_ok(data["password"])
    if data["password"] != data.get("confirm"):
        raise ValueError('Passwords do not match')
    if not user.emby_id:raise HTTPException(403,'Media account required')
    result = emby.authenticate(user.name, data["current"])
    if result["User"]["Id"] != user.emby_id:
        raise HTTPException(403, 'Emby identity mismatch')
    emby.password(user.emby_id, data["password"], token=result["AccessToken"])
    invalidate(request.state.db, user)
    log.info("Password changed user_id=%s", user.id)
    return redirect("/login")

def issue_token(db, user, purpose, email=None):
    db.execute(update(Token).where(Token.user_id == user.id, Token.purpose == purpose).values(used=True))
    raw = secrets.token_urlsafe(32)
    db.add(Token(digest=digest(raw), user_id=user.id, purpose=purpose, email=email, expires=now()+1800, used=False, version=user.version))
    db.commit()
    return raw

def mail_token(db, user, purpose, raw, recipient):
    base = config(db, "public_url", settings.public_url)
    link = base + ("/reset?" if purpose == "reset" else "/verify-email?") + urlencode({"token": raw})
    mail_language=user.locale if user.locale in i18n.languages(db) else "en"
    send(db, recipient, purpose, {"app_name": i18n.content(db,"branding:app_name",config(db,"app_name",settings.app_name),mail_language), "username": user.name, "link": link, "minutes": "30", "_locale": mail_language})

@app.post("/account/email")
def change_email(request: Request, data=Depends(form)):
    user = require_user(request)
    limit(request, "email", str(user.id))
    email = email_ok(data["email"])
    if not user.emby_id:raise HTTPException(403,'Media account required')
    result = emby.authenticate(user.name, data["current"])
    if result["User"]["Id"] != user.emby_id:
        raise HTTPException(403, 'Emby identity mismatch')
    raw = issue_token(request.state.db, user, "verify", email)
    try:
        enqueue_mail(request.state.db, "verify", raw, email)
    except Exception:
        log.warning("Verification email delivery failed user_id=%s", user.id)
        raise HTTPException(503, 'The email could not be queued. Contact the administrator.')
    return render(request, "message.html", message='Check your inbox and confirm the new address. Your previous address remains active until confirmation.')

def valid_token(db, raw, purpose):
    token = db.get(Token, digest(raw))
    user = db.get(User, token.user_id) if token else None
    if not token or token.used or token.expires <= now() or token.purpose != purpose or not user or not user.active or user.version != token.version:
        raise HTTPException(400, 'Invalid, expired or already used link')
    return token, user

def consume(db, token):
    result = db.execute(update(Token).where(Token.digest == token.digest, Token.used.is_(False), Token.expires > now(), Token.version == select(User.version).where(User.id == token.user_id).scalar_subquery()).values(used=True))
    db.commit()
    if result.rowcount != 1:
        raise HTTPException(400, 'Link already used or expired')

@app.get("/verify-email")
def verify_page(request: Request, token: str = ""):
    valid_token(request.state.db, token, "verify")
    return render(request, "verify.html", token=token)

@app.post("/verify-email")
def verify_email(request: Request, data=Depends(form)):
    db = request.state.db
    token, user = valid_token(db, data.get("token", ""), "verify")
    consume(db, token)
    user.newsletter_pending = user.newsletter_opt_in is not None
    user.preferences_version += 1
    user.email = token.email
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This address is already linked to another account')
    # An email change invalidates any previously issued reset link.
    db.execute(update(Token).where(Token.user_id == user.id, Token.purpose == "reset").values(used=True))
    db.commit()
    queue_user(db, user)
    return render(request, "message.html", message='Email address verified. You can now recover your account by email.')

@app.get("/forgot")
def forgot_page(request: Request):
    return render(request, "forgot.html")

@app.post("/forgot")
def forgot(request: Request, data=Depends(form)):
    supplied = str(data.get("email", "")).strip().lower()[:320]
    limit(request, "reset_request", supplied)
    db = request.state.db
    user = db.scalar(select(User).where(User.email == supplied, User.active.is_(True)))
    if user and user.emby_id:
        raw = issue_token(db, user, "reset")
        try:
            enqueue_mail(db, "reset", raw, user.email)
        except Exception:
            log.warning("Reset email delivery failed user_id=%s", user.id)
    # All linked media accounts, including portal administrators, share this recovery flow.
    return render(request, "message.html", message='If this address is linked to an active Emby account, a recovery link will be sent.')

@app.get("/reset")
def reset_page(request: Request, token: str = ""):
    valid_token(request.state.db, token, "reset")
    return render(request, "reset.html", token=token)

@app.post("/reset")
def reset_password(request: Request, data=Depends(form)):
    limit(request, "reset_use", maximum=10)
    db = request.state.db
    token, user = valid_token(db, data.get("token", ""), "reset")
    password_ok(data["password"])
    if data["password"] != data.get("confirm"):
        raise ValueError('Passwords do not match')
    remote = emby.user(user.emby_id)
    if remote.get("Policy", {}).get("IsDisabled"):
        raise HTTPException(403, 'Account disabled')
    # Burn before network mutation: replay and concurrent redemption cannot change it twice.
    consume(db, token)
    try:
        emby.password(user.emby_id, data["password"])
    except EmbyError:
        raise HTTPException(502, 'Emby rejected the operation. Request a new link before trying again.')
    invalidate(db, user)
    log.info("Password reset user_id=%s", user.id)
    return render(request, "message.html", message='Password changed. Sign in with your new password.')

ADMIN_SECTIONS={'branding':'Branding','emails':'Emails','services':'Services','users':'Users'}

@app.get('/admin')
def admin(request:Request):
    require_admin(request)
    if config(request.state.db,'onboarding_required')=='true':return redirect('/admin/setup')
    return render(request,'admin_index.html')

def admin_section(request:Request,section:str):
    # Only these exact section names belong to this route; static routes are registered below.
    if section not in ADMIN_SECTIONS:raise HTTPException(404,'Section not found')
    require_admin(request)
    from .sync_status import user_statuses
    db=request.state.db
    return render(request,'admin.html',section=section,section_title=ADMIN_SECTIONS[section],sync_statuses=user_statuses(db,request.state.locale),users=list(db.scalars(select(User).where(User.emby_id.is_not(None)).order_by(User.id))),items=list(db.scalars(select(MenuItem).order_by(MenuItem.position,MenuItem.id))),mail_defaults=DEFAULTS)


def section_handler(section):
    def page(request:Request):return admin_section(request,section)
    return page

for _section in ADMIN_SECTIONS:
    app.add_api_route('/admin/'+_section,section_handler(_section),methods=['GET'])

@app.post("/admin/sync")
def admin_sync(request: Request, data=Depends(form)):
    require_admin(request)
    count = sync_users(request.state.db)
    return render(request, "message.html", message=i18n.translate('Synchronization complete: {count} Emby accounts. Removed or disabled accounts can no longer use the portal.', request.state.locale, overrides=i18n.overrides(request.state.db,request.state.locale), count=count))

@app.post("/admin/settings")
def admin_settings(request: Request, data=Depends(form)):
    require_admin(request)
    db = request.state.db
    public = url_ok(data["public_url"])
    if urlsplit(public).path not in ("", "/") or urlsplit(public).query or urlsplit(public).fragment:
        raise ValueError('The public URL must be at the domain root')
    if settings.secure_cookie and not public.startswith("https://"):
        raise ValueError('The public URL must use HTTPS')
    values = {"login_text": str(data["login_text"])[:2000], "default_locale":"en", "app_name":str(data["app_name"]).strip()[:80], "logo_url":url_ok(data["logo_url"],optional=True), "emby_link":url_ok(data["emby_link"],optional=True), "public_url":public}

    for key, value in values.items():
        set_config(db, key, value)
    db.commit()
    return redirect("/admin/branding")

@app.post("/admin/smtp")
def admin_smtp(request: Request, data=Depends(form)):
    require_admin(request)
    db = request.state.db
    port = int(data["smtp_port"])
    if not 1 <= port <= 65535 or data["smtp_mode"] not in ("ssl", "starttls", "plain"):
        raise ValueError('Invalid SMTP configuration')
    if data["smtp_mode"] == "plain" and data.get("smtp_username"):
        raise ValueError('SMTP authentication requires TLS')
    values = {"smtp_host": str(data["smtp_host"]).strip()[:255], "smtp_port": str(port), "smtp_mode": data["smtp_mode"], "smtp_username": str(data.get("smtp_username", ""))[:320], "smtp_from": email_ok(data["smtp_from"])}
    if data.get("smtp_password"):
        values["smtp_password"] = encrypt(data["smtp_password"])
    if data.get("clear_password") == "on":
        values["smtp_password"] = ""
    for key, value in values.items():
        set_config(db, key, value)
    db.commit()
    return redirect("/admin/emails")

@app.post("/admin/mail-templates")
def mail_templates(request: Request, data=Depends(form)):
    require_admin(request)
    values = {"app_name": "Gatearr", "username": 'User', "link": "https://example.com/reset", "minutes": "30"}
    mail_locale = data.get("mail_locale", request.state.locale)
    if mail_locale not in i18n.languages(request.state.db):
        raise ValueError('Invalid language')
    for key in DEFAULTS:
        if key not in data:continue
        value = str(data[key])
        if len(value) > 10000 or (key.endswith("subject") and ("\n" in value or "\r" in value)):
            raise ValueError('Template too long or invalid subject')
        try:
            Template(value).substitute(values)
        except (ValueError, KeyError):
            raise ValueError('Allowed variables: ${app_name}, ${username}, ${link}, ${minutes}')
        if key.endswith("body") and "${link}" not in value:
            raise ValueError('The message body must contain ${link}')
        if mail_locale=='en':
            set_config(request.state.db,key,value)
            if key.endswith('_body'):set_config(request.state.db,key.removesuffix('_body')+'_html','')
        else:
            purpose,part=key.rsplit('_',1)
            i18n.store_content(request.state.db,'mail:'+purpose+':'+part,config(request.state.db,key,DEFAULTS[key]),mail_locale,value)
    request.state.db.commit()
    return redirect("/admin?mail_locale="+mail_locale)

@app.post("/admin/smtp-test")
def smtp_test(request: Request, data=Depends(form)):
    user = require_admin(request)
    limit(request, "smtp_test", str(user.id))
    if not user.email:raise HTTPException(400, "Verify your email in My account before sending a test")
    try:
        send(request.state.db, user.email, "verify", {"app_name": settings.app_name, "username": user.name, "link": config(request.state.db, "public_url", settings.public_url), "minutes": "30", "_locale": user.locale})
    except Exception:
        log.warning("SMTP test failed")
        raise HTTPException(503, 'SMTP failed. Check host, TLS, credentials and sender.')
    return render(request, "message.html", message='Test message sent to the administrator’s address.')

@app.post("/admin/menu")
def menu_save(request: Request, data=Depends(form)):
    require_admin(request)
    db = request.state.db
    item = db.get(MenuItem, int(data["id"])) if data.get("id") else MenuItem()
    if not item:
        raise HTTPException(404, 'Link not found')
    item.label = str(data.get("label_en") or data["label"]).strip()[:100]
    if not item.label:
        raise ValueError('Label required')
    item.label_en = None
    service_key = str(data.get("access_service", ""))
    if service_key and not db.get(AccessService, service_key):
        raise ValueError('Invalid service')
    item.access_service = service_key or None
    item.url = url_ok(data.get("url", ""), optional=bool(service_key))
    from .icons import icon_value
    item.icon_url = icon_value(db,data)
    item.icon = str(data["icon"])[:30]
    item.position = int(data["position"])
    item.new_tab = data.get("new_tab") == "on"
    menu_key = str(data.get("menu_key", "main"))
    if not re.fullmatch(r"[a-z0-9_-]{1,40}", menu_key):
        raise ValueError('Invalid menu ID')
    item.menu_key = menu_key
    db.add(item)
    db.flush()
    if data.get("label_en") and data["label"]!=item.label:i18n.store_content(db,"menu:"+str(item.id)+":label",item.label,"fr",str(data["label"])[:100])
    db.commit()
    return redirect("/admin/services")

@app.post("/admin/menu/delete")
def menu_delete(request: Request, data=Depends(form)):
    require_admin(request)
    db = request.state.db
    db.execute(delete(MenuItem).where(MenuItem.id == int(data["id"])))
    db.commit()
    return redirect("/admin/services")

@app.post("/admin/user-email")
def admin_email(request: Request, data=Depends(form)):
    require_admin(request)
    db = request.state.db
    user = db.get(User, int(data["id"]))
    if not user or not user.emby_id:
        raise HTTPException(404, 'Emby account not found')
    # Imported emails still require proof of mailbox ownership.
    email = email_ok(data["email"])
    language=data.get("locale",user.locale)
    if language not in i18n.languages(db):raise ValueError('Invalid language')
    if not user.active:raise ValueError('Account disabled')
    limit(request,"admin_invitation",str(user.id),maximum=5)
    user.locale=language
    user.preferences_version+=1
    db.commit()
    queue_user(db,user,force=True)
    raw = issue_token(db, user, "verify", email)
    try:
        enqueue_mail(db, "invite", raw, email)
    except Exception:
        log.warning("Administrator verification delivery failed user_id=%s", user.id)
        raise HTTPException(503, 'Unable to send address confirmation')
    return render(request, "message.html", message='Verification invitation queued. The address will be saved after confirmation.')


@app.post("/language")
def change_language(request: Request, data=Depends(form)):
    language = data["locale"]
    if language not in i18n.languages(request.state.db):
        raise ValueError('Invalid language')
    if request.state.user:
        request.state.user.locale = language
        request.state.user.preferences_version+=1
        request.state.db.commit()
        queue_user(request.state.db,request.state.user,force=True)
    target = data.get("next", "/")
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//") or "\\" in target or any(c in target for c in "\r\n"):
        target = "/"
    response = redirect(target)
    response.set_cookie("gatearr_language", language, max_age=31536000, secure=request.state.cookie_secure, samesite="lax", httponly=True)
    return response

from .admin_features import router as features_router
app.include_router(features_router)

from .guides import router as guides_router
app.include_router(guides_router)

from .access import router as access_router
app.include_router(access_router)

from .preferences import router as preferences_router
app.include_router(preferences_router)

from .translations import router as translations_router
app.include_router(translations_router)

from .onboarding import router as onboarding_router
app.include_router(onboarding_router)

from .email_editor import router as email_editor_router
app.include_router(email_editor_router)
