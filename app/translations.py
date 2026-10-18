"""Language management and one translation workspace for interface and authored content."""
import re
from string import Formatter
from urllib.parse import urlencode
from sqlalchemy import delete,select
from fastapi import APIRouter,Depends,HTTPException,Request
from . import i18n,rich_mail
from .main import form,require_admin,render,redirect,set_config
from .models import Config,Language,ContentTranslation
from .content_catalog import sources
router=APIRouter()

def validated_value(key,locale,value,source=None):
    value=value.strip();source=source if source is not None else i18n.CATALOGS['en'][i18n.canonical(key)]
    if len(value)>5000:raise ValueError('Text must not exceed 5000 characters')
    if value:
        def fields(text):
            result=set()
            for literal,field,spec,conversion in Formatter().parse(text):
                if field is not None:
                    if spec or conversion:raise ValueError('Keep the reference placeholders without additional formatting')
                    result.add(field)
            return result
        expected=fields(source);actual=fields(value)
        optional=i18n.canonical(key)=='{app_name} · Your services, one place.'
        if not (actual<=expected if optional else actual==expected):raise ValueError('Keep the reference placeholders without additional formatting')
    return value

def source_link(key):
    parts=key.split(':')
    if parts[0]=='mail':return '/admin/mail-editor?purpose='+parts[1]
    if parts[0]=='guide':return '/admin/guides/'+parts[1]
    if parts[0]=='journey':return '/admin/access/'+parts[1]
    return {'branding':'/admin/branding','menu':'/admin/services','block':'/admin/portal','service':'/admin/guides'}.get(parts[0],'/admin')

@router.get('/admin/translations')
def translations(request:Request):
    require_admin(request);db=request.state.db
    available=i18n.languages(db,all=True)
    locale=request.query_params.get('edit_locale','en')
    if locale not in available:raise HTTPException(400,'Invalid language')
    scope=request.query_params.get('scope','all')
    if scope not in ('all','interface','content','email'):raise HTTPException(400,'Invalid translation section')
    query=request.query_params.get('q','')[:200];page=max(1,int(request.query_params.get('page','1')))
    custom=i18n.overrides(db,locale);rows=[]
    if scope in ('all','interface'):
        for key,source in i18n.CATALOGS['en'].items():
            default=i18n.CATALOGS.get(locale,{}).get(key,'')
            value=custom.get(key,default)
            rows.append({'key':key,'source':source,'default':default,'value':value,'custom':key in custom,'translated':bool(value),'context':'Interface','hash':'','kind':'text','maximum':5000,'scope':'interface'})
    if scope in ('all','content','email'):
        stored={(row.resource,row.source_hash):row.value for row in db.scalars(select(ContentTranslation).where(ContentTranslation.locale==locale))}
        for entry in sources(db):
            if scope!='all' and (entry['key'].startswith('mail:'))!=(scope=='email'):continue
            key=entry['key'];stamp=i18n.source_hash(entry['source']);value=stored.get((key,stamp),'')
            rows.append({**entry,'hash':stamp,'value':value,'default':'','custom':bool(value),'translated':bool(value) or locale=='en','edit_href':source_link(key),'scope':'email' if key.startswith('mail:') else 'content','stale':any(resource==key and old_hash!=stamp for resource,old_hash in stored) and not value})
    for row in rows:row['anchor']=i18n.source_hash(row['key']+'\0'+row['source'])[:16]
    total_sources=len(rows);translated=sum(row['translated'] for row in rows)
    rows=[row for row in rows if query.casefold() in '\n'.join((row['key'],row['source'],row['value'],row['context'])).casefold()]
    rows.sort(key=lambda row:(row['context'],row['source'].casefold()));pages=1;page=1
    def href(number):return '/admin/translations?'+urlencode({'edit_locale':locale,'scope':scope,'q':query,'page':number})
    return render(request,'translations.html',entries=rows,edit_locale=locale,scope=scope,query=query,page=page,pages=pages,total=len(rows),translated=translated,total_sources=total_sources,managed_languages=list(db.scalars(select(Language).order_by(Language.code))),all_languages=available,previous=href(page-1) if page>1 else '',next_page=href(page+1) if page<pages else '')

@router.post('/admin/translations/languages')
def create_language(request:Request,data=Depends(form)):
    require_admin(request);db=request.state.db
    code=str(data.get('code','')).strip().lower();name=str(data.get('name','')).strip()
    if len(code)>10 or not re.fullmatch(r'[a-z]{2,3}(?:-[a-z0-9]{2,6})?',code) or not name or len(name)>80:raise ValueError('Use a language code such as de, es or pt-br and a name')
    if db.get(Language,code):raise HTTPException(409,'This language already exists')
    if len(i18n.languages(db,all=True))>=32:raise ValueError('A maximum of 32 languages is supported')
    db.add(Language(code=code,name=name,enabled=data.get('enabled')=='on'));db.commit()
    return redirect('/admin/translations?edit_locale='+code)

@router.post('/admin/translations/languages/{code}')
def update_language(request:Request,code:str,data=Depends(form)):
    require_admin(request);db=request.state.db;row=db.get(Language,code)
    if not row:raise HTTPException(404,'Language not found')
    name=str(data.get('name',row.name)).strip()
    if not name or len(name)>80:raise ValueError('Invalid language name')
    if code=='en' and data.get('enabled')!='on':raise ValueError('English is the source language and must remain enabled')
    row.name=name;row.enabled=data.get('enabled')=='on';db.commit()
    return redirect('/admin/translations?edit_locale='+code)

@router.post('/admin/translations')
def save(request:Request,data=Depends(form)):
    require_admin(request);db=request.state.db
    locale=str(data.get('edit_locale',''));scope=str(data.get('scope','interface'));key=str(data.get('key',''))
    if locale not in i18n.languages(db,all=True):raise HTTPException(400,'Invalid language')
    action=data.get('action','save')
    if action not in ('save','reset'):raise ValueError('Invalid action')
    raw='' if action=='reset' else str(data.get('value','')).strip()
    if scope=='interface':
        key=i18n.canonical(key)
        if key not in i18n.CATALOGS['en']:raise HTTPException(400,'Unknown translation')
        value=validated_value(key,locale,raw);storage_key=i18n.translation_key(locale,key)
        if value and value!=i18n.CATALOGS.get(locale,{}).get(key):set_config(db,storage_key,value)
        else:db.execute(delete(Config).where(Config.key==storage_key))
    elif scope in ('content','email'):
        if locale=='en':raise ValueError('Edit English source content in its original editor')
        entry=next((item for item in sources(db) if item['key']==key and i18n.source_hash(item['source'])==data.get('source_hash')),None)
        if not entry or (key.startswith('mail:'))!=(scope=='email'):raise HTTPException(409,'The source text has changed. Reload the translation page.')
        if len(raw)>entry['maximum']:raise ValueError('Translation is too long')
        if entry['kind'] in ('html','subject','mail'):value=rich_mail.validate(raw,html=entry['kind']=='html',subject=entry['kind']=='subject') if raw else ''
        else:value=validated_value(key,locale,raw,entry['source'])
        i18n.store_content(db,key,entry['source'],locale,value)
    else:raise ValueError('Invalid translation section')
    db.commit()
    view_scope=data.get('view_scope',scope)
    if view_scope not in ('all','interface','content','email'):view_scope=scope
    return redirect('/admin/translations?'+urlencode({'edit_locale':locale,'scope':view_scope,'q':str(data.get('q',''))[:200]})+'#translation-'+str(data.get('anchor',''))[:16])
