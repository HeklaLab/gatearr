import json
import re
from sqlalchemy import select
from app import main
from app.db import SessionLocal
from app.models import User,AccessService
from test_portal import setup,post,logout,login_user


def policy(mode):
    with SessionLocal() as db:
        main.set_config(db,'themes_published',json.dumps({'mode':mode}))
        db.commit()


def test_guest_remembers_last_appearance_without_overriding_account_or_policy(client):
    setup(client);policy('user')
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)))
        owner.theme_preference='dark';db.commit()
    assert '@media' not in client.get('/theme.css').text
    assert client.cookies.get('gatearr_appearance')=='dark'
    logout(client)
    assert 'color-scheme:dark' in client.get('/theme.css').text
    assert '@media' not in client.get('/theme.css').text
    policy('light')
    assert 'color-scheme:light' in client.get('/theme.css').text
    policy('user')
    # A different account retains its own saved preference.
    with SessionLocal() as db:
        member=db.scalar(select(User).where(User.name=='demo'))
        member.theme_preference='light';db.commit()
    assert login_user(client).status_code==303
    assert 'color-scheme:light' in client.get('/theme.css').text
    assert client.cookies.get('gatearr_appearance')=='light'


def test_guest_without_remembered_choice_uses_system_and_invalid_cookie_is_ignored(client):
    setup(client);policy('user');logout(client)
    client.cookies.clear()
    assert '@media(prefers-color-scheme:dark)' in client.get('/theme.css').text
    client.cookies.set('gatearr_appearance','bogus')
    assert '@media(prefers-color-scheme:dark)' in client.get('/theme.css').text


def test_intermediate_guide_groups_offer_device_return_above_and_below(client):
    setup(client)
    client.get('/admin/pages')
    with SessionLocal() as db:
        service=db.get(AccessService,'emby');service.entry_mode='direct'
        service.access_published=json.dumps([
            {'id':'computer','kind':'group','title':'Computer','position':1},
            {'id':'windows','kind':'group','title':'Windows','parent':'computer','position':2},
            {'id':'download','kind':'link','title':'Download','parent':'windows','position':3,'url':'https://example.test'}])
        db.commit()
    for route in ('computer','windows'):
        page=client.get('/access/emby/'+route+'?view=guide').text
        buttons=re.findall(r'<div class="guide-device-navigation">(.*?)</div>',page)
        assert len(buttons)==2
        assert all('href="/access/emby?view=guide"' in button and 'Choose another device' in button for button in buttons)
    assert 'guide-device-navigation' not in client.get('/access/emby?view=guide').text


def test_guest_can_change_appearance_only_when_users_choose(client):
    setup(client);policy('user');logout(client);client.cookies.clear()
    page=client.get('/login').text
    assert 'guest-language-menu' in page and 'class="theme-capsule"' in page
    for choice in ('dark','light','auto'):
        response=post(client,'/account/theme',{'theme':choice,'next':'/login'},'/login')
        assert response.status_code==303
        assert client.cookies.get('gatearr_appearance')==choice
        css=client.get('/theme.css').text
        assert ('@media(prefers-color-scheme:dark)' in css) == (choice=='auto')
        if choice!='auto':assert 'color-scheme:'+choice in css
        html=client.get('/login').text
        assert 'value="'+choice+'"' in html and 'aria-pressed="true"' in html
    policy('dark')
    assert 'class="theme-capsule"' not in client.get('/login').text
    assert post(client,'/account/theme',{'theme':'light'},'/login').status_code==400
    assert 'color-scheme:dark' in client.get('/theme.css').text
