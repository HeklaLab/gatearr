"""Server-owner capability followed by proof of an existing media identity."""
import secrets
from urllib.parse import urlsplit
from fastapi import HTTPException
from sqlalchemy import select,text,delete,update
from .models import Config,Session,User,Token,Language
from .settings import settings
from .security import digest,url_ok
from .mailer import config
from .main import render,redirect,limit,set_config,now,rotate,cookie
from . import i18n
from .emby import EmbyError
from . import main
from .onboarding import connect_media


def page(request):
    if request.state.db.get(Config,'setup_complete'):return redirect('/login')
    return render(request,'setup.html')


def connect(request,data):
    db=request.state.db
    if db.get(Config,'setup_complete'):raise HTTPException(403,'Setup already completed')
    limit(request,'setup')
    if not str(data.get('api_key','')).strip():raise ValueError('API key required')
    name=str(data.get('app_name',settings.app_name)).strip()
    if not name or len(name)>80:raise ValueError('Invalid name')
    public=url_ok(str(data.get('public_url',settings.public_url))).rstrip('/')
    parsed=urlsplit(public)
    if parsed.path or parsed.query or parsed.fragment:raise ValueError('The public URL must be at the domain root')
    if settings.secure_cookie and parsed.scheme!='https':raise ValueError('The public URL must use HTTPS')
    locale=str(data.get("default_locale",i18n.default_language(db)))
    if locale not in i18n.languages(db,all=True) or locale not in i18n.CATALOGS:raise ValueError("Choose a supported language")
    connect_media(db,data)
    db.rollback()
    db.execute(text('BEGIN IMMEDIATE'))
    if db.get(Config,'setup_complete'):raise HTTPException(403,'Setup already completed')
    # Rotate the anonymous session: the setup token never grants an ordinary login.
    db.delete(request.state.session)
    raw=secrets.token_urlsafe(32)
    fingerprint=digest(raw)
    db.add(Session(digest=fingerprint,csrf=secrets.token_urlsafe(32),expires=now()+1800,setup_expires=now()+1800,version=0))
    set_config(db,'onboarding_media_verified','true')
    set_config(db,'setup_owner_digest',fingerprint)
    if 'default_locale' in data:
        for language in db.scalars(select(Language)):language.enabled=language.code==locale
    set_config(db,'default_locale',locale)
    set_config(db,'app_name',name)
    set_config(db,'public_url',public)
    db.commit()
    response=redirect('/setup/admin')
    cookie(response,raw,settings.secure_cookie or parsed.scheme=='https')
    request.state.rotated=True
    return response


def capability(request):
    db=request.state.db
    session=request.state.session
    if db.get(Config,'setup_complete'):raise HTTPException(403,'Setup already completed')
    if not session.setup_expires or session.setup_expires<=now() or not secrets.compare_digest(config(db,'setup_owner_digest'),session.digest):
        raise HTTPException(403,'Restart setup and enter the media server API key')


def administrator_page(request):
    capability(request)
    users=[{'Id':u['Id'],'Name':u['Name']} for u in main.emby.users() if not u.get('Policy',{}).get('IsDisabled')]
    return render(request,'setup_admin.html',media_users=users)


def claim(request,data):
    db=request.state.db
    capability(request)
    limit(request,'setup_admin',str(data.get('user_id','')),maximum=10)
    remote=main.emby.user(str(data.get('user_id','')))
    if remote.get('Policy',{}).get('IsDisabled'):raise HTTPException(401,'Invalid credentials')
    try:proof=main.emby.authenticate(remote['Name'],str(data.get('password','')))['User']
    except EmbyError:raise HTTPException(401,'Invalid credentials')
    if proof.get('Id')!=remote['Id'] or proof.get('Policy',{}).get('IsDisabled'):
        raise HTTPException(401,'Invalid credentials')
    # Serialize the final claim; another browser cannot install a second first admin.
    owner=request.state.session.digest
    db.rollback()
    db.execute(text('BEGIN IMMEDIATE'))
    capability(request)
    if config(db,'setup_owner_digest')!=owner:raise HTTPException(403,'Restart setup and enter the media server API key')
    user=db.scalar(select(User).where(User.emby_id==remote['Id']))
    if not user or not user.active:raise HTTPException(403,'Media account required')
    user.version+=1
    db.execute(delete(Session).where(Session.user_id==user.id))
    db.execute(update(Token).where(Token.user_id==user.id).values(used=True))
    user.admin=True
    user.password_hash=None
    user.locale=request.state.locale
    set_config(db,'setup_complete','true')
    set_config(db,'onboarding_required','true')
    set_config(db,'onboarding_step','seerr')
    db.delete(db.get(Config,'setup_owner_digest'))
    db.commit()
    return rotate(request,user)
