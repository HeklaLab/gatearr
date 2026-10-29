"""Authored 0.5 content must be discoverable and use its own resource at render time."""
import json
from pathlib import Path
from sqlalchemy import select
from app import content_catalog,i18n,portal,visual_builder,page_builder,page_presets
from app.db import SessionLocal
from app.models import User,ContentPage,AccessService,Language
from test_portal import setup,post
from test_content_pages import create_page,save_page


def test_sources_include_all_system_pages_and_independent_accordion_items(client):
    setup(client);key,value=create_page(client,'translated-faq')
    value['page_settings']['description']='A custom page summary'
    value['blocks']=[page_presets.block('accordion','questions',items=[dict(id='first',question='Same question',answer='<p>First <strong>answer</strong></p>',rich=True),dict(id='second',question='Same question',answer='Second answer')])]
    assert save_page(client,key,value,True).status_code==200
    with SessionLocal() as db:
        catalog={x['key']:x for x in content_catalog.sources(db)}
        prefix='page:'+key[2:]
        assert catalog[prefix+':description']['source']=='A custom page summary'
        for ident in ('first','second'):
            assert catalog[prefix+':questions:item:'+ident+':question']['source']=='Same question'
        assert catalog[prefix+':questions:item:first:answer']['kind']=='accordion_html'
        for page in ('login','forgot','reset','account','footer'):
            expected={page+'-block:'+b['id']+':'+f for b in visual_builder.load(db,page,True)['blocks'] for f in ('title','body','alt') if b.get(f)}
            assert expected<=catalog.keys(),(page,expected-catalog.keys())
    listing=client.get('/admin/translations?scope=content&edit_locale=en&q=Same+question').text
    assert 'Same question' in listing and '/admin/design/'+key in listing
    assert 'publication-pair' not in listing


def test_translated_rich_accordion_is_scoped_safe_and_visible_after_save(client):
    setup(client,locale='fr');key,value=create_page(client,'scoped-translation')
    value['blocks']=[page_presets.block('accordion','faq',items=[dict(id='one',question='Same question',answer='<p>Source answer</p>',rich=True),dict(id='two',question='Same question',answer='Other answer')])]
    assert save_page(client,key,value,True).status_code==200
    prefix='page:'+key[2:]+':faq:item:'
    for resource,source,target in [(prefix+'one:question','Same question','Une question précise'),(prefix+'one:answer','<p>Source answer</p>','<p>Une <strong>réponse</strong><img src="/static/x.png"><script>bad()</script></p>')]:
        response=post(client,'/admin/translations',dict(edit_locale='fr',scope='content',key=resource,source_hash=i18n.source_hash(source),value=target),'/admin/translations')
        assert response.status_code==303,response.text
    html=client.get('/pages/scoped-translation').text
    assert 'Une question précise' in html and 'Une <strong>réponse</strong>' in html
    assert 'Same question' in html # another item with the same source stays independent
    assert '/static/x.png' not in html and 'bad()' not in html
    with SessionLocal() as db:assert page_builder.row_for(db,key).draft==page_builder.row_for(db,key).published


def test_page_menu_title_description_and_account_custom_greeting_use_content_overrides(client):
    setup(client,locale='fr');key,value=create_page(client,'menu-copy')
    value['page_settings']['navigation']=True;value['page_settings']['description']='A helpful page'
    assert save_page(client,key,value,True).status_code==200
    with SessionLocal() as db:
        i18n.store_content(db,'page:'+key[2:]+':title','Example help','fr','Assistance personnalisée')
        i18n.store_content(db,'page:'+key[2:]+':description','A helpful page','fr','Tout pour bien commencer')
        owner=db.scalar(select(User).where(User.emby_id=='admin-1'))
        home=visual_builder.load(db,'home',True);home['blocks']=[page_presets.block('page_menu','links',page_ids=[key])]
        visual_builder.save(db,'home',home,visual_builder.version(db,'home'),True)
        account=visual_builder.load(db,'account',True);intro=next(b for b in account['blocks'] if b['kind']=='account_intro')
        i18n.store_content(db,'account-block:'+intro['id']+':title',intro['title'],'fr','Bienvenue chez vous, {name}.')
        db.commit()
    page=client.get('/home').text
    assert 'Assistance personnalisée' in page and 'Tout pour bien commencer' in page
    assert 'Bienvenue chez vous, Owner.' in client.get('/account').text
    assert 'published-pages-nav' not in client.get('/account').text # navigation is an explicit block now


