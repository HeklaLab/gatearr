"""Verified-mail propagation. No matching by username or old email."""
import json
import logging
import time
from urllib.parse import quote, urlsplit
import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert
from .models import User, IntegrationJob
from .db import SessionLocal
from .connections import media_kind
from .mailer import config
from .security import decrypt, digest

log = logging.getLogger("gatearr.integrations")
SERVICES = ("seerr", "tracearr")
SECRET_CONFIG = {"smtp_password", "seerr_api_key", "tracearr_api_key", "tracearr_owner_password", "emby_api_key", "emby_url"}

def enabled(db, service):
    return config(db, service + "_enabled") == "true"

class SyncError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def request(client, method, path, **kwargs):
    try:
        response = client.request(method, path, **kwargs)
        if response.status_code in (401, 403):
            raise SyncError('authentication')
        if response.status_code == 404:
            raise SyncError('not_found')
        if response.status_code >= 300:
            raise SyncError('remote_error')
        return response.json() if response.content else {}
    except (httpx.HTTPError, ValueError) as exc:
        raise SyncError('unavailable') from exc

def normalized_id(value):
    return str(value).replace("-", "").lower()

def sync_seerr(db, user):
    base = config(db, "seerr_url")
    key = decrypt(config(db, "seerr_api_key"))
    if not base or not key:
        raise SyncError('configuration')
    with httpx.Client(base_url=base+"/", headers={"X-Api-Key": key}, timeout=15, follow_redirects=False, trust_env=False) as client:
        remote = request(client, "GET", "api/v1/user/jellyfin/" + quote(user.emby_id, safe=""))
        if not remote.get("id") or normalized_id(remote.get("jellyfinUserId", "")) != normalized_id(user.emby_id):
            raise SyncError('identity_mismatch')
        user_id = remote["id"]
        path = "api/v1/user/" + str(user_id) + "/settings/main"
        original = request(client, "GET", path)
        # Seerr's handler overwrites these fields: echo writable settings, excluding computed defaults.
        fields = ("username", "locale", "discoverRegion", "streamingRegion", "originalLanguage", "movieQuotaLimit", "movieQuotaDays", "tvQuotaLimit", "tvQuotaDays", "watchlistSyncMovies", "watchlistSyncTv")
        body = {key: original[key] for key in fields if key in original}
        body["email"] = user.email
        body["locale"] = user.locale
        result = request(client, "POST", path, json=body)
        if result.get("email", "").lower() != user.email.lower():
            raise SyncError('verification_failed')
        verified = request(client, "GET", path)
        if verified.get("email", "").lower() != user.email.lower() or verified.get("locale") != user.locale:
            raise SyncError('verification_failed')
        sync_seerr_notifications(db,client,user,"api/v1/user/"+str(user_id)+"/settings/notifications")

def tracearr_account(db, client, user):
    server_id = config(db, "tracearr_server_id")
    key = decrypt(config(db, "tracearr_api_key"))
    if not server_id or not key:
        raise SyncError('configuration')
    cursor, visited, matches = None, set(), set()
    for _ in range(1000):
        params = {"pageSize": 100}
        if cursor:
            params["cursor"] = cursor
        page = request(client, "GET", "api/v2/public/users", headers={"Authorization": "Bearer " + key}, params=params)
        if not isinstance(page.get("data"), list):
            raise SyncError('unsupported_api')
        for identity in page["data"]:
            for account in identity.get("accounts", []):
                if (account.get("server_id") == server_id and account.get("server_type") == media_kind(db) and not account.get("removed_at") and normalized_id(account.get("external_user_id", "")) == normalized_id(user.emby_id)):
                    matches.add(account.get("server_user_id"))
        cursor = page.get("meta", {}).get("nextCursor")
        if not cursor:
            break
        if cursor in visited:
            raise SyncError('invalid_pagination')
        visited.add(cursor)
    else:
        raise SyncError('invalid_pagination')
    if len(matches) != 1 or None in matches:
        raise SyncError('not_found' if not matches else 'ambiguous')
    return matches.pop()

def tracearr_login(db, client):
    email = config(db, "tracearr_owner_email")
    password = decrypt(config(db, "tracearr_owner_password"))
    if not email or not password:
        raise SyncError('configuration')
    # The public API is read-only for this operation. The owner-only dashboard API is explicit opt-in.
    request(client, "POST", "api/v1/auth/sign-in/email", json={"email": email, "password": password, "rememberMe": False})
    if not client.cookies:
        raise SyncError('authentication')

def sync_tracearr(db, user):
    base = config(db, "tracearr_url")
    if not base or config(db, "tracearr_internal_api") != "true":
        raise SyncError('configuration')
    parsed = urlsplit(base)
    origin = parsed.scheme + "://" + parsed.netloc
    with httpx.Client(base_url=base+"/", headers={"Origin": origin}, timeout=15, follow_redirects=False, trust_env=False) as client:
        account_id = tracearr_account(db, client, user)
        tracearr_login(db, client)
        try:
            path = "api/v1/users/" + quote(account_id, safe="")
            remote = request(client, "GET", path + "/full")
            account = remote.get("user", {})
            if (account.get("serverId") != config(db, "tracearr_server_id") or normalized_id(account.get("externalId", "")) != normalized_id(user.emby_id)):
                raise SyncError('identity_mismatch')
            # contactEmail is for notifications/newsletters. Never rewrite the owner's login email or name.
            request(client, "PATCH", path + "/identity", json={"contactEmail": user.email})
            verified = request(client, "GET", path + "/full")
            if verified.get("identity", {}).get("contactEmail", "").lower() != user.email.lower():
                raise SyncError('verification_failed')
            return sync_newsletter(client,user)
        finally:
            try:
                request(client, "POST", "api/v1/auth/sign-out", json={})
            except SyncError:
                pass

