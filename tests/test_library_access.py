from copy import deepcopy
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from app import main,admin_features
from app.db import SessionLocal
from app.models import User
from app.emby import EmbyClient,EmbyError
from test_portal import setup,post,logout,login_user


def test_user_library_page_current_access_edit_remove_and_permissions(client,monkeypatch):
    setup(client)
    with SessionLocal() as db:
        main.sync_users(db)
        uid=db.scalar(select(User.id).where(User.emby_id=='user-1'))
    state={'Id':'user-1','Name':'demo','Policy':{'EnableAllFolders':True,'EnabledFolders':[],'BlockedTags':['restricted'],'EnableContentDeletion':False}}
    writes=[]
    def assign(remote_id,selected,all_folders):
        assert remote_id=='user-1'
        writes.append((list(selected),all_folders))
        state['Policy'].update(EnableAllFolders=all_folders,EnabledFolders=sorted(selected))
    monkeypatch.setattr(admin_features,'emby',SimpleNamespace(user=lambda remote_id:deepcopy(state),libraries=lambda:[{'Id':'movies','Name':'Movies'},{'Id':'films','Name':'Films'}],users=lambda:[],copy_options=lambda:[],assign_libraries=assign))
    path='/admin/users/'+str(uid)
    page=client.get(path).text
    assert 'name="access_mode" value="all" checked' in page
    assert 'name="libraries" value="movies" checked' in page
    assert 'name="libraries" value="films" checked' in page
    assert 'username-link' in client.get('/admin/users').text
    response=post(client,'/admin/emby/libraries',{'id':uid,'access_mode':'selected','libraries':['films']},path)
    assert response.status_code==303
    page=client.get(response.headers['location']).text
    assert 'Library access saved and verified in Emby.' in page
    assert 'name="libraries" value="films" checked' in page
    assert 'name="libraries" value="movies" checked' not in page
    assert state['Policy']['BlockedTags']==['restricted'] and state['Policy']['EnableContentDeletion'] is False
    assert post(client,'/admin/emby/libraries',{'id':uid,'action':'remove_all'},path).status_code==303
    assert writes[-1]==([],False)
    assert 'No libraries allowed' in client.get(path).text
    assert post(client,'/admin/emby/libraries',{'id':uid,'access_mode':'invalid'},path).status_code==400
    assert client.post('/admin/emby/libraries',data={'csrf':'bad','id':uid}).status_code==403
    logout(client);login_user(client)
    assert client.get(path).status_code==403
    assert post(client,'/admin/emby/libraries',{'id':uid,'action':'remove_all'},'/account').status_code==403
    assert writes[-1]==([],False)


def test_library_write_is_not_reported_as_success_if_readback_differs(monkeypatch):
    api=EmbyClient()
    monkeypatch.setattr(api,'libraries',lambda:[{'Id':'films','Name':'Films'}])
    monkeypatch.setattr(api,'user',lambda uid:{'Id':uid,'Policy':{'EnableAllFolders':True,'EnabledFolders':[]}})
    monkeypatch.setattr(api,'policy',lambda uid,policy:None)
    with pytest.raises(EmbyError,match='Vérification des accès'):
        api.assign_libraries('user-1',['films'],False)
