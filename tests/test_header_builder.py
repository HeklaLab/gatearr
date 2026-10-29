import re
from copy import deepcopy
from app import header,visual_builder
from app.db import SessionLocal
from test_portal import setup,logout
from test_visual_studio import design


def header_html(html):return re.search(r'<header class="topbar-modern.*?</header>',html,re.S)[0]


def test_header_default_and_shared_draft_publication(client):
    setup(client)
    with SessionLocal() as db:value=header.load(db,True)
    assert [b['kind'] for b in value['blocks']]==['header_container','columns','logo','header_navigation','header_account']
    assert value['blocks'][1]['column_sizes']==[4,6,2]
    assert value['blocks'][2]['title']=='{app_name}' and value['blocks'][2]['logo_mode']=='logo'
    editor=client.get('/admin/design/header')
    assert editor.status_code==200 and 'data-header-audience' in editor.text
    assert 'name="brand_display"' not in client.get('/admin/branding').text
    assert 'name="browser_title"' not in client.get('/admin/branding').text
    logo=next(b for b in value['blocks'] if b['kind']=='logo');logo.update(logo_mode='both',title='Our community');logo['style']['align']='center'
    logo['slot']=1
    next(b for b in value['blocks'] if b['kind']=='header_navigation')['slot']=0
    next(b for b in value['blocks'] if b['kind']=='columns')['column_sizes']=[4,4,4]
    value['browser_title']='${app_name} — Shared header'
    assert design(client,'header','save',value).status_code==200
    assert 'Our community' not in header_html(client.get('/home').text)
    preview=design(client,'header','preview',value)
    assert preview.status_code==200 and 'Our community' in header_html(preview.text)
    assert design(client,'header','publish',value,1).status_code==200
    for url in ('/home','/account','/admin/pages'):
        h=header_html(client.get(url).text)
        assert 'Our community' in h and h.index('kind-header_navigation')<h.index('kind-logo')
        assert 'action="/logout"' in h
    assert '<title>Gatearr — Shared header</title>' in client.get('/home').text
    assert design(client,'header','save',value,1).status_code==409
    logout(client)
    guest=header_html(client.get('/login').text)
    assert 'Our community' in guest and 'href="/login"' in guest
    assert 'action="/logout"' not in guest and 'href="/admin"' not in guest
    assert client.get('/admin/design/header',follow_redirects=False).status_code in (401,403,303)


def test_header_removable_system_controls_report_impact_and_reject_wrong_blocks(client):
    setup(client)
    with SessionLocal() as db:value=header.load(db,True)
    for kind in header.FUNCTIONS:
        missing=deepcopy(value);missing['blocks']=[b for b in missing['blocks'] if b['kind']!=kind]
        preview=design(client,'header','preview',missing)
        assert preview.status_code==200 and ('kind-'+kind) not in header_html(preview.text)
        with SessionLocal() as db:revision=visual_builder.version(db,'header')
        response=design(client,'header','save',missing,revision)
        assert response.status_code==200
        assert [b['kind'] for b in response.json()['header_missing']]==[kind]
        duplicate=deepcopy(value);b=deepcopy(next(b for b in value['blocks'] if b['kind']==kind));b['id']='duplicate';duplicate['blocks'].append(b)
        assert design(client,'header','save',duplicate).status_code==400
    restricted=deepcopy(value);restricted['blocks'][0]['visibility']='admins'
    assert design(client,'header','save',restricted).status_code==400
    invalid=deepcopy(value);next(b for b in invalid['blocks'] if b['kind']=='logo')['logo_mode']='bad'
    assert design(client,'header','save',invalid).status_code==400
    with SessionLocal() as db:home=visual_builder.load(db,'home',True)
    home['blocks'].append(dict(next(b for b in value['blocks'] if b['kind']=='header_navigation'),id='illegal',parent=''))
    assert design(client,'home','save',home).status_code==400


def test_header_logo_modes_and_preview_guest_state(client):
    setup(client)
    with SessionLocal() as db:value=header.load(db,True)
    logo=next(b for b in value['blocks'] if b['kind']=='logo')
    for mode in ('logo','name','both'):
        logo['logo_mode']=mode
        response=design(client,'header','preview',value)
        assert response.status_code==200
        h=header_html(response.text)
        assert ('class="header-brand-text"' in h)==(mode!='logo')
        assert ('data-default-brand-logo' in h)==(mode!='name')
    from test_portal import post
    import json
    guest=post(client,'/admin/design/header/preview',{'payload':json.dumps(value),'audience':'guest','version':0},'/admin/design/header')
    h=header_html(guest.text)
    assert 'guest-primary-capsule' in h and 'action="/logout"' not in h


def test_header_container_removal_readdition_and_dynamic_identity_name(client):
    setup(client)
    with SessionLocal() as db:value=header.load(db,True)
    logo=next(b for b in value['blocks'] if b['kind']=='logo');logo['logo_mode']='name'
    assert '{app_name}' not in header_html(design(client,'header','preview',value).text)
    from app.main import set_config
    with SessionLocal() as db:set_config(db,'app_name','Community cinema');db.commit()
    assert 'Community cinema</span>' in header_html(design(client,'header','preview',value).text)
    logo['title']='My custom name'
    assert 'My custom name</span>' in header_html(design(client,'header','preview',value).text)
    value['blocks']=[b for b in value['blocks'] if b['kind'] not in header.FUNCTIONS]
    response=design(client,'header','publish',value)
    assert response.status_code==200 and len(response.json()['header_missing'])==2
    h=header_html(client.get('/home').text)
    assert 'primary-capsule' not in h and 'class="account-menu"' not in h
    # These blocks affect header controls, not account authorization or routes.
    assert client.get('/account').status_code==200
    with SessionLocal() as db:original=header.default(db)
    original['browser_title']=value['browser_title']
    assert design(client,'header','publish',original,1).status_code==200
    assert 'primary-capsule' in header_html(client.get('/home').text)


def test_legacy_flat_header_is_wrapped_without_changing_saved_snapshots(client):
    setup(client)
    legacy=dict(page='header',nav_position='top',sidebar_position='left',blocks=[dict(id='legacy-logo',kind='logo',region='main',order=10,span=12,title='Custom legacy name',logo_mode='name')])
    old=deepcopy(legacy);converted=header.normalize(legacy)
    assert old==legacy
    assert converted['blocks'][0]['kind']=='header_container'
    assert converted['blocks'][1]['parent']==converted['blocks'][0]['id']
    assert converted['blocks'][1]['title']=='Custom legacy name'
    assert header.validate(converted)
    assert header.normalize(converted)==converted
