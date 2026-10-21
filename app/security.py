import base64
import hashlib
import secrets
from urllib.parse import urlsplit
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from cryptography.fernet import Fernet
from email_validator import validate_email, EmailNotValidError
from .settings import settings

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))
def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()
def verify(encoded, password):
    try:
        return hasher.verify(encoded or DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False

def password_policy(db=None):
    import json
    default={'enabled':True,'minimum':12,'uppercase':False,'lowercase':False,'digit':False,'symbol':False}
    if db is None:return default
    from .mailer import config
    raw=config(db,'password_policy')
    return {**default,**json.loads(raw)} if raw else default

def password_ok(value,db=None):
    policy=password_policy(db)
    if not isinstance(value,str) or not 1<=len(value)<=256:raise ValueError('The password must contain between 1 and 256 characters.')
    if not policy['enabled']:return
    if len(value)<policy['minimum']:raise ValueError('Password does not meet the minimum length requirement.')
    for key,valid in [('uppercase',any(c.isupper() for c in value)),('lowercase',any(c.islower() for c in value)),('digit',any(c.isdigit() for c in value)),('symbol',any(not c.isalnum() and not c.isspace() for c in value))]:
        if policy[key] and not valid:raise ValueError('Password does not meet the required character rules.')


def url_ok(value, optional=False):
    if not value and optional:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or any(c in value for c in '\r\n'):
        raise ValueError('Use a complete HTTP(S) URL without embedded credentials.')
    try:port=parsed.port
    except ValueError:raise ValueError('Use a complete HTTP(S) URL without embedded credentials.')
    if port is not None and not 1<=port<=65535:
        raise ValueError('Use a complete HTTP(S) URL without embedded credentials.')
    return value.rstrip("/")

def email_ok(value):
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        raise ValueError('Invalid email address.')

def cipher():
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest()))
def encrypt(value):
    return cipher().encrypt(value.encode()).decode() if value else ""
def decrypt(value):
    return cipher().decrypt(value.encode()).decode() if value else ""


def origin(value):
    try:
        parsed=urlsplit(value)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
            return None
        return (parsed.scheme,parsed.hostname.lower(),parsed.port or (443 if parsed.scheme=='https' else 80))
    except ValueError:
        return None
