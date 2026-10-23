"""Editable dark palette; generated CSS accepts only validated colors/numbers."""
import json,re
from copy import deepcopy
from fastapi import APIRouter,Request,Depends
from . import portal
from .mailer import config
router=APIRouter()
DARK={'accent':'#159eff','button_hover':'#45cdf4','bg':'#05070d','surface':'#0b101b','text':'#e7f2ff','muted':'#a7bbd9','ink':'#051c40'}
LIGHT={'accent':'#079df5','button_hover':'#37c6e8','bg':'#f4f7fb','surface':'#ffffff','text':'#0b1425','muted':'#536580','ink':'#031426'}
def palette(colors):return {**colors,'gradient_start':colors['bg'],'gradient_end':colors['bg'],'angle':135,'gradient':False}
PRESETS={'boreal':{'name':'Blue Boréal','dark':palette(DARK),'light':palette(LIGHT)},
'electric-lime':{'name':'Electric Lime','dark':palette({**DARK,'accent':'#c5f52c','button_hover':'#d4ff5e','bg':'#0d1311','surface':'#171e1a','text':'#f0f5f1','muted':'#abb9ae','ink':'#172000'}),'light':palette({**LIGHT,'accent':'#c5f52c','button_hover':'#d4ff5e','bg':'#f6f8f3','text':'#111c15','muted':'#526354','ink':'#172000'})},
'neon-rose':{'name':'Neon Rose','dark':palette({**DARK,'accent':'#fb65c5','button_hover':'#ff9bda','bg':'#151216','surface':'#211c24','text':'#f7eff9','muted':'#c0b2c7','ink':'#2e0522'}),'light':palette({**LIGHT,'accent':'#f331af','button_hover':'#fa83cd','bg':'#fbf7fa','text':'#241623','muted':'#715c70','ink':'#290320'})}}
PRESETS['boreal']['dark'].update(gradient=True,gradient_start='#0a1222',gradient_end='#04060b')
LOGOS={'boreal':'/static/gatearr-logo.png',
       'electric-lime':'/static/branding-variants/gatearr-electric-lime.png',
       'neon-rose':'/static/branding-variants/gatearr-neon-rose.png'}
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

def css(db,user=None,draft=False):
    value=validate(load(db,draft));mode=value['mode']
    if mode=='user':mode=getattr(user,'theme_preference','auto') or 'auto'
    def rules(name):
        p=value[name];colors=''.join('--'+key+':'+p[key]+';' for key in portal.DEFAULT['theme'])
        bg='linear-gradient('+str(p['angle'])+'deg,'+p['gradient_start']+','+p['gradient_end']+')' if p['gradient'] else p['bg']
        logo='brightness(0) invert(1)' if name=='dark' else 'brightness(0)'
        return ':root{'+colors+'--default-brand-logo:url("'+logo_url(value['preset'])+'");--logo-filter:'+logo+';color-scheme:'+name+';}body{background:'+bg+';}'
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
    from .main import require_user,redirect
    user=require_user(request)
    if load(request.state.db)['mode']!='user' or data.get('theme') not in ('light','dark','auto'):raise ValueError('Theme is managed by the administrator')
    user.theme_preference=data['theme'];request.state.db.commit();return redirect(data.get('next','/account') if str(data.get('next','')).startswith('/') and not str(data.get('next','')).startswith('//') else '/account')
