"""Stable application identities shared by the editor and permission-filtered portal."""
from sqlalchemy import select
from .models import AccessService,MenuItem
from .mailer import config
from .service_assets import service_icon,default_icon

def catalog(db,user=None,editor=False,locale='en'):
    from .guides import access_href
    from .tools_proxy import allowed_tools
    from .i18n import content
    tools=allowed_tools(db,user);result=[]
    from .group_access import seerr_allowed
    can_seerr=editor or seerr_allowed(db,user)
    media='jellyfin' if config(db,'media_server')=='jellyfin' else 'emby'
    menu_rows=list(db.scalars(select(MenuItem).order_by(MenuItem.position,MenuItem.id)))
    attached={m.access_service for m in menu_rows if m.access_service}
    for s in db.scalars(select(AccessService).order_by(AccessService.name)):
        if s.key in ('radarr','sonarr','bazarr') or s.key in attached and s.key not in ('emby','seerr'):continue
        if s.key=='seerr' and not can_seerr:continue
        href=access_href(db,s.key)
        manual=next((m for m in menu_rows if m.access_service==s.key or m.label.casefold()==s.key),None)
        if not editor and (not href and not manual or (s.key=='seerr' and not config(db,'seerr_public_url') and not s.browser_url and not manual)):continue
        if manual and not manual.access_service:href=manual.url
        result.append(dict(key='access:'+s.key,name=content(db,'menu:'+str(manual.id)+':label',manual.label,locale) if manual else content(db,'service:'+s.key+':name',s.name,locale),href=href,image=(manual.icon_url or (service_icon(db,s.key,media) if manual.icon=='link' else '')) if manual else service_icon(db,s.key,media),icon=manual.icon if manual else s.icon,external=not href.startswith('/'),howto=s.key,entry_mode=s.entry_mode))
    for item in menu_rows:
        if any(a['key']=='access:'+(item.access_service or item.label.casefold()) for a in result):continue
        key=item.access_service
        if not can_seerr and (key=='seerr' or item.label.casefold()=='seerr'):continue
        if key in ('radarr','sonarr','bazarr'):continue
        href=access_href(db,key) if key else item.url
        result.append(dict(key='menu:'+str(item.id),name=content(db,'menu:'+str(item.id)+':label',item.label,locale),href=href,image=item.icon_url or default_icon(key or item.label,media),icon=item.icon,external=item.new_tab and not key,howto=key or '',menu_key=item.menu_key))
    for tool in ('radarr','sonarr','bazarr'):
        if editor or tool in tools:result.append(dict(key=tool,name=tool.capitalize(),href='/tools/'+tool,image=default_icon(tool,media),icon='gears',external=False,howto=''))
    result.append(dict(key='account',name='My account',href='/account',image='',icon='user-circle',external=False,howto=''))
    return result

def normalize(layout,db):
    """Upgrade old block variants in memory without overwriting existing snapshots."""
    from copy import deepcopy
    value=deepcopy(layout);apps=catalog(db,editor=True);legacy_rows=[b for b in value['blocks'] if b['kind']=='services'];last_legacy=max(legacy_rows,key=lambda b:(b['order'],b['id']))['id'] if legacy_rows else None
    old_services=any(b['kind']=='services' for b in value['blocks'])
    for b in value['blocks']:
        kind=b['kind']
        if kind not in ('services','application','account','applications'):continue
        if kind=='account' and old_services and b['id']=='account' and b.get('body')=='Manage your details and password.':
            b['_remove']=True;continue
        if kind=='services':
            b['applications']=[a['key'] for a in apps if (a['key']!='access:emby' or b.get('include_emby')) and (not a.get('menu_key') or a['menu_key']==b.get('menu_key','main')) and (a['key']!='account' or b['id']==last_legacy) and (a['key'] not in ('radarr','sonarr','bazarr') or config(db,a['key']+'_enabled')=='true')]
        elif kind=='application':b['applications']=[b.get('service_key','emby') if b.get('service_key') in ('radarr','sonarr','bazarr') else 'access:'+b.get('service_key','emby')]
        elif kind=='account':b['applications']=['account']
        b.update(kind='applications',span=12,region='main');b.pop('parent',None);b.pop('slot',None);b.setdefault('columns',3)
    value['blocks']=[b for b in value['blocks'] if not b.pop('_remove',False)]
    # Preserve older selections when converting multi-row application grids.
    rows=[];used={b['id'] for b in value['blocks']}
    for b in sorted(value['blocks'],key=lambda b:(b['order'],b['id'])):
        if b['kind']!='applications':rows.append(b);continue
        selected=b.get('applications',[]);capacity=b.get('columns',3)
        chunks=[selected[i:i+capacity] for i in range(0,len(selected),capacity)] or [[]]
        for index,chunk in enumerate(chunks):
            row=deepcopy(b);row['applications']=chunk
            if index:
                suffix=1
                while (ident:=b['id'][:27]+'-row-'+str(suffix)) in used:suffix+=1
                used.add(ident);row['id']=ident
            rows.append(row)
    for index,row in enumerate(rows):row['order']=(index+1)*10
    value['blocks']=rows
    return value
