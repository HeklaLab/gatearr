from fastapi import APIRouter,Request,Depends,HTTPException
from .main import form,require_user,redirect,limit
from .mailer import config
from .integrations import queue_user,enabled

router=APIRouter()

@router.post('/account/preferences')
def preferences(request: Request,data=Depends(form)):
    user=require_user(request)
    if not user.emby_id:raise HTTPException(403,'Emby account required')
    if not user.email:raise HTTPException(400,'Verify your email address before changing your preferences')
    db=request.state.db
    limit(request,'preferences',str(user.id),maximum=20)
    service=data.get('service')
    if config(db,'smtp_host') and service=='seerr' and __import__('app.seerr_permissions',fromlist=['configured']).configured(db) and __import__('app.group_access',fromlist=['seerr_allowed']).seerr_allowed(db,user) and config(db,'seerr_notification_mode','unmanaged')=='optional':
        user.seerr_notifications=data.get('enabled')=='on'
    else:raise HTTPException(403,'This preference is managed by the administrator')
    user.preferences_version+=1
    db.commit()
    queue_user(db,user,force=True)
    return redirect('/account')

@router.post('/account/notifications')
def notifications(request:Request,data=Depends(form)):
    user=require_user(request);db=request.state.db
    limit(request,'notification_preferences',str(user.id),maximum=20)
    if not user.email or not config(db,'smtp_host'):raise HTTPException(409,'Verify your email address before changing your preferences')
    from .tracearr import configured as tracearr_ready
    from .seerr_permissions import configured as seerr_ready
    from .group_access import seerr_allowed
    from .widgets import preference
    if seerr_ready(db) and seerr_allowed(db,user) and config(db,'seerr_notification_mode')=='optional':
        user.seerr_notifications=data.get('requests')=='on';user.preferences_version+=1
        db.commit();queue_user(db,user,force=True)
    if tracearr_ready(db):
        row=preference(db,user);row.seasons=True;row.email=data.get('seasons_email')=='on'
    db.commit();return redirect('/account?tab=notifications')


def available_notifications(db,user):
    from .seerr_permissions import configured as seerr_ready
    from .tracearr import configured as tracearr_ready
    from .group_access import seerr_allowed
    if not user or not user.emby_id or not config(db,'smtp_host'):return {}
    return {'requests':seerr_ready(db) and seerr_allowed(db,user) and config(db,'seerr_notification_mode') in ('optional','forced'),'seasons':tracearr_ready(db)}
