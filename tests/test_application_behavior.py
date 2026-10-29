import importlib
import json
import re
from copy import deepcopy
import pytest
from sqlalchemy import select
from app import main, portal
from app.application_behavior import media_browser_page
from app.db import SessionLocal
from app.models import AccessService, Config, MenuItem, User
from test_portal import setup, post, logout, login_user


def row(ident, key, mode, **options):
    return {'id': ident, 'kind': 'applications', 'region': 'main', 'span': 12, 'order': 10, 'columns': 1, 'applications': [key], 'application_behaviors': {key: {'mode': mode, **options}}}


def state():
    with SessionLocal() as db:
        return portal.load(db, True), portal.version(db)


def write(client, layout, version, action='publish'):
    return post(client, '/admin/design/home/' + action, {'version': version, 'payload': json.dumps(layout)}, '/admin/design/home')


def card_href(page, ident):
    section = page.split('data-block-id="' + ident + '"', 1)[1].split('</section>', 1)[0]
    return re.search(r'<a class="service portal-service" href="([^"]*)"', section)[1]


def test_two_emby_cards_have_independent_draft_and_published_destinations(client):
    setup(client)
    with SessionLocal() as db:
        service = db.get(AccessService, 'emby')
        service.entry_mode = 'direct'
        service.browser_url = 'http://media.example.test:8096'
        db.commit()
    layout, version = state()
    layout['blocks'] = [row('member-guide', 'access:emby', 'guide'), row('admin-direct', 'access:emby', 'guide')]
    initial = write(client, layout, version)
    assert initial.status_code == 200
    changed = deepcopy(layout)
    changed['blocks'][1]['application_behaviors']['access:emby'] = {'mode': 'direct', 'url': 'http://media.example.test:8096/web/index.html#!/dashboard', 'new_tab': True}
    draft = write(client, changed, initial.json()['version'], 'save')
    assert draft.status_code == 200
    home = client.get('/home').text
    assert card_href(home, 'member-guide') == card_href(home, 'admin-direct') == '/access/emby?view=guide'
    assert client.get('/access/emby?view=guide').status_code == 200
    assert write(client, changed, draft.json()['version']).status_code == 200
    home = client.get('/home').text
    assert card_href(home, 'member-guide') == '/access/emby?view=guide'
    assert card_href(home, 'admin-direct') == 'http://media.example.test:8096/web/index.html#!/dashboard'
    with SessionLocal() as db:
        assert db.get(AccessService, 'emby').entry_mode == 'direct'
    # An obsolete browser must not mutate global behavior through the old endpoint.
    assert post(client, '/admin/design/home/application/emby/behavior', {'mode': 'structured'}, '/admin/design/home').status_code == 410


@pytest.mark.parametrize('tool', ['radarr', 'sonarr', 'bazarr', 'tracearr', 'tdarr'])
def test_native_tools_offer_direct_and_embedded_cards_without_extending_permissions(client, tool):
    setup(client)
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.admin.is_(True)))
        owner.tool_access = json.dumps([tool])
        main.set_config(db, tool + '_url', 'http://' + tool + ':1234')
        main.set_config(db, tool + '_api_key', 'test-key')
        main.set_config(db, tool + '_enabled', 'true')
        main.set_config(db, tool + '_interface_enabled', 'true')
        main.set_config(db, tool + '_public_url', 'https://' + tool + '.example.test:9443')
        db.commit()
    layout, version = state()
    layout['blocks'] = [row('tool-frame', tool, 'embedded'), row('tool-direct', tool, 'direct')]
    if tool=='tracearr':
        for block in layout['blocks']:block['visibility']='admins'
    assert write(client, layout, version).status_code == 200
    home = client.get('/home').text
    assert card_href(home, 'tool-frame') == '/tools/' + tool
    assert card_href(home, 'tool-direct') == 'https://' + tool + '.example.test:9443'
    frame = client.get('/tools/' + tool)
    assert frame.status_code == 200 and 'class="tool-frame"' in frame.text
    logout(client)
    assert login_user(client).status_code == 303
    home = client.get('/home').text
    assert 'data-block-id="tool-frame"' not in home
    assert 'data-block-id="tool-direct"' not in home
    assert client.get('/tools/' + tool).status_code == 403


def test_missing_public_url_blocks_publication_without_breaking_draft_editing(client):
    setup(client)
    layout, version = state()
    layout['blocks'] = [row('no-address', 'radarr', 'direct')]
    draft = write(client, layout, version, 'save')
    assert draft.status_code == 200
    assert write(client, layout, draft.json()['version']).status_code == 400
    layout['blocks'][0]['application_behaviors']['radarr']['url'] = 'https://radarr.example.test'
    assert write(client, layout, draft.json()['version']).status_code == 200


