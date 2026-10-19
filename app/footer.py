"""Global, translated footer content with independent draft/publish control."""
import json, re, secrets
from copy import deepcopy
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert
from .models import Config
from .mailer import config
from .security import url_ok
from .icons import icon_value
from . import i18n
from .main import form, require_admin, render, redirect
router = APIRouter()
DEFAULT = {'alignment':'left','enabled':True,'items':[{'id':'signature','kind':'text','text':'{app_name} · Your services, one place.','url':'','icon_url':'','position':10,'new_tab':False}]}

def validate(value):
    if value.get('alignment') not in ('left','center','right') or type(value.get('enabled')) is not bool: raise ValueError('Invalid footer')
    items=value.get('items')
    if not isinstance(items,list) or len(items)>30: raise ValueError('A footer supports up to 30 items')
    identifiers=set()
    for item in items:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',item.get('id','')) or item['id'] in identifiers: raise ValueError('Invalid footer item')
        identifiers.add(item['id'])
        if item.get('kind') not in ('text','link','logo') or type(item.get('position')) is not int or type(item.get('new_tab')) is not bool: raise ValueError('Invalid footer item')
        if not isinstance(item.get('text'),str) or not item['text'].strip() or len(item['text'])>2000: raise ValueError('Footer text required (up to 2000 characters)')
        url_ok(item.get('url',''),optional=item['kind']!='link')
        image=item.get('icon_url','')
        if item['kind']=='logo' and not image: raise ValueError('Choose a logo')
        if image and not re.fullmatch(r'/media/icons/[a-f0-9]{64}\.png',image): url_ok(image)
    return value

def load(db,draft=False):
    raw=config(db,'footer_draft' if draft else 'footer_published')
    return validate(json.loads(raw)) if raw else deepcopy(DEFAULT)

def version(db): return int(config(db,'footer_version','0'))

def save(db,value,expected,publish=False):
    validate(value)
    db.execute(insert(Config).values(key='footer_version',value='0').on_conflict_do_nothing())
    result=db.execute(update(Config).where(Config.key=='footer_version',Config.value==str(expected)).values(value=str(expected+1)))
    if result.rowcount!=1:
        db.rollback();raise HTTPException(409,'The footer has changed. Reload the builder.')
    for key in (('footer_draft','footer_published') if publish else ('footer_draft',)):
        encoded=json.dumps(value,ensure_ascii=False)
        db.execute(insert(Config).values(key=key,value=encoded).on_conflict_do_update(index_elements=['key'],set_={'value':encoded}))
    db.commit()

def display(db,value,locale,app_name):
    value=deepcopy(value)
    for item in value['items']:
        source=item['text'];text=i18n.content(db,'footer:'+item['id']+':text',source,locale)
        if item['id']=='signature' and source==DEFAULT['items'][0]['text'] and text==source:
            text=i18n.translate(source,locale,overrides=i18n.overrides(db,locale),base_overrides=i18n.overrides(db,'en'),app_name=app_name)
        item['text']=text.replace('{app_name}',app_name)
    value['items'].sort(key=lambda item:(item['position'],item['id']))
    return value

@router.get('/admin/footer')
def editor(request: Request):
    require_admin(request)
    return render(request,'footer_editor.html',footer_draft=load(request.state.db,True),footer_version=version(request.state.db))

@router.get('/admin/footer/preview')
def preview(request: Request):
    require_admin(request)
    return render(request,'home.html',footer_layout=load(request.state.db,True),footer_preview=True,preview=False)

@router.post('/admin/footer')
def edit(request: Request,data=Depends(form)):
    require_admin(request)
    db=request.state.db;value=load(db,True);action=data.get('action','save');expected=int(data.get('version','-1'))
    if action=='publish':save(db,value,expected,True)
    elif action=='reset':save(db,load(db),expected)
    elif action=='settings':
        value.update(alignment=str(data.get('alignment','left')),enabled=data.get('enabled')=='on');save(db,value,expected)
    elif action=='delete':
        value['items']=[item for item in value['items'] if item['id']!=data.get('id')];save(db,value,expected)
    elif action=='save':
        ident=str(data.get('id') or secrets.token_hex(8))
        if data.get('id') and not any(item['id']==ident for item in value['items']):raise HTTPException(404,'Footer item not found')
        item={'id':ident,'kind':str(data.get('kind','text')),'text':str(data.get('text','')).strip(),'url':str(data.get('url','')).strip(),'icon_url':icon_value(db,data),'position':int(data.get('position','10')),'new_tab':data.get('new_tab')=='on'}
        value['items']=[old for old in value['items'] if old['id']!=ident]+[item];save(db,value,expected)
    else:raise ValueError('Invalid action')
    return redirect('/admin/footer')
