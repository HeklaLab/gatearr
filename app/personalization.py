"""Explicit content reset; connection secrets and account permissions stay untouched."""
import json,secrets
from fastapi import APIRouter,Request,Depends,HTTPException
from sqlalchemy import select,delete,func
from .models import Config,Guide,AccessService,MenuItem,ContentTranslation,ContentPage,Session,User
from .main import require_admin,form,redirect,set_config
from .mailer import config
router=APIRouter()
SYSTEM_PAGES=('login','forgot','reset','account','header')
PREFIXES=('header_','portal_','footer_','themes_','ui_translation_','deleted_system_page:')+tuple(page+'_'+part for page in SYSTEM_PAGES for part in ('draft','published','version'))
KEYS={'app_name','logo_url','logo_url_light','login_text','menu_version','browser_title','brand_display'}

@router.post('/admin/updates/reset-content')
def reset(request:Request,data=Depends(form)):
    require_admin(request);db=request.state.db
    if data.get('confirm')!='on' or data.get('confirmation')!='RESET':raise HTTPException(400,'Type RESET and confirm the content reset')
    next_id=(db.scalar(select(func.max(Guide.id))) or 0)+1
    leases={key:int(config(db,key,'0'))+1 for key in ('portal_version','footer_version','themes_version','menu_version',*(page+'_version' for page in SYSTEM_PAGES))}
    # Keep page identities monotonic, including pages removed by this reset.
    from .page_builder import next_page_id
    next_page_id(db)
    from .email_editor import PURPOSES,ALL_PURPOSES
    mail_keys={purpose+'_'+part for purpose in {**PURPOSES,**ALL_PURPOSES} for part in ('html','body','subject')}
    for row in list(db.scalars(select(Config))):
        if row.key.startswith(PREFIXES) or row.key in KEYS|mail_keys:db.delete(row)
    # Legacy application links may still hold the only public address.
    for service in db.scalars(select(AccessService)):
        if service.key not in ('emby','seerr') or service.browser_url:continue
        legacy=db.scalar(select(MenuItem).where((MenuItem.access_service==service.key)|(func.lower(MenuItem.label)==service.key)).order_by(MenuItem.id))
        if legacy and legacy.url:service.browser_url=legacy.url
    db.execute(delete(ContentTranslation));db.execute(delete(ContentPage));db.execute(delete(Guide));db.execute(delete(MenuItem))
    for service in list(db.scalars(select(AccessService))):
        if service.key not in ('emby','seerr','radarr','sonarr','bazarr','tracearr','tdarr'):db.delete(service);continue
        service.name=service.key.capitalize() if service.key!='seerr' else 'Seerr'
        service.icon='link';service.icon_url='';service.entry_mode='structured' if service.key=='emby' else 'direct'
        service.access_draft=service.access_published=None;service.access_version+=1
        if service.key=='tracearr':
            service.access_draft=service.access_published=json.dumps([dict(id='browser',kind='browser',title='Browser',position=10,icon='globe')])
    db.flush()
    from .default_journeys import seed,seed_seerr
    seed(db,activate=True,first_id=next_id);seed_seerr(db)
    # Rebuild pages before Home so its page-menu references point at the new IDs.
    from . import portal,header,footer,visual_builder
    home=portal.initial_layout(db)
    for page,value in [('portal',home),*((page,header.default(db) if page=='header' else visual_builder.system_default(db,page)) for page in SYSTEM_PAGES),('footer',footer.DEFAULT)]:
        for part in ('draft','published'):set_config(db,page+'_'+part,json.dumps(value,ensure_ascii=False))
    for key,value in leases.items():set_config(db,key,str(value))
    # Invalidate stale editor forms, without signing users out or changing API access.
    for session in db.scalars(select(Session).join(User).where(User.admin.is_(True))):session.csrf=secrets.token_urlsafe(32)
    request.state.audit_action='content.reset';request.state.audit_detail='Custom pages and URL applications removed; page, Home, system-page, header, footer and guide presets restored. Accounts, groups, permissions, native application connections and SMTP settings retained.'
    db.commit();return redirect('/admin/updates?content_reset=1')
