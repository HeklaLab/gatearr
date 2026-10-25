"""Narrow, opt-in additive access to one administrator-selected Bazarr profile.

Bazarr writes all profiles through its settings endpoint. Preserve the complete
snapshot, serialize Gatearr writes, check for intervening edits and read back.
The native API has no conditional-write token; a simultaneous native edit in
its final read/write window cannot be made atomic by this client.
"""
from copy import deepcopy
import json
import re
import threading
import time
from datetime import datetime,timezone
from contextlib import contextmanager
import httpx
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy import text, select
from .models import Config, User, Language
from .mailer import config
from .security import decrypt, digest
from .main import form, require_admin, require_user, redirect, set_config, limit

router=APIRouter()
_write_lock=threading.Lock()
PROFILE_KEYS={'profileId','name','cutoff','items','mustContain','mustNotContain','originalFormat','tag'}


def connection_id(db):
    return digest(json.dumps([config(db,'bazarr_url'),config(db,'bazarr_api_key')]))


def configured(db):
    from .connection_health import configured as connected
    return connected(db,'bazarr')


def offered(db):
    return configured(db) and config(db,'bazarr_subtitles_enabled')=='true' and config(db,'bazarr_subtitles_connection')==connection_id(db) and config(db,'bazarr_subtitles_profile').isdigit()


@contextmanager
def connection(db):
    if not configured(db):raise HTTPException(409,'Configure and enable Bazarr in Applications & API first.')
    from .tools_proxy import prefix
    with httpx.Client(base_url=config(db,'bazarr_url').rstrip('/')+prefix('bazarr')+'/',headers={'X-Api-Key':decrypt(config(db,'bazarr_api_key'))},timeout=8,trust_env=False,follow_redirects=False) as client:
        yield client


def api_request(client,method,path,**kwargs):
    try:
        response=client.request(method,'api/system/'+path,**kwargs)
        if response.status_code in (401,403):raise HTTPException(502,'Bazarr rejected its configured API key.')
        if response.status_code>=300:raise HTTPException(502,'Bazarr could not complete the subtitle-language request.')
        return response.json() if response.content else None
    except (httpx.HTTPError,ValueError) as exc:
        raise HTTPException(502,'Bazarr is unavailable. Try again later.') from exc


def profiles(client,verification=False):
    rows=api_request(client,'GET','languages/profiles')
    valid=isinstance(rows,list) and len(rows)<=2000
    if valid:
        valid=all(isinstance(p,dict) and not (set(p)-PROFILE_KEYS) and PROFILE_KEYS-{'tag'}<=set(p) and type(p['profileId']) is int and isinstance(p['name'],str) and isinstance(p['items'],list) and all(isinstance(i,dict) and type(i.get('id')) is int and isinstance(i.get('language'),str) for i in p['items']) for p in rows)
        valid=valid and len({p['profileId'] for p in rows})==len(rows)
    if not valid:raise HTTPException(502,'Bazarr did not confirm the profile update. Contact your administrator before retrying.' if verification else 'This Bazarr profile format is not supported. No changes were made.')
    return rows


def languages(client,verification=False):
    rows=api_request(client,'GET','languages')
    if not isinstance(rows,list) or not all(isinstance(r,dict) and isinstance(r.get('name'),str) and isinstance(r.get('code2'),str) and re.fullmatch(r'[a-zA-Z]{2,3}(?:-[a-zA-Z]{2,4})?',r['code2']) and 'enabled' in r for r in rows):
        raise HTTPException(502,'Bazarr did not confirm the language activation. Contact your administrator.' if verification else 'This Bazarr language format is not supported. No changes were made.')
    return rows


def selected_profile(db,rows):
    profile=next((p for p in rows if str(p['profileId'])==config(db,'bazarr_subtitles_profile')),None)
    if not profile:raise HTTPException(409,'The shared Bazarr profile is no longer available. Contact your administrator.')
    return profile


def parse_capacity(value):
    if not re.fullmatch(r'\d{1,2}',str(value)) or not 0<=int(value)<=50:
        raise HTTPException(400,'Choose a subtitle-language limit between 0 and 50.')
    return int(value)


def personal_languages(user):
    return json.loads(user.bazarr_subtitle_languages or '[]')


def replacement_policy(db):
    mode=config(db,'bazarr_subtitle_lock_mode','free')
    return {'mode':mode if mode in ('free','days','permanent') else 'permanent','days':int(config(db,'bazarr_subtitle_lock_days','30')),'since':int(config(db,'bazarr_subtitle_policy_since','0'))}


