import json
from sqlalchemy import select
from app.models import User
from app import visual_builder
from app.db import SessionLocal
from test_portal import setup,post,logout,login_user


def test_account_builder_draft_publication_and_function_blocks(client):
    setup(client)
    editor=client.get('/admin/design/account')
    assert editor.status_code==200 and 'System pages' in editor.text
    with SessionLocal() as db:
        value=visual_builder.load(db,'account',True);version=visual_builder.version(db,'account')
    value['blocks'].insert(0,dict(id='account-extra',kind='text',span=12,region='main',order=0,title='Account draft marker',body='Personal settings',rich=False))
    save=post(client,'/admin/design/account/save',{'payload':json.dumps(value),'version':version},'/admin');assert save.status_code==200
    assert 'Account draft marker' not in client.get('/account').text
    preview=post(client,'/admin/design/account/preview',{'payload':json.dumps(value)},'/admin')
    assert preview.status_code==200 and 'Account draft marker' in preview.text
    for action in ('email','password','photo'):assert 'action="/account/'+action+'"' in preview.text
    assert post(client,'/admin/design/account/publish',{'payload':json.dumps(value),'version':save.json()['version']},'/admin').status_code==200
    assert 'Account draft marker' in client.get('/account').text
    value['blocks']=[b for b in value['blocks'] if b['kind']!='account_email']
    removed=post(client,'/admin/design/account/save',{'payload':json.dumps(value),'version':save.json()['version']+1},'/admin')
    assert removed.status_code==200 and removed.json()['account_missing'][0]['kind']=='account_email'
    with SessionLocal() as db:home=visual_builder.load(db,'home',True)
    home['blocks'].append(dict(id='invalid-account',kind='account_form',span=12,region='main',order=99))
    assert post(client,'/admin/design/home/preview',{'payload':json.dumps(home)},'/admin').status_code==400


def test_account_stays_personal_authenticated_and_editor_is_admin_only(client):
    setup(client)
    page=client.get('/account').text
    assert 'Hello, Owner.' in page
    logout(client)
    assert client.get('/account',follow_redirects=False).status_code in (303,401)
    assert client.get('/admin/design/account',follow_redirects=False).status_code in (303,401)
    assert login_user(client).status_code==303
    page=client.get('/account').text
    with SessionLocal() as db:name=db.scalar(select(User).where(User.emby_id=='user-1')).name
    assert 'Hello, '+name+'.' in page and 'Hello, Owner.' not in page
    assert 'action="/account/password"' in page
    assert client.get('/admin/design/account').status_code==403


def test_account_functions_are_removable_scoped_and_preset_is_complete(client,monkeypatch):
    from app.account_blocks import KINDS,OPTIONAL,missing_required,default_blocks
    from app import bazarr_subtitles
    setup(client)
    with SessionLocal() as db:
        value=visual_builder.load(db,'account',True)
        assert KINDS=={b['kind'] for b in value['blocks']}
        assert all(kind in {b['kind'] for b in value['blocks']} for kind in OPTIONAL)
        assert not missing_required(db,value)
        monkeypatch.setattr(bazarr_subtitles,'offered',lambda db:True)
        value['blocks']=[b for b in value['blocks'] if b['kind'] not in OPTIONAL]
        assert not missing_required(db,value)
        value['blocks']=[]
        assert {b['kind'] for b in missing_required(db,value)}=={'account_email','account_password','account_subtitles'}
        monkeypatch.setattr(bazarr_subtitles,'offered',lambda db:False)
        assert {b['kind'] for b in missing_required(db,value)}=={'account_email','account_password'}
        version=visual_builder.version(db,'account')
    result=post(client,'/admin/design/account/publish',{'payload':json.dumps(value),'version':version},'/admin')
    assert result.status_code==200
    page=client.get('/account').text
    assert 'action="/account/email"' not in page and 'action="/account/password"' not in page
    for kind in KINDS:
        with SessionLocal() as db:home=visual_builder.load(db,'home',True)
        home['blocks'].append(dict(id='only-account',kind=kind,span=12,region='main',order=99))
        assert post(client,'/admin/design/home/preview',{'payload':json.dumps(home)},'/admin').status_code==400
    value['blocks']=default_blocks();value['blocks'].append({**value['blocks'][1],'id':'duplicate-email'})
    assert post(client,'/admin/design/account/save',{'payload':json.dumps(value),'version':version+1},'/admin').status_code==400


def test_old_account_snapshots_split_without_losing_surrounding_content(client):
    from app import main
    from app.models import Config
    setup(client)
    with SessionLocal() as db:
        layout=visual_builder.system_default(db,'account')
        layout['blocks']=[dict(id='before',kind='text',span=12,region='main',order=10,title='Before',body='Keep me'),dict(id='legacy-account',kind='account_form',span=12,region='main',order=20,title='Original greeting',body='Original intro'),dict(id='after',kind='text',span=12,region='main',order=30,title='After',body='Keep this too')]
        raw=json.dumps(layout);main.set_config(db,'account_published',raw);main.set_config(db,'account_draft',raw);db.commit()
        published=visual_builder.load(db,'account');draft=visual_builder.load(db,'account',True)
        assert published==draft
        assert not any(b['kind']=='account_form' for b in draft['blocks'])
        assert draft['blocks'][0]['id']=='before' and draft['blocks'][-1]['id']=='after'
        assert next(b for b in draft['blocks'] if b['kind']=='account_intro')['title']=='Original greeting'
        assert db.get(Config,'account_published').value==raw
    assert 'Original greeting' in client.get('/account').text


def test_unavailable_account_functions_leave_no_empty_public_blocks(client,monkeypatch):
    from app import portal,preferences,bazarr_subtitles,i18n
    from app.models import User
    setup(client)
    monkeypatch.setattr(preferences,'available_notifications',lambda db,user:{'requests':False,'seasons':False})
    monkeypatch.setattr(bazarr_subtitles,'offered',lambda db:False)
    monkeypatch.setattr(i18n,'languages',lambda db,all=False:{'en':'English'})
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.admin.is_(True)))
        value=visual_builder.load(db,'account')
        public=portal.for_display(value,'en',user,db)
        preview=portal.for_display(value,'en',user,db,True)
        assert not {b['kind'] for b in public['main']} & {'account_notifications','account_language','account_subtitles'}
        assert {'account_notifications','account_language','account_subtitles'} <= {b['kind'] for b in preview['main']}
