"""English source catalog with database-managed languages and content translations."""
import json,hashlib
from pathlib import Path
from sqlalchemy import select
from .models import Config,Language,ContentTranslation

ROOT=Path(__file__).parent
CATALOGS={'en':json.loads((ROOT/'locales/en.json').read_text())}
LEGACY_KEYS=json.loads((ROOT/'legacy_i18n.json').read_text())
BASE_LANGUAGE='en'

def canonical(message):return LEGACY_KEYS.get(str(message),str(message))
def source_hash(value):return hashlib.sha256(value.encode()).hexdigest()

def languages(db,all=False):
    rows=db.scalars(select(Language).order_by(Language.code))
    return {row.code:row.name for row in rows if row.enabled or all or row.code==BASE_LANGUAGE}

def translate(message,locale=BASE_LANGUAGE,*,overrides=None,base_overrides=None,**values):
    key=canonical(message)
    translated=(overrides or {}).get(key) or CATALOGS.get(locale,{}).get(key) or (base_overrides or {}).get(key) or CATALOGS[BASE_LANGUAGE].get(key,key)
    return translated.format(**values) if values else translated

def resolve(request,user=None):
    available=languages(request.state.db)
    if user:return user.locale if user.locale in available else BASE_LANGUAGE
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
    return BASE_LANGUAGE

ACCOUNT_LABEL_KEYS={'newsletter':'Receive the newsletter','requests':'Receive notifications about my requests'}
ACCOUNT_LABEL_DEFAULTS={'en':ACCOUNT_LABEL_KEYS}

def translation_key(locale,message):return 'ui_translation_'+locale+'_'+source_hash(canonical(message))

def overrides(db,locale):
    names={translation_key(locale,key):key for key in CATALOGS['en']}
    return {names[row.key]:row.value for row in db.scalars(select(Config).where(Config.key.like('ui_translation_'+locale+'_%'))) if row.key in names and row.value}

def content(db,resource,source,locale):
    if not source or locale==BASE_LANGUAGE:return source
    row=db.get(ContentTranslation,(locale,resource,source_hash(source)))
    return row.value if row and row.value else source

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
