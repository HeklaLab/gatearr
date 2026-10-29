"""The interface skin must actually be CSS, not a misplaced HTML/Jinja template."""
from pathlib import Path


def test_interface_stylesheet_delivery_contains_skin_and_recent_blocks(client):
    response=client.get('/static/interface-v042.css')
    assert response.status_code==200
    assert response.headers['content-type'].startswith('text/css')
    css=response.text
    assert '{%' not in css and '{{' not in css and '<section' not in css
    assert len(css)>40000
    for selector in ('--glass-fill',':root','border-radius:999px','.page-menu.layout-pills','.page-accordion','.translation-search .translation-search-actions','.application-statistics-period','.portal-block.kind-title>.standalone-title'):
        assert selector in css,selector
