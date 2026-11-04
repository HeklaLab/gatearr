"""Editable dark palette; generated CSS accepts only validated colors/numbers."""
import json,re
from copy import deepcopy
from fastapi import APIRouter,Request,Depends,HTTPException
from fastapi.responses import Response
from . import portal
from .mailer import config
router=APIRouter()
DARK={'accent':'#159eff','button_hover':'#45cdf4','bg':'#05070d','surface':'#0b101b','text':'#e7f2ff','muted':'#a7bbd9','ink':'#051c40'}
LIGHT={'accent':'#079df5','button_hover':'#37c6e8','bg':'#f4f7fb','surface':'#ffffff','text':'#0b1425','muted':'#536580','ink':'#031426'}
def palette(colors):return {**colors,'gradient_start':colors['bg'],'gradient_end':colors['bg'],'angle':135,'gradient':False}
PRESETS={'boreal':{'name':'Blue Boréal','dark':palette(DARK),'light':palette(LIGHT)},
'electric-lime':{'name':'Electric Lime','dark':palette({**DARK,'accent':'#c5f52c','button_hover':'#d4ff5e','bg':'#0d1311','surface':'#171e1a','text':'#f0f5f1','muted':'#abb9ae','ink':'#172000'}),'light':palette({**LIGHT,'accent':'#c5f52c','button_hover':'#d4ff5e','bg':'#f6f8f3','text':'#111c15','muted':'#526354','ink':'#172000'})},
'neon-rose':{'name':'Neon Rose','dark':palette({**DARK,'accent':'#fb65c5','button_hover':'#ff9bda','bg':'#151216','surface':'#211c24','text':'#f7eff9','muted':'#c0b2c7','ink':'#2e0522'}),'light':palette({**LIGHT,'accent':'#f331af','button_hover':'#fa83cd','bg':'#fbf7fa','text':'#241623','muted':'#715c70','ink':'#290320'})}}
# Additional visual presets for the theme preview demo.
def themed(name, dark, light):
    return {'name':name, 'dark':palette({**DARK, **dark}), 'light':palette({**LIGHT, **light})}
PRESETS.update({
 'pumpkin-glow':themed('Pumpkin Glow', {'accent':'#ff8a00','button_hover':'#ffb13b','bg':'#211008','surface':'#32190f','text':'#fff4e4','muted':'#e5c3a6','ink':'#301200'}, {'accent':'#bc4800','button_hover':'#aa4500','bg':'#fff6e9','surface':'#fffaf2','text':'#31190c','muted':'#795a45','ink':'#ffffff'}),
 'mocha-latte':themed('Mocha Latte', {'accent':'#d9a17c','button_hover':'#edc2a4','bg':'#100705','surface':'#21100b','text':'#fff2e9','muted':'#d2b4a4','ink':'#28140e'}, {'accent':'#69351e','button_hover':'#884a2b','bg':'#f6e8dc','surface':'#fff8f2','text':'#2f1912','muted':'#795d50','ink':'#ffffff'}),
 'electric-terminal':themed('Electric Terminal', {'accent':'#ffe500','button_hover':'#fff266','bg':'#0c0c08','surface':'#1b1b13','text':'#fffef2','muted':'#c9c7ae','ink':'#161400'}, {'accent':'#796800','button_hover':'#665900','bg':'#fffdf0','surface':'#ffffff','text':'#18170d','muted':'#625f4c','ink':'#ffffff'}),
 'graphite-shades':themed('Graphite Shades', {'accent':'#c5cad2','button_hover':'#e2e5e9','bg':'#101114','surface':'#1c1e23','text':'#f2f3f5','muted':'#adb2bb','ink':'#17191c'}, {'accent':'#505761','button_hover':'#626a76','bg':'#f0f1f3','surface':'#ffffff','text':'#202329','muted':'#626a76','ink':'#ffffff'}),
 'purple-haze':themed('Purple Haze', {'accent':'#c879ff','button_hover':'#e0abff','bg':'#160a20','surface':'#281535','text':'#faf0ff','muted':'#d0b5df','ink':'#260c39'}, {'accent':'#7e25c1','button_hover':'#8939be','bg':'#f8f0ff','surface':'#fffaff','text':'#291334','muted':'#795c88','ink':'#ffffff'}),
 'bloody-mary':themed('Bloody Mary', {'accent':'#ff554b','button_hover':'#ff7070','bg':'#200909','surface':'#190808','text':'#fff0f2','muted':'#dfb2ba','ink':'#350611'}, {'accent':'#b51419','button_hover':'#dc3436','bg':'#fff3f3','surface':'#fffbfb','text':'#35151b','muted':'#806068','ink':'#ffffff'})
})
for _key in ('pumpkin-glow','mocha-latte','electric-terminal','graphite-shades','purple-haze','bloody-mary'):
    for _mode in ('dark','light'):
        _p=PRESETS[_key][_mode]
        _p.update(gradient=True, gradient_start=_p['bg'], gradient_end=_p['surface'])
