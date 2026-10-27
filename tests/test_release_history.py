from app import versioning
from app.release_history import grouped
from app.release import CHANGELOG
from test_portal import setup


def test_history_cannot_reveal_future_or_unreleased_notes():
    entries = [
        {'version': '0.4.3', 'changes': ['Future fix'], 'features': [{'title': 'Future feature', 'text': 'Secret future feature'}]},
        {'version': '0.4.2', 'changes': ['Installed fix']},
        {'version': '0.4.1', 'date': 'Unreleased', 'changes': ['Unpublished fix']},
        {'version': '0.3.4', 'changes': ['Older fix']},
    ]
    history = grouped(entries, '0.4.2')
    assert [g['version'] for g in history] == ['0.4', '0.3']
    assert [p['version'] for g in history for p in g['patches']] == ['0.4.2', '0.3.4']
    assert 'Future' not in str(history) and 'Unpublished' not in str(history)


def test_features_keep_their_origin_and_do_not_leak_after_downgrade():
    entries = [
        {'version': '0.4.2', 'features': [{'title': 'Interface', 'text': 'New glass'}], 'fixes': ['Current fix']},
        {'version': '0.4.0', 'features': [{'title': 'Interface', 'text': 'New navigation'}], 'fixes': []},
    ]
    current = grouped(entries, '0.4.2')[0]
    assert len(current['features']) == 1
    assert [f['version'] for f in current['features'][0]['items']] == ['0.4.2', '0.4.0']
    older = grouped(entries, '0.4.0')[0]
    assert 'New glass' not in str(older)
    assert older['patches'][0]['current']


def test_shipped_history_classification_preserves_every_original_note():
    for entry in CHANGELOG:
        visible = {feature['text'] for feature in entry['features']} | set(entry['fixes'])
        assert set(entry['changes']) <= visible, entry['version']


def test_updates_future_notes_are_hidden_and_roadmap_link_is_available(client, monkeypatch):
    setup(client)
    monkeypatch.setattr(versioning, 'CHANGELOG', [
        {'version': '0.4.5', 'changes': ['Do not display this future fix']},
        {'version': '0.4.2', 'changes': ['Installed fix']},
    ])
    page = client.get('/admin/updates').text
    assert 'Do not display this future fix' not in page
    assert 'data-release-version="0.4.5"' not in page
    assert 'https://github.com/HeklaLab/gatearr/blob/main/ROADMAP.md' in page


def test_all_series_have_visible_features_and_unmodified_patch_fixes(client):
    setup(client)
    from html.parser import HTMLParser
    class Scan(HTMLParser):
        def __init__(self):
            super().__init__();self.stack=[];self.features=[];self.patches=[]
        def handle_starttag(self,tag,attrs):
            data=dict(attrs)
            if tag=='section' and data.get('class')=='release-feature':self.features.append(data)
            if tag=='details' and data.get('class')=='release-entry':self.patches.append(data.get('data-release-version'))
    page=client.get('/admin/updates').text
    scanner=Scan();scanner.feed(page)
    history=grouped(CHANGELOG,versioning.VERSION)
    assert len(scanner.features)==sum(len(series['features']) for series in history)
    assert all('open' not in row for row in scanner.features)
    assert scanner.patches==[patch['version'] for series in history for patch in series['patches']]
    for series in history:
        for patch in series['patches']:
            for fix in patch['fixes']:
                from html import escape
                assert escape(fix) in page


def test_empty_feature_categories_are_not_shown_and_future_content_remains_hidden():
    entries = [
        {'version':'0.4.4','features':[{'title':'Future only','text':'Later'}],'fixes':[]},
        {'version':'0.4.3','features':[{'title':'Empty','text':''},{'title':'Blank','text':'   '},{'title':'Valid','text':'New feature'}],'fixes':['Detailed fix']},
        {'version':'0.4.2','features':[],'fixes':['Another fix']},
    ]
    history=grouped(entries,'0.4.3')[0]
    assert [feature['title'] for feature in history['features']]==['Valid']
    assert [patch['fixes'] for patch in history['patches']]==[['Detailed fix'],['Another fix']]
