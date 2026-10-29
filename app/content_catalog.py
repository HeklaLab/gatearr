"""Discover translatable English source fields without duplicating content per language."""
import json
from sqlalchemy import select
from .models import Config,MenuItem,AccessService,Guide
from .mailer import config,DEFAULTS,html_source
from . import i18n


def sources(db):
    from . import portal
    rows={}
    def add(key,source,context,kind='text',maximum=5000):
        if source:rows[(key,i18n.source_hash(source))]={'key':key,'source':source,'context':context,'kind':kind,'maximum':maximum}
    add('branding:browser_title',config(db,'browser_title',''),'Branding',maximum=200)
    add('branding:app_name',config(db,'app_name','Gatearr'),'Branding',maximum=80)
    def blocks(value,scope,context):
        for block in value['blocks']:
            prefix=scope+':'+block['id']
            for field in ('title','body','alt'):
                add(prefix+':'+field,block.get(field,''),context+' · '+block['id'],'footer_html' if block.get('rich') and field=='body' else 'text',10000 if block.get('rich') else 5000)
            if block['kind']=='accordion':
                for item in block.get('items',[]):
                    for field in ('question','answer'):
                        add(prefix+':item:'+item['id']+':'+field,item.get(field,''),context+' · '+block['id']+' · '+item['id'],'accordion_html' if field=='answer' and item.get('rich') else 'text',10000)
            if block['kind']=='applications':
                defaults={'access:emby':'Access medias','access:seerr':'Request new movies & series','account':'Manage my account'}
                for key in block.get('applications',[]):
                    source=block.get('subtitles',{}).get(key,defaults.get(key,'Open application'))
                    add(prefix+':application-subtitle:'+key,source,'Application subtitle · '+block['id'],maximum=300)
                    if source:rows[(prefix+':application-subtitle:'+key,i18n.source_hash(source))]['target']=('My account' if key=='account' else key.split(':')[-1].capitalize())
    from . import footer
    from .visual_builder import load as load_design
    for draft in (False,True):
        blocks(portal.load(db,draft),'block','Home · '+('draft' if draft else 'published'))
    for page in ('login','forgot','reset','account','footer','header'):
        for draft in (False,True):
            if page=='header':add('branding:browser_title',load_design(db,page,draft).get('browser_title',''),'Header',maximum=200)
            blocks(load_design(db,page,draft),page+'-block',page.capitalize()+' page · '+('draft' if draft else 'published'))
    from .models import ContentPage
    for page in db.scalars(select(ContentPage).where(ContentPage.archived.is_(False))):
        for field in ('draft','published'):
            raw=getattr(page,field)
            if not raw:continue
            value=json.loads(raw);scope='page:'+str(page.id);context='Page '+str(page.id)+' · '+field
            for name in ('title','description'):add(scope+':'+name,value.get('page_settings',{}).get(name,''),context)
            blocks(value,scope,context)
    for draft in (False,True):
        for item in footer.load(db,draft)['items']:add('footer:'+item['id']+':text',item['text'],'Footer · '+('draft' if draft else 'published'),maximum=2000)
    for draft in (False,True):
        for index,column in enumerate(footer.load(db,draft).get('columns',[])):add('footer:column:'+str(index),column,'Footer column '+str(index+1),'footer_html',10000)
    for item in db.scalars(select(MenuItem)):add('menu:'+str(item.id)+':label',item.label,'Menu '+item.menu_key,maximum=100)
    for service in db.scalars(select(AccessService)):
        add('service:'+service.key+':name',service.name,'Service '+service.key,maximum=100)
        for column in ('access_draft','access_published'):
            for node in json.loads(getattr(service,column) or '[]'):add('journey:'+service.key+':'+node['id']+':title',node.get('title',''),'Journey '+service.key+' · '+column,maximum=200)
    for guide in db.scalars(select(Guide)):
        for column in ('draft','published'):
            if not getattr(guide,column):continue
            article=json.loads(getattr(guide,column));prefix='guide:'+str(guide.id)
            for field in ('title','summary'):add(prefix+':'+field,article.get(field,''),'Guide '+str(guide.id)+' · '+column,maximum=200 if field=='title' else 2000)
            for step in article['steps']:
                for field in ('title','body','link_label'):add(prefix+':'+step['id']+':'+field,step.get(field,''),'Guide '+str(guide.id)+' · '+step['id']+' · '+column,'footer_html' if step.get('rich') and field=='body' else 'text')
    from .models import PolicyState
    from .permissions import label
    for policy in db.scalars(select(PolicyState)):
        for key in json.loads(policy.observed):add('policy-label:'+key,label(key),'Media-server permissions',maximum=200)
    from .email_editor import purposes
    for purpose in purposes(db):
        for part in ('subject','body','html'):
            source=html_source(db,purpose) if part=='html' else config(db,purpose+'_'+part,DEFAULTS[purpose+'_'+part])
            add('mail:'+purpose+':'+part,source,'Email · '+purpose,'html' if part=='html' else 'subject' if part=='subject' else 'mail',50000 if part=='html' else 300 if part=='subject' else 10000)
    # Authored block content remains editable regardless of its audience.
    # Native administration/permission labels are not authored content.
    return [entry for entry in rows.values() if not entry['key'].startswith('policy-label:')]
