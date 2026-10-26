import json
from app import portal
from app.db import SessionLocal
from test_portal import setup, post


def test_empty_image_saves_as_placeholder_but_is_not_published_as_broken_image(client):
    setup(client)
    with SessionLocal() as db:
        layout = portal.load(db, True)
        version = portal.version(db)
    layout['blocks'].append({'id': 'empty-image', 'kind': 'image', 'region': 'main', 'span': 12, 'order': 100, 'url': '', 'alt': ''})
    fields = {'version': version, 'payload': json.dumps(layout)}
    response = post(client, '/admin/design/home/save', fields, '/admin/design/home')
    assert response.status_code == 200
    fields['version'] = response.json()['version']
    preview = post(client, '/admin/design/home/preview', fields, '/admin/design/home')
    assert preview.status_code == 200 and 'image-block-placeholder' in preview.text
    assert 'class="portal-image" src=""' not in preview.text
    assert post(client, '/admin/design/home/publish', fields, '/admin/design/home').status_code == 200
    assert 'data-block-id="empty-image"' not in client.get('/home').text
    layout['blocks'][-1]['url'] = 'https://untrusted.example/image.png'
    fields.update(version=fields['version']+1, payload=json.dumps(layout))
    assert post(client, '/admin/design/home/save', fields, '/admin/design/home').status_code == 400
