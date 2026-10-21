"""Declarative, escaped block layouts. Drafts never change the published portal."""
import json
import re
import secrets
from copy import deepcopy
from sqlalchemy import update
from .models import Config
from .mailer import config
from .security import url_ok
from . import i18n

REGIONS = ('login', 'header', 'sidebar', 'main', 'footer')
KINDS = ('welcome', 'text', 'image', 'button', 'menu', 'services', 'account', 'guides', 'spacer', 'columns', 'login_form', 'logo', 'divider', 'application', 'applications')
DEFAULT = {'nav_position': 'top', 'sidebar_position': 'left', 'theme': {'accent': '#159eff', 'button_hover':'#45cdf4', 'bg': '#edf4ff', 'surface': '#ffffff', 'text': '#12234a', 'muted': '#526789', 'ink':'#051c40'}, 'blocks': [{'id': 'welcome', 'kind': 'welcome', 'region': 'main', 'order': 10, 'span': 12, 'title': 'Welcome, {username}.', 'body': 'All your services, one place.', 'alt': ''}, {'id': 'services', 'kind': 'services', 'region': 'main', 'order': 20, 'span': 12, 'menu_key': 'main', 'include_emby': True, 'title': '', 'body': '', 'alt': ''}, {'id': 'account', 'kind': 'account', 'region': 'main', 'order': 30, 'span': 12, 'title': 'My account', 'body': 'Manage your details and password.', 'alt': ''}]}

def load(db, draft=False):
    raw = config(db, 'portal_draft' if draft else 'portal_published')
    if not raw:
        from .applications import normalize
        return normalize(DEFAULT,db)
    from .applications import normalize
    return validate(normalize(json.loads(raw),db))

def validate(layout):
    if layout.get('nav_position') not in ('top', 'left', 'right'):
        raise ValueError('Invalid navigation position')
    if layout.get('sidebar_position', 'left') not in ('left','right'):
        raise ValueError('Invalid navigation position')
    theme = layout.get('theme', {})
    for key, default in DEFAULT['theme'].items():
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', theme.get(key, default)):
            raise ValueError('Invalid color: use #RRGGBB')
    if not isinstance(layout.get('blocks'), list) or len(layout['blocks']) > 50:
        raise ValueError('The portal supports up to 50 blocks')
    ids = set()
    for block in layout['blocks']:
        if not isinstance(block,dict) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',str(block.get('id',''))) or block.get('id') in ids:
            raise ValueError('Invalid block ID')
        ids.add(block['id'])
        if block.get('kind') not in KINDS or block.get('region') not in REGIONS or type(block.get('span')) is not int or not 1 <= block['span'] <= 12 or type(block.get('order')) is not int:
            raise ValueError('Invalid block')
        for field in ('title','body','alt'):
            if not isinstance(block.get(field, ''), str) or len(block.get(field, '')) > 5000:
                raise ValueError('Block text too long')
        from .page_design import asset_url,link_url,validate_style
        validate_style(block.get('style',{}))
        if block['kind']=='applications':
            selected=block.get('applications',[])
            if not isinstance(selected,list) or len(selected)>100 or any(not isinstance(k,str) or not re.fullmatch(r'(?:access:[a-z0-9_-]{1,80}|menu:[0-9]+|account|radarr|sonarr|bazarr)',k) for k in selected) or len(set(selected))!=len(selected):raise ValueError('Invalid application selection')
            if block.get('columns',3) not in (1,2,3,4,5,6) or block['span']!=12 or block.get('parent') or block['region']!='main':raise ValueError('Applications use a full row in the main content')
        if block['kind']=='image':asset_url(block.get('url',''))
        if block['kind']=='button':link_url(block.get('url',''),layout.get('page')=='login')
        if block['kind']=='columns' and block.get('columns',2) not in (1,2,3):raise ValueError('Choose one, two or three columns')
        if block.get('visibility','everyone') not in ('everyone','admins','members'):raise ValueError('Invalid visibility')
        if not re.fullmatch(r'[a-z0-9_-]{1,40}', block.get('menu_key', 'main')):
            raise ValueError('Invalid menu ID')
    from .page_design import validate_style
    validate_style(layout.get('colors',{}))
    if type(layout.get('show_header',True)) is not bool:raise ValueError('Invalid header setting')
    indexed={b['id']:b for b in layout['blocks']}
    for block in layout['blocks']:
        parent=block.get('parent','');seen={block['id']}
        if parent:
            owner=indexed.get(parent)
            if not owner or owner['kind']!='columns' or type(block.get('slot',0)) is not int or not 0<=block.get('slot',0)<owner.get('columns',2):raise ValueError('Invalid column')
        for _ in range(4):
            if not parent:break
            if parent in seen or parent not in indexed:raise ValueError('Invalid nested block')
            seen.add(parent);parent=indexed[parent].get('parent','')
        else:raise ValueError('Use up to three nested column blocks')
    return layout

