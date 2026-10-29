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
PAGES=('home','login','forgot','reset','account','footer','header')
SYSTEM_FORMS={'login':'login_form','forgot':'forgot_form','reset':'reset_form'}

def login_default(db):
    legacy=portal.load(db)
    intro={'id':'login-intro','kind':'welcome','region':'main','order':10,'span':6,'title':'Everything starts here.','body':config(db,'login_text','Access your services and manage your account with ease.')}
    blocks=[intro,{'id':'sign-in','kind':'login_form','region':'main','order':20,'span':6,'title':'Welcome','body':''}]
    blocks += [{**b,'region':'main','order':30+i*10} for i,b in enumerate(legacy['blocks']) if b['region']=='login']
    return {'page':'login','nav_position':'top','sidebar_position':'left','theme':deepcopy(legacy['theme']),'colors':{},'blocks':blocks,'show_header':True}

def system_default(db,page):
    if page=='login':return login_default(db)
    value=login_default(db);value['page']=page
    if page=='account':
        from .account_blocks import default_blocks
        value['blocks']=default_blocks();return value
    value['blocks']=[dict(id=page+'-form',kind=SYSTEM_FORMS[page],region='main',order=10,span=12,title='A fresh start.' if page=='forgot' else 'New password',body='Enter the verified email address of your Emby account. You will receive a link valid for 30 minutes.' if page=='forgot' else '')]
    return value

def _load(db,page,draft=False):
    if page not in PAGES:
        from .page_builder import row_for
        row=row_for(db,page)
        raw=row.draft if draft else row.published
        if not raw:raise HTTPException(404,'Page not found')
        return dict(json.loads(raw),page=page)
    if page=='header':return __import__('app.header',fromlist=['load']).load(db,draft)
    if page=='home':return {**portal.load(db,draft),'page':'home'}
    if page in SYSTEM_FORMS or page=='account':
        raw=config(db,page+('_draft' if draft else '_published'))
        return portal.validate(json.loads(raw)) if raw else system_default(db,page)
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

def load(db,page,draft=False):
    from .image_blocks import normalize
    value=normalize(_load(db,page,draft))
    return __import__('app.account_blocks',fromlist=['normalize']).normalize(value) if page=='account' else value

def version(db,page):
    if page not in PAGES:
        from .page_builder import row_for
        return row_for(db,page).version
    return footer.version(db) if page=='footer' else portal.version(db) if page=='home' else int(config(db,page+'_version','0'))

def validate(db,page,value):
    if not isinstance(value,dict):raise ValueError('Invalid page')
    from .page_builder import is_access_guide
    access_page=is_access_guide(db,page)
    value=deepcopy(value);value['page']=page
    if page=='header':
        from . import header
        value=header.normalize(value);header.validate(value)
    elif any(b['kind'] in ('header_container','header_navigation','header_account') for b in value.get('blocks',[])):raise ValueError('Header blocks are only available in the header builder.')
    from .account_blocks import KINDS as ACCOUNT_KINDS,normalize as normalize_account
    if page=='account':value=normalize_account(value)
    if page!='account' and any(b['kind'] in ACCOUNT_KINDS or b['kind']=='account_form' for b in value.get('blocks',[])):raise ValueError('Account blocks are only available on My account.')
    if page=='account' and any(b['kind'] in ACCOUNT_KINDS and b.get('region')=='login' for b in value.get('blocks',[])):raise ValueError('Place account blocks in a visible page region.')
    if any(sum(b['kind']==kind for b in value.get('blocks',[]))>1 for kind in ACCOUNT_KINDS):raise ValueError('Use each account block only once.')
    portal.validate(value)
    if page!='home' and any(b['kind'] in ('applications','services','application','account') for b in value['blocks']):raise ValueError('Application blocks are only available on Home.')
    if access_page and any(b['kind'].startswith('widget_') for b in value['blocks']):raise ValueError('Widgets are not available on Access guide pages.')
    from .image_blocks import normalize as normalize_images
    value=normalize_images(value)
    if page=='home' or page.startswith('p-'):
        from .applications import normalize
        value=normalize(value,db);portal.validate(value)
    for system,kind in SYSTEM_FORMS.items():
        count=sum(b['kind']==kind for b in value['blocks'])
        if count!=(1 if page==system else 0):raise ValueError('Keep exactly one required form on its system page.')
    if page in (*SYSTEM_FORMS,'account','footer') and any(b['kind'].startswith('widget_') for b in value['blocks']):raise ValueError('Widgets belong on the member portal')
    if page in SYSTEM_FORMS and any(b['kind'] in ('services','account','guides','application','applications','page_menu','guide_embed') or b.get('visibility','everyone')!='everyone' or ('audience' in b and not b['audience'].get('everyone')) for b in value['blocks']):raise ValueError('Use public blocks on system pages')
    for b in value['blocks']:
        if page=='home' and b['kind']=='page_menu' and b.get('show_back',False):raise ValueError('Back navigation is not available on Home.')
        if 'audience' in b:__import__('app.block_audience',fromlist=['validate']).validate(b['audience'],db)
        if b['kind']=='application' and b.get('service_key','emby') not in ('radarr','sonarr','bazarr','tracearr','tdarr') and not db.get(AccessService,b.get('service_key','emby')):raise ValueError('Invalid service')
        if b['kind']=='image':
            from .image_sources import require_image
            b['url']=require_image(b.get('url',''),db,optional=True)
        if b.get('style',{}).get('background_image'):
            from .image_sources import require_image
            require_image(b['style']['background_image'],db)
        if b.get('rich'):b['body']=footer.clean_html(b.get('body',''))
    if page=='home' or page.startswith('p-'):
        from .page_builder import validate_settings,HOME_SETTINGS
        value['page_settings']=validate_settings(db,value.get('page_settings',deepcopy(HOME_SETTINGS)),home=page=='home')
    if page=='footer' and any(b['kind'] in ('guide_embed','guides') for b in value['blocks']):raise ValueError('Add member pages and journeys to a member page, not the shared footer.')
    if page in PAGES and any(b['kind']=='guide_embed' for b in value['blocks']):raise ValueError('Access guide blocks are only available on subpages.')
    for block in value['blocks']:
        if block['kind']=='accordion':
            from .accordion import validate_item
            for item in block.get('items',[]):validate_item(item,db)
    embeds=[b for b in value['blocks'] if b['kind']=='guide_embed']
    if any(b['kind']=='button' and b.get('button_action')=='choose_device' for b in value['blocks']) and (not access_page or not embeds):raise ValueError('Device navigation is only available on Access guide pages.')
    if len(embeds)>1:raise ValueError('Use one journey per page.')
    for b in embeds:
        if not db.get(AccessService,b.get('service_key','')):raise ValueError('Select an existing application journey.')
    return value

