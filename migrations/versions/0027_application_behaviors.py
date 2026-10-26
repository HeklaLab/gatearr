"""Freeze existing application destinations before introducing per-card behavior."""
from alembic import op
import sqlalchemy as sa
import json
from copy import deepcopy

revision = '0027'
down_revision = '0026'
branch_labels = depends_on = None
TOOLS = ('radarr', 'sonarr', 'bazarr', 'tracearr', 'tdarr')


def upgrade():
    db = op.get_bind()
    services = dict(db.execute(sa.text('SELECT key, entry_mode FROM access_services')).all())
    menus = list(db.execute(sa.text('SELECT id, label, url, access_service, new_tab FROM menu_items ORDER BY position, id')).mappings())
    defaults = {'access:' + key: {'mode': 'guide' if mode == 'structured' else 'direct'} for key, mode in services.items() if key not in TOOLS}
    defaults.update({key: {'mode': 'embedded'} for key in TOOLS})
    for row in menus:
        defaults['menu:' + str(row['id'])] = deepcopy(defaults.get('access:' + str(row['access_service']), {'mode': 'direct'}))
    # Preserve the old name-based destination only in already-saved snapshots.
    # New native cards never consult an unrelated custom link's label.
    for key in ('emby', 'seerr'):
        if any(row['access_service'] == key for row in menus):
            continue
        alias = next((row for row in menus if not row['access_service'] and row['label'].casefold() == key), None)
        if alias and alias['url']:
            defaults['access:' + key] = {'mode': 'direct', 'url': alias['url'], 'new_tab': bool(alias['new_tab'])}
    changed = False
    for key, raw in db.execute(sa.text("SELECT key, value FROM config WHERE key IN ('portal_draft','portal_published')")).all():
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(value, dict) or not isinstance(value.get('blocks'), list):
            continue
        touched = False
        for block in value['blocks']:
            if not isinstance(block, dict):
                continue
            kind = block.get('kind')
            if kind == 'applications':
                keys = block.get('applications', [])
            elif kind == 'services':
                keys = list(defaults)
            elif kind == 'application':
                service = block.get('service_key', 'emby')
                keys = [service if service in TOOLS else 'access:' + service]
            else:
                continue
            behavior = block.setdefault('application_behaviors', {})
            for app in keys:
                if app in defaults and app not in behavior:
                    behavior[app] = deepcopy(defaults[app])
                    touched = True
        if touched:
            db.execute(sa.text('UPDATE config SET value=:value WHERE key=:key'), {'key': key, 'value': json.dumps(value, ensure_ascii=False)})
            changed = True
    if changed:
        # Stale browser editors must reload instead of overwriting the migration.
        db.execute(sa.text("UPDATE config SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE key='portal_version'"))


def downgrade():
    # Retain saved choices so a downgrade/upgrade cycle does not discard them.
    pass
