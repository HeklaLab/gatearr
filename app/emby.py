import httpx
import secrets
from copy import deepcopy
from urllib.parse import quote
from .settings import settings
from .connections import emby_connection, media_kind

_ADMIN = object()

class EmbyError(Exception):
    pass

class EmbyClient:
    kind='emby'
    def __init__(self,base_url=None,api_key=None):
        self.base_url=base_url
        self.api_key=api_key

    def request(self, method, path, *, token=None, **kwargs):
        base, api_key = (self.base_url,self.api_key) if self.base_url is not None else emby_connection()
        if token is _ADMIN:
            token = api_key
        if not base:
            raise EmbyError("Emby non configuré")
        headers = {"X-Emby-Authorization": 'Emby Client="Gatearr", Device="Portal", DeviceId="gatearr-portal", Version="1.0"'}
        if self.kind=='jellyfin':
            headers={'Authorization':'MediaBrowser Client="Gatearr", Device="Portal", DeviceId="gatearr-portal", Version="1.0"'}
            if token:
                headers['Authorization']+=', Token="'+token+'"'
        elif token:
            headers["X-Emby-Token"] = token
        try:
            with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
                response = client.request(method, base + path, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except (httpx.HTTPError, ValueError) as exc:
            raise EmbyError("Emby indisponible ou accès refusé") from exc

    def authenticate(self, name, password):
        result = self.request("POST", "/Users/AuthenticateByName", json={"Username": name, "Pw": password})
        if not isinstance(result, dict) or not result.get("User", {}).get("Id") or not result.get("AccessToken"):
            raise EmbyError("Réponse Emby invalide")
        return result

    def users(self):
        users, start = [], 0
        while True:
            page = self.request("GET", "/Users/Query", token=_ADMIN, params={"StartIndex": start, "Limit": 200})
            if not isinstance(page, dict) or not isinstance(page.get("Items"), list):
                raise EmbyError("Réponse de synchronisation invalide")
            items = page["Items"]
            users.extend(items)
            start += len(items)
            if start >= page.get("TotalRecordCount", start) or not items:
                return users
            if start > 100000:
                raise EmbyError("Trop d'utilisateurs")

    def user(self, user_id):
        result = self.request("GET", "/Users/" + quote(user_id, safe=""), token=_ADMIN)
        if not isinstance(result, dict) or result.get("Id") != user_id:
            raise EmbyError("Réponse utilisateur invalide")
        return result

    def password(self, user_id, password, token=None):
        self.request("POST", "/Users/" + quote(user_id, safe="") + "/Password", token=token or _ADMIN,
                     json={"Id": user_id, "NewPw": password, "ResetPassword": False})

    def libraries(self):
        folders, start = [], 0
        for _ in range(1000):
            page = self.request("GET", "/Library/VirtualFolders/Query", token=_ADMIN,
                                params={"StartIndex": start, "Limit": 200})
            if not isinstance(page, dict) or not isinstance(page.get("Items"), list):
                raise EmbyError("Invalid library response")
            items = page["Items"]
            folders.extend(items)
            start += len(items)
            if not items or start >= page.get("TotalRecordCount", start):
                break
        else:
            raise EmbyError("Invalid library pagination")
        # Discard paths/library credentials before passing data to any template.
        result=[]
        for item in folders:
            if not item.get('Name'):continue
            permission_id=item.get('Guid')
            if not permission_id:
                # Older Emby versions may already expose a GUID in Id/ItemId.
                candidate=str(item.get('Id') or item.get('ItemId') or '')
                import re
                if not re.fullmatch(r'[a-fA-F0-9]{32}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}',candidate):
                    raise EmbyError('The server did not provide permission GUIDs for its libraries')
                permission_id=candidate
            result.append({'Id':str(permission_id).replace('-','').lower(),'Name':str(item['Name'])})
        return result

    def copy_options(self):
        result = self.request("GET", "/Users/CopyDataOptions", token=_ADMIN)
        if not isinstance(result, dict) or not isinstance(result.get("DataOptions"), list):
            raise EmbyError("Invalid copy options")
        # Never copy authentication material, even if a future server offers it.
        return [x for x in result["DataOptions"] if isinstance(x, dict) and x.get("Id") and not any(word in (str(x["Id"])+str(x.get("Name", ""))).lower() for word in ("password", "credential", "token", 'authentication'))]

    def policy(self, user_id, policy):
        self.request("POST", "/Users/" + quote(user_id, safe="") + "/Policy", token=_ADMIN, json=policy)

    def assign_libraries(self, user_id, selected, all_folders=False):
        allowed = {item["Id"] for item in self.libraries()}
        if not set(selected) <= allowed:
            raise ValueError('Unknown library. Reload the page.')
        policy = deepcopy(self.user(user_id).get("Policy", {}))
        policy.update(EnableAllFolders=all_folders, EnabledFolders=sorted(set(selected)), ExcludedSubFolders=[])
        policy.pop('BlockedMediaFolders',None)
        self.policy(user_id, policy)
        confirmed=self.user(user_id).get('Policy',{})
        normalize=lambda values:{str(value).replace('-','').lower() for value in (values or [])}
        if not isinstance(confirmed,dict) or confirmed.get('EnableAllFolders') is not bool(all_folders) or (not all_folders and normalize(confirmed.get('EnabledFolders',[])) != normalize(selected)):
            raise EmbyError('Vérification des accès Emby échouée')

    def validate_copy(self, source_id, options):
        source = self.user(source_id)
        if source.get("Policy", {}).get("IsAdministrator"):
            raise ValueError('Choose a non-administrator template user.')
        allowed = {x["Id"] for x in self.copy_options()}
        if not options or not set(options) <= allowed:
            raise ValueError('Select valid copy options.')
        return source

    def clone(self, source_id, name, password, options):
        self.validate_copy(source_id, options)
        # A random temporary name avoids publishing the requested login until it is protected.
        created = self.request("POST", "/Users/New", token=_ADMIN,
            json={"Name": "gatearr-" + secrets.token_hex(16), "CopyFromUserId": source_id, "UserCopyOptions": options})
        if not isinstance(created, dict) or not created.get("Id") or created["Id"] == source_id:
            raise EmbyError("Invalid created user")
        target_id = created["Id"]
        try:
            policy = deepcopy(self.user(target_id).get("Policy", {}))
            policy.update(IsDisabled=True, IsAdministrator=False)
            self.policy(target_id, policy)
            self.password(target_id, password)
            renamed = deepcopy(self.user(target_id))
            renamed["Name"] = name
            self.request("POST", "/Users/" + quote(target_id, safe=""), token=_ADMIN, json=renamed)
            policy["IsDisabled"] = False
            self.policy(target_id, policy)
        except Exception as exc:
            # Compensate only the newly created user, never the template or existing accounts.
            try:
                self.request("DELETE", "/Users/" + quote(target_id, safe=""), token=_ADMIN)
            except EmbyError:
                raise EmbyError("Provisioning failed; inspect temporary gatearr user " + target_id) from exc
            raise EmbyError("Provisioning failed; new user removed") from exc
        return self.user(target_id)

    def copy_to_existing(self, source_id, target_id, options):
        self.validate_copy(source_id, options)
        if source_id == target_id:
            raise ValueError('The template and target must be different.')
        original = self.user(target_id).get("Policy", {})
        self.request("POST", "/Users/" + quote(source_id, safe="") + "/CopyData", token=_ADMIN,
            json={"UserId": source_id, "ToUserIds": [target_id], "CopyOptions": options})
        policy = deepcopy(self.user(target_id).get("Policy", {}))
        policy.update(IsAdministrator=bool(original.get("IsAdministrator")), IsDisabled=bool(original.get("IsDisabled")))
        self.policy(target_id, policy)

class JellyfinClient(EmbyClient):
    kind='jellyfin'

    def users(self):
        users=self.request('GET','/Users',token=_ADMIN)
        if not isinstance(users,list) or len(users)>100000:
            raise EmbyError('Réponse de synchronisation invalide')
        return users

    def password(self,user_id,password,token=None):
        self.request('POST','/Users/Password',token=token or _ADMIN,params={'userId':user_id},json={'NewPw':password,'ResetPassword':False})

    def libraries(self):
        folders=self.request('GET','/Library/VirtualFolders',token=_ADMIN)
        if not isinstance(folders,list):raise EmbyError('Invalid library response')
        return [{'Id':str(item['ItemId']),'Name':str(item['Name'])} for item in folders if item.get('ItemId') and item.get('Name')]

    def copy_options(self):
        return [{'Id':'Policy','Name':'Accès et permissions des bibliothèques'},{'Id':'Configuration','Name':'User configuration'},{'Id':'DisplayPreferences','Name':'Web home preferences'}]

    def copy_to_existing(self,source_id,target_id,options):
        source=self.validate_copy(source_id,options)
        if source_id==target_id:raise ValueError('The template and target must be different.')
        original=self.user(target_id).get('Policy',{})
        if 'Policy' in options:
            policy=deepcopy(source.get('Policy',{}))
            policy.update(IsAdministrator=bool(original.get('IsAdministrator')),IsDisabled=bool(original.get('IsDisabled')))
            self.policy(target_id,policy)
        if 'Configuration' in options:
            self.request('POST','/Users/Configuration',token=_ADMIN,params={'userId':target_id},json=deepcopy(source.get('Configuration',{})))
        if 'DisplayPreferences' in options:
            path='/DisplayPreferences/usersettings'
            preferences=self.request('GET',path,token=_ADMIN,params={'userId':source_id,'client':'emby'})
            if not isinstance(preferences,dict):raise EmbyError('Invalid display preferences')
            preferences.pop('Id',None)
            self.request('POST',path,token=_ADMIN,params={'userId':target_id,'client':'emby'},json=preferences)

    def clone(self,source_id,name,password,options):
        self.validate_copy(source_id,options)
        created=self.request('POST','/Users/New',token=_ADMIN,json={'Name':name,'Password':password})
        if not isinstance(created,dict) or not created.get('Id') or created['Id']==source_id:raise EmbyError('Invalid created user')
        target_id=created['Id']
        try:
            policy=deepcopy(self.user(target_id).get('Policy',{}))
            policy.update(IsDisabled=True,IsAdministrator=False)
            self.policy(target_id,policy)
            self.copy_to_existing(source_id,target_id,options)
            policy=deepcopy(self.user(target_id).get('Policy',{}))
            policy.update(IsDisabled=False,IsAdministrator=False)
            self.policy(target_id,policy)
        except Exception as exc:
            try:self.request('DELETE','/Users/'+quote(target_id,safe=''),token=_ADMIN)
            except EmbyError:raise EmbyError('Provisioning failed; inspect temporary user '+target_id) from exc
            raise EmbyError('Provisioning failed; new user removed') from exc
        return self.user(target_id)


def client_for(kind,base_url=None,api_key=None):
    if kind not in ('emby','jellyfin'):raise ValueError('Invalid media server')
    return (JellyfinClient if kind=='jellyfin' else EmbyClient)(base_url,api_key)

class MediaClient:
    def __getattr__(self,name):
        return getattr(client_for(media_kind()),name)

emby=MediaClient()
