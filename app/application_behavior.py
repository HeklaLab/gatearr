"""Per-card destinations; connection credentials and permission checks stay shared."""
import re
from urllib.parse import urlsplit, urlunsplit

TOOLS = ('radarr', 'sonarr', 'bazarr', 'tracearr', 'tdarr')
KEY = re.compile(r'(?:access:[a-z0-9_-]{1,80}|menu:[0-9]+|radarr|sonarr|bazarr|tracearr|tdarr)')


def validate(settings):
    from .security import url_ok
    if not isinstance(settings, dict) or len(settings) > 100:
        raise ValueError('Invalid application behavior')
    for key, value in settings.items():
        if not KEY.fullmatch(key) or not isinstance(value, dict) or set(value) - {'mode', 'url', 'new_tab'}:
            raise ValueError('Invalid application behavior')
        modes = ('direct','embedded','guide') if key=='tracearr' else ('direct','embedded') if key in TOOLS else ('direct','guide')
        if value.get('mode') not in modes or type(value.get('new_tab', False)) is not bool:
            raise ValueError('Invalid application behavior')
        url = value.get('url', '')
        if not isinstance(url, str) or len(url) > 2000:
            raise ValueError('Invalid application URL')
        url_ok(url, optional=True)


def describe(db, app):
    """Admin catalog metadata; never derive a browser address from a private API URL."""
    from .models import AccessService
    from .mailer import config
    key = app['key']
    if key == 'account':
        return app
    if key in TOOLS:
        from .connection_health import configured
        ready = configured(db, key) and (key not in ('tracearr', 'tdarr') or config(db, key + '_interface_enabled', 'true') == 'true')
        app.update(opening_modes=(['embedded','direct'] if ready else ['direct']), default_mode='embedded' if ready else 'direct', direct_url=config(db, key + '_public_url'), integration_configured=ready)
    else:
        service = db.get(AccessService, app['howto']) if app.get('howto') else None
        direct = service.browser_url if service else app['href']
        if service and service.key == 'seerr' and not direct:
            from .seerr_login import public_url
            direct = public_url(db)
        app.update(opening_modes=['direct', 'guide'] if service else ['direct'], default_mode='guide' if service and service.entry_mode == 'structured' else 'direct', direct_url=direct)
    return app


def freeze(layout, apps):
    """Initialize new selections without sharing the behavior dict between rows."""
    for block in layout['blocks']:
        if block['kind'] != 'applications':
            continue
        settings = block.setdefault('application_behaviors', {})
        for key in block.get('applications', []):
            app = apps.get(key)
            if key != 'account' and app and key not in settings:
                settings[key] = {'mode': app['default_mode']}
    return layout


def guide_href(db, key):
    import json
    from .models import Guide
    from .mailer import config
    root = json.loads(config(db, 'howto_root_published_' + key, '{}'))
    guide = db.get(Guide, root.get('guide_id', 0)) if root.get('mode') == 'guide' else None
    if guide and guide.service_key == key and guide.published:
        return '/access/' + key + '/guide/' + str(guide.id)
    from .models import AccessService
    service = db.get(AccessService, key)
    return '/access/' + key + ('?view=guide' if service and service.entry_mode == 'direct' else '')


def destination(db, app, behavior, publishing=False):
    if app['key'] == 'account':
        return dict(app)
    value = behavior or {'mode': app['default_mode']}
    mode = value['mode']
    # Legacy embedded cards stay dormant if their integration is removed.
    # They must never silently become external links or grant proxy access.
    if app['key']=='tracearr' and mode=='guide' and not app.get('can_embed',True):return dict(app,href='')
    if mode == 'embedded' and app['key'] in TOOLS and (not app.get('integration_configured') or not app.get('can_embed', True)):
        return dict(app, href='')
    if mode not in app['opening_modes']:
        raise ValueError('Invalid application behavior')
    result = dict(app)
    if mode == 'embedded':
        href = '/tools/' + app['key']
    elif mode == 'guide':
        href = guide_href(db, app['howto'])
    else:
        public = value.get('url') or app.get('direct_url', '')
        if publishing and not public and app['key'] not in ('access:emby','access:seerr'):
            raise ValueError('Configure the public interface URL for direct links')
        # Preserve native session handoff only for the configured public address.
        # A card-specific URL never receives a media token.
        href = public
        if public and not value.get('url') and app.get('howto') in ('emby', 'seerr'):
            from .models import AccessService
            from .guides import service_url
            service = db.get(AccessService, app['howto'])
            if service:
                href = service_url(db, service)
    result.update(href=href, external=value.get('new_tab', mode == 'direct' and app.get('external', False)))
    return result


def media_browser_page(base):
    """Append the WebUI path without changing scheme, host, explicit port or route."""
    parsed = urlsplit(base)
    path = parsed.path.rstrip('/')
    if not path.endswith('/web/index.html'):
        path += '/index.html' if path.endswith('/web') else '/web/index.html'
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
