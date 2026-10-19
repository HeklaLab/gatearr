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
    if service=='seerr' and enabled(db,'seerr') and config(db,'seerr_notification_mode','unmanaged')=='optional':
        user.seerr_notifications=data.get('enabled')=='on'
    else:raise HTTPException(403,'This preference is managed by the administrator')
    user.preferences_version+=1
    db.commit()
    queue_user(db,user,force=True)
    return redirect('/account')
