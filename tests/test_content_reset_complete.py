import json
from sqlalchemy import select
from app import main,portal,header,footer,visual_builder
from app.db import SessionLocal
from app.models import Config,ContentPage,AccessService,MenuItem,User,PermissionGroup,GroupMember,ContentTranslation,PolicyState,SeerrPolicyState,GroupBaseline
from test_portal import setup,post,csrf
from test_content_pages import create_page,save_page


def snapshot(db,model):
    return sorted((tuple(getattr(row,c.name) for c in model.__table__.columns) for row in db.scalars(select(model))),key=repr)


def test_content_reset_rebuilds_all_presets_and_preserves_accounts_permissions_connections_smtp(client):
    setup(client)
    page,value=create_page(client,'custom-private-page')
    assert save_page(client,page,value,True).status_code==200
    archived,archived_value=create_page(client,'archived-custom-page')
    with SessionLocal() as db:
        db.get(ContentPage,int(archived[2:])).archived=True
        user=db.scalar(select(User));user.tool_access='["radarr"]';user.bazarr_subtitles=True
        group=PermissionGroup(name='Retained group',policy='{}');db.add(group);db.flush()
        db.add(GroupMember(group_id=group.id,user_id=user.id))
        native=db.get(AccessService,'emby');native.browser_url='https://media.example.com';native.server_url='http://emby.private:8096'
        db.add(AccessService(key='service-999',name='Emby',browser_url='https://custom.example.com',server_url='https://custom.example.com'))
        db.add(MenuItem(label='Emby',url='https://custom.example.com',menu_key='main',position=10,access_service='service-999'))
        for key,value in {'smtp_host':'smtp.private','smtp_port':'2525','smtp_user':'retained','smtp_password':'encrypted-mail-secret','smtp_from':'portal@example.com','smtp_tls':'true','radarr_url':'http://radarr.private:7878','radarr_api_key':'encrypted-radarr-secret','radarr_enabled':'true','bazarr_subtitle_profile':'2','captcha_login':'true'}.items():main.set_config(db,key,value)
        main.set_config(db,'app_name','Custom branding')
        main.set_config(db,'deleted_system_page:faq','true')
        main.set_config(db,'deleted_system_page:guide:emby','true')
        for key in ('login','forgot','reset','account','header'):
            layout=visual_builder.load(db,key,True)
            layout['blocks'].append(dict(id='custom-'+key,kind='text',region='main',span=12,order=900,title='Old customization',body=''))
            if key=='header':layout=header.normalize(layout)
            for part in ('draft','published'):main.set_config(db,key+'_'+part,json.dumps(layout))
            main.set_config(db,key+'_version','12')
        old_ids=set(db.scalars(select(ContentPage.id)))
        protected={key:main.config(db,key) for key in ('smtp_host','smtp_port','smtp_user','smtp_password','smtp_from','smtp_tls','emby_url','emby_api_key','radarr_url','radarr_api_key','radarr_enabled','bazarr_subtitle_profile','captcha_login','public_url')}
        db.commit()
        users=snapshot(db,User);groups=snapshot(db,PermissionGroup);members=snapshot(db,GroupMember)
        policies={model:snapshot(db,model) for model in (PolicyState,SeerrPolicyState,GroupBaseline)}
        addresses={s.key:(s.browser_url,s.server_url) for s in db.scalars(select(AccessService)) if s.key!='service-999'}
    token=csrf(client,'/admin/updates')
    response=client.post('/admin/updates/reset-content',data=dict(csrf=token,confirm='on',confirmation='RESET'),follow_redirects=False)
    assert response.status_code==303,response.text
    with SessionLocal() as db:
        assert snapshot(db,User)==users and snapshot(db,PermissionGroup)==groups and snapshot(db,GroupMember)==members
        assert all(snapshot(db,model)==before for model,before in policies.items())
        assert {key:main.config(db,key) for key in protected}==protected
        assert {s.key:(s.browser_url,s.server_url) for s in db.scalars(select(AccessService)) if s.key in addresses}==addresses
        assert not list(db.scalars(select(MenuItem))) and not db.get(AccessService,'service-999')
        pages=list(db.scalars(select(ContentPage)))
        assert pages and old_ids.isdisjoint({p.id for p in pages})
        assert all(p.system_key and not p.archived and p.enabled and p.draft==p.published for p in pages)
        assert any(p.system_key=='faq' for p in pages)
        assert any(p.system_key=='guide:emby' for p in pages)
        assert not list(db.scalars(select(Config).where(Config.key.like('deleted_system_page:%'))))
        assert not list(db.scalars(select(ContentTranslation)))
        home=portal.load(db)
        assert home==portal.load(db,True)
        page_menu=next(b for b in home['blocks'] if b['kind']=='page_menu')
        assert page_menu['page_ids']==['p-'+str(next(p.id for p in pages if p.system_key=='faq'))]
        assert main.config(db,'app_name','Gatearr')=='Gatearr'
        for key in ('login','forgot','reset','account','header'):
            assert 'Old customization' not in json.dumps(visual_builder.load(db,key,True))
            assert visual_builder.load(db,key,True)==visual_builder.load(db,key)
            assert visual_builder.version(db,key)==13
        assert header.load(db)==header.default(db)
        assert footer.load(db)==footer.DEFAULT
    assert client.get('/pages/custom-private-page').status_code==404
    assert client.get('/admin/design/'+page).status_code==404
    assert client.post('/admin/design/header/save',data=dict(csrf=token,payload='{}',version=12)).status_code==403


def test_failed_preset_rebuild_rolls_back_content_removal(client,monkeypatch):
    setup(client)
    key,value=create_page(client,'keep-on-failed-reset')
    with SessionLocal() as db:
        before_pages=snapshot(db,ContentPage)
        before_services=snapshot(db,AccessService)
        before_config=snapshot(db,Config)
    original=portal.initial_layout
    def unavailable(db,seed_pages=True):
        if seed_pages:raise ValueError('Preset rebuild unavailable')
        return original(db,seed_pages=False)
    monkeypatch.setattr(portal,'initial_layout',unavailable)
    # The request already has a saved Home; only the reset rebuild calls this function.
    response=post(client,'/admin/updates/reset-content',dict(confirm='on',confirmation='RESET'),'/admin/updates')
    assert response.status_code==400
    with SessionLocal() as db:
        assert snapshot(db,ContentPage)==before_pages
        assert snapshot(db,AccessService)==before_services
        assert snapshot(db,Config)==before_config
