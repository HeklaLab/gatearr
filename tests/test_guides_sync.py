import json
import time
from sqlalchemy import select
from app import main, integrations
from app.db import SessionLocal
from app.models import Guide, AccessService, User, IntegrationJob
from app.sync_status import user_statuses
from app.security import digest
from test_portal import setup, post, logout, login_user, prepare_user, PASSWORD


def create(client):
    response=post(client,'/admin/guides/create',{'service_key':'emby','title_fr':'Emby sur mobile','title_en':'Emby on mobile'},'/admin/guides')
    assert response.status_code==303,response.text
    return int(response.headers['location'].split('/')[-1])


def guide_data(action='save',version=0,**extra):
    return {'action':action,'version':str(version),'device':'mobile','position':'10','title_fr':'Emby sur mobile','title_en':'Emby on mobile','summary_fr':'Pour {username}','summary_en':'For {username}','step_count':'2',
        'step_0_title_fr':'Sign in','step_0_title_en':'Connect','step_0_body_fr':'Serveur {server_host}, port {server_port} : {server_url}', 'step_0_body_en':'Server {server_host}, port {server_port}: {server_url}','step_0_position':'20',
        'step_1_title_fr':'Installer','step_1_title_en':'Install','step_1_body_fr':'<script>test</script>','step_1_link_url':'https://apps.apple.com/example','step_1_link_label_fr':'App Store','step_1_position':'10',**extra}


def edit(client,gid,data):
    return post(client,'/admin/guides/'+str(gid),data,'/admin/guides/'+str(gid))


def test_guide_publication_device_choices_localization_and_placeholders(client):
    setup(client,empty_journeys=True)
    assert post(client,'/admin/guides/service',{'key':'emby','name':'Emby','server_url':'https://media.example.com:8920','browser_url':'https://media.example.com/web'},'/admin/guides').status_code==303
    gid=create(client)
    assert edit(client,gid,guide_data()).status_code==303
    assert 'Emby sur mobile' not in client.get('/help').text
    assert client.get('/help/'+str(gid)).status_code==404
    preview=client.get('/help/'+str(gid)+'?preview=1').text
    assert 'Serveur media.example.com, port 8920' in preview
    assert '&lt;script&gt;' in preview and '<script>test</script>' not in preview
    assert preview.index('Installer')<preview.index('Sign in</h2>')
    assert 'http://emby.test' not in preview and 'test-api-key' not in preview
    assert edit(client,gid,guide_data('publish',1)).status_code==303
    with SessionLocal() as db:
        from app.access import save
        service=db.get(AccessService,'emby')
        save(db,service,[{'id':'browser','parent':'','kind':'browser','position':0,'title_fr':'Browser','title_en':'Browser'}, {'id':'mobile','parent':'','kind':'guide','guide_id':gid,'position':1,'title_fr':'Emby sur mobile','title_en':'Emby on mobile'}],0,True)
    home=client.get('/home').text
    assert 'href="/access/emby"' in home
    choices=client.get('/access/emby').text
    assert 'Browser' in choices and 'Emby sur mobile' in choices
    assert 'https://media.example.com/web' in choices
    assert client.get('/help',follow_redirects=False).headers['location']=='/home'
    assert post(client,'/language',{'locale':'en','next':'/help'},'/help').status_code==303
    assert 'Emby on mobile' in client.get('/access/emby').text
    article=client.get('/help/'+str(gid)).text
    assert 'Server media.example.com, port 8920' in article and 'For Owner' in article
    assert edit(client,gid,guide_data('save',2,title_fr='Brouillon secret',title_en='Secret draft')).status_code==303
    assert 'Secret draft' not in client.get('/help/'+str(gid)).text
    logout(client); login_user(client)
    assert client.get('/help/'+str(gid)).status_code==200
    assert client.get('/help/'+str(gid)+'?preview=1').status_code==403
    assert client.get('/admin/guides').status_code==403
    assert client.get('/admin/guides/'+str(gid)).status_code==403
    assert post(client,'/admin/guides/'+str(gid),guide_data('publish',3),'/home').status_code==403
    logout(client)
    assert client.get('/help').status_code==401
    assert client.get('/access/emby').status_code==401


def test_guide_validation_conflicts_unpublish_and_direct_fallback(client):
    setup(client);gid=create(client)
    assert edit(client,gid,guide_data('publish',0,step_count='0')).status_code==400
    assert edit(client,gid,guide_data('publish',0,step_1_link_url='javascript:alert(1)')).status_code==400
    assert edit(client,gid,guide_data('publish',0,step_1_image_url='https://user:secret@example.com/image')).status_code==400
    assert edit(client,gid,guide_data('save',0,device='bad')).status_code==400
    assert edit(client,gid,guide_data('publish',0)).status_code==303
    assert edit(client,gid,guide_data('save',0)).status_code==409
    assert client.post('/admin/guides/'+str(gid),data={'csrf':'wrong'}).status_code==403
    assert edit(client,gid,{'action':'unpublish','version':'1'}).status_code==303
    assert client.get('/help/'+str(gid)).status_code==404
    assert 'Sign in</h2>' in client.get('/help/'+str(gid)+'?preview=1').text
    assert client.get('/access/unknown').status_code==404
    for url in ('https://example.com:99999','http://name:password@example.com','https://example.com?secret=1'):
        assert post(client,'/admin/guides/service',{'key':'emby','name':'Emby','server_url':url},'/admin/guides').status_code==400


