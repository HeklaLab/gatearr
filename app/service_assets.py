"""Bundled upstream logos; custom images and explicit icon selections win."""
from pathlib import Path
from .models import AccessService
KEYS=('emby','jellyfin','seerr','radarr','sonarr','bazarr')
def default_icon(key,media='emby'):
    key=str(key).strip().casefold()
    if key=='emby':key=media
    return '/static/services/'+key+'.png' if key in KEYS else ''
def service_icon(db,key,media='emby'):
    row=db.get(AccessService,key)
    if row and row.icon_url:return row.icon_url
    return default_icon(key,media) if not row or row.icon in ('link','gears') else ''
