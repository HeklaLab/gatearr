"""Image references are uploads or bundled assets; ordinary HTTP links stay separate."""
import re
from urllib.parse import urlsplit
from .settings import settings
UPLOAD=re.compile(r'/media/icons/[a-f0-9]{64}\.(?:png|svg)')
BUNDLED=re.compile(r'/static/(?:gatearr-logo\.png|branding-variants/gatearr-(?:electric-lime|neon-rose)\.png|services/(?:emby|jellyfin|seerr|radarr|sonarr|bazarr|tracearr|tdarr)\.png)')
def local_path(value,db=None):
    if not isinstance(value,str) or not value or any(c in value for c in '\r\n'):return None
    parsed=urlsplit(value)
    if parsed.query or parsed.fragment or parsed.username or parsed.password:return None
    if parsed.scheme or parsed.netloc:
        from .security import origin
        from .mailer import config
        public=settings.public_url
        if db is not None:public=config(db,'public_url',public)
        else:
            from .db import SessionLocal
            from sqlalchemy.exc import SQLAlchemyError
            try:
                with SessionLocal() as session:public=config(session,'public_url',public)
            except SQLAlchemyError:pass
        if origin(parsed.scheme+'://'+parsed.netloc)!=origin(public):return None
    path=parsed.path
    return path if UPLOAD.fullmatch(path) or BUNDLED.fullmatch(path) else None

def require_image(value,db=None,optional=False):
    if not value and optional:return ''
    path=local_path(value,db)
    if not path:raise ValueError('Upload a PNG/SVG image instead of using an image URL')
    if db is not None and UPLOAD.fullmatch(path):
        from .models import IconAsset
        if not db.get(IconAsset,path.split('/')[-1].split('.')[0]):raise ValueError('Image not found')
    return path