def save(db,page,value,expected,publish=False):
    value=validate(db,page,value)
    if publish:
        from .application_behavior import destination
        apps={app['key']:app for app in catalog(db,editor=True)}
        for block in value['blocks']:
            if block['kind']=='applications':
                for key in block.get('applications',[]):
                    if key in apps:destination(db,apps[key],block.get('application_behaviors',{}).get(key),publishing=True)
        from .widgets import conflicts
        if conflicts(value['blocks']):raise ValueError('Widget audiences overlap at the same priority. Change their audience or priority.')
    if page not in PAGES:
        from .page_builder import save as save_page
        return save_page(db,page,value,expected,publish)
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
        i18n.normalize_fields(db,b,('login-block' if page=='login' else page+'-block')+':'+b['id'],('title','body','alt'))
    db.execute(insert(Config).values(key=page+'_version',value='0').on_conflict_do_nothing())
    result=db.execute(update(Config).where(Config.key==page+'_version',Config.value==str(expected)).values(value=str(expected+1)))
    if result.rowcount!=1:db.rollback();raise HTTPException(409,'The page has changed. Reload the builder.')
    raw=json.dumps(value,ensure_ascii=False)
    for key in ((page+'_draft',page+'_published') if publish else (page+'_draft',)):
        db.execute(insert(Config).values(key=key,value=raw).on_conflict_do_update(index_elements=['key'],set_={'value':raw}))
    db.commit()

def editor(request,page='home'):
    require_admin(request);db=request.state.db
    from .themes import load as themes
    return render(request,'visual_builder.html',builder_data={'page':page,'home_preset':portal.initial_layout(db,seed_pages=False) if page=='home' else None,'header_blocks':[dict(kind=k,label=l,impact=i) for k,l,i in __import__('app.header',fromlist=['BLOCKS']).BLOCKS] if page=='header' else [],'account_blocks':__import__('app.account_blocks',fromlist=['builder_data']).builder_data(db) if page=='account' else [],'default_layout':system_default(db,'account') if page=='account' else __import__('app.header',fromlist=['default']).default(db) if page=='header' else None,'system_key':__import__('app.page_builder',fromlist=['row_for']).row_for(db,page).system_key if page.startswith('p-') else '','layout':load(db,page,True),'version':version(db,page),'palette':themes(db)['dark'],'services':catalog(db,editor=True),'widgets':__import__('app.widgets',fromlist=['builder_data']).builder_data(db),'pages':__import__('app.page_builder',fromlist=['catalog']).catalog(db,request.state.user,True),'groups':[{'id':g.id,'name':g.name} for g in db.scalars(select(__import__('app.models',fromlist=['PermissionGroup']).PermissionGroup))],'menus':sorted({'main',*(m.menu_key for m in db.scalars(select(MenuItem)))})},builder_page=page)

