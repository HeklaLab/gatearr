"""Editable light/dark palettes; generated CSS accepts only validated colors/numbers."""
import json,re
from copy import deepcopy
from fastapi import APIRouter,Request,Depends
from . import portal
from .mailer import config
router=APIRouter()
DARK={'accent':'#159eff','button_hover':'#45cdf4','bg':'#080f24','surface':'#111e3c','text':'#e7f2ff','muted':'#a7bbd9','ink':'#051c40'}
def load(db,draft=False):
    raw=config(db,'themes_draft' if draft else 'themes_published')
    light={**portal.DEFAULT['theme'],**portal.load(db,draft)['theme']}
    return json.loads(raw) if raw else {'mode':'user','light':{**light,'gradient_start':'#c9eaff','gradient_end':'#edf4ff','angle':135,'gradient':light==portal.DEFAULT['theme']},'dark':{**DARK,'gradient_start':'#062751','gradient_end':'#080f24','angle':135,'gradient':True}}
def validate(value):
    if value.get('mode') not in ('light','dark','auto','user'):raise ValueError('Invalid theme mode')
    for name in ('light','dark'):
        palette=value[name]
        for key in (*portal.DEFAULT['theme'],'gradient_start','gradient_end'):
            if not re.fullmatch(r'#[a-fA-F0-9]{6}',palette[key]):raise ValueError('Invalid color: use #RRGGBB')
        if type(palette['angle']) is not int or not 0<=palette['angle']<=360 or type(palette['gradient']) is not bool:raise ValueError('Invalid gradient')
    return value

def css(db,user=None,draft=False):
    value=validate(load(db,draft));mode=value['mode']
    if mode=='user':mode=user.theme_preference if user else 'auto'
    def rules(name):
        p=value[name];colors=''.join('--'+key+':'+p[key]+';' for key in portal.DEFAULT['theme'])
        bg='linear-gradient('+str(p['angle'])+'deg,'+p['gradient_start']+','+p['gradient_end']+')' if p['gradient'] else p['bg']
        rgb=[int(p['bg'][i:i+2],16) for i in (1,3,5)]
        logo='brightness(0) invert(1)' if sum(a*b for a,b in zip(rgb,(.2126,.7152,.0722)))<120 else 'none'
        return ':root{'+colors+'--logo-filter:'+logo+';color-scheme:'+name+';}body{background:'+bg+';}'
    return rules(mode) if mode in ('light','dark') else rules('light')+'@media(prefers-color-scheme:dark){'+rules('dark')+'}'

@router.get('/admin/branding/themes')
def editor(request:Request):
    from .main import require_admin,render
    require_admin(request)
    return render(request,'themes.html',themes=load(request.state.db,True),theme_version=int(config(request.state.db,'themes_version','0')))

@router.post('/admin/branding/themes')
def save(request:Request,data=Depends(__import__('app.main',fromlist=['form']).form)):
    from .main import require_admin,redirect,set_config
    from .models import Config
    from sqlalchemy import update
    from sqlalchemy.dialects.sqlite import insert
    from fastapi import HTTPException
    require_admin(request);db=request.state.db;v=load(db,True)
    v['mode']=data.get('mode',v['mode'])
    name=data.get('palette')
    if name in ('light','dark'):
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
    user.theme_preference=data['theme'];request.state.db.commit();return redirect('/account')
