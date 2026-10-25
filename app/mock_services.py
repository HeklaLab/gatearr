"""Isolated demo-only Seerr contract simulator, not real services."""
from fastapi import FastAPI, Request, HTTPException, Response

app = FastAPI()
SEERR_USER = {'username':'demo','email':'initial@example.com','locale':'fr','movieQuotaLimit':5,'movieQuotaDays':7}
SEERR_NOTIFICATIONS = {'emailEnabled':True,'discordIds':[],'notificationTypes':{'email':0,'discord':8}}
SERVER_ID = '11111111-1111-4111-8111-111111111111'

def public(request, service):
    expected = 'demo-seerr-key'
    header = 'X-Api-Key' if service == 'seerr' else 'Authorization'
    if request.headers.get(header) != expected:
        raise HTTPException(401)

def owner(request):
    if request.cookies.get('demo_owner_session') != 'demo-session':
        raise HTTPException(401)

@app.get('/healthz')
def health():
    return {'status':'ok'}

@app.get('/seerr/api/v1/user/jellyfin/{user_id}')
def seerr_user(request: Request, user_id: str):
    public(request,'seerr')
    if user_id not in ('demo-user-1','demo-admin-1'):raise HTTPException(404)
    return {'id':2 if user_id=='demo-user-1' else 3,'jellyfinUserId':user_id}

@app.get('/seerr/api/v1/user/2/settings/main')
def seerr_settings(request: Request):
    public(request,'seerr')
    return SEERR_USER

@app.post('/seerr/api/v1/user/2/settings/main')
async def seerr_update(request: Request):
    public(request,'seerr')
    SEERR_USER.update(await request.json())
    return SEERR_USER






@app.get('/seerr/api/v1/user/2/settings/notifications')
def notifications(request:Request):
    public(request,'seerr')
    return SEERR_NOTIFICATIONS

@app.post('/seerr/api/v1/user/2/settings/notifications')
async def notification_update(request:Request):
    public(request,'seerr')
    SEERR_NOTIFICATIONS.update(await request.json())
    return SEERR_NOTIFICATIONS




@app.get('/seerr/api/v1/user')
def seerr_list(request:Request):
    public(request,'seerr')
    return {'results':[{'id':2,'jellyfinUserId':'demo-user-1'}],'pageInfo':{'results':1}}

@app.post('/seerr/api/v1/auth/jellyfin')
async def seerr_session_login(request: Request):
    data=await request.json()
    if data.get('username')!='demo' or data.get('password') not in ('DemoPassword123!','ResetPassword123!'):
        raise HTTPException(401)
    from fastapi.responses import JSONResponse
    response=JSONResponse({'id':2})
    response.set_cookie('connect.sid','demo-seerr-session',httponly=True)
    return response

@app.get('/seerr/api/v1/auth/me')
def seerr_session_me(request: Request):
    if request.cookies.get('connect.sid')!='demo-seerr-session':raise HTTPException(401)
    return {'id':2}

@app.post('/seerr/api/v1/auth/logout')
def seerr_session_logout():return {'status':'ok'}

# Minimal official permission/quota contracts for the isolated browser demo.
DEMO_PERMISSIONS={2:32|262144|524288,3:2}
@app.get('/seerr/api/v1/user/{uid}/settings/permissions')
def get_permissions(request:Request,uid:int):
    public(request,'seerr')
    if uid not in DEMO_PERMISSIONS:raise HTTPException(404)
    return {'permissions':DEMO_PERMISSIONS[uid]}

@app.post('/seerr/api/v1/user/{uid}/settings/permissions')
async def set_permissions(request:Request,uid:int):
    public(request,'seerr')
    if uid not in DEMO_PERMISSIONS:raise HTTPException(404)
    DEMO_PERMISSIONS[uid]=(await request.json())['permissions']
    return {'permissions':DEMO_PERMISSIONS[uid]}

@app.post('/seerr/api/v1/user/{uid}/settings/password')
async def rotate_demo_password(request:Request,uid:int):
    public(request,'seerr')
    if uid not in DEMO_PERMISSIONS:raise HTTPException(404)
    if len((await request.json()).get('newPassword',''))<8:raise HTTPException(400)
    return Response(status_code=204)

@app.get('/seerr/api/v1/user/{uid}/quota')
def quota(request:Request,uid:int):
    public(request,'seerr')
    if uid not in DEMO_PERMISSIONS:raise HTTPException(404)
    return {'movie':{'limit':5,'used':2,'remaining':3,'restricted':False},'tv':{'limit':10,'used':3,'remaining':7,'restricted':False}}

@app.get('/seerr/api/v1/request')
def requests_summary(request:Request):
    public(request,'seerr')
    counts={'processing':4,'pending':2,'approved':3,'available':2}
    return {'pageInfo':{'results':counts.get(request.query_params.get('filter'),0)},'results':[]}

# Fictitious subtitle profiles are available only in this explicit demo server.
from .mock_bazarr import router as bazarr_demo_router
app.include_router(bazarr_demo_router)
