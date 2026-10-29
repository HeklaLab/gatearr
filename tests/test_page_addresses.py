from app.db import SessionLocal
from app import page_builder
from test_portal import setup
from test_content_pages import create_page,save_page
from test_page_action_groups import item


def test_guide_addresses_match_the_view_destination_not_the_generic_slug(client):
    setup(client)
    html=client.get('/admin/pages').text
    for service,name in [('emby','Emby'),('seerr','Seerr'),('tracearr','Tracearr')]:
        row=item(html,name+' access guides')
        path='/access/'+service+('' if service=='emby' else '?view=guide')
        assert '<code>'+path+'</code>' in row
        assert '<code>/pages/guide-' not in row
        assert 'href="'+path+'"' in row
    with SessionLocal() as db:
        from app.models import AccessService
        db.add(AccessService(key='service-99',name='Emby',browser_url='https://example.com',icon='link'))
        page_builder.ensure_defaults(db);db.commit()
    html=client.get('/admin/pages').text
    assert '<code>/access/service-99?view=guide</code>' in html


def test_directory_shows_configured_address_without_confusing_draft_and_live_urls(client):
    setup(client)
    key,value=create_page(client,'my-help')
    row=item(client.get('/admin/pages').text,'Example help')
    assert '<code>/pages/my-help</code>' in row
    assert save_page(client,key,value,True).status_code==200
    value['page_settings']['slug']='new-help'
    assert save_page(client,key,value).status_code==200
    row=item(client.get('/admin/pages').text,'Example help')
    assert '<code>/pages/new-help</code><span>Draft</span>' in row
    assert '<code>/pages/my-help</code>' in row
    assert 'href="/pages/my-help"' in row
    assert client.get('/pages/new-help').status_code==404
    assert save_page(client,key,value,True).status_code==200
    row=item(client.get('/admin/pages').text,'Example help')
    assert '<code>/pages/new-help</code>' in row
    assert '/pages/my-help' not in row


def test_guide_path_tracks_the_actual_card_destination_without_a_domain(client):
    setup(client)
    from app.application_behavior import guide_href
    from app.models import AccessService,Guide
    from app.main import set_config
    import json
    with SessionLocal() as db:
        service=db.get(AccessService,'emby');service.entry_mode='direct'
        set_config(db,'public_url','https://portal.example.com:8443');db.commit()
        expected=guide_href(db,'emby')
    row=item(client.get('/admin/pages').text,'Emby access guides')
    assert '<code>'+expected+'</code>' in row
    assert expected=='/access/emby?view=guide'
    assert '<code>https://' not in row and '<code>http://' not in row
    with SessionLocal() as db:
        guide=db.scalar(__import__('sqlalchemy').select(Guide).where(Guide.service_key=='emby',Guide.published.is_not(None)))
        set_config(db,'howto_root_published_emby',json.dumps(dict(mode='guide',guide_id=guide.id)));db.commit()
        expected=guide_href(db,'emby')
    row=item(client.get('/admin/pages').text,'Emby access guides')
    assert '/guide/' in expected and '<code>'+expected+'</code>' in row
