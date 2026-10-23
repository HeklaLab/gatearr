"""Visual choice trees and step editors, retaining existing guide IDs and snapshots."""
import json,secrets
from fastapi import APIRouter,Request,Depends,HTTPException
from sqlalchemy import select
from .main import form,require_admin,render,set_config
from . import access,guides
from .models import Guide,MenuItem
from .mailer import config
from .security import url_ok
from .page_design import asset_url
router=APIRouter()

def decode(data):
    try:value=json.loads(data.get('payload','{}'))
    except (ValueError,TypeError):raise ValueError('Invalid editor content')
    if not isinstance(value,dict):raise ValueError('Invalid editor content')
    return value

def howto_editor(request,key):
    require_admin(request)
    if key in ('radarr','sonarr','bazarr','tracearr','tdarr'):raise HTTPException(400,'How to is unavailable for this application')
    db=request.state.db;service=access.service_or_404(db,key)
    rows=list(db.scalars(select(Guide).where(Guide.service_key==key)))
    return render(request,'visual_howto.html',howto_data={'type':'choices','key':key,'name':service.name,'version':service.access_version,'nodes':[{**node,'icon':access.category_icon(node)} for node in access.load(service,True)],'guides':[{'id':r.id,'title':json.loads(r.draft).get('title',''),'published':bool(r.published)} for r in rows],'server_url':service.server_url,'root':json.loads(config(db,'howto_root_draft_'+key,'{}')),'browser_url':service.browser_url},service=service)

def guide_editor(request,guide_id):
    require_admin(request);row=guides.guide_or_404(request.state.db,guide_id)
    service=access.service_or_404(request.state.db,row.service_key)
    return render(request,'visual_howto.html',howto_data={'type':'guide','id':row.id,'nodes':access.load(service,True),'key':row.service_key,'name':service.name,'version':row.version,'article':json.loads(row.draft),'published':bool(row.published),'server_url':service.server_url},service=service)

@router.post('/admin/visual-howto/{key}/{action}')
def choices(request:Request,key:str,action:str,data=Depends(form)):
    require_admin(request)
    if key in ('radarr','sonarr','bazarr','tracearr','tdarr'):raise HTTPException(400,'How to is unavailable for this application')
    db=request.state.db;service=access.service_or_404(db,key);value=decode(data)
    if action=='new-guide':
        title=str(value.get('title','New guide')).strip()[:200]
        if not title:raise ValueError('Guide title required')
        row=Guide(service_key=key,draft=json.dumps({'title':title,'summary':'','position':10,'device':'other','steps':[]}),version=0)
        db.add(row);db.commit();return {'id':row.id,'title':title,'published':False}
    if action not in ('save','publish','preview','restore'):raise HTTPException(404,'Page not found')
    if action=='restore':value={**json.loads(config(db,'howto_root_published_'+key,'{}')),'nodes':access.load(service)}
    nodes=value.get('nodes',[])
    mode=value.get('mode','choices')
    if mode not in ('choices','link','guide'):raise ValueError('Invalid action')
    browser=url_ok(value.get('browser_url',service.browser_url),optional=mode!='link')
    root_guide=db.get(Guide,int(value.get('guide_id',0) or 0)) if mode=='guide' else None
    if mode=='guide' and (not root_guide or root_guide.service_key!=key or (action=='publish' and not root_guide.published)):raise ValueError('Choose a published guide for this service')
    if action=='restore':nodes=access.load(service)
    access.validate(db,service,nodes,publish=action=='publish' and mode=='choices')
    if action=='preview':
        if mode=='guide':return render(request,'guide.html',guide=root_guide,service=service,article=guides.display(root_guide.draft,service,request.state.user,request.state.locale,db),visual_preview=True)
        if mode=='link':return render(request,'direct_preview.html',service=service,url=browser,visual_preview=True)
        parent=str(value.get('parent',''));index={n['id']:n for n in nodes};current=index.get(parent);entries=[]
        for n in sorted(nodes,key=lambda n:(n['position'],n['id'])):
            if n.get('parent','')!=parent:continue
            href='/access/'+key+'/'+n['id']
            if n['kind']=='guide':href='/access/'+key+'/guide/'+str(n['guide_id'])+'?preview=1'
            if n['kind']=='link':href=n['url']
            if n['kind']=='browser':href=guides.service_url(db,service) or '#'
            entries.append({**n,'icon':access.category_icon(n),'href':href,'external':n['kind'] in ('link','browser')})
        crumbs=[];node=current
        while node:
            crumbs.append({'title':node['title'],'href':'/access/'+key+'/'+node['id']});node=index.get(node.get('parent',''))
        return render(request,'access.html',service=service,entries=entries,crumbs=list(reversed(crumbs)),current_title=current['title'] if current else service.name,visual_preview=True)
    expected=int(data.get('version','-1'))
    if service.access_version!=expected:raise HTTPException(409,'The journey was changed. Reload this page.')
    root=json.dumps({'mode':mode,'guide_id':root_guide.id if root_guide else 0,'browser_url':browser})
    set_config(db,'howto_root_draft_'+key,root)
    if action=='publish':
        set_config(db,'howto_root_published_'+key,root)
        service.browser_url=browser
    access.save(db,service,nodes,expected,action=='publish',mode=mode)
    request.state.audit_detail=('Published' if action=='publish' else 'Saved draft')+': '+service.name+' How to, '+str(len(nodes))+' choices'
    return {'version':db.get(type(service),key).access_version,'nodes':nodes,'root':json.loads(root)}

