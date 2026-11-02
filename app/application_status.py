"""Permission-filtered cached application health; no upstream addresses or errors."""
from fastapi import APIRouter,Request
from .connection_health import public_status

router=APIRouter()

def service_key(key):
    if key in ('access:emby','access:seerr'):return key.split(':')[1]
    if key in ('radarr','sonarr','bazarr','tracearr','tdarr'):return key
    return None

@router.get('/api/application-status')
def status(request:Request):
    from .main import require_user
    from .applications import catalog
    from fastapi.responses import JSONResponse
    user=require_user(request);db=request.state.db
    values={item['key']:public_status(db,service) for item in catalog(db,user) if (service:=service_key(item['key']))}
    return JSONResponse(values,headers={'Cache-Control':'no-store'})
