"""Server-side connection settings. Environment provides the initial fallback."""
from .db import SessionLocal
from .mailer import config
from .security import decrypt
from .settings import settings


def tdarr_upstream_url(value):
    """Browser hash routes are not part of the HTTP upstream's base address."""
    from urllib.parse import urlsplit,urlunsplit
    return urlunsplit(urlsplit(value)._replace(fragment='')).rstrip('/')


def emby_connection():
    with SessionLocal() as db:
        url = config(db,'emby_url')
        encoded = config(db,'emby_api_key')
        return url, decrypt(encoded) if encoded else ''


def media_kind(db=None):
    if db is not None:
        return config(db,'media_server',settings.media_server)
    with SessionLocal() as db:
        return config(db,'media_server',settings.media_server)