PRESETS['boreal']['dark'].update(gradient=True,gradient_start='#0a1222',gradient_end='#04060b')
LOGOS={'boreal':'/static/gatearr-logo.png',
       'electric-lime':'/static/branding-variants/gatearr-electric-lime.png',
       'neon-rose':'/static/branding-variants/gatearr-neon-rose.png',
       'pumpkin-glow':'/static/branding-variants/gatearr-pumpkin-glow.png',
       'mocha-latte':'/static/branding-variants/gatearr-mocha-latte.png',
       'electric-terminal':'/static/branding-variants/gatearr-electric-terminal.png',
       'graphite-shades':'/static/branding-variants/gatearr-graphite-shades.png',
       'purple-haze':'/static/branding-variants/gatearr-purple-haze.png',
       'bloody-mary':'/static/branding-variants/gatearr-bloody-mary.png'}
def logo_url(preset):
    return LOGOS.get(preset,LOGOS['boreal'])

def load(db,draft=False):
    raw=config(db,'themes_draft' if draft else 'themes_published')
    old=json.loads(raw) if raw else {}
    legacy=portal.load(db,draft)['theme']
    dark=old.get('dark',legacy if legacy!=portal.DEFAULT['theme'] else {})
    return {'mode':old.get('mode','dark'),'preset':old.get('preset','boreal'),'dark':{**PRESETS['boreal']['dark'],**dark},'light':{**LIGHT,**PRESETS['boreal']['light'],**old.get('light',{})}}
def validate(value):
    if value.get('mode') not in ('dark','light','user') or value.get('preset','boreal') not in PRESETS:raise ValueError('Invalid theme')
    for name in ('dark','light'):
        p=value[name]
        for key in (*portal.DEFAULT['theme'],'gradient_start','gradient_end'):
            if not re.fullmatch(r'#[a-fA-F0-9]{6}',p[key]):raise ValueError('Invalid color: use #RRGGBB')
        if type(p['angle']) is not int or not 0<=p['angle']<=360 or type(p['gradient']) is not bool:raise ValueError('Invalid gradient')
    return value

def landscape_svg(bg,accent,end,mode,angle=135):
    """Procedural, blurred artwork derived only from validated palette colors."""
    def rgb(value):return tuple(int(value[i:i+2],16) for i in (0,2,4))
    base=rgb(bg);color=rgb(accent);light=mode=='light'
    linear=[(v/255)/12.92 if v/255<=.04045 else ((v/255+.055)/1.055)**2.4 for v in color]
    luminance=sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))
    strength=min(1,.28/max(luminance,.01))
    def mixed(weight):return '#'+''.join(f'{round(a*weight+b*(1-weight)):02x}' for a,b in zip(color,base))
    layers=''.join(f'<path d="M-100 {760+i*80} C160 {450+i*140} 300 {910+i*70} 580 {640+i*100} C820 {420+i*160} 1040 {820+i*55} 1300 {470+i*145} V1200 H-100Z" fill="{mixed(w)}"/>' for i,w in enumerate((.10,.07,.04) if light else (.15,.09,.04)))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1100" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="base" x2="1" y2="1" gradientTransform="rotate({angle-135} .5 .5)"><stop stop-color="#{bg}"/><stop offset="1" stop-color="#{end}"/></linearGradient><radialGradient id="glow" cx=".78" cy=".12" r=".8"><stop stop-color="#{accent}" stop-opacity="{.16 if light else .35*strength}"/><stop offset="1" stop-color="#{accent}" stop-opacity="0"/></radialGradient><filter id="soft"><feGaussianBlur stdDeviation="18"/></filter><filter id="ribbon"><feGaussianBlur stdDeviation="48"/></filter></defs><rect width="1200" height="1100" fill="url(#base)"/><g filter="url(#soft)"><rect width="1200" height="1100" fill="url(#glow)"/>{layers}</g><path d="M-120 790 C170 330 620 850 1320 420" fill="none" stroke="#{accent}" stroke-opacity="{.10 if light else .16*strength}" stroke-width="100" filter="url(#ribbon)"/></svg>'''

@router.get('/theme-landscape.svg',include_in_schema=False)
def landscape(bg:str,accent:str,end:str,mode:str,angle:int=135):
    if not 0<=angle<=360 or mode not in ('light','dark') or any(not re.fullmatch('[0-9a-fA-F]{6}',v) for v in (bg,accent,end)):
        raise HTTPException(422,'Invalid landscape palette')
    return Response(landscape_svg(bg,accent,end,mode,angle),media_type='image/svg+xml')

