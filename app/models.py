from sqlalchemy import String, Integer, Boolean, Text, ForeignKey, LargeBinary
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    emby_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    admin: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    theme_preference: Mapped[str] = mapped_column(String(10), default="auto", server_default="auto")
    tool_access: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    password_hash: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=0)
    seerr_notifications: Mapped[bool | None] = mapped_column(Boolean)
    preferences_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    emby_missing: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    emby_seen_at: Mapped[int | None] = mapped_column(Integer)
    locale: Mapped[str] = mapped_column(String(10), default="en", server_default="en")

class Config(Base):
    __tablename__ = "config"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)

class Session(Base):
    __tablename__ = "sessions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    setup_expires: Mapped[int | None] = mapped_column(Integer)
    csrf: Mapped[str] = mapped_column(String(100))
    expires: Mapped[int] = mapped_column(Integer, index=True)
    version: Mapped[int] = mapped_column(Integer, default=0)

class Token(Base):
    __tablename__ = "tokens"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    purpose: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(320))
    expires: Mapped[int] = mapped_column(Integer, index=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer)

class MenuItem(Base):
    __tablename__ = "menu_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    label_en: Mapped[str | None] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(30), default="↗")
    position: Mapped[int] = mapped_column(Integer, default=0)
    new_tab: Mapped[bool] = mapped_column(Boolean, default=True)
    icon_url: Mapped[str] = mapped_column(Text, default="", server_default="")
    access_service: Mapped[str | None] = mapped_column(String(40))
    menu_key: Mapped[str] = mapped_column(String(40), default="main", server_default="main")

class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    expires: Mapped[int] = mapped_column(Integer, index=True)

class MailJob(Base):
    __tablename__ = "mail_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt: Mapped[int] = mapped_column(Integer, index=True)
    expires: Mapped[int] = mapped_column(Integer)

class IntegrationJob(Base):
    __tablename__ = "integration_jobs"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    service: Mapped[str] = mapped_column(String(20), primary_key=True)
    email_digest: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20), default='pending')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt: Mapped[int] = mapped_column(Integer, index=True)
    updated_at: Mapped[int] = mapped_column(Integer)
    error: Mapped[str] = mapped_column(String(40), default="")

    last_success_at: Mapped[int | None] = mapped_column(Integer)

class AccessService(Base):
    __tablename__ = "access_services"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    browser_url: Mapped[str] = mapped_column(Text, default="")
    server_url: Mapped[str] = mapped_column(Text, default="")
    icon_url: Mapped[str] = mapped_column(Text, default="", server_default="")
    icon: Mapped[str] = mapped_column(String(80), default="link", server_default="link")
    entry_mode: Mapped[str] = mapped_column(String(20), default="direct", server_default="direct")
    access_draft: Mapped[str | None] = mapped_column(Text)
    access_published: Mapped[str | None] = mapped_column(Text)
    access_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

class Guide(Base):
    __tablename__ = "guides"
    id: Mapped[int] = mapped_column(primary_key=True)
    service_key: Mapped[str] = mapped_column(ForeignKey("access_services.key"), index=True)
    draft: Mapped[str] = mapped_column(Text)
    published: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=0)

class Language(Base):
    __tablename__='languages'
    code: Mapped[str] = mapped_column(String(10),primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    enabled: Mapped[bool] = mapped_column(Boolean,default=False)

class ContentTranslation(Base):
    __tablename__='content_translations'
    locale: Mapped[str] = mapped_column(ForeignKey('languages.code',ondelete='CASCADE'),primary_key=True)
    resource: Mapped[str] = mapped_column(String(240),primary_key=True)
    source_hash: Mapped[str] = mapped_column(String(64),primary_key=True)
    value: Mapped[str] = mapped_column(Text)

class IconAsset(Base):
    __tablename__='icon_assets'
    digest: Mapped[str] = mapped_column(String(64),primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    mime: Mapped[str] = mapped_column(String(40),default='image/png',server_default='image/png')

class ConnectionCheck(Base):
    __tablename__='connection_checks'
    service: Mapped[str] = mapped_column(String(20),primary_key=True)
    state: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(String(100))
    checked_at: Mapped[int] = mapped_column(Integer)

class PermissionGroup(Base):
    __tablename__='permission_groups'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100),unique=True)
    policy: Mapped[str] = mapped_column(Text,default='{}')
    version: Mapped[int] = mapped_column(Integer,default=0)

class GroupMember(Base):
    __tablename__='group_members'
    group_id: Mapped[int] = mapped_column(ForeignKey('permission_groups.id',ondelete='CASCADE'),primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),primary_key=True)

class PolicyState(Base):
    __tablename__='policy_states'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),primary_key=True)
    baseline: Mapped[str] = mapped_column(Text,default='{}')
    overrides: Mapped[str] = mapped_column(Text,default='{}')
    desired: Mapped[str] = mapped_column(Text,default='{}')
    observed: Mapped[str] = mapped_column(Text,default='{}')
    confirmed: Mapped[str] = mapped_column(Text,default='{}')
    version: Mapped[int] = mapped_column(Integer,default=0)
    pending: Mapped[bool] = mapped_column(Boolean,default=False)
    error: Mapped[str] = mapped_column(String(100),default='')
    checked_at: Mapped[int | None] = mapped_column(Integer)

class SeerrSession(Base):
    __tablename__='seerr_sessions'
    session_digest: Mapped[str] = mapped_column(ForeignKey('sessions.digest',ondelete='CASCADE'),primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    payload: Mapped[str] = mapped_column(Text)
    expires: Mapped[int] = mapped_column(Integer)

class SeerrTicket(Base):
    __tablename__='seerr_tickets'
    actor_digest: Mapped[str | None] = mapped_column(String(64))
    digest: Mapped[str] = mapped_column(String(64),primary_key=True)
    session_digest: Mapped[str] = mapped_column(ForeignKey('seerr_sessions.session_digest',ondelete='CASCADE'))
    expires: Mapped[int] = mapped_column(Integer)

class AuditEvent(Base):
    __tablename__='audit_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[int] = mapped_column(Integer,index=True)
    actor_id: Mapped[int | None] = mapped_column(Integer)
    subject_id: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(200))
    outcome: Mapped[int] = mapped_column(Integer)
    detail: Mapped[str] = mapped_column(Text,default='')

class MediaSession(Base):
    __tablename__='media_sessions'
    session_digest: Mapped[str] = mapped_column(ForeignKey('sessions.digest',ondelete='CASCADE'),primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    payload: Mapped[str] = mapped_column(Text)
    expires: Mapped[int] = mapped_column(Integer)

class SupportSession(Base):
    __tablename__='support_sessions'
    session_digest: Mapped[str] = mapped_column(ForeignKey('sessions.digest',ondelete='CASCADE'),primary_key=True)
    source_digest: Mapped[str] = mapped_column(ForeignKey('sessions.digest',ondelete='CASCADE'))
    target_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    target_version: Mapped[int] = mapped_column(Integer)
    expires: Mapped[int] = mapped_column(Integer)

class ToolGrant(Base):
    __tablename__='tool_grants'
    digest: Mapped[str] = mapped_column(String(64),primary_key=True)
    session_digest: Mapped[str] = mapped_column(ForeignKey('sessions.digest',ondelete='CASCADE'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    tool: Mapped[str] = mapped_column(String(20))
    expires: Mapped[int] = mapped_column(Integer)
    redeemed: Mapped[bool] = mapped_column(Boolean,default=False)
