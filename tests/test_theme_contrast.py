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
def test_export_real_pages_for_browser_review(client,policy_api):
    target=Path(os.environ['GATEARR_THEME_REVIEW']);target.mkdir(parents=True,exist_ok=True)
    group=post(client,'/admin/groups',{'name':'Famille'},'/admin/groups').headers['location']
    for preset in PRESETS:
        for mode in ('light','dark'):
            case=preset+'-'+mode
            with SessionLocal() as db:
                theme={'preset':preset,'mode':mode,**{key:deepcopy(PRESETS[preset][key]) for key in ('dark','light')}}
                for key in ('themes_published','themes_draft'):main.set_config(db,key,json.dumps(theme))
                db.commit()
            (target/(case+'.css')).write_text(client.get('/theme.css').text)
            for name,path in [('users','/admin/users'),('account','/admin/users/1'),('group',group),('admin','/admin'),('home','/home'),('themes','/admin/branding/themes')]:
                response=client.get(path);assert response.status_code==200
                page=response.text.replace('href="/theme.css','href="/'+case+'.css')
                (target/(case+'-'+name+'.html')).write_text(page)