def test_custom_service_guides_in_menus_and_30_step_editor(client):
    setup(client)
    assert post(client,'/admin/guides/service',{'key':'seerr','name':'Seerr','browser_url':'https://requests.example.com'},'/admin/guides').status_code==303
    response=post(client,'/admin/menu',{'label':'Demandes','url':'','access_service':'seerr','icon':'★','position':'2'},'/admin')
    assert response.status_code==303,response.text
    assert 'href="/access/seerr"' in client.get('/home').text
    assert 'href="https://requests.example.com"' in client.get('/access/seerr').text
    assert post(client,'/admin/menu',{'label':'Bad','url':'','access_service':'missing','icon':'★','position':'2'},'/admin').status_code==400
    gid=create(client)
    data=guide_data(step_count='30')
    for index in range(30):
        data.update({f'step_{index}_title_fr':f'Étape {index}',f'step_{index}_body_fr':'Instructions',f'step_{index}_position':str(index)})
    assert edit(client,gid,data).status_code==303
    page=client.get('/admin/guides/'+str(gid)).text
    assert 'name="step_count" value="30"' in page
    assert 'step_29_body' in page and 'step_30_body' not in page
    assert edit(client,gid,guide_data('publish',1,step_count='1',step_0_delete='on')).status_code==400


def test_sync_history_pending_success_stale_error_and_hover_details(client,monkeypatch):
    prepare_user(client)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.emby_id=='user-1'));uid=user.id
        main.sync_users(db)
        main.set_config(db,'seerr_enabled','true');main.set_config(db,'seerr_url','https://seerr.test');main.set_config(db,'seerr_api_key','encrypted-for-status-test');db.commit()
        integrations.queue_user(db,user)
        statuses=user_statuses(db,'fr')[uid]
        assert statuses[0]['color']=='green' and statuses[1]['color']=='red'
        job=db.get(IntegrationJob,(uid,'seerr'));assert job.last_success_at is None
    monkeypatch.setattr(integrations,'sync_seerr',lambda db,user:None)
    integrations.run_jobs()
    with SessionLocal() as db:
        job=db.get(IntegrationJob,(uid,'seerr'));last=job.last_success_at
        assert last is not None
        assert user_statuses(db,'en')[uid][1]['label']=='Synchronized'
        user=db.get(User,uid);user.email='new@example.com';db.commit()
        assert user_statuses(db,'fr')[uid][1]['color']=='orange'
        integrations.queue_user(db,user)
        db.refresh(job)
        assert job.state=='pending' and job.last_success_at==last
    def failed(db,user):raise integrations.SyncError('authentication')
    monkeypatch.setattr(integrations,'sync_seerr',failed);integrations.run_jobs()
    with SessionLocal() as db:
        status=user_statuses(db,'fr')[uid][1]
        assert status['color']=='orange' and 'Authentication rejected' in status['detail']
        assert db.get(IntegrationJob,(uid,'seerr')).last_success_at==last
    logout(client)
    assert post(client,'/login',{'name':'Owner','password':PASSWORD}).status_code==303
    page=client.get('/admin/users').text
    assert 'sync-green' in page and 'sync-orange' in page and 'sync-red' in page
    assert 'role="tooltip"' in page and 'tabindex="0"' in page
    assert 'Authentication rejected' in page and 'Last success:' in page
    assert 'new@example.com' in page and 'test-api-key' not in page


def test_emby_missing_and_outage_retain_last_success(client,fake,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        main.sync_users(db)
        uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
        last=db.get(User,uid).emby_seen_at
        fake.deleted=True
        main.sync_users(db)
        status=user_statuses(db,'fr')[uid][0]
        assert status['color']=='orange' and 'Account missing from the latest import' in status['detail']
        assert db.get(User,uid).emby_seen_at==last
        fake.deleted=False
        main.sync_users(db)
        assert user_statuses(db,'fr')[uid][0]['color']=='green'
        def fail():raise main.EmbyError('secret remote error')
        monkeypatch.setattr(fake,'users',fail)
        import pytest
        with pytest.raises(main.EmbyError):main.sync_users(db)
        status=user_statuses(db,'fr')[uid][0]
        assert status['color']=='orange' and 'Service unavailable' in status['detail']
        assert 'secret remote error' not in status['detail']


def test_migration_recovers_prior_email_success(client):
    from alembic import command
    from alembic.config import Config as AlembicConfig
    setup(client)
    with SessionLocal() as db:
        main.sync_users(db)
        uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
        db.add(IntegrationJob(user_id=uid,service='seerr',email_digest=digest('demo@example.com'),state='success',attempts=0,next_attempt=0,updated_at=1700000000,error=''))
        db.commit()
    configuration=AlembicConfig('alembic.ini')
    command.downgrade(configuration,'0003')
    command.upgrade(configuration,'head')
    with SessionLocal() as db:
        assert db.get(IntegrationJob,(uid,'seerr')).last_success_at==1700000000
        assert db.get(AccessService,'emby').name=='Emby'
        assert db.get(User,uid).name=='demo'
