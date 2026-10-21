"""Admin-chosen application journeys: nested groups, links and published guides."""
import json
import re
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from .models import AccessService, Guide
from .main import form, require_admin, require_user, render, redirect
from .guides import local, service_url
from .security import url_ok
from . import i18n

router=APIRouter()

def service_or_404(db,key):
    service=db.get(AccessService,key)
    if not service:raise HTTPException(404,'Service not found')
    return service

def load(service,draft=False):
    return json.loads((service.access_draft if draft else service.access_published) or '[]')

def validate(db,service,nodes,publish=False):
    if not isinstance(nodes,list) or len(nodes)>100:raise ValueError('A journey supports up to 100 entries')
    indexed={}
    for node in nodes:
        ident=node.get('id','')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',ident) or ident in indexed:raise ValueError('Invalid journey entry')
        indexed[ident]=node
        if node.get('kind') not in ('group','browser','link','guide') or type(node.get('position')) is not int:raise ValueError('Invalid journey entry')
        if not str(node.get('title','')).strip():raise ValueError('Title required')
        if not isinstance(node.get('title',''),str) or len(node.get('title',''))>200:raise ValueError('Guide text is too long')
        image=node.get('icon_url','')
        if image and not re.fullmatch(r'/media/icons/[a-f0-9]{64}\.(?:png|svg)',image):url_ok(image)
        if node.get('icon'):
            from .icons import font_icon
            font_icon(node['icon'])
        if node['kind']=='link':url_ok(node.get('url',''))
        if node['kind']=='guide':
            guide=db.get(Guide,int(node.get('guide_id',0)))
            if not guide or guide.service_key!=service.key or (publish and not guide.published):raise ValueError('Choose a published guide for this service')
    for node in nodes:
        path={node['id']};parent=node.get('parent','')
        for _ in range(9):
            if not parent:break
            if parent in path or parent not in indexed or indexed[parent]['kind']!='group':raise ValueError('Invalid or circular submenu')
            path.add(parent);parent=indexed[parent].get('parent','')
        else:raise ValueError('A journey supports up to 8 levels')
    return nodes

def save(db,service,nodes,expected,publish=False,mode='choices'):
    for node in nodes:
        node["_i18n_key"]="journey:"+service.key+":"+node["id"]
        i18n.normalize_fields(db,node,node["_i18n_key"],("title",))
    validate(db,service,nodes,publish and mode=='choices')
    values={'access_draft':json.dumps(nodes,ensure_ascii=False),'access_version':expected+1}
    if publish:values.update(access_published=values['access_draft'],entry_mode='direct' if mode=='link' else 'structured')
    result=db.execute(update(AccessService).where(AccessService.key==service.key,AccessService.access_version==expected).values(**values))
    if result.rowcount!=1:
        db.rollback();raise HTTPException(409,'The journey was changed. Reload this page.')
    db.commit()

def access_href(db,key):
    service=db.get(AccessService,key)
    if not service:return ''
    from .mailer import config
    root=json.loads(config(db,'howto_root_published_'+key,'{}'))
    if service.entry_mode=='structured' and root.get('mode')=='guide':
        guide=db.get(Guide,root.get('guide_id',0))
        if guide and guide.service_key==key and guide.published:return '/access/'+key+'/guide/'+str(guide.id)
    return '/access/'+key if service.entry_mode=='structured' else service_url(db,service)

def visible_nodes(db,service,nodes):
    published=set(db.scalars(select(Guide.id).where(Guide.service_key==service.key,Guide.published.is_not(None))))
    visible=[node for node in nodes if (node['kind']!='guide' or node['guide_id'] in published) and (node['kind']!='browser' or service_url(db,service))]
    for _ in range(10):
        parents={node.get('parent','') for node in visible}
        filtered=[node for node in visible if node['kind']!='group' or node['id'] in parents]
        if len(filtered)==len(visible):break
        visible=filtered
    return visible

