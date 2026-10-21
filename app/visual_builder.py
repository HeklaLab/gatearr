"""One visual workspace for public login, member home and shared footer.
All previews are admin-only, validated and transient; saves use revision leases.
"""
import json
from copy import deepcopy
from fastapi import APIRouter,Request,Depends,HTTPException
from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert
from .main import form,require_admin,render,redirect
from .models import Config,AccessService,MenuItem
from sqlalchemy import select
from .mailer import config
from . import portal,footer
from .applications import catalog
from .page_design import validate_style,asset_url
router=APIRouter()
PAGES=('home','login','footer')

def login_default(db):
    legacy=portal.load(db)
    intro={'id':'login-intro','kind':'welcome','region':'main','order':10,'span':6,'title':'Everything starts here.','body':config(db,'login_text','Access your services and manage your account with ease.')}
    blocks=[intro,{'id':'sign-in','kind':'login_form','region':'main','order':20,'span':6,'title':'Welcome','body':''}]
    blocks += [{**b,'region':'main','order':30+i*10} for i,b in enumerate(legacy['blocks']) if b['region']=='login']
    return {'page':'login','nav_position':'top','sidebar_position':'left','theme':deepcopy(legacy['theme']),'colors':{},'blocks':blocks,'show_header':True}

def load(db,page,draft=False):
    if page not in PAGES:raise HTTPException(404,'Page not found')
    if page=='home':return {**portal.load(db,draft),'page':'home'}
    if page=='login':
        raw=config(db,'login_draft' if draft else 'login_published')
        return portal.validate(json.loads(raw)) if raw else login_default(db)
    value=footer.editor_value(db,draft)
    if 'design' in value:return portal.validate(deepcopy(value['design']))
    columns=value.get('columns')
    if columns is None:
        # Convert legacy footer safely through its existing HTML conversion.
        import html
        columns=[''.join('<p>'+html.escape(item['text'])+'</p>' for item in value['items'])]
    block={'id':'footer-columns','kind':'columns','region':'main','order':10,'span':12,'columns':len(columns),'title':'','body':''}
    blocks=[block]+[{'id':'footer-column-'+str(i),'parent':block['id'],'slot':i,'kind':'text','region':'main','order':(i+2)*10,'span':12,'title':'','body':text,'rich':True} for i,text in enumerate(columns)]
    return {'page':'footer','nav_position':'top','sidebar_position':'left','theme':deepcopy(portal.DEFAULT['theme']),'colors':{},'blocks':blocks,'show_header':False}

def version(db,page):return footer.version(db) if page=='footer' else portal.version(db) if page=='home' else int(config(db,'login_version','0'))

def validate(db,page,value):
    if not isinstance(value,dict):raise ValueError('Invalid page')
    value=deepcopy(value);value['page']=page;portal.validate(value)
    login_forms=sum(b['kind']=='login_form' for b in value['blocks'])
    if (page=='login' and login_forms!=1) or (page!='login' and login_forms):raise ValueError('The sign-in page must contain exactly one sign-in form')
    if page=='login' and any(b['kind'] in ('services','account','guides','application','applications') or b.get('visibility','everyone')!='everyone' for b in value['blocks']):raise ValueError('Use public blocks on the sign-in page')
    for b in value['blocks']:
        if b['kind']=='application' and b.get('service_key','emby') not in ('radarr','sonarr','bazarr') and not db.get(AccessService,b.get('service_key','emby')):raise ValueError('Invalid service')
        if b['kind']=='image':asset_url(b['url'],db)
        if b.get('rich'):b['body']=footer.clean_html(b.get('body',''))
    return value

def save(db,page,value,expected,publish=False):
    value=validate(db,page,value)
    if page=='home':
        try:return portal.save(db,value,expected,publish)
        except ValueError as e:
            if 'has changed' in str(e):raise HTTPException(409,'The page has changed. Reload the builder.')
            raise
    if page=='footer':
        raw=footer.load(db,True);raw['design']=value;raw['alignment']='center'
        return footer.save(db,raw,expected,publish)
    for b in value['blocks']:
        from . import i18n
        i18n.normalize_fields(db,b,'login-block:'+b['id'],('title','body','alt'))
    db.execute(insert(Config).values(key='login_version',value='0').on_conflict_do_nothing())
    result=db.execute(update(Config).where(Config.key=='login_version',Config.value==str(expected)).values(value=str(expected+1)))
    if result.rowcount!=1:db.rollback();raise HTTPException(409,'The page has changed. Reload the builder.')
    raw=json.dumps(value,ensure_ascii=False)
    for key in (('login_draft','login_published') if publish else ('login_draft',)):
        db.execute(insert(Config).values(key=key,value=raw).on_conflict_do_update(index_elements=['key'],set_={'value':raw}))
    db.commit()

