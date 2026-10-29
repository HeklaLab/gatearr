"""Published pages, independent drafts, explicit audiences and reusable guide envelopes."""
import json
import re
from copy import deepcopy
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy import select, update, delete, text
from sqlalchemy.exc import IntegrityError
from .models import ContentPage, PermissionGroup, AccessService, ContentTranslation
from . import page_presets
router=APIRouter()
HOME_SETTINGS=dict(title='Home',slug='home',description='',icon='house',icon_url='',navigation=False,audience=dict(everyone=True,admins=True,groups=[]))

def is_content(page):return page=='home' or bool(re.fullmatch(r'p-[1-9][0-9]*',str(page)))
def is_access_guide(db,page):
    if not is_content(page) or page=='home':return False
    row=row_for(db,page)
    return bool(row.system_key and row.system_key.startswith('guide:'))

def next_page_id(db):
    # Never reuse a purged ID: old menu references and editor URLs must stay stale.
    return int(db.execute(text("INSERT INTO config(key,value) VALUES ('page_id_sequence',CAST((SELECT COALESCE(MAX(id),0)+1 FROM content_pages) AS TEXT)) ON CONFLICT(key) DO UPDATE SET value=CAST(MAX(CAST(config.value AS INTEGER),(SELECT COALESCE(MAX(id),0) FROM content_pages))+1 AS TEXT) RETURNING value")).scalar_one())

def deleted_system(db,key):
    from .mailer import config
    return config(db,'deleted_system_page:'+key)=='true'

def row_for(db,page):
    row=db.get(ContentPage,int(page[2:])) if is_content(page) and page!='home' else None
    if not row or row.archived:raise HTTPException(404,'Page not found')
    return row

def validate_settings(db,value,home=False):
    if not isinstance(value,dict):raise ValueError('Invalid page settings')
    title=value.get('title','');slug=value.get('slug','home' if home else '')
    if home and title!='Home':raise ValueError('The Home page cannot be renamed.')
    if not isinstance(title,str) or not title.strip() or len(title)>120:raise ValueError('Enter a page title (up to 120 characters).')
    if not isinstance(slug,str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug) or len(slug)>80 or (slug=='home' and not home):raise ValueError('Use a unique page address with lowercase letters, numbers and hyphens.')
    description=value.get('description','')
    if not isinstance(description,str) or len(description)>500:raise ValueError('Page description is too long')
    from .icons import font_icon
    from .image_sources import require_image
    audience=deepcopy(HOME_SETTINGS['audience']) if home else value.get('audience',HOME_SETTINGS['audience'])
    if not isinstance(audience,dict) or any(type(audience.get(k,False)) is not bool for k in ('everyone','admins')):raise ValueError('Invalid page audience')
    groups=audience.get('groups',[])
    if not isinstance(groups,list) or len(groups)>500 or any(type(g) is not int for g in groups):raise ValueError('Invalid page groups')
    known=set(db.scalars(select(PermissionGroup.id)))
    if not set(groups)<=known:raise ValueError('A selected group no longer exists. Reload page settings.')
    if type(value.get('navigation',True)) is not bool:raise ValueError('Invalid navigation setting')
    return dict(title=title.strip(),slug='home' if home else slug,description=description,icon=font_icon(value.get('icon','file-lines')),icon_url=require_image(value.get('icon_url',''),db,optional=True),navigation=value.get('navigation',True),audience=dict(everyone=audience.get('everyone',False),admins=audience.get('admins',False),groups=sorted(set(groups))))

def allowed(db,user,settings):
    if not user or not user.active or user.portal_disabled:return False
    audience=settings.get('audience',HOME_SETTINGS['audience'])
    if audience.get('everyone'):return True
    if audience.get('admins') and user.admin:return True
    from .group_access import group_for
    group=group_for(db,user)
    return bool(group and group.id in audience.get('groups',[]))