def public_access(request,key,node_id=''):
    user=require_user(request)
    from .group_access import seerr_allowed
    if key=='seerr' and not seerr_allowed(request.state.db,user):raise HTTPException(403,'Seerr access is not granted')
    db=request.state.db;service=service_or_404(db,key)
    if service.entry_mode=='direct':
        url=service_url(db,service)
        if not url:raise HTTPException(404,'Service not found')
        return redirect(url)
    if not node_id and '/guide/' in (href:=access_href(db,key)):return redirect(href)
    nodes=visible_nodes(db,service,load(service));indexed={node['id']:node for node in nodes}
    current=indexed.get(node_id) if node_id else None
    if node_id and (not current or current['kind']!='group'):raise HTTPException(404,'Submenu not found')
    crumbs=[];parent=current
    while parent:
        crumbs.append({'title':local(parent,'title',request.state.locale,db),'href':'/access/'+key+'/'+parent['id']})
        parent=indexed.get(parent.get('parent',''))
    crumbs.reverse()
    entries=[]
    for node in sorted(nodes,key=lambda node:(node['position'],node['id'])):
        if node.get('parent','')!=node_id:continue
        kind=node['kind'];href='/access/'+key+'/'+node['id']
        if kind=='browser':href=service_url(db,service)
        elif kind=='link':href=node['url']
        elif kind=='guide':href='/access/'+key+'/guide/'+str(node['guide_id'])
        entries.append({**node,'title':local(node,'title',request.state.locale,db),'href':href,'external':kind in ('link','browser')})
    return render(request,'access.html',service=service,entries=entries,crumbs=crumbs,current_title=local(current,'title',request.state.locale,db) if current else i18n.content(db,"service:"+service.key+":name",service.name,request.state.locale))

@router.get('/access/{key}/{node_id}')
def submenu(request: Request,key: str,node_id: str):
    return public_access(request,key,node_id)

@router.get('/admin/access/{key}')
def editor(request: Request,key: str):
    require_admin(request)
    from .visual_howto import howto_editor
    return howto_editor(request,key)

@router.post('/admin/access/{key}')
def edit(request: Request,key: str,data=Depends(form)):
    require_admin(request)
    db=request.state.db;service=service_or_404(db,key);nodes=load(service,True)
    action=data.get('action','save');expected=int(data.get('version','-1'))
    if action=='publish':save(db,service,nodes,expected,True)
    elif action=='reset':save(db,service,load(service),expected)
    elif action=='delete':
        ident=str(data.get('id',''));removed={ident}
        for _ in range(10):removed.update(node['id'] for node in nodes if node.get('parent') in removed)
        save(db,service,[node for node in nodes if node['id'] not in removed],expected)
    elif action=='save':
        ident=str(data.get('id','')) or secrets.token_hex(8)
        if data.get('id') and not any(node['id']==ident for node in nodes):raise HTTPException(404,'Submenu not found')
        from .icons import local_icon_value,font_icon
        image=local_icon_value(db,data)
        node={'icon':font_icon(data.get('icon','link')),'id':ident,'kind':str(data.get('kind','group')),'parent':str(data.get('parent','')),'position':int(data.get('position','10')),**{field:str(data[field]) for field in ('title','title_fr','title_en') if field in data},'icon_url':image,'url':str(data.get('url','')),'guide_id':int(data.get('guide_id','0') or '0')}
        if node['kind']=='guide' and not node['guide_id']:
            if service.access_version!=expected:raise HTTPException(409,'The How to changed. Reload this page.')
            guide=Guide(service_key=key,draft=json.dumps({'title':node['title'],'summary':'','device':'other','steps':[]}),version=0)
            db.add(guide);db.flush();node['guide_id']=guide.id
            save(db,service,[old for old in nodes if old['id']!=ident]+[node],expected)
            return redirect('/admin/guides/'+str(guide.id))
        save(db,service,[old for old in nodes if old['id']!=ident]+[node],expected)
    else:raise ValueError('Invalid action')
    return redirect('/admin/access/'+key)
