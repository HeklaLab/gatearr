import os
import tempfile
from pathlib import Path

os.environ.update({
    'DATABASE_URL': 'sqlite:///' + str(Path(tempfile.mkdtemp()) / 'test.db'),
    'SECRET_KEY': 'test-secret-' + 'x' * 48,
    'PUBLIC_URL': 'http://testserver',
    'COOKIE_SECURE': 'false',
})
import pytest
from alembic.config import Config as AlembicConfig
from alembic import command
from fastapi.testclient import TestClient
from app import main
from app.db import SessionLocal
from app.models import Base, AccessService,Language,ContentTranslation,Config
from app.emby import EmbyError

command.upgrade(AlembicConfig('alembic.ini'), 'head')
with SessionLocal() as seed_db:
    SEED_CONTENT=[(row.locale,row.resource,row.source_hash,row.value) for row in seed_db.query(ContentTranslation)]

class FakeEmby:
    def __init__(self):
        self.password_value = 'DemoPassword123!'
        self.disabled = False
        self.deleted = False
        self.changes = []
    def dto(self):
        return {'Id': 'user-1', 'Name': 'demo', 'Policy': {'IsDisabled': self.disabled, 'IsAdministrator': True}}
    def owner(self):
        return {'Id':'admin-1','Name':'Owner','Policy':{'IsDisabled':False,'IsAdministrator':False}}
    def authenticate(self, name, password):
        if name=='Owner' and password=='AdminPassword123!':return {'User':self.owner(),'AccessToken':'owner-token'}
        if name != 'demo' or password != self.password_value or self.disabled or self.deleted:
            raise EmbyError('denied')
        return {'User': self.dto(), 'AccessToken': 'user-token'}
    def users(self):
        return [self.owner()] + ([] if self.deleted else [self.dto()])
    def user(self, user_id):
        if user_id=='admin-1':return self.owner()
        if self.deleted or user_id != 'user-1':
            raise EmbyError('missing')
        return self.dto()
    def password(self, user_id, password, token=None):
        if self.disabled or self.deleted:
            raise EmbyError('denied')
        self.password_value = password
        self.changes.append((user_id, password, token))

@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr('app.versioning.refresh_due',lambda:None)
    monkeypatch.setattr('app.permissions.run_pending',lambda:None)
    monkeypatch.setattr('app.permission_refresh.refresh_due',lambda:None)
    monkeypatch.setattr('app.library_updates.run_due',lambda:None)
    instance = FakeEmby()
    monkeypatch.setattr(main, 'emby', instance)
    monkeypatch.setattr('app.onboarding.probe_media', lambda kind,base,key: {'id':'test-media-server','name':'Test media','count':len(instance.users())})
    monkeypatch.setattr('app.connection_health.checks',lambda db,refresh=False:{service:{'state':'unconfigured','detail':'Connection not configured','checked_at':None} for service in ('emby','seerr','radarr','sonarr','bazarr')})
    return instance

@pytest.fixture
def client(fake):
    command.upgrade(AlembicConfig('alembic.ini'),'head')
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.add_all([Language(code='en',name='English',enabled=True),Language(code='fr',name='Français',enabled=True)])
        db.flush()
        db.add_all([ContentTranslation(locale=locale,resource=resource,source_hash=stamp,value=value) for locale,resource,stamp,value in SEED_CONTENT])
        db.add(AccessService(key="emby",name="Emby",browser_url="",server_url=""))
        db.add_all([Config(key='captcha_login',value='false'),Config(key='captcha_forgot',value='false')])
        db.commit()
    with TestClient(main.app) as instance:
        yield instance

@pytest.fixture
def sent(monkeypatch):
    messages = []
    monkeypatch.setattr(main, 'send', lambda db, recipient, purpose, values: messages.append((recipient, purpose, values)))
    return messages
