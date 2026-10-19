import json
from types import SimpleNamespace
import httpx
import pytest
from sqlalchemy import select
from app import main, access, integrations
from app.db import SessionLocal
from app.models import User, AccessService, Guide, IntegrationJob
from app.security import decrypt, digest
from app.connections import emby_connection
from app.emby import EmbyClient
from test_portal import setup,post,logout,login_user,prepare_user
from test_gatearr import configured
from test_guides_sync import create,edit,guide_data


def nodes(client, action='save', **values):
    with SessionLocal() as db:version=db.get(AccessService,'emby').access_version
    return post(client,'/admin/access/emby',{'version':version,'action':action,**values},'/admin/access/emby')


def test_nested_journey_direct_mode_icons_and_no_help_navigation(client):
    setup(client);gid=create(client)
    assert edit(client,gid,guide_data('publish')).status_code==303
    assert post(client,'/admin/guides/service',{'key':'emby','name':'Emby','browser_url':'https://media.test','entry_mode':'direct','icon_url':'https://cdn.test/emby.png'},'/admin/guides').status_code==303
    assert 'href="/services/emby/open"' in client.get('/home').text
    assert 'href="/help"' not in client.get('/home').text
    assert 'https://cdn.test/emby.png' in client.get('/home').text
    for kind,title,parent in [('browser','Browser',''),('group','Computer',''),('group','Mobile','')]:
        assert nodes(client,kind=kind,title_fr=title,title_en=title,parent=parent,position=1).status_code==303
    with SessionLocal() as db:tree=access.load(db.get(AccessService,'emby'),True)
    desktop=next(node['id'] for node in tree if node['title']=='Computer')
    mobile=next(node['id'] for node in tree if node['title']=='Mobile')
    assert nodes(client,kind='guide',title_fr='Mac',title_en='Mac',parent=desktop,guide_id=gid,position=2,icon_url='https://cdn.test/mac.png').status_code==303
    assert nodes(client,kind='link',title_fr='iPhone',title_en='iPhone',parent=mobile,url='https://apps.apple.com/example',position=2).status_code==303
    # Draft remains private; direct mode is not inferred from a published guide.
    assert client.get('/access/emby',follow_redirects=False).headers['location']=='/services/emby/open'
    assert nodes(client,'publish').status_code==303
    home=client.get('/home').text
    assert 'href="/access/emby"' in home
    root=client.get('/access/emby').text
    assert 'Computer' in root and 'Mobile' in root and '>Mac<' not in root
    page=client.get('/access/emby/'+desktop).text
    assert 'Mac' in page and 'https://cdn.test/mac.png' in page
    assert '/access/emby/guide/'+str(gid) in page
    assert client.get('/access/emby/guide/'+str(gid)).status_code==200
    # The admin can switch back to a direct link without losing the saved journey.
    post(client,'/admin/guides/service',{'key':'emby','name':'Emby','browser_url':'https://media.test','entry_mode':'direct'},'/admin/guides')
    assert 'href="/services/emby/open"' in client.get('/home').text
    assert post(client,'/admin/menu',{'label':'Requests','url':'https://requests.test','icon':'link','icon_url':'https://cdn.test/requests.png','position':2},'/admin').status_code==303
    assert 'https://cdn.test/requests.png' in client.get('/account').text


def test_journey_validation_conflicts_and_draft_deletion(client):
    setup(client,empty_journeys=True)
    nodes(client,kind='group',title_fr='Computer',position=1)
    with SessionLocal() as db:
        row=db.get(AccessService,'emby');tree=access.load(row,True);ident=tree[0]['id'];version=row.access_version
    assert nodes(client,id=ident,kind='group',title_fr='Cycle',parent=ident,position=1).status_code==400
    assert nodes(client,kind='group',title_fr='Orphan',parent='missing',position=1).status_code==400
    assert nodes(client,kind='link',title_fr='Bad',url='javascript:alert(1)',position=1).status_code==400
    assert nodes(client,kind='group',title_fr='Bad',icon_url='data:image/png;base64,bad',position=1).status_code==400
    assert nodes(client,kind='link',title_fr='Download',url='https://store.test',parent=ident,position=2).status_code==303
    assert post(client,'/admin/access/emby',{'action':'publish','version':version},'/admin').status_code==409
    assert nodes(client,'publish').status_code==303
    assert nodes(client,'delete',id=ident).status_code==303
    assert 'Computer' in client.get('/access/emby').text
    assert nodes(client,'publish').status_code==303
    assert 'Computer' not in client.get('/access/emby').text
    logout(client);login_user(client)
    assert client.get('/admin/access/emby').status_code==403
    assert post(client,'/admin/access/emby',{'action':'publish','version':0},'/home').status_code==403


