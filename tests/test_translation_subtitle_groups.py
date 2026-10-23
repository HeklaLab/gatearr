"""Application subtitles share an editor only within the same block and translation."""
import json
from app import i18n, main, portal
from app.db import SessionLocal
from test_portal import setup, post


def prepare(client):
    setup(client)
    layout={'theme':portal.DEFAULT['theme'],'nav_position':'top','blocks':[{'id':'admin-apps','kind':'applications','region':'main','span':12,'order':10,'columns':3,'applications':['access:emby','access:seerr','account'],'subtitles':{'access:emby':'Open application','access:seerr':'Open application','account':'Open application'}}]}
    with SessionLocal() as db:
        for key in ('portal_draft','portal_published'):
            main.set_config(db,key,json.dumps(layout))
        db.commit()
    return ['block:admin-apps:application-subtitle:'+tool for tool in ('access:emby','access:seerr','account')]


def test_equal_subtitles_group_and_save_all_resources(client):
    keys=prepare(client)
    page=client.get('/admin/translations?edit_locale=fr&scope=content&q=Open+application').text
    assert page.count('class="card translation-entry"')==1
    assert 'Emby, Seerr, My account' in page
    for key in keys:assert 'name="related_key" value="'+key+'"' in page
    response=post(client,'/admin/translations',{'edit_locale':'fr','scope':'content','key':keys[0],'related_key':keys,'source_hash':i18n.source_hash('Open application'),'value':'Ouvrir le service'},'/admin/translations')
    assert response.status_code==303,response.text
    with SessionLocal() as db:
        for key in keys:assert i18n.content(db,key,'Open application','fr')=='Ouvrir le service'


def test_distinct_existing_translations_are_not_merged(client):
    keys=prepare(client)
    with SessionLocal() as db:
        i18n.store_content(db,keys[0],'Open application','fr','Gérer les films')
        db.commit()
    page=client.get('/admin/translations?edit_locale=fr&scope=content&q=Open+application').text
    assert page.count('class="card translation-entry"')==2
    assert 'Gérer les films' in page and 'Seerr, My account' in page


def test_group_cannot_update_unrelated_resource(client):
    keys=prepare(client)
    response=post(client,'/admin/translations',{'edit_locale':'fr','scope':'content','key':keys[0],'related_key':[keys[0],'branding:login_text'],'source_hash':i18n.source_hash('Open application'),'value':'Ouvrir'},'/admin/translations')
    assert response.status_code==409
    with SessionLocal() as db:
        assert i18n.content(db,keys[0],'Open application','fr')==i18n.translate('Open application','fr')
