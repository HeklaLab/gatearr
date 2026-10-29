"""Admin-authored device guides. Only published snapshots are visible to members."""
import json
import re
import secrets
from urllib.parse import urlsplit
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy import select, update
from .main import form, require_admin, require_user, render, redirect
from .models import AccessService, Guide
from .mailer import config
from .security import url_ok
from . import i18n

router = APIRouter()
DEVICES = ('mobile', 'tv', 'tablet', 'desktop', 'other')

def service_url(db, service):
    if service.key=='tracearr':return '/tools/tracearr' if config(db,'tracearr_enabled')=='true' and config(db,'tracearr_interface_enabled','true')=='true' and config(db,'tracearr_public_url') else ''
    if service.key=='emby' and service.browser_url:return '/services/emby/open'
    if service.key=='seerr':
        from .seerr_login import enabled,public_url
        if enabled(db):return '/services/seerr/open'
        return service.browser_url or public_url(db)
    return service.browser_url or ''

def access_href(db, key):
    from .access import access_href as href
    return href(db,key)

def local(value,field,locale,db=None):
    source=value.get(field,'')
    return i18n.content(db,value['_i18n_key']+':'+field,source,locale) if db and value.get('_i18n_key') else source

def normalize(db,value,guide_id):
    prefix='guide:'+str(guide_id);value['_i18n_key']=prefix
    i18n.normalize_fields(db,value,prefix,('title','summary'))
    for step in value['steps']:
        step['_i18n_key']=prefix+':'+step['id']
        i18n.normalize_fields(db,step,step['_i18n_key'],('title','body','link_label'))
    return value

def display(raw, service, user, locale, db=None):
    value = json.loads(raw)
    # Public client address is explicitly configured. Never use the private media-server address.
    address = service.server_url
    parsed = urlsplit(address)
    variables = {'server_url': address, 'server_host': parsed.hostname or '', 'server_port': str(parsed.port or (443 if parsed.scheme == 'https' else 80)) if address else '', 'username': user.name}
    def text(source,rich=False):
        import html
        return re.sub(r'\{(server_url|server_host|server_port|username)\}', lambda match: html.escape(variables[match[1]]) if rich else variables[match[1]], source)
    value['title'] = text(local(value, 'title', locale,db))
    value['summary'] = text(local(value, 'summary', locale,db))
    value['steps'] = [{**step, 'title': text(local(step,'title',locale,db)), 'body': text(local(step,'body',locale,db),step.get('rich',False)), 'link_label': text(local(step,'link_label',locale,db))} for step in value['steps']]
    return value

def guide_or_404(db, guide_id):
    guide = db.get(Guide, guide_id)
    if not guide:
        raise HTTPException(404, 'Guide not found')
    return guide

def save(db, guide, expected, **values):
    result = db.execute(update(Guide).where(Guide.id == guide.id, Guide.version == expected).values(**values, version=expected+1))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'The guide was changed. Reload this page.')
    db.commit()

def validated(data):
    value = {'device': str(data.get('device','mobile')), 'position': int(data.get('position','10')), 'steps': []}
    if value['device'] not in DEVICES:
        raise ValueError('Invalid device')
    for field in ('title','summary','title_fr','title_en','summary_fr','summary_en'):
        if field not in data:continue
        value[field] = str(data[field])
        if len(value[field]) > (200 if field.startswith('title') else 2000):
            raise ValueError('Guide text is too long')
    if not any(str(value.get(field,'')).strip() for field in ('title','title_fr','title_en')):
        raise ValueError('Guide title required')
    count = int(data.get('step_count','1'))
    if not 1 <= count <= 31:
        raise ValueError('A guide supports up to 30 steps')
    for index in range(count):
        prefix = 'step_'+str(index)+'_'
        if data.get(prefix+'delete') == 'on':
            continue
        step = {field:str(data[prefix+field]) for field in ('title','body','link_label','title_fr','title_en','body_fr','body_en','link_label_fr','link_label_en','link_url','image_url') if prefix+field in data}
        if not any(step.values()):
            continue
        if any(len(v) > 5000 for v in step.values()):
            raise ValueError('Guide text is too long')
        step['id']=str(data.get(prefix+'id','')) or secrets.token_hex(8)
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',step['id']) or any(old['id']==step['id'] for old in value['steps']):raise ValueError('Invalid step identifier')
        step['position'] = int(data.get(prefix+'position', str((index+1)*10)))
        step['link_url']=url_ok(step.get('link_url',''),optional=True)
        from .image_sources import require_image
        step['image_url']=require_image(step.get('image_url',''),optional=True)
        value['steps'].append(step)
    if len(value['steps']) > 30:
        raise ValueError('A guide supports up to 30 steps')
    value['steps'].sort(key=lambda step:step['position'])
    return value

@router.get('/help')
def knowledge_base(request: Request):
    require_user(request)
    return redirect('/home')

@router.get('/access/{key}')
def access(request: Request, key: str):
    from .access import public_access
    return public_access(request,key)