def editor(request,page='home'):
    require_admin(request);db=request.state.db
    from .themes import load as themes
    return render(request,'visual_builder.html',builder_data={'page':page,'layout':load(db,page,True),'version':version(db,page),'palette':themes(db)['dark'],'services':catalog(db,editor=True),'menus':sorted({'main',*(m.menu_key for m in db.scalars(select(MenuItem)))})},builder_page=page)

@router.get('/admin/design/{page}')
def design(request:Request,page:str):return editor(request,page)

@router.post('/admin/design/{page}/{action}')
def edit(request:Request,page:str,action:str,data=Depends(form)):
    require_admin(request);db=request.state.db
    if page not in PAGES or action not in ('save','preview','publish','restore'):raise HTTPException(404,'Page not found')
    try:value=json.loads(data.get('payload','{}'))
    except (ValueError,TypeError):raise HTTPException(400,'Invalid page')
    value=validate(db,page,load(db,page) if action=='restore' else value)
    if action=='preview':
        if page=='footer':
            f=footer.load(db);f['design']=value;f['enabled']=True
            return render(request,'footer_preview.html',layout=value,footer_layout=f,visual_preview=True)
        return render(request,'login.html' if page=='login' else 'home.html',layout=value,visual_preview=True,anonymous_preview=page=='login')
    save(db,page,value,int(data.get('version','-1')),action=='publish')
    request.state.audit_action='POST /admin/design/'+page+'/'+action
    request.state.audit_detail={'login':'Login screen','home':'Portal','footer':'Footer'}[page]+' · '+str(len(value['blocks']))+' blocks'

    return {'version':version(db,page),'layout':value}

@router.post('/admin/applications/order')
def application_order(request:Request,data=Depends(form)):
    require_admin(request);db=request.state.db
    try:identifiers=json.loads(data.get('payload','{}'))['ids']
    except (ValueError,KeyError,TypeError):raise ValueError('Invalid application order')
    rows=list(db.scalars(select(MenuItem)))
    if not isinstance(identifiers,list) or any(type(i) is not int for i in identifiers) or len(set(identifiers))!=len(identifiers) or set(identifiers)!={r.id for r in rows}:raise ValueError('Reload the application list before reordering')
    expected=int(data.get('version','-1'))
    db.execute(insert(Config).values(key='menu_version',value='0').on_conflict_do_nothing())
    result=db.execute(update(Config).where(Config.key=='menu_version',Config.value==str(expected)).values(value=str(expected+1)))
    if result.rowcount!=1:db.rollback();raise HTTPException(409,'The application list changed. Reload this page.')
    for row in rows:row.position=(identifiers.index(row.id)+1)*10
    db.commit();request.state.audit_detail='Reordered applications: '+', '.join(next(r.label for r in rows if r.id==i) for i in identifiers)
    return {'version':expected+1}

@router.get('/admin/design/home/howto/{key}')
def howto(request:Request,key:str):
    if key in ('radarr','sonarr','bazarr'):raise HTTPException(400,'How to is unavailable for this application')
    from .visual_howto import howto_editor
    return howto_editor(request,key)

@router.get('/admin/design/home/guide/{guide_id}')
def guide(request:Request,guide_id:int):
    from .visual_howto import guide_editor
    return guide_editor(request,guide_id)

@router.post('/admin/design/home/enable-howto/{item_id}')
def enable_howto(request:Request,item_id:int,data=Depends(form)):
    require_admin(request);db=request.state.db;item=db.get(MenuItem,item_id)
    if not item:raise HTTPException(404,'Application not found')
    if item.label.strip().casefold() in ('radarr','sonarr','bazarr'):raise HTTPException(400,'How to is unavailable for this application')
    key=item.access_service
    if not key:
        key='service-'+str(item.id)
        service=db.get(AccessService,key)
        if not service:
            service=AccessService(key=key,name=item.label,browser_url=item.url,server_url=item.url,icon=item.icon,icon_url=item.icon_url,entry_mode='direct',access_version=0,access_draft='[]',access_published='[]');db.add(service)
        item.access_service=key;db.commit()
    return {'url':'/admin/design/home/howto/'+key}

@router.post('/admin/design/home/application/{key}/behavior')
def application_behavior(request:Request,key:str,data=Depends(form)):
    require_admin(request);db=request.state.db
    if key in ('radarr','sonarr','bazarr'):raise HTTPException(400,'Access guides are unavailable for admin tools')
    service=db.get(AccessService,key)
    if not service:raise HTTPException(404,'Application not found')
    mode=data.get('mode')
    if mode not in ('direct','structured'):raise ValueError('Invalid application behavior')
    service.entry_mode=mode;db.commit()
    return {'mode':mode}

@router.get('/admin/access-guides')
def guide_index(request:Request):
    require_admin(request)
    return render(request,'access_guides_index.html',guide_apps=[a for a in catalog(request.state.db,editor=True) if a.get('howto')])
