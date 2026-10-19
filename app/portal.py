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
KINDS = ('welcome', 'text', 'image', 'button', 'menu', 'services', 'account', 'guides', 'spacer')
DEFAULT = {'nav_position': 'top', 'sidebar_position': 'left', 'theme': {'accent': '#159eff', 'button_hover':'#45cdf4', 'bg': '#edf4ff', 'surface': '#ffffff', 'text': '#12234a', 'muted': '#526789', 'ink':'#051c40'}, 'blocks': [{'id': 'welcome', 'kind': 'welcome', 'region': 'main', 'order': 10, 'span': 12, 'title': 'Welcome, {username}.', 'body': 'All your services, one place.', 'alt': ''}, {'id': 'services', 'kind': 'services', 'region': 'main', 'order': 20, 'span': 12, 'menu_key': 'main', 'include_emby': True, 'title': '', 'body': '', 'alt': ''}, {'id': 'account', 'kind': 'account', 'region': 'main', 'order': 30, 'span': 12, 'title': 'My account', 'body': 'Manage your details and password.', 'alt': ''}]}

def load(db, draft=False):
    raw = config(db, 'portal_draft' if draft else 'portal_published')
    if not raw:
        return deepcopy(DEFAULT)
    return validate(json.loads(raw))

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
        if block.get('id') in ids or not isinstance(block.get('id'), str):
            raise ValueError('Invalid block ID')
        ids.add(block['id'])
        if block.get('kind') not in KINDS or block.get('region') not in REGIONS or type(block.get('span')) is not int or not 1 <= block['span'] <= 12 or type(block.get('order')) is not int:
            raise ValueError('Invalid block')
        for field in ('title','body','alt'):
            if not isinstance(block.get(field, ''), str) or len(block.get(field, '')) > 5000:
                raise ValueError('Block text too long')
        if block['kind'] in ('image','button'):
            url_ok(block.get('url', ''))
        if not re.fullmatch(r'[a-z0-9_-]{1,40}', block.get('menu_key', 'main')):
            raise ValueError('Invalid menu ID')
    return layout

def localized(block,name,locale,db=None):
    source=block.get(name,'')
    return i18n.content(db,'block:'+block['id']+':'+name,source,locale) if db else source

def for_display(layout,locale,user=None,db=None):
    layout=deepcopy(layout);regions={key:[] for key in REGIONS}
    for block in sorted(layout['blocks'],key=lambda block:(block['order'],block['id'])):
        for field in ('title','body','alt'):
            block[field]=localized(block,field,locale,db).replace('{username}',user.name if user else '')
        regions[block['region']].append(block)
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
