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
    add('branding:app_name',config(db,'app_name','Gatearr'),'Branding',maximum=80)
    add('branding:login_text',config(db,'login_text','Access your services and manage your account with ease.'),'Sign-in page',maximum=2000)
    for draft in (False,True):
        for block in portal.load(db,draft)['blocks']:
            for field in ('title','body','alt'):add('block:'+block['id']+':'+field,block.get(field,''),'Block '+block['id']+(' · draft' if draft else ' · published'))
    from . import footer
    for draft in (False,True):
        for item in footer.load(db,draft)['items']:add('footer:'+item['id']+':text',item['text'],'Footer · '+('draft' if draft else 'published'),maximum=2000)
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
                for field in ('title','body','link_label'):add(prefix+':'+step['id']+':'+field,step.get(field,''),'Guide '+str(guide.id)+' · '+step['id']+' · '+column)
    from .models import PolicyState
    from .permissions import label
    for policy in db.scalars(select(PolicyState)):
        for key in json.loads(policy.observed):add('policy-label:'+key,label(key),'Media-server permissions',maximum=200)
    for purpose in ('invite','verify','reset'):
        for part in ('subject','body','html'):
            source=html_source(db,purpose) if part=='html' else config(db,purpose+'_'+part,DEFAULTS[purpose+'_'+part])
            add('mail:'+purpose+':'+part,source,'Email · '+purpose,'html' if part=='html' else 'subject' if part=='subject' else 'mail',50000 if part=='html' else 300 if part=='subject' else 10000)
    return list(rows.values())