def remember_appearance(request,response,user):
    """Keep only the last appearance choice on this browser, never an identity."""
    if user and not getattr(request.state,'support',None) and load(request.state.db)['mode']=='user':
        choice=getattr(user,'theme_preference','auto') or 'auto'
        if choice in ('light','dark','auto'):
            response.set_cookie('gatearr_appearance',choice,max_age=31536000,httponly=True,secure=request.state.cookie_secure,samesite='lax',path='/')
    return response

def css(db,user=None,draft=False):
    value=validate(load(db,draft));mode=value['mode']
    if mode=='user':mode=getattr(user,'theme_preference','auto') or 'auto'
    def rules(name):
        p=value[name];colors=''.join('--'+key+':'+p[key]+';' for key in portal.DEFAULT['theme'])
        bg='linear-gradient('+str(p['angle'])+'deg,'+p['gradient_start']+','+p['gradient_end']+')' if p['gradient'] else p['bg']
        logo='brightness(0) invert(1)' if name=='dark' else 'brightness(0)'
        landscape_url='/theme-landscape.svg?bg='+(p['gradient_start'] if p['gradient'] else p['bg'])[1:]+'&accent='+p['accent'][1:]+'&end='+(p['gradient_end'] if p['gradient'] else p['bg'])[1:]+'&mode='+name+'&angle='+str(p['angle'])
        return ':root{'+colors+'--landscape-image:url("'+landscape_url+'");--default-brand-logo:url("'+logo_url(value['preset'])+'");--logo-filter:'+logo+';--custom-logo-dark-display:'+('block' if name=='dark' else 'none')+';--custom-logo-light-display:'+('block' if name=='light' else 'none')+';color-scheme:'+name+';}body{background:'+bg+';}'
    return rules(mode) if mode in ('light','dark') else rules('light')+'@media(prefers-color-scheme:dark){'+rules('dark')+'}'

@router.get('/admin/branding/themes')
def editor(request:Request):
    from .main import require_admin,render
    require_admin(request)
    return render(request,'themes.html',themes=load(request.state.db,True),theme_version=int(config(request.state.db,'themes_version','0')),presets=PRESETS,has_previous=bool(config(request.state.db,'themes_previous')))

@router.post('/admin/branding/themes')
def save(request:Request,data=Depends(__import__('app.main',fromlist=['form']).form)):
    from .main import require_admin,redirect,set_config
    from .models import Config
    from sqlalchemy import update
    from sqlalchemy.dialects.sqlite import insert
    from fastapi import HTTPException
    require_admin(request);db=request.state.db;v=load(db,True)
    v['mode']=str(data.get('mode',v['mode']))
    if data.get('preset'):
        if data['preset'] not in PRESETS:raise ValueError('Invalid theme')
        set_config(db,'themes_previous',json.dumps(v))
        p=PRESETS[data['preset']];v.update(preset=data['preset'],dark=deepcopy(p['dark']),light=deepcopy(p['light']))
    if data.get('action')=='undo' and config(db,'themes_previous'):
        v=validate(json.loads(config(db,'themes_previous')))
    name=data.get('palette')
    if name:
        if name not in ('dark','light'):raise ValueError('Invalid theme')
        v[name]={**{k:str(data.get(k,v[name].get(k,''))) for k in (*portal.DEFAULT['theme'],'gradient_start','gradient_end')},'angle':int(data.get('angle','135')),'gradient':data.get('gradient')=='on'}
    validate(v)
    db.execute(insert(Config).values(key='themes_version',value='0').on_conflict_do_nothing())
    result=db.execute(update(Config).where(Config.key=='themes_version',Config.value==str(data.get('version','-1'))).values(value=str(int(data['version'])+1)))
    if result.rowcount!=1:db.rollback();raise HTTPException(409,'Themes changed. Reload this page.')
    set_config(db,'themes_draft',json.dumps(v))
    if data.get('action')=='publish':set_config(db,'themes_published',json.dumps(v))
    db.commit();return redirect('/admin/branding/themes')

@router.post('/account/theme')
def preference(request:Request,data=Depends(__import__('app.main',fromlist=['form']).form)):
    from .main import redirect
    user=request.state.user
    if load(request.state.db)['mode']!='user' or data.get('theme') not in ('light','dark','auto'):raise ValueError('Theme is managed by the administrator')
    if user:
        user.theme_preference=data['theme'];request.state.db.commit()
    fallback='/account' if user else '/login'
    response=redirect(data.get('next',fallback) if str(data.get('next','')).startswith('/') and not str(data.get('next','')).startswith('//') else fallback)
    if user:return remember_appearance(request,response,user)
    response.set_cookie('gatearr_appearance',data['theme'],max_age=31536000,httponly=True,secure=request.state.cookie_secure,samesite='lax',path='/')
    return response
