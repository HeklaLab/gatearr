"""English source catalog with database-managed languages and content translations."""
import json,hashlib
from pathlib import Path
from sqlalchemy import select
from .models import Config,Language,ContentTranslation

ROOT=Path(__file__).parent
CATALOGS={p.stem:json.loads(p.read_text()) for p in (ROOT/'locales').glob('*.json') if p.stem!='languages'}
LEGACY_KEYS=json.loads((ROOT/'legacy_i18n.json').read_text())
BASE_LANGUAGE='en'
PUBLIC_INTERFACE_KEYS=frozenset(json.loads((ROOT/'public_interface_keys.json').read_text()))
INTERFACE_KEYS=frozenset(json.loads((ROOT/'interface_keys.json').read_text()))

def canonical(message):return LEGACY_KEYS.get(str(message),str(message))
def source_hash(value):return hashlib.sha256(value.encode()).hexdigest()

def languages(db,all=False):
    rows=db.scalars(select(Language).order_by(Language.code))
    return {row.code:row.name for row in rows if row.enabled or all}

def default_language(db):
    from .mailer import config
    available=languages(db)
    chosen=config(db,'default_locale','en')
    return chosen if chosen in available else next(iter(available),'en')

def translate(message,locale=BASE_LANGUAGE,*,overrides=None,base_overrides=None,source_locale=BASE_LANGUAGE,**values):
    key=canonical(message)
    translated=(overrides or {}).get(key) or CATALOGS.get(locale,{}).get(key) or (base_overrides or {}).get(key) or CATALOGS.get(source_locale,{}).get(key) or CATALOGS[BASE_LANGUAGE].get(key,key)
    return translated.format(**values) if values else translated

def resolve(request,user=None):
    available=languages(request.state.db)
    if user:return user_language(request.state.db,user)
    selected=request.cookies.get('gatearr_language')
    if selected in available:return selected
    candidates=[]
    for part in request.headers.get('accept-language','').split(','):
        pieces=part.strip().lower().split(';');code=pieces[0]
        code=code if code in available else code.split('-')[0]
        try:quality=float(next((item.strip()[2:] for item in pieces[1:] if item.strip().startswith('q=')),'1'))
        except ValueError:continue
        if code in available and 0<quality<=1:candidates.append((quality,code))
    if candidates:return sorted(candidates,key=lambda item:item[0],reverse=True)[0][1]
    return default_language(request.state.db)

def language_policy(db):
    from .mailer import config
    return 'group' if config(db,'language_policy','user')=='group' else 'user'

def user_language(db,user):
    """Effective language without overwriting the saved personal preference."""
    if language_policy(db)=='group':
        from .group_access import group_for
        group=group_for(db,user)
        selected=group.locale if group else None
    else:selected=user.locale if user else None
    return selected if selected in languages(db) else default_language(db)

def require_personal_language(db):
    from fastapi import HTTPException
    if language_policy(db)=='group':raise HTTPException(409,'Language is managed by your group.')

def queue_language_sync(db,users=None):
    from .models import User
    from .integrations import queue_user
    for user in users if users is not None else db.scalars(select(User).where(User.active.is_(True))):
        queue_user(db,user,force=True)

ACCOUNT_LABEL_KEYS={'requests':'Receive notifications about my requests'}
ACCOUNT_LABEL_DEFAULTS={'en':ACCOUNT_LABEL_KEYS}

def translation_key(locale,message):return 'ui_translation_'+locale+'_'+source_hash(canonical(message))

def overrides(db,locale):
    names={translation_key(locale,key):key for key in PUBLIC_INTERFACE_KEYS}
    return {names[row.key]:row.value for row in db.scalars(select(Config).where(Config.key.like('ui_translation_'+locale+'_%'))) if row.key in names and row.value}

def content(db,resource,source,locale):
    if not source:return source
    row=db.get(ContentTranslation,(locale,resource,source_hash(source)))
    if row and row.value:return row.value
    if resource=='login-block:login-intro:body':
        from .mailer import config
        if source==config(db,'login_text','Access your services and manage your account with ease.'):
            old=db.get(ContentTranslation,(locale,'branding:login_text',source_hash(source)))
            if old and old.value:return old.value
    translated=builtin_content(db,source,locale)
    if translated:return translated
    base=default_language(db)
    if base!=locale:
        fallback=db.get(ContentTranslation,(base,resource,source_hash(source)))
        if fallback and fallback.value:return fallback.value
        return CATALOGS.get(base,{}).get(source,source)
    return source

def builtin_content(db,source,locale):
    if source in ('{page_title}','{app_name}'):return source
    translated=CATALOGS.get(locale,{}).get(source)
    if translated:return translated
    if source.endswith(' access guides'):
        from .models import AccessService
        name=source[:-len(' access guides')]
        if db.scalar(select(AccessService.key).where(AccessService.name==name)):
            return translate('{app} access guides',locale,app=name)
    return ''


def store_content(db,resource,source,locale,value):
    key=(locale,resource,source_hash(source));row=db.get(ContentTranslation,key)
    if not value or value==source:
        if row:db.delete(row)
    elif row:row.value=value
    else:db.add(ContentTranslation(locale=locale,resource=resource,source_hash=key[2],value=value))

def normalize_fields(db,value,resource,fields):
    """Read old API payloads without storing paired language fields in the new model."""
    for field in fields:
        base=str(value.get(field,value.get(field+'_en') or value.get(field+'_fr') or ''))
        old=value.get(field+'_fr')
        if old and old!=base:store_content(db,resource+':'+field,base,'fr',str(old))
        value[field]=base
        value.pop(field+'_fr',None);value.pop(field+'_en',None)
    return value


def language_flag(code):
    region={'en':'GB','fr':'FR','de':'DE','es':'ES','it':'IT','pt-br':'BR','pt':'PT','nl':'NL','da':'DK','sv':'SE','nb':'NO','fi':'FI','cs':'CZ','pl':'PL','uk':'UA','ru':'RU','tr':'TR','ar':'SA','he':'IL','ja':'JP','ko':'KR','zh-cn':'CN','el':'GR','ro':'RO','hu':'HU','bg':'BG','sk':'SK','hr':'HR','id':'ID','vi':'VN','th':'TH','hi':'IN','is':'IS'}.get(code.lower())
    return ''.join(chr(127397+ord(c)) for c in region) if region else '🌐'
