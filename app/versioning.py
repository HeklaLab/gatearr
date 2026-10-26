"""Bounded, cached release checks. No GitHub credentials or user data are sent."""
import json, logging, re, time
import httpx
from fastapi import APIRouter, Request, Depends
from .db import SessionLocal
from .mailer import config
from .release import VERSION, BUILD_REVISION, CHANGELOG
from .main import form, require_admin, render, redirect, limit, set_config
router = APIRouter()
log = logging.getLogger('gatearr.updates')
API = 'https://api.github.com/repos/HeklaLab/gatearr'
RELEASES = 'https://github.com/HeklaLab/gatearr/releases'
INTERVAL = 6 * 3600

def number(value):
    match = re.fullmatch(r'v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', value)
    if not match: raise ValueError('Invalid release version')
    return tuple(map(int, match.groups()))

def status(db):
    try: result = json.loads(config(db, 'release_check', '{}'))
    except (ValueError, TypeError): result = {}
    if not isinstance(result,dict):result={}
    result.setdefault('state', 'unchecked')
    # Availability belongs to this installed version, not the process that cached it.
    try:
        remote=number(result.get('version',''))
        result['available']=remote>number(VERSION)
        result['url']=RELEASES+'/tag/v'+result['version'].lstrip('v')
    except (ValueError,TypeError):result['available']=False
    result['enabled'] = config(db, 'release_checks_enabled', 'true') == 'true'
    return result

def read_json(client, path):
    with client.stream('GET', API + path) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > 131072: raise ValueError('Oversized release response')
    return json.loads(content)

def check(db, force=False):
    previous = status(db); now = int(time.time())
    delay = 3600 if previous['state'] == 'error' else INTERVAL
    if not force and (not previous['enabled'] or (previous.get('checked_version')==VERSION and now - previous.get('checked_at', 0) < delay)): return previous
    try:
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False, headers={'Accept':'application/vnd.github+json', 'User-Agent':'Gatearr/'+VERSION}) as client:
            release = read_json(client, '/releases/latest'); tag = release['tag_name']; remote = number(tag)
            if release.get('draft') or release.get('prerelease'): raise ValueError('Not a stable release')
            available = remote > number(VERSION)
            result = {'state':'success', 'available':available, 'checked_at':now, 'checked_version':VERSION, 'version':tag.lstrip('v'), 'url':RELEASES+'/tag/'+tag}
        log.info('Release check complete update_available=%s', available)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        result = {**previous, 'state':'error', 'checked_at':now, 'checked_version':VERSION}
        log.warning('GitHub release check failed; retrying later')
    result.pop('enabled', None); set_config(db, 'release_check', json.dumps(result)); db.commit()
    return status(db)

def refresh_due():
    with SessionLocal() as db:
        if config(db, 'setup_complete'): check(db)

@router.get('/admin/updates')
def updates(request: Request):
    require_admin(request)
    from .release_history import grouped
    return render(request, 'updates.html', release_status=status(request.state.db), release_series=grouped(CHANGELOG, VERSION))

@router.post('/admin/updates/check')
def refresh(request: Request, data=Depends(form)):
    require_admin(request); limit(request, 'release-check', maximum=5, window=600)
    check(request.state.db, force=True)
    return redirect('/admin/updates')

@router.post('/admin/updates/settings')
def preferences(request: Request, data=Depends(form)):
    require_admin(request)
    set_config(request.state.db, 'release_checks_enabled', 'true' if data.get('enabled') == 'on' else 'false'); request.state.db.commit()
    return redirect('/admin/updates')
