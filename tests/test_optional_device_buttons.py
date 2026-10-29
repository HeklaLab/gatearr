"""Device return controls are independent page blocks, never compulsory guide markup."""
import json,re
from app import page_builder,visual_builder,page_presets
from app.db import SessionLocal
from app.models import AccessService,ContentPage
from test_portal import setup,post
from test_content_pages import create_page,save_page


def prepare(client):
    setup(client,fresh_layout=True)
    with SessionLocal() as db:
        service=db.get(AccessService,'emby');nodes=json.loads(service.access_published)
        group=next(n['id'] for n in nodes if n['kind']=='group')
        guide=next(n['guide_id'] for n in nodes if n['kind']=='guide')
        row=page_builder.guide_row(db,'emby');key='p-'+str(row.id)
        value=visual_builder.load(db,key,True)
    return key,value,group,guide


def buttons(html):return re.findall(r'<div class="guide-device-navigation">(.*?)</div>',html)


def test_default_buttons_can_be_removed_without_changing_published_content_until_publication(client):
    key,value,group,guide=prepare(client)
    root='/access/emby?view=guide';sub='/access/emby/'+group+'?view=guide';article='/access/emby/guide/'+str(guide)
    assert not buttons(client.get(root).text)
    assert len(buttons(client.get(sub).text))==2
    assert len(buttons(client.get(article).text))==2
    assert len([b for b in value['blocks'] if b.get('button_action')=='choose_device'])==2
    value['blocks']=[b for b in value['blocks'] if b.get('button_action')!='choose_device']
    assert save_page(client,key,value).status_code==200
    assert len(buttons(client.get(sub).text))==2
    assert save_page(client,key,value,True).status_code==200
    assert not buttons(client.get(sub).text) and not buttons(client.get(article).text)
    client.get('/admin/pages')
    assert not buttons(client.get(sub).text)  # No automatic reinsertion.


def test_access_guide_button_can_be_renamed_or_shown_on_root(client):
    key,value,group,guide=prepare(client)
    back=page_presets.device_button('back',10);back['title']='Select my device'
    value['blocks']=[back,page_presets.block('guide_embed','access',20,service_key='emby')]
    assert save_page(client,key,value,True).status_code==200
    assert not buttons(client.get('/access/emby?view=guide').text)
    for path in ('/access/emby/'+group+'?view=guide','/access/emby/guide/'+str(guide)):
        result=buttons(client.get(path).text)
        assert len(result)==1 and 'href="/access/emby?view=guide"' in result[0] and 'Select my device' in result[0]
    back['after_device']=False
    assert save_page(client,key,value,True).status_code==200
    assert len(buttons(client.get('/access/emby?view=guide').text))==1


def test_navigation_actions_are_validated_and_available_only_with_a_subpage_guide(client):
    _,_,_,_=prepare(client)
    key,value=create_page(client,preset='blank')
    value['blocks']=[page_presets.device_button('back',10)]
    assert save_page(client,key,value).status_code==400
    value['blocks'].append(page_presets.block('guide_embed','access',20,service_key='emby'))
    value['blocks'][0]['button_action']='unsafe-action'
    assert save_page(client,key,value).status_code==400
    with SessionLocal() as db:home=visual_builder.load(db,'home',True);version=visual_builder.version(db,'home')
    home['blocks'].append(page_presets.device_button('back',100))
    assert post(client,'/admin/design/home/save',dict(version=version,payload=json.dumps(home)),'/admin').status_code==400
