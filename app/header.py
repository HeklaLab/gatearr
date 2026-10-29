"""Shared header layout; removable functions report their impact without granting access."""
import json
from copy import deepcopy
from . import portal
from .mailer import config

KINDS={'header_container','logo','header_navigation','header_account','columns','spacer','divider','title','text','button','page_menu'}
FUNCTIONS={'header_navigation','header_account'}
BLOCKS=(('header_navigation','Main navigation','Links to Home, My account and Administration are no longer shown in the header.'),
        ('header_account','Account menu','Profile, sign-out, language and appearance controls are no longer shown in the header.'))


def default(db):
    def block(key,kind,order,align):
        return dict(id=key,kind=kind,region='main',span=12,order=order,title='',body='',style={'align':align})
    root=dict(block('header-container','header_container',0,'left'),columns=1)
    columns=dict(block('header-columns','columns',10,'left'),parent=root['id'],slot=0,columns=3,column_sizes=[4,6,2])
    children=[dict(block('header-logo','logo',20,'left'),parent=columns['id'],slot=0,logo_mode='logo',logo_width=180,title='{app_name}'),
              dict(block('header-navigation','header_navigation',30,'right'),parent=columns['id'],slot=1),
              dict(block('header-account','header_account',40,'right'),parent=columns['id'],slot=2)]
    return dict(page='header',nav_position='top',sidebar_position='left',theme=deepcopy(portal.DEFAULT['theme']),colors={},show_header=True,
                browser_title=config(db,'browser_title',''),blocks=[root,columns,*children])


def normalize(value):
    """Wrap earlier flat headers independently in draft and published snapshots."""
    value=deepcopy(value);blocks=value['blocks'];used={b['id'] for b in blocks}
    def unique(seed):
        while seed in used:seed+='-root'
        used.add(seed);return seed
    if not any(b['kind']=='header_container' for b in blocks):
        root=dict(id=unique('header-container'),kind='header_container',region='main',span=12,order=0,columns=1,title='',body='')
        top=sorted((b for b in blocks if not b.get('parent')),key=lambda b:b['order'])
        if len(top)==3 and {b['kind'] for b in top}=={'logo',*FUNCTIONS} and sum(b['span'] for b in top)==12:
            columns=dict(id=unique('header-columns'),kind='columns',region='main',span=12,order=1,columns=3,column_sizes=[b['span'] for b in top],title='',body='',parent=root['id'],slot=0)
            for i,b in enumerate(top):b.update(parent=columns['id'],slot=i,span=12)
            blocks.insert(0,columns)
        else:
            for b in top:b.update(parent=root['id'],slot=0)
        blocks.insert(0,root)
    for b in blocks:
        if b['kind']=='logo':
            if b.get('logo_mode','auto')=='auto':b['logo_mode']='logo'
            if not b.get('title'):b['title']='{app_name}'
    return value


def load(db,draft=False):
    raw=config(db,'header_draft' if draft else 'header_published')
    return normalize(json.loads(raw)) if raw else default(db)


def missing(value):
    present={b['kind'] for b in value['blocks']}
    return [dict(kind=kind,label=label,impact=impact) for kind,label,impact in BLOCKS if kind not in present]


def validate(value):
    portal.validate(value)
    if any(b['kind'] not in KINDS or b['region']!='main' or b.get('visibility','everyone')!='everyone' or b.get('audience') for b in value['blocks']):
        raise ValueError('Use shared header blocks without access restrictions.')
    roots=[b for b in value['blocks'] if b['kind']=='header_container']
    if len(roots)!=1 or roots[0].get('parent') or roots[0]['span']!=12 or roots[0].get('columns',1)!=1:
        raise ValueError('Keep one full-width header container.')
    if any(b['id']!=roots[0]['id'] and not b.get('parent') for b in value['blocks']):raise ValueError('Place blocks inside the header container.')
    for kind in FUNCTIONS:
        if sum(b['kind']==kind for b in value['blocks'])>1:raise ValueError('Use each system menu only once.')
    for b in value['blocks']:
        if b['kind']=='logo':
            if b.get('logo_mode','logo') not in ('logo','name','both'):raise ValueError('Invalid logo display')
            if type(b.get('logo_width',180)) is not int or not 24<=b.get('logo_width',180)<=600:raise ValueError('Choose a logo width from 24 to 600 pixels.')
        if b['kind']=='columns' and 'column_sizes' in b:
            sizes=b['column_sizes']
            if not isinstance(sizes,list) or len(sizes)!=b.get('columns',2) or any(type(n) is not int or not 1<=n<=12 for n in sizes):raise ValueError('Choose a width from 1 to 12 for each column.')
    title=value.get('browser_title','')
    if not isinstance(title,str) or len(title)>200 or any(ord(c)<32 for c in title):raise ValueError('Enter a valid browser title')
    return value