@pytest.mark.parametrize('url', ['javascript:alert(1)', '//evil.example', 'https://key:secret@evil.example', 'data:text/html,hello'])
def test_card_destinations_reject_unsafe_urls(client, url):
    setup(client)
    layout, version = state()
    layout['blocks'] = [row('invalid-url', 'access:emby', 'direct', url=url)]
    assert write(client, layout, version, 'save').status_code == 400


def test_guide_choices_work_even_when_the_global_application_mode_is_direct(client):
    setup(client)
    with SessionLocal() as db:
        service = db.get(AccessService, 'emby')
        service.entry_mode = 'direct'
        service.browser_url = 'http://media.example.test:8096'
        service.access_published = json.dumps([{'id': 'desktop', 'kind': 'group', 'title': 'Computers', 'position': 1}, {'id': 'download', 'kind': 'link', 'parent': 'desktop', 'title': 'Download', 'position': 1, 'url': 'https://example.test/app'}])
        db.commit()
    root = client.get('/access/emby?view=guide')
    assert root.status_code == 200 and '/access/emby/desktop?view=guide' in root.text
    child = client.get('/access/emby/desktop?view=guide')
    assert child.status_code == 200 and 'https://example.test/app' in child.text
    assert client.get('/access/emby', follow_redirects=False).headers['location'] == '/services/emby/open'


@pytest.mark.parametrize('base,expected', [
    ('http://media.test:8096', 'http://media.test:8096/web/index.html'),
    ('https://media.test:8920/emby', 'https://media.test:8920/emby/web/index.html'),
    ('http://media.test:8096/web', 'http://media.test:8096/web/index.html'),
    ('http://media.test:8096/web/index.html#!/dashboard', 'http://media.test:8096/web/index.html#!/dashboard'),
    ('https://play.test/web?theme=dark#/home', 'https://play.test/web/index.html?theme=dark#/home'),
])
def test_media_web_paths_preserve_explicit_port_query_and_fragment(base, expected):
    assert media_browser_page(base) == expected


def test_migration_freezes_legacy_destinations_and_is_idempotent(client, monkeypatch):
    setup(client)
    original = deepcopy(portal.DEFAULT)
    original['blocks'].append(row('existing', 'access:emby', 'guide'))
    original['blocks'][-1].pop('application_behaviors')
    migration = importlib.import_module('migrations.versions.0027_application_behaviors')
    with SessionLocal() as db:
        db.add(MenuItem(label='Emby', url='http://old-media.test:8096', menu_key='main', new_tab=True, position=10))
        for key in ('portal_published', 'portal_draft'):
            main.set_config(db, key, json.dumps(original))
        main.set_config(db, 'portal_version', '10')
        db.commit()
        monkeypatch.setattr(migration.op, 'get_bind', lambda: db.connection())
        migration.upgrade()
        db.commit()
        frozen = json.loads(db.get(Config, 'portal_published').value)
        assert frozen['blocks'][-1]['application_behaviors']['access:emby'] == {'mode': 'direct', 'url': 'http://old-media.test:8096', 'new_tab': True}
        assert frozen['blocks'][0] == original['blocks'][0]
        assert portal.version(db) == 11
        migration.upgrade()
        db.commit()
        assert portal.version(db) == 11
        assert json.loads(db.get(Config, 'portal_published').value) == frozen


@pytest.mark.parametrize('tool', ['radarr', 'sonarr', 'bazarr', 'tracearr', 'tdarr'])
def test_unconfigured_admin_tool_is_direct_only_and_does_not_enable_proxy(client, tool):
    from app.applications import catalog
    setup(client)
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.admin.is_(True)))
        app = next(a for a in catalog(db, owner, editor=True) if a['key'] == tool)
        assert app['opening_modes'] == ['direct']
        assert app['default_mode'] == 'direct'
        assert not app['direct_url']
        # A private API address alone is not a complete integration or public URL.
        main.set_config(db, tool + '_url', 'http://private-only:1234')
        db.commit()
        app = next(a for a in catalog(db, owner, editor=True) if a['key'] == tool)
        assert app['opening_modes'] == ['direct'] and not app['direct_url']
    layout, version = state()
    layout['blocks'] = [row('direct-tool', tool, 'direct', url='https://public.example.test:9443/' + tool)]
    if tool=='tracearr':layout['blocks'][0]['visibility']='admins'
    assert write(client, layout, version).status_code == 200
    assert card_href(client.get('/home').text, 'direct-tool') == 'https://public.example.test:9443/' + tool
    assert client.get('/tools/' + tool).status_code == 403
    logout(client)
    assert login_user(client).status_code == 303
    assert 'data-block-id="direct-tool"' not in client.get('/home').text