@router.get('/access/{key}/guide/{guide_id}')
@router.get('/help/{guide_id}')
def read_guide(request: Request, guide_id: int, key: str | None = None):
    require_user(request)
    db = request.state.db
    guide = guide_or_404(db,guide_id)
    if key and guide.service_key != key:
        raise HTTPException(404,'Guide not found')
    preview = request.query_params.get('preview') == '1'
    if preview:
        require_admin(request)
    raw = guide.draft if preview else guide.published
    if not raw:
        raise HTTPException(404,'Guide not found')
    service = db.get(AccessService,guide.service_key)
    from .page_builder import service_allowed,enforce_guide
    if not preview and not service_allowed(db,request.state.user,service.key):raise HTTPException(403,'Application access is not granted')
    if not preview:enforce_guide(db,request.state.user,service.key)
    return render(request,'guide.html',guide=guide,service=service,article=display(raw,service,request.state.user,request.state.locale,db),guide_preview=preview)

@router.get('/admin/guides')
def admin_guides(request: Request):
    require_admin(request)
    return redirect('/admin/portal')

@router.post('/admin/guides/service')
def save_service(request: Request, data=Depends(form)):
    require_admin(request)
    db = request.state.db
    key = str(data.get('key',''))
    name = str(data.get('name','')).strip()
    if not re.fullmatch(r'[a-z0-9_-]{1,40}',key) or not name or len(name)>100:
        raise ValueError('Invalid service')
    if key in ('radarr','sonarr','bazarr','tracearr','tdarr'):raise ValueError('How to is unavailable for this application')
    row = db.get(AccessService,key) or AccessService(key=key)
    row.name = name
    row.browser_url = url_ok(str(data.get('browser_url','')),optional=True)
    address = url_ok(str(data.get('server_url','')),optional=True)
    parsed = urlsplit(address)
    # Force port parsing now, not later in member-facing rendering.
    if address and (parsed.query or parsed.fragment or (parsed.port is not None and not 1 <= parsed.port <= 65535)):
        raise ValueError('Invalid URL')
    from .icons import local_icon_value,font_icon
    row.icon_url = local_icon_value(db,data)
    row.icon = font_icon(data.get('icon','link')) if not row.icon_url else 'link'
    mode = str(data.get('entry_mode',row.entry_mode or 'direct'))
    if mode not in ('direct','structured'):
        raise ValueError('Mode de parcours invalide')
    row.entry_mode = mode
    row.server_url = address
    db.add(row)
    from .models import MenuItem
    for item in db.scalars(select(MenuItem)):
        if item.access_service==key:
            item.access_service=key;item.label=row.name;item.icon=row.icon;item.icon_url=row.icon_url
            if row.browser_url:item.url=row.browser_url
    db.commit()
    return redirect('/admin/integrations')

@router.post('/admin/guides/create')
def create_guide(request: Request, data=Depends(form)):
    require_admin(request)
    db = request.state.db
    key = str(data.get('service_key',''))
    if key in ('radarr','sonarr','bazarr','tracearr','tdarr'):raise ValueError('How to is unavailable for this application')
    if not db.get(AccessService,key):
        raise ValueError('Invalid service')
    value = validated(data)
    row = Guide(service_key=key,draft=json.dumps(value,ensure_ascii=False),version=0)
    db.add(row)
    db.flush()
    row.draft=json.dumps(normalize(db,value,row.id),ensure_ascii=False)
    db.commit()
    return redirect('/admin/guides/'+str(row.id))


@router.post('/admin/guides/defaults')
def add_defaults(request: Request, data=Depends(form)):
    require_admin(request)
    from .default_journeys import seed
    if not seed(request.state.db,activate=True):
        raise ValueError('Existing journeys are preserved. Edit them in Build submenus.')
    request.state.db.commit()
    return redirect('/admin/guides')

@router.get('/admin/guides/{guide_id}')
def edit_guide(request: Request, guide_id: int):
    require_admin(request)
    row = guide_or_404(request.state.db,guide_id)
    from .visual_howto import guide_editor
    return guide_editor(request,guide_id)

@router.post('/admin/guides/{guide_id}')
def update_guide(request: Request, guide_id: int, data=Depends(form)):
    require_admin(request)
    db = request.state.db
    row = guide_or_404(db,guide_id)
    action = data.get('action','save')
    expected = int(data.get('version','-1'))
    if action == 'unpublish':
        save(db,row,expected,published=None)
    elif action in ('save','publish'):
        value = validated(data)
        if action == 'publish' and not value['steps']:
            raise ValueError('Add at least one step before publishing')
        normalize(db,value,row.id)
        encoded = json.dumps(value,ensure_ascii=False)
        save(db,row,expected,**({'draft':encoded,'published':encoded} if action == 'publish' else {'draft':encoded}))
    else:
        raise ValueError('Invalid action')
    return redirect('/admin/guides/'+str(guide_id))