def language_locks(db,user,at=None):
    now=int(time.time()) if at is None else at
    policy=replacement_policy(db);stamps=json.loads(user.bazarr_subtitle_locks or '{}');result={}
    if policy['mode']=='free':return result
    for code in personal_languages(user):
        if code in stamps and stamps[code]==0:continue  # Explicit administrative release.
        start=max(stamps.get(code,policy['since'] or now),policy['since'])
        until=start+policy['days']*86400 if policy['mode']=='days' else None
        if until is None or now<until:
            result[code]={'until':until,'label':datetime.fromtimestamp(until,timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if until else '', 'iso':datetime.fromtimestamp(until,timezone.utc).isoformat() if until else ''}
    return result


def admin_lock_context(db,user):
    choices=[]
    for code,lock in language_locks(db,user).items():
        language=db.get(Language,code)
        choices.append({'code':code,'name':language.name if language else code.upper(),**lock})
    return {'visible':replacement_policy(db)['mode']!='free' and bool(personal_languages(user)),'choices':choices}


def account_context(db,user):
    if not user or not user.bazarr_subtitles or not offered(db):return None
    result={'error':'','profile':None,'languages':[],'selected':personal_languages(user),'limit':user.bazarr_subtitle_limit,'version':user.bazarr_subtitle_version,'connection':connection_id(db),'locks':language_locks(db,user)}
    try:
        with connection(db) as client:
            profile=selected_profile(db,profiles(client));catalog=languages(client)
        # Never filter based on the shared profile or another person's choices.
        # Include an unavailable personal choice so it can still be removed.
        known={r['code2'] for r in catalog}
        result.update(profile=profile,languages=catalog+[{'code2':code,'name':code,'enabled':False} for code in result['selected'] if code not in known])
    except HTTPException:return None
    return result


@router.get('/admin/bazarr/subtitle-profiles')
def profile_options(request:Request):
    require_admin(request)
    with connection(request.state.db) as client:rows=profiles(client)
    return {'profiles':[{'id':row['profileId'],'name':row['name']} for row in rows]}


@router.post('/admin/bazarr/subtitles')
def configure(request:Request,data=Depends(form)):
    require_admin(request);db=request.state.db
    active=data.get('enabled')=='on'
    mode=str(data.get('lock_mode',config(db,'bazarr_subtitle_lock_mode','free')))
    days=str(data.get('lock_days',config(db,'bazarr_subtitle_lock_days','30')))
    if mode not in ('free','days','permanent') or not re.fullmatch(r'\d{1,4}',days) or not 1<=int(days)<=3650:raise HTTPException(400,'Choose a valid subtitle replacement policy and a duration between 1 and 3650 days.')
    previous=replacement_policy(db)
    if active:
        fingerprint=connection_id(db)
        with connection(db) as client:rows=profiles(client)
        chosen=next((p for p in rows if str(p['profileId'])==str(data.get('profile_id',''))),None)
        if not chosen:raise HTTPException(400,'Select an existing Bazarr language profile.')
        set_config(db,'bazarr_subtitles_profile',str(chosen['profileId']))
        set_config(db,'bazarr_subtitles_profile_name',chosen['name'])
        set_config(db,'bazarr_subtitles_connection',fingerprint)
    if mode!=previous['mode'] or (mode=='days' and int(days)!=previous['days']):set_config(db,'bazarr_subtitle_policy_since',str(int(time.time())))
    set_config(db,'bazarr_subtitle_lock_mode',mode);set_config(db,'bazarr_subtitle_lock_days',str(int(days)))
    set_config(db,'bazarr_subtitles_enabled','true' if active else 'false');db.commit()
    return redirect('/admin/integrations?connection=bazarr#connection-bazarr')


@router.post('/account/subtitles/language')
def save_languages(request:Request,data=Depends(form)):
    user=require_user(request);db=request.state.db
    if getattr(request.state,'support',None):raise HTTPException(403,'End assistance before changing shared subtitle languages.')
    if not user.bazarr_subtitles:raise HTTPException(403,'Subtitle-language permission required.')
    limit(request,'bazarr-subtitle-language',str(user.id),maximum=30,window=3600)
    with _write_lock:
        uid=user.id;db.rollback()
        if db.bind.dialect.name=='sqlite':db.execute(text('BEGIN IMMEDIATE'))
        else:db.execute(select(User).where(User.id==uid).with_for_update());db.execute(select(Config).where(Config.key=='bazarr_subtitles_profile').with_for_update())
        db.expire_all();user=db.get(User,uid)
        if not user or not user.active or user.portal_disabled or not user.bazarr_subtitles:raise HTTPException(403,'Subtitle-language permission required.')
        if not offered(db):raise HTTPException(409,'Subtitle-language requests are not enabled. Contact your administrator.')
        if data.get('profile_id')!=config(db,'bazarr_subtitles_profile') or data.get('connection')!=connection_id(db):raise HTTPException(409,'Bazarr settings changed. Reload your account page.')
        if str(data.get('subtitle_version',''))!=str(user.bazarr_subtitle_version):raise HTTPException(409,'Your subtitle preferences changed. Reload your account page.')
        submitted=data.getlist('languages')
        selected=list(dict.fromkeys(str(code) for code in submitted))
        if len(submitted)>50 or len(selected)>user.bazarr_subtitle_limit:raise HTTPException(400,'Your subtitle-language limit has been reached.')
        previous=personal_languages(user)
        if set(language_locks(db,user))-set(selected):raise HTTPException(409,'Some subtitle languages are locked. Wait until their unlock date or contact your administrator.')
        # A purely personal removal never needs a remote write or removes a
        # shared language that another person may still need.
        if set(selected)-set(previous):
            with connection(db) as client:
                original=profiles(client);profile=selected_profile(db,original);catalog=languages(client)
                if not set(selected)<={r['code2'] for r in catalog}:raise HTTPException(400,'Select a language offered by Bazarr.')
                existing={item['language'] for item in profile['items']}
                missing=[code for code in selected if code not in existing]
                if missing:
                    updated=deepcopy(original);target=next(p for p in updated if p['profileId']==profile['profileId'])
                    next_id=max([0]+[i['id'] for i in target['items']])+1
                    for code in missing:
                        target['items'].append({'id':next_id,'language':code,'forced':'False','hi':'False','audio_exclude':'False','audio_only_include':'False'});next_id+=1
                    if profiles(client)!=original or languages(client)!=catalog:raise HTTPException(409,'Bazarr profiles changed. Reload your account page and try again.')
                    payload={'languages-profiles':json.dumps(updated)}
                    enabled=[r['code2'] for r in catalog if r['enabled']]
                    if set(missing)-set(enabled):payload['languages-enabled']=list(dict.fromkeys(enabled+missing))
                    api_request(client,'POST','settings',data=payload)
                    verified=profiles(client,verification=True)
                    if sorted(verified,key=lambda p:p['profileId'])!=sorted(updated,key=lambda p:p['profileId']):raise HTTPException(502,'Bazarr did not confirm the profile update. Contact your administrator before retrying.')
                    if not set(missing)<={r['code2'] for r in languages(client,verification=True) if r['enabled']}:raise HTTPException(502,'Bazarr did not confirm the language activation. Contact your administrator.')
        stamps=json.loads(user.bazarr_subtitle_locks or '{}');now=int(time.time())
        user.bazarr_subtitle_locks=json.dumps({code:stamps.get(code,now) if code in previous else now for code in selected})
        user.bazarr_subtitle_languages=json.dumps(selected);user.bazarr_subtitle_version+=1
        request.state.audit_detail='Personal subtitle languages: '+', '.join(selected)
        db.commit()
    return redirect('/account?saved=subtitle-languages')


@router.post('/admin/users/{uid}/subtitle-unlock')
def unlock_language(request:Request,uid:int,data=Depends(form)):
    actor_id=require_admin(request).id;db=request.state.db
    with _write_lock:
        db.rollback()
        if db.bind.dialect.name=='sqlite':db.execute(text('BEGIN IMMEDIATE'))
        actor=db.get(User,actor_id)
        if not actor or not actor.admin or not actor.active or not actor.emby_id:raise HTTPException(403,'Administrator access required')
        user=db.get(User,uid,with_for_update=db.bind.dialect.name!='sqlite')
        if not user:raise HTTPException(404,'User not found')
        code=str(data.get('language',''))
        if code not in personal_languages(user):raise HTTPException(400,'Select a subtitle language currently saved by this user.')
        stamps=json.loads(user.bazarr_subtitle_locks or '{}');stamps[code]=0
        user.bazarr_subtitle_locks=json.dumps(stamps);user.bazarr_subtitle_version+=1
        request.state.audit_subject=uid;request.state.audit_detail='Subtitle replacement unlocked: '+code
        db.commit()
    return redirect('/admin/users/'+str(uid)+'?tab=access')
