"""Isolated demo-only Seerr and Tracearr contract simulators, not real services."""
from fastapi import FastAPI, Request, HTTPException, Response

app = FastAPI()
SEERR_USER = {'username':'demo','email':'initial@example.com','locale':'fr','movieQuotaLimit':5,'movieQuotaDays':7}
TRACEARR_EMAIL = 'initial@example.com'
TRACEARR_SUPPRESSIONS = set()
SEERR_NOTIFICATIONS = {'emailEnabled':True,'discordIds':[],'notificationTypes':{'email':0,'discord':8}}
SERVER_ID = '11111111-1111-4111-8111-111111111111'

def public(request, service):
    expected = 'demo-seerr-key' if service == 'seerr' else 'Bearer demo-tracearr-key'
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

@app.get('/tracearr/api/v2/public/users')
def tracearr_users(request: Request):
    public(request,'tracearr')
    return {'data':[{'id':'identity-demo','accounts':[{'server_id':SERVER_ID,'server_type':'emby','external_user_id':'demo-user-1','server_user_id':'demo-account','removed_at':None}]}],'meta':{'nextCursor':None}}

@app.post('/tracearr/api/v1/auth/sign-in/email')
async def login(request: Request, response: Response):
    data=await request.json()
    if data.get('email') != 'owner@example.com' or data.get('password') != 'DemoOwnerPassword123!':
        raise HTTPException(401)
    response.set_cookie('demo_owner_session','demo-session',httponly=True)
    return {'user':{'role':'owner'}}

@app.post('/tracearr/api/v1/auth/sign-out')
def logout(request: Request,response:Response):
    owner(request)
    response.delete_cookie('demo_owner_session')
    return {'success':True}

@app.get('/tracearr/api/v1/users/demo-account/full')
def full(request: Request):
    owner(request)
    return {'user':{'serverId':SERVER_ID,'externalId':'demo-user-1'},'identity':{'contactEmail':TRACEARR_EMAIL}}

@app.patch('/tracearr/api/v1/users/demo-account/identity')
async def update(request: Request):
    owner(request)
    global TRACEARR_EMAIL
    data=await request.json()
    if set(data) != {'contactEmail'}:
        raise HTTPException(400)
    TRACEARR_EMAIL=data['contactEmail']
    return {'success':True,'contactEmail':TRACEARR_EMAIL}

@app.get('/seerr/api/v1/user/2/settings/notifications')
def notifications(request:Request):
    public(request,'seerr')
    return SEERR_NOTIFICATIONS

@app.post('/seerr/api/v1/user/2/settings/notifications')
async def notification_update(request:Request):
    public(request,'seerr')
    SEERR_NOTIFICATIONS.update(await request.json())
    return SEERR_NOTIFICATIONS

@app.get('/tracearr/api/v1/email/suppressions')
def suppressions(request:Request):
    owner(request)
    return [{'address':address,'reason':'manual'} for address in sorted(TRACEARR_SUPPRESSIONS)]

@app.post('/tracearr/api/v1/email/suppressions',status_code=201)
async def suppress(request:Request):
    owner(request)
    address=(await request.json()).get('address','').lower()
    if not address:raise HTTPException(400)
    TRACEARR_SUPPRESSIONS.add(address)
    return {'address':address}

@app.delete('/tracearr/api/v1/email/suppressions/{address}',status_code=204)
def unsuppress(request:Request,address:str):
    owner(request)
    if address not in TRACEARR_SUPPRESSIONS:raise HTTPException(404)
    TRACEARR_SUPPRESSIONS.remove(address)
    return Response(status_code=204)

@app.get('/seerr/api/v1/user')
def seerr_list(request:Request):
    public(request,'seerr')
    return {'results':[{'id':2,'jellyfinUserId':'demo-user-1'}],'pageInfo':{'results':1}}
