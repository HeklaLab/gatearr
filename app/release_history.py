"""Installed release history: shared highlights, followed by patch-specific fixes."""
import re

TITLES = {
    '0.5': 'Page builder',
    '0.4': 'Personalization and user experience',
    '0.3': 'Visual studio and administration',
    '0.2': 'Administration, assistance and integrations',
    '0.1': 'First public release',
}


def grouped(entries, installed):
    def version(value):
        match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', str(value))
        return tuple(map(int, match.groups())) if match else None

    ceiling = version(installed)
    unique = {}
    for entry in entries:
        current = version(entry.get('version'))
        if not current or not ceiling or current > ceiling:
            continue
        if entry.get('released') is False or str(entry.get('date', '')).lower() in ('unreleased', 'in preparation'):
            continue
        unique.setdefault(current, entry)
    groups = {}
    for current, entry in sorted(unique.items(), reverse=True):
        key = '.'.join(map(str, current[:2]))
        group = groups.setdefault(key, {'version': key, 'title': TITLES.get(key, 'Release history'), 'current': current[:2] == ceiling[:2], 'features': [], 'patches': []})
        features = entry.get('features')
        categories = entry.get('categories', {})
        if features is None:
            features = [{'title': category, 'text': change} for category, changes in categories.items() if category in ('New features', 'Improvements') for change in changes]
        for feature in features:
            if isinstance(feature, dict) and isinstance(feature.get('title'), str) and feature['title'].strip() and isinstance(feature.get('text'), str) and feature['text'].strip():
                group['features'].append({**feature, 'version': entry['version']})
        fixes = entry.get('fixes')
        if fixes is None:
            fixes = [change for category, changes in categories.items() if category not in ('New features', 'Improvements') for change in changes] if categories else entry.get('changes', [])
        group['patches'].append({**entry, 'fixes': fixes, 'current': current == ceiling})
    for group in groups.values():
        group['first'] = group['patches'][-1]['version']
        group['last'] = group['patches'][0]['version']
        # Merge repeated themes, retaining the release where each addition appeared.
        merged = {}
        for feature in group['features']:
            item = merged.setdefault(feature['title'], {'title': feature['title'], 'items': []})
            if not any(row['text'] == feature['text'] for row in item['items']):
                item['items'].append(feature)
        group['features'] = list(merged.values())
    result = list(groups.values())
    installed_date = unique.get(ceiling, {}).get('date') or ''
    archives = [entry for entry in entries if entry.get('archive') and re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(entry.get('date', ''))) and entry['date'] <= installed_date]
    if archives:
        result.append({'version': 'Before 0.1', 'title': 'The beginnings of Gatearr', 'current': False, 'first': min(entry['date'] for entry in archives), 'last': max(entry['date'] for entry in archives), 'patches': [], 'features': [{'title': feature['title'], 'items': [{'text': feature['text'], 'version': entry['date']}]} for entry in archives for feature in entry.get('features', []) if isinstance(feature, dict) and isinstance(feature.get('title'), str) and feature['title'].strip() and isinstance(feature.get('text'), str) and feature['text'].strip()]})
    return result