def service_allowed(db,user,key):
    if key=='tracearr':
        from .tools_proxy import allowed_tools
        return 'tracearr' in allowed_tools(db,user)
    if key=='seerr':
        from .group_access import seerr_allowed
        return seerr_allowed(db,user)
    return True

def descriptor(row,value):
    meta={key:value.get('page_settings',{}).get(key,deepcopy(default)) for key,default in HOME_SETTINGS.items()}
    if row is None:meta['audience']=deepcopy(HOME_SETTINGS['audience'])
    key='home' if row is None else 'p-'+str(row.id)
    system=row.system_key if row else 'home'
    href='/home' if row is None else '/access/'+system[6:]+'?view=guide' if system and system.startswith('guide:') else '/pages/'+row.slug
    return dict(key=key,href=href,system=system or '',guide_origin=('Native application' if system[6:] in ('emby','seerr','tracearr') else 'Custom application') if system and system.startswith('guide:') else '',**meta)

def catalog(db,user=None,editor=False,locale=None):
    from . import portal
    result=[]
    value=portal.load(db,editor);home=descriptor(None,value)
    if editor or allowed(db,user,home):
        if locale is not None:
            from . import i18n
            home['title']=i18n.content(db,'page:home:title','Home',locale)
        result.append(home)
    for row in db.scalars(select(ContentPage).where(ContentPage.archived.is_(False)).order_by(ContentPage.id)):
        raw=row.draft if editor else row.published
        if not raw or (not editor and not row.enabled):continue
        item=descriptor(row,json.loads(raw))
        if (row.system_key or '').startswith('guide:'):
            from .application_behavior import guide_href
            item['href']=guide_href(db,row.system_key[6:])
        eligible=allowed(db,user,item)
        if (row.system_key or '').startswith('guide:'):eligible=eligible and service_allowed(db,user,row.system_key[6:])
        if editor or eligible:
            if not editor or locale is not None:
                from . import i18n
                for field in ('title','description'):item[field]=i18n.content(db,'page:'+str(row.id)+':'+field,item[field],locale or i18n.user_language(db,user))
            result.append(item)
    return result

def enforce_home(db,user):
    # Home has no page-level audience; authentication remains enforced by its route.
    return

def guide_row(db,key):return db.scalar(select(ContentPage).where(ContentPage.system_key=='guide:'+key))
def enforce_guide(db,user,key):
    row=guide_row(db,key)
    if not row and deleted_system(db,'guide:'+key):raise HTTPException(404,'Page not found')
    if row and (row.archived or not row.enabled or not row.published or not allowed(db,user,json.loads(row.published).get('page_settings',HOME_SETTINGS))):raise HTTPException(404,'Page not found')

def ensure_defaults(db,fresh=False):
    """Existing installs keep their portal and guide content exactly as published."""
    from .application_guides import tracearr_service
    tracearr_service(db)
    for service in db.scalars(select(AccessService)):
        existing=guide_row(db,service.key)
        if fresh and existing:
            value=page_presets.guide_layout(service.key,service.name,service.icon,service.icon_url,True)
            existing.draft=existing.published=json.dumps(value)
        if not existing and not deleted_system(db,'guide:'+service.key):
            value=page_presets.guide_layout(service.key,service.name,service.icon,service.icon_url,fresh)
            slug=value['page_settings']['slug'];candidate=slug;counter=1
            while db.scalar(select(ContentPage.id).where(ContentPage.slug==candidate)):
                counter+=1;candidate=slug[:74]+'-'+str(counter)
            value['page_settings']['slug']=candidate
            db.add(ContentPage(id=next_page_id(db),slug=candidate,system_key='guide:'+service.key,draft=json.dumps(value),published=json.dumps(value),version=1))
    db.flush()
    for system,make in [('faq',page_presets.faq_layout)]:
        if not deleted_system(db,system) and not db.scalar(select(ContentPage.id).where(ContentPage.system_key==system)):
            value=make();value['page_settings']['navigation']=fresh
            db.add(ContentPage(id=next_page_id(db),slug=value['page_settings']['slug'],system_key=system,draft=json.dumps(value),published=json.dumps(value),version=1))
    db.flush()

