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
    for draft in (False,True):
        for block in portal.load(db,draft)['blocks']:
            for field in ('title','body','alt'):add('block:'+block['id']+':'+field,block.get(field,''),'Block '+block['id']+(' · draft' if draft else ' · published'),'footer_html' if block.get('rich') and field=='body' else 'text')
            if block['kind']=='applications':
                defaults={'access:emby':'Access medias','access:seerr':'Request new movies & series','account':'Manage my account'}
                for key in block.get('applications',[]):
                    add('block:'+block['id']+':application-subtitle:'+key,block.get('subtitles',{}).get(key,defaults.get(key,'Open application')),'Application subtitle · '+block['id'],maximum=300)
                    source=block.get('subtitles',{}).get(key,defaults.get(key,'Open application'))
                    if source:
                        entry=rows[('block:'+block['id']+':application-subtitle:'+key,i18n.source_hash(source))]
                        entry['target']=('My account' if key=='account' else key.split(':')[-1].capitalize())
    from . import footer
    from .visual_builder import load as load_design
    for page in ('login','footer'):
        for draft in (False,True):
            for block in load_design(db,page,draft)['blocks']:
                for field in ('title','body','alt'):add(page+'-block:'+block['id']+':'+field,block.get(field,''),page.capitalize()+' page','footer_html' if block.get('rich') and field=='body' else 'text',10000 if block.get('rich') else 5000)
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
    # Keep native admin translations separate from editable public content.
    public_blocks=set(); public_subtitles=set()
    for draft in (False,True):
        blocks=portal.load(db,draft)['blocks'];by_id={b['id']:b for b in blocks}
        for block in blocks:
            ancestor=block;admin_only=False;seen=set()
            while ancestor and ancestor['id'] not in seen:
                seen.add(ancestor['id']);admin_only|=ancestor.get('visibility')=='admins';ancestor=by_id.get(ancestor.get('parent'))
            if admin_only:continue
            public_blocks.add(block['id'])
            for app in block.get('applications',[]):
                if app not in ('radarr','sonarr','bazarr','tdarr','tracearr'):public_subtitles.add('block:'+block['id']+':application-subtitle:'+app)
    def public(entry):
        key=entry['key']
        if key.startswith('policy-label:'):return False
        if key.startswith('block:'):
            if key.split(':')[1] not in public_blocks:return False
            if ':application-subtitle:' in key:return key in public_subtitles
        return True
    return [entry for entry in rows.values() if public(entry)]
