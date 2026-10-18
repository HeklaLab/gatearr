import httpx
import pytest
from app.emby import EmbyClient, EmbyError

def transport_client(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))

def test_auth_fields_password_fields_headers_and_empty_success(monkeypatch):
    captured = []
    def handle(request):
        captured.append(request)
        if request.url.path.endswith('/AuthenticateByName'):
            return httpx.Response(200, json={'User': {'Id': 'u1'}, 'AccessToken': 'user-token'})
        return httpx.Response(204)
    transport_client(monkeypatch, handle)
    emby = EmbyClient()
    result = emby.authenticate('demo', 'password')
    emby.password('u1', 'new-password', result['AccessToken'])
    import json
    assert json.loads(captured[0].content) == {'Username': 'demo', 'Pw': 'password'}
    assert 'X-Emby-Token' not in captured[0].headers
    assert 'Emby Client=' in captured[0].headers['X-Emby-Authorization']
    assert captured[1].headers['X-Emby-Token'] == 'user-token'
    assert json.loads(captured[1].content) == {'Id': 'u1', 'NewPw': 'new-password', 'ResetPassword': False}
    assert 'api_key' not in str(captured[1].url)

def test_listing_pagination_uses_admin_key(monkeypatch):
    offsets = []
    def handle(request):
        offsets.append(request.url.params['StartIndex'])
        assert request.headers['X-Emby-Token'] == 'test-api-key'
        return httpx.Response(200, json={'Items': [{'Id': offsets[-1]}], 'TotalRecordCount': 2})
    transport_client(monkeypatch, handle)
    assert len(EmbyClient().users()) == 2
    assert offsets == ['0', '1']

def test_emby_error_is_sanitized(monkeypatch):
    transport_client(monkeypatch, lambda request: httpx.Response(403, text='secret-api-key'))
    with pytest.raises(EmbyError, match='accès refusé') as exc:
        EmbyClient().password('u1', 'password')
    assert 'secret-api-key' not in str(exc.value)

def test_remote_identity_checked_before_reset(monkeypatch):
    transport_client(monkeypatch, lambda request: httpx.Response(200, json={'Id': 'different-user'}))
    with pytest.raises(EmbyError, match='utilisateur invalide'):
        EmbyClient().user('u1')


def test_library_query_pagination_and_no_path_credentials_exposed(monkeypatch):
    def handler(request):
        assert request.url.path.endswith('/Library/VirtualFolders/Query')
        offset=int(request.url.params['StartIndex'])
        return httpx.Response(200,json={'Items':[{'ItemId':'film-'+str(offset),'Guid':str(offset+1)*32,'Name':'Films','Locations':['/private/media'],'LibraryOptions':{'PathInfos':[{'Password':'library-secret'}]}}], 'TotalRecordCount':2})
    transport_client(monkeypatch,handler)
    folders=EmbyClient().libraries()
    assert folders==[{'Id':'1'*32,'Name':'Films'},{'Id':'2'*32,'Name':'Films'}]
    assert 'library-secret' not in str(folders) and '/private/media' not in str(folders)
