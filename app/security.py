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

def password_ok(value):
    if not 12 <= len(value) <= 256:
        raise ValueError('The password must contain between 12 and 256 characters.')

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
