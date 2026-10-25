"""Persistent fictitious Bazarr API. Imported only by the local demo runner."""
import json
import os
import sqlite3
from contextlib import contextmanager
from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import HTMLResponse
router=APIRouter(prefix='/tools/bazarr/app')

def profile(pid,name,codes):
    return {'profileId':pid,'name':name,'cutoff':None,'items':[{'id':i+1,'language':code,'forced':'False','hi':'False','audio_exclude':'False','audio_only_include':'False'} for i,code in enumerate(codes)],'mustContain':[],'mustNotContain':[],'originalFormat':0,'tag':None}


@contextmanager
def state():
    db=sqlite3.connect(os.environ.get('MOCK_DB','/data/mock.db'))
    db.execute('create table if not exists bazarr_demo_state (id integer primary key, payload text not null)')
    if not db.execute('select 1 from bazarr_demo_state where id=1').fetchone():
        payload={'profiles':[profile(1,'Gatearr · Shared subtitles',['en','fr','de']),profile(2,'Original versions',['es'])],'languages':[{'code2':code,'name':name,'enabled':code in ('en','fr','de','es')} for code,name in [('en','English'),('fr','French'),('de','German'),('es','Spanish'),('it','Italian'),('pt','Portuguese'),('ja','Japanese'),('is','Icelandic')]]}
        db.execute('insert into bazarr_demo_state values (1,?)',(json.dumps(payload),));db.commit()
    try:yield db
    finally:db.close()


def authenticate(request):
    if request.headers.get('X-Api-Key')!='demo-bazarr-key':raise HTTPException(401)


def read():
    with state() as db:return json.loads(db.execute('select payload from bazarr_demo_state where id=1').fetchone()[0])


@router.get('/api/system/status')
def status(request:Request):
    authenticate(request);return {'bazarr_version':'local-demo','demo':True}


@router.get('/api/system/languages/profiles')
def profiles(request:Request):authenticate(request);return read()['profiles']


@router.get('/api/system/languages')
def languages(request:Request):authenticate(request);return read()['languages']


@router.post('/api/system/settings')
async def settings(request:Request):
    authenticate(request);data=await request.form()
    with state() as db:
        payload=json.loads(db.execute('select payload from bazarr_demo_state where id=1').fetchone()[0])
        if 'languages-profiles' in data:payload['profiles']=json.loads(data['languages-profiles'])
        if 'languages-enabled' in data:
            for language in payload['languages']:language['enabled']=language['code2'] in data.getlist('languages-enabled')
        db.execute('update bazarr_demo_state set payload=? where id=1',(json.dumps(payload),));db.commit()
    return Response(status_code=204)


@router.get('/')
def interface():return HTMLResponse('<h1>Bazarr · Local demo</h1><p>Fictitious subtitle profiles. No media files or actual subtitle downloads.</p>')