SYSTEM_PAGE_DIRECTORY=(('login','Login screen','door-open','/login'),('forgot','Password recovery','envelope','/forgot'),('reset','New password','key','/reset'),('account','My account','circle-user','/account'))

@router.get('/admin/system-pages')
def system_pages(request:Request):
    require_admin(request);db=request.state.db
    pages=[dict(key=key,title=title,icon=icon,href=href,changes=load(db,key,True)!=load(db,key)) for key,title,icon,href in SYSTEM_PAGE_DIRECTORY]
    return render(request,'system_pages.html',builder_page='system',system_pages=pages)

@router.get('/admin/system-pages/{page}/preview')
def system_page_preview(request:Request,page:str):
    require_admin(request)
    if page not in (*SYSTEM_FORMS,'account'):raise HTTPException(404,'Page not found')
    db=request.state.db;value=load(db,page)
    if page=='account':
        from .bazarr_subtitles import account_context
        return render(request,'account.html',layout=value,visual_preview=True,bazarr_subtitles=account_context(db,request.state.user))
    return render(request,'system_page.html',layout=value,visual_preview=True,anonymous_preview=True,token='preview' if page=='reset' else '')

@router.get('/admin/design/{page}')
def design(request:Request,page:str):return editor(request,page)

@router.post('/admin/design/{page}/{action}')
def edit(request:Request,page:str,action:str,data=Depends(form)):
    require_admin(request);db=request.state.db
    if (page not in PAGES and not __import__('app.page_builder',fromlist=['is_content']).is_content(page)) or action not in ('save','preview','publish','restore'):raise HTTPException(404,'Page not found')
    try:value=json.loads(data.get('payload','{}'))
    except (ValueError,TypeError):raise HTTPException(400,'Invalid page')
    value=validate(db,page,load(db,page) if action=='restore' else value)
    if action=='preview':
        if page=='header':return render(request,'header_preview.html',layout=value,header_layout=value,header_preview=True,visual_preview=True,anonymous_preview=data.get('audience')=='guest')
        if page=='footer':
            f=footer.load(db);f['design']=value;f['enabled']=True
            return render(request,'footer_preview.html',layout=value,footer_layout=f,visual_preview=True)
        if page=='account':
            from .bazarr_subtitles import account_context
            return render(request,'account.html',layout=value,visual_preview=True,bazarr_subtitles=account_context(db,request.state.user))
        return render(request,'system_page.html' if page in SYSTEM_FORMS else 'home.html',layout=value,visual_preview=True,anonymous_preview=page in ('login','forgot','reset'),token='preview' if page=='reset' else '')
    save(db,page,value,int(data.get('version','-1')),action=='publish')
    request.state.audit_action='POST /admin/design/'+page+'/'+action
    request.state.audit_detail={'login':'Login screen','home':'Home','footer':'Footer'}.get(page,'Page')+' · '+str(len(value['blocks']))+' blocks'

    return {'version':version(db,page),'layout':value,**({'header_missing':__import__('app.header',fromlist=['missing']).missing(value)} if page=='header' else {}),**({'account_missing':__import__('app.account_blocks',fromlist=['missing_required']).missing_required(db,value)} if page=='account' else {})}

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
    if key in ('radarr','sonarr','bazarr','tdarr'):raise HTTPException(400,'How to is unavailable for this application')
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
    from .application_guides import custom_service
    service=custom_service(db,item)
    if not service:raise HTTPException(404,'Service not found')
    from .page_builder import ensure_defaults,guide_row
    ensure_defaults(db);db.commit()
    key=service.key;url='/admin/design/home/howto/'+key
    if data.get('open_editor')=='on':return redirect(url)
    page=guide_row(db,key)
    return {'url':url,'page_url':'/admin/design/p-'+str(page.id)}

@router.post('/admin/design/home/application/{key}/behavior')
def application_behavior(request:Request,key:str,data=Depends(form)):
    require_admin(request);db=request.state.db
    if key in ('radarr','sonarr','bazarr','tdarr'):raise HTTPException(400,'Access guides are unavailable for admin tools')
    service=db.get(AccessService,key)
    if not service:raise HTTPException(404,'Application not found')
    raise HTTPException(410,'Reload the builder to configure each application card independently')

@router.get('/admin/access-guides')
def guide_index(request:Request):
    require_admin(request)
    return redirect('/admin/pages')
