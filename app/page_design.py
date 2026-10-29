"""Validated presentation settings shared by the visual editors and public pages."""
import re
from .security import url_ok
COLORS=('accent','button_hover','bg','surface','text','muted','ink','gradient_start','gradient_end')

def validate_style(value):
    if not isinstance(value,dict) or set(value)-set(COLORS)-{'gradient','angle','align','padding','radius','background_mode','background_image','border_mode','border_color','border_width'}:raise ValueError('Invalid visual style')
    for key in COLORS:
        if key in value and not re.fullmatch(r'#[0-9a-fA-F]{6}',str(value[key])):raise ValueError('Invalid color: use #RRGGBB')
    if 'gradient' in value and type(value['gradient']) is not bool:raise ValueError('Invalid gradient')
    if value.get('background_mode','default') not in ('default','transparent','color','gradient','picture'):raise ValueError('Invalid background')
    if value.get('border_mode','default') not in ('default','none','color'):raise ValueError('Invalid border')
    if 'border_color' in value and not re.fullmatch(r'#[0-9a-fA-F]{6}',str(value['border_color'])):raise ValueError('Invalid color: use #RRGGBB')
    if value.get('background_image'):
        from .image_sources import require_image
        require_image(value['background_image'])
    for key,maximum in [('angle',360),('padding',100),('radius',80),('border_width',12)]:
        if key in value and (type(value[key]) is not int or not 0<=value[key]<=maximum):raise ValueError('Invalid visual style')
    if value.get('align','left') not in ('left','center','right'):raise ValueError('Invalid alignment')
    return value

def style_css(value):
    validate_style(value)
    css=''.join('--'+key+':'+value[key]+';' for key in COLORS if key in value)
    if 'bg' in value:css+='background:'+value['bg']+';'
    if value.get('gradient') and 'gradient_start' in value and 'gradient_end' in value:css+='background:linear-gradient('+str(value.get('angle',135))+'deg,'+value['gradient_start']+','+value['gradient_end']+');'
    if 'text' in value:css+='color:'+value['text']+';'
    if 'align' in value:css+='text-align:'+value['align']+';--block-justify:'+{'left':'flex-start','center':'center','right':'flex-end'}[value['align']]+';'
    if 'padding' in value:css+='padding:'+str(value['padding'])+'px;'
    if 'radius' in value:css+='border-radius:'+str(value['radius'])+'px;'
    mode=value.get('background_mode','default')
    if mode=='transparent':css+='background:transparent;box-shadow:none;'
    elif mode=='color':css+='background:'+value.get('bg','#0b101b')+';'
    elif mode=='gradient':css+='background:linear-gradient('+str(value.get('angle',135))+'deg,'+value.get('gradient_start','#0b101b')+','+value.get('gradient_end','#159eff')+');'
    elif mode=='picture' and value.get('background_image'):css+='background:center/cover no-repeat url("'+value['background_image']+'");'
    if value.get('border_mode')=='none':css+='border:0;'
    elif value.get('border_mode')=='color':css+='border:'+str(value.get('border_width',1))+'px solid '+value.get('border_color','#526789')+';'
    return css

def asset_url(value,db=None,optional=False):
    from .models import IconAsset
    if not value and optional:return ''
    if re.fullmatch(r'/static/services/(?:emby|jellyfin|seerr|radarr|sonarr|bazarr|tracearr|tdarr)\.png',value):return value
    if re.fullmatch(r'/media/icons/[a-f0-9]{64}\.(?:png|svg)',value):
        if db is not None and not db.get(IconAsset,value.split('/')[-1].split('.')[0]):raise ValueError('Image not found')
        return value
    return url_ok(value,optional=optional)

def link_url(value,public=False):
    # Authored public menus cannot link to session-changing or private admin routes.
    if re.fullmatch(r'/(?:login|forgot|home|account|pages/[a-z0-9]+(?:-[a-z0-9]+)*|access/[a-z0-9_-]{1,40})',value):
        if public and value not in ('/login','/forgot'):raise ValueError('Public links must be public pages or HTTP(S) URLs')
        return value
    return url_ok(value)