def test_api_connection_ui_encryption_current_url_and_key(client,monkeypatch):
    setup(client)
    response=post(client,'/admin/connections/emby',{'url':'https://new-backend.test/emby','api_key':'private-new-emby-key'},'/admin/integrations')
    assert response.status_code==303,response.text
    assert emby_connection()==('https://new-backend.test/emby','private-new-emby-key')
    with SessionLocal() as db:
        from app.models import Config
        stored=db.get(Config,'emby_api_key').value
        assert stored!='private-new-emby-key' and decrypt(stored)=='private-new-emby-key'
    page=client.get('/admin/integrations').text
    assert 'Emby API URL' in page and 'new-backend.test' in page
    assert 'private-new-emby-key' not in page
    observed=[];original=httpx.Client
    def handler(req):
        observed.append(req)
        return httpx.Response(200,json={'Items':[],'TotalRecordCount':0})
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    assert EmbyClient().users()==[]
    assert observed[0].url.host=='new-backend.test'
    assert observed[0].headers['X-Emby-Token']=='private-new-emby-key'
    logout(client);login_user(client)
    assert 'new-backend.test' not in client.get('/account').text
    assert client.get('/admin/integrations').status_code==403
    assert post(client,'/admin/connections/emby',{'url':'https://evil.test'},'/account').status_code==403


def test_preference_permissions_queue_and_forced_seerr(client):
    prepare_user(client)
    with SessionLocal() as db:
        configured(db,'seerr')
        main.set_config(db,'seerr_notification_mode','optional');db.commit()
    page=client.get('/account').text
    assert 'Receive the newsletter' not in page and 'Receive notifications about my requests' in page
    assert post(client,'/account/preferences',{'service':'seerr','enabled':'on'},'/account').status_code==303
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'))
        assert user.seerr_notifications
        main.set_config(db,'seerr_notification_mode','forced');db.commit()
    assert post(client,'/account/preferences',{'service':'seerr'},'/account').status_code==403
    assert 'Your administrator requires these notifications.' in client.get('/account').text
    assert client.post('/account/preferences',data={'csrf':'bad','service':'tracearr'}).status_code==403
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'));user.email=None;db.commit()
    assert post(client,'/account/preferences',{'service':'tracearr'},'/account').status_code==400




def test_seerr_notification_writes_preserve_other_agents_and_pgp(client):
    prepare_user(client)
    values={'emailEnabled':True,'pgpKey':'public-pgp-key','discordIds':['123'],'telegramChatId':'456','telegramMessageThreadId':'8','notificationTypes':{'email':0,'discord':8,'telegram':64}}
    writes=[]
    def handler(req):
        if req.method=='POST':
            body=json.loads(req.content);writes.append(body);values.update(body)
        return httpx.Response(200,json=values)
    with SessionLocal() as db:
        main.set_config(db,'seerr_notification_mode','optional');db.commit()
        user=db.scalar(select(User).where(User.emby_id=='user-1'));user.seerr_notifications=True
        with httpx.Client(base_url='https://seerr.test',transport=httpx.MockTransport(handler)) as api:
            integrations.sync_seerr_notifications(db,api,user,'/notifications')
            assert values['notificationTypes']=={'email':8190,'discord':8,'telegram':64}
            assert writes[0]['pgpKey']=='public-pgp-key' and writes[0]['telegramChatId']=='456'
            user.seerr_notifications=False
            integrations.sync_seerr_notifications(db,api,user,'/notifications')
            assert values['notificationTypes']['email']==0
            main.set_config(db,'seerr_notification_mode','forced');db.commit()
            integrations.sync_seerr_notifications(db,api,user,'/notifications')
            assert values['notificationTypes']['email']==8190
            values['emailEnabled']=False
            with pytest.raises(integrations.SyncError,match='notifications_disabled'):integrations.sync_seerr_notifications(db,api,user,'/notifications')




def test_upgrade_migrates_existing_published_guides_into_explicit_journey(client):
    from alembic import command
    from alembic.config import Config as AlembicConfig
    setup(client,empty_journeys=True);gid=create(client)
    assert edit(client,gid,guide_data('publish')).status_code==303
    configuration=AlembicConfig('alembic.ini')
    command.downgrade(configuration,'0004')
    command.upgrade(configuration,'head')
    with SessionLocal() as db:
        service=db.get(AccessService,'emby');tree=access.load(service)
        assert service.entry_mode=='structured'
        assert next(node for node in tree if node['kind']=='guide')['guide_id']==gid
        assert any(node['kind']=='browser' for node in tree)
        assert db.get(Guide,gid).published is not None