def sync_digest(db,user,service):
    mode=config(db,'seerr_notification_mode','unmanaged')
    preference=user.newsletter_opt_in if service=='tracearr' else (True if mode=='forced' else user.seerr_notifications if mode=='optional' else None)
    return digest(json.dumps([user.email,user.locale,preference,user.preferences_version,mode if service=='seerr' else 'newsletter']))


def sync_seerr_notifications(db,client,user,path):
    mode=config(db,'seerr_notification_mode','unmanaged')
    desired=True if mode=='forced' else user.seerr_notifications if mode=='optional' else None
    if desired is None:return
    current=request(client,'GET',path)
    if desired and not current.get('emailEnabled'):
        raise SyncError('notifications_disabled')
    fields=('pgpKey','discordIds','pushbulletAccessToken','pushoverApplicationToken','pushoverUserKey','pushoverSound','telegramChatId','telegramMessageThreadId','telegramSendSilently')
    body={key:current[key] for key in fields if key in current}
    body['notificationTypes']={**current.get('notificationTypes',{}),'email':8190 if desired else 0}
    request(client,'POST',path,json=body)
    verified=request(client,'GET',path)
    if verified.get('notificationTypes',{}).get('email') != body['notificationTypes']['email']:
        raise SyncError('verification_failed')


def sync_newsletter(client,user):
    if user.newsletter_opt_in is None:return None
    path='api/v1/email/suppressions'
    def state():
        rows=request(client,'GET',path)
        if not isinstance(rows,list):raise SyncError('unsupported_api')
        return any(str(row.get('address','')).lower()==user.email.lower() for row in rows)
    suppressed=state()
    if user.newsletter_pending:
        if user.newsletter_opt_in and suppressed:
            request(client,'DELETE',path+'/'+quote(user.email,safe=''))
        elif not user.newsletter_opt_in and not suppressed:
            request(client,'POST',path,json={'address':user.email})
        suppressed=state()
        if (not suppressed)!=user.newsletter_opt_in:raise SyncError('verification_failed')
    # A remote unsubscribe wins unless the member explicitly requested a new change.
    return {'newsletter_opt_in':not suppressed,'newsletter_pending':False}

def queue_user(db, user, force=False):
    if not user.emby_id or not user.email or not user.active:
        return
    current = int(time.time())
    for service in SERVICES:
        if not enabled(db, service):
            continue
        previous = db.get(IntegrationJob, (user.id, service))
        if previous and previous.email_digest == sync_digest(db,user,service) and not force:
            continue
        statement = insert(IntegrationJob).values(user_id=user.id, service=service, email_digest=sync_digest(db,user,service), state='pending', attempts=0, next_attempt=current, updated_at=current, error="")
        db.execute(statement.on_conflict_do_update(index_elements=[IntegrationJob.user_id, IntegrationJob.service], set_={"email_digest": sync_digest(db,user,service), "state": 'pending', "attempts": 0, "next_attempt": current, "updated_at": current, 'error': ""}))
    db.commit()

def queue_all(db, force=False):
    for user in db.scalars(select(User).where(User.emby_id.is_not(None), User.email.is_not(None), User.active.is_(True))):
        queue_user(db, user, force)

def run_jobs():
    current = int(time.time())
    with SessionLocal() as db:
        active_services = [service for service in SERVICES if enabled(db, service)]
        if not active_services:
            return
        jobs = list(db.scalars(select(IntegrationJob).join(User, User.id == IntegrationJob.user_id).where(
            IntegrationJob.service.in_(active_services), IntegrationJob.state != 'success', IntegrationJob.next_attempt <= current,
            User.active.is_(True), User.email.is_not(None), User.emby_id.is_not(None)
        ).order_by(IntegrationJob.next_attempt).limit(10)))
        for job in jobs:
            user = db.get(User, job.user_id)
            if not enabled(db, job.service) or not user or not user.active or not user.email:
                continue
            expected = sync_digest(db,user,job.service)
            if job.email_digest != expected:
                queue_user(db,user)
                continue
            preference_version=user.preferences_version
            try:
                changes=(sync_seerr if job.service == "seerr" else sync_tracearr)(db, user)
                if isinstance(changes,dict):
                    result=db.execute(update(User).where(User.id==user.id,User.preferences_version==preference_version).values(**changes))
                    if result.rowcount != 1:
                        db.rollback()
                        continue
                values = {"state": 'success', 'error': "", "updated_at": current, "last_success_at": current, "email_digest": sync_digest(db,user,job.service)}
            except Exception as exc:
                code = exc.code if isinstance(exc, SyncError) else 'unavailable'
                values = {"state": 'error', 'error': code, "attempts": job.attempts+1, "updated_at": current, "next_attempt": current + min(3600, 30 * 2**min(job.attempts, 7))}
                log.warning("Email propagation failed service=%s user_id=%s code=%s", job.service, user.id, code)
            # A newer verified email can be queued while the remote HTTP call is in flight.
            db.execute(update(IntegrationJob).where(IntegrationJob.user_id == job.user_id, IntegrationJob.service == job.service, IntegrationJob.email_digest == expected).values(**values))
            db.commit()
