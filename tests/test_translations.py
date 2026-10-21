from sqlalchemy import select
from app import i18n
from app.db import SessionLocal
from app.models import Config
from test_portal import setup,post,logout,login_user


def change(client,key,value='',locale='fr',action='save'):
    return post(client,'/admin/translations',{'key':key,'value':value,'edit_locale':locale,'action':action},'/admin/translations')


def test_translations_customize_public_recovery_and_account_labels(client):
    setup(client,locale='fr')
    assert i18n.translate('Translations / Labels','fr') in client.get('/admin').text
    for key,value in [('ACCOUNT RECOVERY','RETROUVER MON ACCÈS'),('A fresh start.','Un nouvel accès.'),("Enter the verified email address of your Emby account. You will receive a link valid for 30 minutes.",'Saisissez votre adresse pour recevoir le lien.'),('Receive notifications about my requests','Suivre mes demandes')]:
        assert change(client,key,value).status_code==303
    assert change(client,'A fresh start.','Recover your access','en').status_code==303
    assert 'Un nouvel accès.' in client.get('/forgot').text
    page=client.get('/admin/translations?edit_locale=fr&q=nouvel').text
    assert 'Un nouvel accès.' in page and i18n.translate('Customized','fr') in page
    assert 'Un nouvel accès.' in page
    logout(client)
    page=client.get('/forgot').text
    assert 'RETROUVER MON ACCÈS' in page and 'Saisissez votre adresse' in page
    assert 'A fresh start.' not in page
    post(client,'/language',{'locale':'en','next':'/forgot'},'/forgot')
    assert 'Recover your access' in client.get('/forgot').text
    with SessionLocal() as db:
        assert i18n.overrides(db,'fr')['Receive notifications about my requests']=='Suivre mes demandes'


def test_translation_variables_escaping_reset_and_isolated_keys(client):
    setup(client,locale='fr')
    assert change(client,'Hello, {name}.','<b>Bienvenue {name}</b>').status_code==303
    assert '&lt;b&gt;Bienvenue Owner&lt;/b&gt;' in client.get('/account').text
    for value in ('Bonjour','Bonjour {name.__class__}','Bonjour {name!r}','Bonjour {name:>20}','Bonjour {'):
        assert change(client,'Hello, {name}.',value).status_code==400
    assert '&lt;b&gt;Bienvenue Owner&lt;/b&gt;' in client.get('/account').text
    assert change(client,'A fresh start.','Récupérer mon compte').status_code==303
    assert change(client,'A fresh start.',action='reset').status_code==303
    assert i18n.translate('A fresh start.','fr') in client.get('/forgot').text
    assert '&lt;b&gt;Bienvenue Owner&lt;/b&gt;' in client.get('/account').text
    assert change(client,'Hello, {name}.','').status_code==303
    assert i18n.translate('Hello, {name}.','fr',name='Owner') in client.get('/account').text
    with SessionLocal() as db:
        assert db.get(Config,i18n.translation_key('fr','Hello, {name}.')) is None


def test_translation_admin_only_validation_and_pagination(client):
    setup(client)
    assert client.get('/admin/translations?page=99999').status_code==200
    assert 'name="key"' in client.get('/admin/translations').text
    assert client.get('/admin/translations?edit_locale=unknown').status_code==400
    assert change(client,'not-a-catalog-key','Bad').status_code==400
    assert change(client,'A fresh start.','x'*5001).status_code==400
    assert client.post('/admin/translations',data={'csrf':'bad'}).status_code==403
    logout(client)
    assert client.get('/admin/translations').status_code==401
    login_user(client)
    assert client.get('/admin/translations').status_code==403
    assert post(client,'/admin/translations',{'key':'A fresh start.','value':'Bad','edit_locale':'fr'},'/account').status_code==403


def test_footer_fully_customizable_and_recovery_hint_removed(client):
    setup(client,locale='fr')
    key='{app_name} · Your services, one place.'
    assert change(client,key,'Mon portail · Bienvenue chez nous.').status_code==303
    page=client.get('/forgot').text
    assert 'Mon portail · Bienvenue chez nous.</span>' in page
    assert 'Sans adresse vérifiée' not in page
    assert 'La récupération du compte administrateur local' not in page
    assert change(client,key,action='reset').status_code==303
    assert i18n.translate('{app_name} · Your services, one place.','fr',app_name='Gatearr')+'</span>' in client.get('/forgot').text