def validated_article(db,value):
    steps=value.get('steps')
    if not isinstance(steps,list) or len(steps)>30:raise ValueError('A guide supports up to 30 steps')
    flat={k:value.get(k,'') for k in ('title','summary')};flat.update(device=value.get('device','other'),position=value.get('position',10),step_count=max(1,len(steps)))
    for i,step in enumerate(steps):
        if not isinstance(step,dict):raise ValueError('Invalid step')
        for key in ('id','title','body','link_label','link_url','image_url'):flat['step_'+str(i)+'_'+key]=step.get(key,'')
        flat['step_'+str(i)+'_position']=(i+1)*10
        # Validate persisted image references against uploaded assets.
        if step.get('image_url'):
            from .image_sources import require_image
            require_image(step['image_url'],db)
        if step.get('image_url','').startswith('/media/icons/'):
            asset_url(step['image_url'],db);flat['step_'+str(i)+'_image_url']=''
    article=guides.validated(flat)
    for index,step in enumerate(article['steps']):
        source=next((s for s in steps if s.get('id')==step['id']),None)
        if source:
            if source.get('image_url','').startswith('/media/icons/'):step['image_url']=source['image_url']
            if source.get('rich'):
                from .footer import clean_html
                step['rich']=True;step['body']=clean_html(step.get('body',''))
    return article

@router.post('/admin/visual-guide/{guide_id}/{action}')
def article(request:Request,guide_id:int,action:str,data=Depends(form)):
    require_admin(request);db=request.state.db;row=guides.guide_or_404(db,guide_id)
    if action not in ('save','publish','preview','restore','unpublish'):raise HTTPException(404,'Page not found')
    value=decode(data)
    if action=='restore':value=json.loads(row.published or row.draft)
    value=validated_article(db,value)
    if action=='preview':
        service=access.service_or_404(db,row.service_key)
        return render(request,'guide.html',guide=row,service=service,article=guides.display(json.dumps(value),service,request.state.user,request.state.locale,db),visual_preview=True)
    if action=='publish' and not value['steps']:raise ValueError('Add at least one step before publishing')
    guides.normalize(db,value,row.id);encoded=json.dumps(value,ensure_ascii=False)
    values={'draft':encoded}
    if action=='publish':values['published']=encoded
    elif action=='unpublish':values['published']=None
    guides.save(db,row,int(data.get('version','-1')),**values)
    request.state.audit_detail=('Published' if action=='publish' else 'Saved draft')+': guide '+value.get('title','')+', '+str(len(value['steps']))+' steps'
    return {'version':db.get(Guide,guide_id).version,'article':value}
