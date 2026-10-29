from app.db import SessionLocal
from app import visual_builder
from test_portal import setup,logout
from test_visual_studio import design


def test_system_page_directory_and_published_previews(client):
    setup(client)
    page=client.get('/admin/system-pages')
    assert page.status_code==200
    for key,title,icon,href in visual_builder.SYSTEM_PAGE_DIRECTORY:
        assert f'/admin/design/{key}' in page.text
        assert f'<code>{href}</code>' in page.text
        assert client.get(f'/admin/system-pages/{key}/preview').status_code==200
        editor=client.get(f'/admin/design/{key}').text
        assert 'system-page-tabs' not in editor
        assert 'href="/admin/system-pages"' in editor
    with SessionLocal() as db:layout=visual_builder.load(db,'reset',True)
    layout['blocks'].append(dict(id='draft-only',kind='text',region='main',span=12,order=100,title='Unpublished secret heading',body=''))
    assert design(client,'reset','save',layout).status_code==200
    assert 'Unpublished changes' in client.get('/admin/system-pages').text
    assert 'Unpublished secret heading' not in client.get('/admin/system-pages/reset/preview').text
    assert client.get('/admin/system-pages/invalid/preview').status_code==404
    logout(client)
    for path in ('/admin/system-pages','/admin/system-pages/reset/preview'):
        assert client.get(path,follow_redirects=False).status_code in (303,401,403)