def save(db,page,value,expected,publish=False):
    row=row_for(db,page)
    meta=validate_settings(db,value.get('page_settings',{}));value['page_settings']=meta
    if row.system_key and row.system_key.startswith('guide:'):
        embeds=[b for b in value['blocks'] if b['kind']=='guide_embed']
        if len(embeds)!=1 or embeds[0].get('service_key')!=row.system_key[6:]:raise ValueError('Keep the application journey block on this guide page.')
    from . import i18n
    for b in value['blocks']:i18n.normalize_fields(db,b,'page:'+str(row.id)+':'+b['id'],('title','body','alt'))
    raw=json.dumps(value,ensure_ascii=False)
    values=dict(draft=raw,version=expected+1)
    if publish:values.update(published=raw,slug=meta['slug'])
    if db.scalar(select(ContentPage.id).where(ContentPage.slug==meta['slug'],ContentPage.id!=row.id)):raise HTTPException(400,'This page address is already in use. Choose another address.')
    try:
        result=db.execute(update(ContentPage).where(ContentPage.id==row.id,ContentPage.version==expected,ContentPage.archived.is_(False)).values(**values))
        if result.rowcount!=1:raise HTTPException(409,'The page has changed. Reload the builder.')
        db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(400,'This page address is already in use. Choose another address.')

def embedded_context(db,user,locale,key,base,device='',guide_id=None,editor=False):
    from .access import load,visible_nodes,category_icon,local
    from .guides import display,service_url
    from .models import Guide
    if not user or (not editor and not service_allowed(db,user,key)):return None
    service=db.get(AccessService,key)
    if not service:return None
    if not editor:enforce_guide(db,user,key)
    context=dict(service=service,crumbs=[],entries=[],current_title='',guide_preview=False,guide_base=base)
    if guide_id:
        guide=db.get(Guide,int(guide_id)) if str(guide_id).isdigit() else None
        if not guide or guide.service_key!=key or not guide.published:raise HTTPException(404,'Guide not found')
        context.update(guide=guide,article=display(guide.published,service,user,locale,db),template='guide_content.html')
        return context
    nodes=visible_nodes(db,service,load(service));indexed={n['id']:n for n in nodes}
    current=indexed.get(device) if device else None
    if device and (not current or current['kind']!='group'):raise HTTPException(404,'Submenu not found')
    def href(kind,value):return base+('&' if '?' in base else '?')+kind+'='+str(value)
    parent=current
    while parent:
        context['crumbs'].insert(0,dict(title=local(parent,'title',locale,db),href=href('device',parent['id'])))
        parent=indexed.get(parent.get('parent',''))
    context['current_title']=local(current,'title',locale,db) if current else service.name
    for node in sorted(nodes,key=lambda n:(n['position'],n['id'])):
        if node.get('parent','')!=device:continue
        kind=node['kind'];url=href('device',node['id'])
        if kind=='guide':url=href('guide',node['guide_id'])
        if kind=='browser':url=service_url(db,service)
        if kind=='link':url=node['url']
        context['entries'].append(dict(node,icon=category_icon(node),title=local(node,'title',locale,db),href=url,external=kind in ('link','browser')))
    context['template']='access_content.html'
    return context

def guide_home_usage(layout, apps):
    """Track each service by identity across all Home application cards."""
    modes={}
    for block in layout['blocks']:
        if block['kind']!='applications' or block.get('region','main')=='login':continue
        for key in block.get('applications',[]):
            app=apps.get(key)
            if not app or not app.get('howto'):continue
            mode=block.get('application_behaviors',{}).get(key,{}).get('mode',app['default_mode'])
            modes.setdefault(app['howto'],set()).add(mode)
    return {key:('' if 'guide' in values else 'direct' if values=={'direct'} else 'other') for key,values in modes.items()}

