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
    if user_id != 'demo-user-1':
        raise HTTPException(404)
    return {'id':2,'jellyfinUserId':user_id}

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
