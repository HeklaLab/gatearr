"""Contrast regressions for the six shipped theme variants and tinted controls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import pytest
from app.themes import PRESETS
from app import main
from app.db import SessionLocal
from test_portal import post
from test_permissions_bridge import policy_api


def rgb(color):
    return tuple(int(color[index:index+2],16) for index in (1,3,5))


def mix(first,second,weight):
    return tuple(round(a*weight+b*(1-weight)) for a,b in zip(first,second))


def luminance(color):
    channels=[value/255 for value in color]
    linear=[value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4 for value in channels]
    return sum(value*weight for value,weight in zip(linear,(.2126,.7152,.0722)))


def contrast(first,second):
    low,high=sorted((luminance(first),luminance(second)))
    return (high+.05)/(low+.05)


@pytest.mark.parametrize('preset',PRESETS)
@pytest.mark.parametrize('mode',['light','dark'])
def test_shipped_theme_foregrounds_are_readable(preset,mode):
    palette=PRESETS[preset][mode]
    stylesheet=(Path(__file__).parents[1]/'app/static/v040.css').read_text()
    weight=int(re.search(r'--accent-label:light-dark\(color-mix\(in srgb,var\(--accent\) (\d+)%',stylesheet)[1])/100
    colors={key:rgb(value) for key,value in palette.items() if isinstance(value,str) and value.startswith('#')}
    label=mix(colors['accent'],colors['text'],weight) if mode=='light' else colors['accent']
    # Includes active capsules, side navigation, avatar initials and selected options.
    surfaces=[colors['surface'],colors['bg'],*([colors['gradient_start'],colors['gradient_end']] if palette['gradient'] else []),*[mix(colors['accent'],colors['surface'],alpha) for alpha in (.10,.12,.15,.18)]]
    for surface in surfaces:
        assert contrast(label,surface)>=4.5,(preset,mode,label,surface)
        assert contrast(colors['text'],surface)>=4.5
    for surface in (colors['surface'],colors['bg']):
        assert contrast(colors['muted'],surface)>=4.5
    for fill in ('accent','button_hover'):
        assert contrast(colors['ink'],colors[fill])>=4.5


@pytest.mark.skipif(not os.getenv('GATEARR_THEME_REVIEW'),reason='Browser review export only')
def test_export_real_pages_for_browser_review(client,policy_api,monkeypatch):
    target=Path(os.environ['GATEARR_THEME_REVIEW']);target.mkdir(parents=True,exist_ok=True)
    group=post(client,'/admin/groups',{'name':'Famille'},'/admin/groups').headers['location']
    from app.models import MailDelivery,MenuItem
    with SessionLocal() as db:
        db.add(MenuItem(label='Sonarr',url='https://sonarr.example.test',position=100,menu_key='main',new_tab=True))
        db.add(MenuItem(label='Additional media tools',url='https://media.example.test/applications',position=110,menu_key='main',new_tab=True))
        db.add_all([MailDelivery(at=1792960000,recipient='alex@example.com',subject='Gatearr — Verify your email',purpose='verify',context='transactional',state='accepted',error=''),MailDelivery(at=1792960001,recipient='emma@example.com',subject='Gatearr — SMTP test',purpose='verify',context='smtp_test',state='failed',error='connection')]);db.commit()
    from contextlib import contextmanager
    from app import bazarr_subtitles as subtitles
    from app.security import encrypt
    import httpx
    native_profile={'profileId':1,'name':'Shared subtitles','cutoff':None,'items':[{'id':1,'language':'en','forced':'False','hi':'False'}],'mustContain':[],'mustNotContain':[],'originalFormat':0,'tag':None}
    def subtitle_api(request):
        return httpx.Response(200,json=[native_profile] if request.url.path.endswith('/profiles') else [{'code2':'en','name':'English','enabled':True},{'code2':'fr','name':'French','enabled':False}])
    @contextmanager
    def subtitle_connection(db):
        with httpx.Client(base_url='http://bazarr.test/',transport=httpx.MockTransport(subtitle_api)) as remote:yield remote
    monkeypatch.setattr(subtitles,'connection',subtitle_connection)
    with SessionLocal() as db:
        for key,value in {'bazarr_enabled':'true','bazarr_url':'http://bazarr.test','bazarr_api_key':encrypt('review-only'),'bazarr_subtitles_profile':'1','bazarr_subtitles_profile_name':'Shared subtitles','bazarr_subtitles_enabled':'true'}.items():main.set_config(db,key,value)
        main.set_config(db,'bazarr_subtitles_connection',subtitles.connection_id(db))
        from app.models import User
        for user in db.query(User):
            user.bazarr_subtitles=True;user.bazarr_subtitle_languages='["en"]'
        db.commit()
    scenes={}
    for preset in PRESETS:
        for mode in ('light','dark'):
            case=preset+'-'+mode
            with SessionLocal() as db:
                theme={'preset':preset,'mode':mode,**{key:deepcopy(PRESETS[preset][key]) for key in ('dark','light')}}
                for key in ('themes_published','themes_draft'):main.set_config(db,key,json.dumps(theme))
                db.commit()
            stylesheet=client.get('/theme.css').text
            scene=re.search(r'--landscape-image:url\("([^"]+)"\)',stylesheet)[1]
            scenes[scene]=case+'.svg'
            response=client.get(scene);assert response.status_code==200
            (target/(case+'.svg')).write_text(response.text)
            (target/(case+'.css')).write_text(stylesheet.replace(scene,'/'+case+'.svg'))
            for name,path in [('updates','/admin/updates'),('users','/admin/users'),('account','/admin/users/1'),('group',group),('admin','/admin'),('mail-log','/admin/activity/mail'),('bazarr','/admin/integrations'),('subtitle-account','/account'),('subtitle-locked','/account'),('subtitle-permanent','/account'),('home','/home'),('themes','/admin/branding/themes'),('integrations','/admin/integrations'),('mail','/admin/mail-editor'),('builder','/admin/portal'),('guides','/admin/design/home/howto/emby'),('translations','/admin/translations')]:
                with SessionLocal() as db:
                    main.set_config(db,'bazarr_subtitle_lock_mode','days' if name in ('subtitle-locked','bazarr') else 'permanent' if name=='subtitle-permanent' else 'free');db.commit()
                response=client.get(path);assert response.status_code==200
                page=response.text.replace('href="/theme.css','href="/'+case+'.css')
                (target/(case+'-'+name+'.html')).write_text(page)
                if name=='guides':
                    boot=json.loads(re.search(r'<script id="howto-data" type="application/json">(.*?)</script>',page,re.S)[1])
                    payload={'nodes':boot['nodes'],'mode':boot.get('root',{}).get('mode','choices'),'guide_id':boot.get('root',{}).get('guide_id',0),'browser_url':boot.get('root',{}).get('browser_url',''),'parent':''}
                    preview=post(client,'/admin/visual-howto/emby/preview',{'payload':json.dumps(payload)},'/admin/design/home/howto/emby')
                    assert preview.status_code==200
                    (target/(case+'-guides-preview.html')).write_text(preview.text.replace('href="/theme.css','href="/'+case+'.css'))
            from app.visual_builder import load
            with SessionLocal() as db:layout=load(db,'home',True)
            preview=post(client,'/admin/design/home/preview',{'payload':json.dumps(layout)},'/admin/design/home')
            assert preview.status_code==200
            (target/(case+'-preview.html')).write_text(preview.text.replace('href="/theme.css','href="/'+case+'.css'))
            layout['show_header']=False
            layout['blocks']=[{'id':'applications-preview','kind':'applications','region':'main','span':12,'order':10,'columns':2,'applications':['access:emby','access:seerr'],'information':{'access:emby':{'enabled':True,'metrics':['movies','series'],'count_mode':'promotion','round_to':100},'access:seerr':{'enabled':True,'metrics':['movies_left','series_left']}}}]
            response=post(client,'/admin/design/home/preview',{'payload':json.dumps(layout)},'/admin/design/home')
            assert response.status_code==200
            (target/(case+'-widgets.html')).write_text(response.text.replace('href="/theme.css','href="/'+case+'.css'))

    (target/'landscapes.json').write_text(json.dumps(scenes))

def test_landscape_is_local_validated_svg(client):
    response=client.get('/theme-landscape.svg?bg=05070d&accent=159eff&end=04060b&mode=dark')
    assert response.status_code==200
    assert response.headers['content-type'].startswith('image/svg+xml')
    import xml.etree.ElementTree as ET
    root=ET.fromstring(response.text)
    assert root.tag=='{http://www.w3.org/2000/svg}svg'
    assert 'feGaussianBlur' in response.text
    assert not any(node.tag.endswith(('script','image','foreignObject')) for node in root.iter())
    for params in ({'bg':'<script>'},{'accent':'url(https://example.com)'},{'mode':'unexpected'},{'angle':361}):
        values={'bg':'05070d','accent':'159eff','end':'04060b','mode':'dark',**params}
        assert client.get('/theme-landscape.svg',params=values).status_code==422