@router.get('/admin/pages')
def index(request:Request):
    from .main import require_admin,render
    require_admin(request);db=request.state.db
    ensure_defaults(db);db.commit()
    pages=catalog(db,request.state.user,True)
    from . import portal
    from .applications import catalog as application_catalog
    apps={app['key']:app for app in application_catalog(db,editor=True)}
    usage=guide_home_usage(portal.load(db),apps)
    draft_usage=guide_home_usage(portal.load(db,True),apps)
    for item in pages:
        row=None if item['key']=='home' else db.get(ContentPage,int(item['key'][2:]))
        if item['system'].startswith('guide:'):
            service=item['system'][6:]
            item['guide_usage']=usage.get(service,'missing')
            draft=draft_usage.get(service,'missing')
            item['guide_draft_usage']=draft if draft!=item['guide_usage'] else None
        item['version']=row.version if row else portal.version(db)
        item['published']=row is None or bool(row.published)
        item['enabled']=row is None or row.enabled
        guide=item['system'].startswith('guide:')
        item['address']=item['href'] if row is None or guide else '/pages/'+item['slug']
        item['published_address']='/pages/'+row.slug if row and not guide and row.published and row.slug!=item['slug'] else None
        item['changes']=__import__('app.portal',fromlist=['load']).load(db,True)!=__import__('app.portal',fromlist=['load']).load(db) if row is None else row.draft!=row.published
    return render(request,'pages.html',builder_page='pages',pages=pages,page_groups=[dict(key='home',title='Home page',pages=[p for p in pages if p['key']=='home']),dict(key='access',title='Access guides',pages=[p for p in pages if p['system'].startswith('guide:')]),dict(key='other',title='Other pages',pages=[p for p in pages if p['key']!='home' and not p['system'].startswith('guide:')])],archived_pages=[dict(descriptor(r,json.loads(r.draft)),version=r.version) for r in db.scalars(select(ContentPage).where(ContentPage.archived.is_(True),(ContentPage.system_key.is_(None)) | (ContentPage.system_key!='directory')))])

from .main import form
@router.post('/admin/pages')
def create(request:Request,data=Depends(form)):
    from .main import require_admin,redirect
    require_admin(request);db=request.state.db
    slug=str(data.get('slug','')).strip();title=str(data.get('title','')).strip()
    value=page_presets.faq_layout(slug) if data.get('preset')=='faq' else page_presets.layout(title,slug)
    value['page_settings']['title']=title
    value['page_settings']=validate_settings(db,value['page_settings'])
    ensure_defaults(db)
    if db.scalar(select(ContentPage.id).where(ContentPage.slug==slug)):
        from fastapi.responses import JSONResponse
        if 'application/json' in request.headers.get('accept',''):return JSONResponse({'field':'slug','error':__import__('app.i18n',fromlist=['translate']).translate('This page address is already in use. Choose another address.',request.state.locale)},status_code=400)
        raise HTTPException(400,'This page address is already in use. Choose another address.')
    row=ContentPage(id=next_page_id(db),slug=slug,draft=json.dumps(value),version=0);db.add(row)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(400,'This page address is already in use. Choose another address.')
    return redirect('/admin/design/p-'+str(row.id))

@router.post('/admin/pages/{page}/archive')
def archive(request:Request,page:str,data=Depends(form)):
    from .main import require_admin,redirect
    require_admin(request);db=request.state.db;row=row_for(db,page)
    if row.system_key=='directory':raise HTTPException(400,'This page cannot be deleted.')
    expected=int(data.get('version','-1'))
    result=db.execute(update(ContentPage).where(ContentPage.id==row.id,ContentPage.version==expected).values(archived=True,version=expected+1))
    if result.rowcount!=1:raise HTTPException(409,'The page has changed. Reload the page list.')
    db.commit();return redirect('/admin/pages')