def localized(block,name,locale,db=None):
    source=block.get(name,'')
    if not db:return source
    if block['id']=='login-intro' and name=='body':
        from .models import ContentTranslation
        primary=db.get(ContentTranslation,(locale,'login-block:login-intro:body',i18n.source_hash(source)))
        legacy=db.get(ContentTranslation,(locale,'branding:login_text',i18n.source_hash(source)))
        if not primary and legacy and legacy.value:return legacy.value
    translated=i18n.content(db,block.get('_scope','block')+':'+block['id']+':'+name,source,locale)
    if block['id']=='login-intro' and name=='body' and translated==source:translated=i18n.content(db,'branding:login_text',source,locale)
    return translated

def for_display(layout,locale,user=None,db=None):
    layout=deepcopy(layout);regions={key:[] for key in REGIONS};indexed={}
    for block in sorted(layout['blocks'],key=lambda block:(block['order'],block['id'])):
        if block['id']=='account' and block['kind']=='account' and block.get('title')=='My account' and block.get('body')=='Manage your details and password.' and any(b['kind']=='services' for b in layout['blocks']):continue
        if block['kind']=='application' and block.get('service_key') in ('radarr','sonarr','bazarr') and db is not None:
            from .tools_proxy import allowed_tools
            if block['service_key'] not in allowed_tools(db,user):continue
        visibility=block.get('visibility','everyone')
        if visibility=='admins' and (not user or not user.admin):continue
        if visibility=='members' and (not user or user.admin):continue
        block['_scope']={'login':'login-block','footer':'footer-block'}.get(layout.get('page'),'block')
        for field in ('title','body','alt'):block[field]=localized(block,field,locale,db).replace('{username}',user.name if user else '')
        if block.get('rich'):
            from .footer import clean_html
            block['body']=clean_html(block['body'])
        block['slots']=[[] for _ in range(block.get('columns',2))] if block['kind']=='columns' else []
        indexed[block['id']]=block
    from .applications import catalog
    available={a['key']:a for a in catalog(db,user,locale=locale)} if db is not None else {}
    for b in indexed.values():
        if b['kind']=='applications':b['cards']=[available[key] for key in b.get('applications',[]) if key in available]
    for block in indexed.values():
        if block.get('parent'):
            parent=indexed.get(block['parent'])
            if parent:parent['slots'][block.get('slot',0)].append(block)
        else:regions[block['region']].append(block)
    return regions

def version(db):
    return int(config(db, 'portal_version', '0'))

def save(db, draft, expected, publish=False):
    for block in draft["blocks"]:i18n.normalize_fields(db,block,"block:"+block["id"],("title","body","alt"))
    validate(draft)
    # Compare-and-swap: two administrators cannot silently overwrite the same draft.
    from sqlalchemy.dialects.sqlite import insert
    db.execute(insert(Config).values(key='portal_version', value='0').on_conflict_do_nothing())
    result = db.execute(update(Config).where(Config.key == 'portal_version', Config.value == str(expected)).values(value=str(expected+1)))
    if result.rowcount != 1:
        db.rollback()
        raise ValueError('The portal has changed. Reload the builder.')
    encoded = json.dumps(draft, ensure_ascii=False)
    keys = ['portal_draft', 'portal_published'] if publish else ['portal_draft']
    for key in keys:
        db.execute(insert(Config).values(key=key, value=encoded).on_conflict_do_update(index_elements=[Config.key], set_={'value': encoded}))
    db.commit()

def block_from_form(data):
    return {
        'id': data.get('block_id') or secrets.token_hex(8), 'kind': data['kind'], 'region': data['region'],
        'order': int(data.get('order','10')), 'span': int(data.get('span','12')),
        **{field:str(data[field]) for field in ('title','body','alt','title_fr','title_en','body_fr','body_en','alt_fr','alt_en','url') if field in data},
        'menu_key': str(data.get('menu_key','main')), 'new_tab': data.get('new_tab') == 'on', 'include_emby': data.get('include_emby') == 'on',
    }