def test_public_inventory_includes_new_function_labels_but_no_admin_controls():
    for name in ('New address','Send confirmation','Confirm new password','Save language','Language is managed by your group.','Subtitle languages','Open page'):
        assert name in i18n.PUBLIC_INTERFACE_KEYS,name
    assert not {'Page settings','Create a page','Publish guide','Select pages in the block settings.','Preview only'} & i18n.PUBLIC_INTERFACE_KEYS


def test_new_public_preset_copy_is_present_in_every_bundled_language_and_keeps_parameters():
    texts={'Help & FAQ','Your question','Your answer','{app} access guides'}
    for value in (page_presets.faq_layout(),page_presets.guide_layout('emby','Emby')):
        for b in value['blocks']:
            texts.update(b.get(field,'') for field in ('title','body','alt'))
            for item in b.get('items',[]):texts.update(item.get(field,'') for field in ('question','answer'))
    texts.discard('')
    for locale,catalog in i18n.CATALOGS.items():
        for text in texts:
            assert catalog.get(text), (locale,text)
            if locale!='en':assert catalog[text]!=text,(locale,text)
        assert '{app}' in catalog['{app} access guides']
    assert i18n.CATALOGS['fr']['How do I start watching?']=='Comment regarder un film ou une série ?'
    assert i18n.CATALOGS['de']['Emby access guides']=='Emby einrichten'
    assert i18n.CATALOGS['ja']['Your question']=='質問を入力'


def test_custom_application_default_guide_heading_is_translated_without_renaming_app(client):
    setup(client)
    with SessionLocal() as db:
        db.add(AccessService(key='sample',name='My media app',browser_url='https://example.com',icon='link'))
        db.commit()
        assert i18n.content(db,'page:42:title','My media app access guides','fr')=='Guides de connexion à My media app'
        i18n.store_content(db,'page:42:title','My media app access guides','fr','Notre guide personnalisé');db.commit()
        assert i18n.content(db,'page:42:title','My media app access guides','fr')=='Notre guide personnalisé'


def test_preset_faq_renders_in_every_bundled_language(client):
    import re,html
    setup(client);key,value=create_page(client,'all-language-faq')
    assert save_page(client,key,value,True).status_code==200
    for locale,catalog in i18n.CATALOGS.items():
        with SessionLocal() as db:
            language=db.get(Language,locale)
            if language:language.enabled=True
            else:db.add(Language(code=locale,name=locale,enabled=True))
            db.scalar(select(User).where(User.emby_id=='admin-1')).locale=locale;db.commit()
        response=client.get('/pages/all-language-faq')
        assert response.status_code==200
        questions=[html.unescape(q) for q in re.findall(r'class="accordion-question">([^<]*)<',response.text)]
        assert questions==[catalog['How do I start watching?'],catalog['How do I request a movie or series?']],locale
        assert catalog['Find answers to common questions about your media library.'] in html.unescape(response.text),locale


def test_shared_header_copy_is_discoverable_and_localized_without_changing_identity(client):
    setup(client,locale='fr')
    with SessionLocal() as db:
        value=visual_builder.load(db,'header',True)
        logo=next(b for b in value['blocks'] if b['kind']=='logo')
        logo['logo_mode']='both';logo['title']='Welcome to {app_name}'
        visual_builder.save(db,'header',value,visual_builder.version(db,'header'),True)
        resource='header-block:'+logo['id']+':title'
        assert resource in {x['key'] for x in content_catalog.sources(db)}
        i18n.store_content(db,resource,logo['title'],'fr','Bienvenue sur {app_name}')
        db.commit()
    for path in ('/home','/account'):
        html=client.get(path).text
        assert 'Bienvenue sur Gatearr</span>' in html
        assert 'Welcome to' not in html
        assert i18n.CATALOGS['fr']['Account menu for {name}'].format(name='Owner') in html
    assert {'Account menu for {name}','Main navigation','Pages'}<=i18n.PUBLIC_INTERFACE_KEYS


def test_recent_public_navigation_and_statistics_copy_has_all_bundled_translations():
    from string import Formatter
    variables=lambda text:{field for _,field,_,_ in Formatter().parse(text) if field}
    keys={'Back','Open page','Main navigation','Pages','Account menu for {name}',
          'Your viewing activity','Watch time','Most watched series','This week','Last 30 days',
          'Bold','Italic','Underline','Bulleted list','Numbered list','Align left','Align center','Align right','Text color'}
    for locale,catalog in i18n.CATALOGS.items():
        for key in keys:
            assert catalog.get(key),(locale,key)
            assert variables(catalog[key])==variables(key),(locale,key)
        if locale!='en':assert catalog['Bulleted list']!='Bulleted list'
    assert i18n.CATALOGS['zh-cn']['Bold']=='粗体'
