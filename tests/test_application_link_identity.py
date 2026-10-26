"""Custom links keep their own identity even when named after a native service."""
import pytest
from sqlalchemy import select
from app import applications
from app.db import SessionLocal
from app.models import MenuItem
from test_portal import setup,post


def add_link(client,label,url='https://apps.example.test/custom'):
    response=post(client,'/admin/menu',{'label':label,'url':url,'position':100,'menu_key':'main','new_tab':'on'},'/admin/integrations')
    assert response.status_code==303
    with SessionLocal() as db:return db.scalars(select(MenuItem).order_by(MenuItem.id.desc())).first().id


@pytest.mark.parametrize('label',['Emby','Jellyfin','Seerr','Radarr','Sonarr','Bazarr','Tracearr','Tdarr'])
def test_native_name_does_not_hide_or_reclassify_a_custom_link(client,label):
    setup(client);ident=add_link(client,label)
    page=client.get('/admin/integrations').text
    assert f'data-id="{ident}"' in page
    with SessionLocal() as db:
        card=next(app for app in applications.catalog(db,editor=True) if app['key']==f'menu:{ident}')
        assert card['href']=='https://apps.example.test/custom' and card['external']
        assert not db.get(MenuItem,ident).access_service


def test_existing_same_named_links_are_recoverable_without_reinstallation(client):
    setup(client);ids=[add_link(client,'Sonarr',f'https://apps.example.test/sonarr-{i}') for i in range(5)]
    page=client.get('/admin/integrations').text
    assert all(f'data-id="{ident}"' in page for ident in ids)
    assert post(client,'/admin/menu',{'id':ids[0],'label':'Sonarr','url':'https://apps.example.test/edited','position':100,'menu_key':'main'},'/admin/integrations').status_code==303
    assert post(client,'/admin/menu/delete',{'id':ids[1]},'/admin/integrations').status_code==303
    with SessionLocal() as db:
        assert db.get(MenuItem,ids[0]).url=='https://apps.example.test/edited'
        assert db.get(MenuItem,ids[1]) is None
        assert all(db.get(MenuItem,ident) for ident in ids[2:])


def test_new_native_card_is_not_overridden_by_same_named_custom_link(client):
    setup(client);ident=add_link(client,'Emby','https://apps.example.test/existing-media')
    with SessionLocal() as db:
        apps={card['key']:card for card in applications.catalog(db,editor=True)}
        assert apps['access:emby']['href']=='/access/emby'
        assert apps[f'menu:{ident}']['href']=='https://apps.example.test/existing-media'


def test_custom_link_named_radarr_can_have_its_own_guides(client):
    setup(client)
    ident=add_link(client,'Radarr')
    response=post(client,f'/admin/design/home/enable-howto/{ident}',{},'/admin/design/home')
    assert response.status_code==200
    assert response.json()['url']==f'/admin/design/home/howto/service-{ident}'
    with SessionLocal() as db:
        assert db.get(MenuItem,ident).access_service==f'service-{ident}'
        apps={a['key']:a for a in applications.catalog(db,editor=True)}
        assert apps[f'menu:{ident}']['howto']==f'service-{ident}'
        assert apps['radarr']['howto']==''