@router.get('/pages/{slug}')
def public(request:Request,slug:str):
    from .main import require_user,render
    user=require_user(request);db=request.state.db
    row=db.scalar(select(ContentPage).where(ContentPage.slug==slug,ContentPage.archived.is_(False)))
    if not row or not row.enabled or not row.published:raise HTTPException(404,'Page not found')
    value=json.loads(row.published)
    if (row.system_key or '').startswith('guide:') and not service_allowed(db,user,row.system_key[6:]):raise HTTPException(404,'Page not found')
    if not allowed(db,user,value.get('page_settings',HOME_SETTINGS)):raise HTTPException(404,'Page not found')
    value['page']='p-'+str(row.id)
    return render(request,'home.html',layout=value,content_page=row)

@router.post('/admin/pages/{page}/restore')
def restore(request:Request,page:str,data=Depends(form)):
    from .main import require_admin,redirect
    require_admin(request);db=request.state.db
    if not is_content(page) or page=='home':raise HTTPException(404,'Page not found')
    row=db.get(ContentPage,int(page[2:]))
    if not row or row.system_key=='directory':raise HTTPException(404,'Page not found')
    result=db.execute(update(ContentPage).where(ContentPage.id==int(page[2:]),ContentPage.version==int(data.get('version','-1')),ContentPage.archived.is_(True)).values(archived=False,version=ContentPage.version+1))
    if result.rowcount!=1:raise HTTPException(409,'The page has changed. Reload the page list.')
    db.commit();return redirect('/admin/pages')

@router.get('/admin/audience-demo')
def audience_demo(request:Request):
    from .main import require_admin,render
    require_admin(request)
    groups=[dict(id=g.id,name=g.name) for g in request.state.db.scalars(select(PermissionGroup))]
    if not groups:groups=[dict(id=1,name='Family'),dict(id=2,name='Friends')]
    return render(request,'audience_demo.html',audience_demo_data=dict(groups=groups))

@router.post('/admin/pages/{page}/publish')
@router.post('/admin/pages/{page}/enable')
def enable_from_list(request:Request,page:str,data=Depends(form)):
    return set_enabled(request,page,data,True)

@router.post('/admin/pages/{page}/unpublish')
@router.post('/admin/pages/{page}/disable')
def disable_from_list(request:Request,page:str,data=Depends(form)):
    return set_enabled(request,page,data,False)

def set_enabled(request,page,data,enabled):
    from .main import require_admin,redirect
    require_admin(request);db=request.state.db;row=row_for(db,page)
    if enabled and not row.published:raise HTTPException(400,'Publish this page from the builder before enabling it.')
    result=db.execute(update(ContentPage).where(ContentPage.id==row.id,ContentPage.version==int(data.get('version','-1'))).values(enabled=enabled,version=ContentPage.version+1))
    if result.rowcount!=1:raise HTTPException(409,'The page has changed. Reload the page list.')
    db.commit();return redirect('/admin/pages')

@router.post('/admin/pages/{page}/purge')
def purge(request:Request,page:str,data=Depends(form)):
    from .main import require_admin,redirect,set_config
    require_admin(request);db=request.state.db
    if not is_content(page) or page=='home':raise HTTPException(404,'Page not found')
    row=db.get(ContentPage,int(page[2:]))
    if not row or not row.archived or row.system_key=='directory':raise HTTPException(404,'Deleted page not found')
    if data.get('confirm')!='delete':raise HTTPException(400,'Confirm permanent deletion.')
    # Reserve the deleted identifier even if this was the highest existing page ID.
    next_page_id(db)
    result=db.execute(delete(ContentPage).where(ContentPage.id==row.id,ContentPage.archived.is_(True),ContentPage.version==int(data.get('version','-1'))))
    if result.rowcount!=1:db.rollback();raise HTTPException(409,'The page has changed. Reload the page list.')
    if row.system_key:set_config(db,'deleted_system_page:'+row.system_key,'true')
    prefix='page:'+str(row.id)
    db.execute(delete(ContentTranslation).where((ContentTranslation.resource==prefix) | ContentTranslation.resource.startswith(prefix+':')))
    db.commit();return redirect('/admin/pages')
