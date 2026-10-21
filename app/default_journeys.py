"""Starter journeys; never overwrite existing guides, paths or administrator text."""
import json
from pathlib import Path
from sqlalchemy import select
from .models import Guide,AccessService
from .mailer import config

def seed(db, activate=False, first_id=None):
    service=db.get(AccessService,'emby')
    if not service or json.loads(service.access_draft or '[]') or json.loads(service.access_published or '[]') or db.scalar(select(Guide.id).where(Guide.service_key=='emby').limit(1)):return False
    kind=config(db,'media_server','emby')
    preset=json.loads((Path(__file__).parent/'journey_defaults.json').read_text())[kind]
    nodes=preset['nodes']
    for offset,article in enumerate(preset['guides']):
        key=article.pop('key');article['_i18n_key']=''
        guide=Guide(id=first_id+offset if first_id is not None else None,service_key='emby',draft='{}',published=None,version=0)
        db.add(guide);db.flush()
        article['_i18n_key']='guide:'+str(guide.id)
        for step in article['steps']:step['_i18n_key']=article['_i18n_key']+':'+step['id']
        guide.draft=guide.published=json.dumps(article,ensure_ascii=False)
        for node in nodes:
            if node.get('guide_key')==key:node.pop('guide_key');node['guide_id']=guide.id
    for node in nodes:node['_i18n_key']='journey:emby:'+node['id']
    service.access_draft=service.access_published=json.dumps(nodes,ensure_ascii=False)
    service.access_version+=1
    if activate:service.entry_mode='structured'
    return True


def seed_seerr(db):
    service=db.get(AccessService,'seerr')
    if service:return
    nodes=[]
    db.add(AccessService(key='seerr',name='Seerr',browser_url='',server_url='',icon_url='',entry_mode='direct',access_draft=json.dumps(nodes),access_published=json.dumps(nodes),access_version=0))
