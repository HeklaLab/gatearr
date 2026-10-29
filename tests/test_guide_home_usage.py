from app.page_builder import guide_home_usage
from test_application_behavior import row,setup,state,write


def test_usage_tracks_all_cards_and_custom_identities():
    apps={'access:emby':{'howto':'emby','default_mode':'direct'},'menu:1':{'howto':'service-1','default_mode':'guide'}}
    layout={'blocks':[row('native','access:emby','direct'),row('custom','menu:1','guide')]}
    assert guide_home_usage(layout,apps)=={'emby':'direct','service-1':''}
    layout['blocks'].append(row('native-guide','access:emby','guide'))
    assert guide_home_usage(layout,apps)['emby']==''
    layout['blocks'][0]['applications']=[]
    layout['blocks'].pop()
    assert 'emby' not in guide_home_usage(layout,apps)


def test_usage_defaults_and_embedded_mode():
    apps={'tracearr':{'howto':'tracearr','default_mode':'embedded'}}
    block=row('stats','tracearr','embedded');block.pop('application_behaviors')
    assert guide_home_usage({'blocks':[block]},apps)=={'tracearr':'other'}


def test_page_index_separates_published_usage_and_draft(client):
    setup(client)
    layout,version=state();layout['blocks']=[row('seerr','access:seerr','direct')]
    result=write(client,layout,version);assert result.status_code==200
    page=client.get('/admin/pages').text
    assert 'Not used from Home' in page and 'Application cards use direct links.' in page
    layout['blocks'].append(row('seerr-guide','access:seerr','guide'))
    result=write(client,layout,result.json()['version'],'save');assert result.status_code==200
    page=client.get('/admin/pages').text
    assert 'Home draft' in page and 'An application card opens this guide.' in page
    assert write(client,layout,result.json()['version']).status_code==200
    page=client.get('/admin/pages').text
    seerr=page.split('<h3>Seerr access guides</h3>',1)[1].split('</article>',1)[0]
    assert 'page-guide-usage' not in seerr and 'page-guide-draft' not in seerr
