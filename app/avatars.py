"""Private, bounded native user photos. Credentials never leave the server."""
import base64,time,struct
from urllib.parse import quote
import httpx
from fastapi import APIRouter,Request,Depends,HTTPException
from fastapi.responses import Response
from starlette.datastructures import UploadFile
from .models import User,UserPhoto
from .mailer import config
from .security import digest,decrypt
from .icons import clean_png,MAX_BYTES
router=APIRouter()

def source(db):return digest(config(db,'media_server_id')+'\n'+config(db,'emby_url')+'\n'+config(db,'emby_api_key'))

def observe(db,user,remote):
    row=db.get(UserPhoto,user.id);tag=str(remote.get('PrimaryImageTag') or '')[:200];fingerprint=source(db)
    if not row and not tag:return
    if not row:row=UserPhoto(user_id=user.id,source=fingerprint,remote_tag=tag);db.add(row)
    if row.source!=fingerprint or row.remote_tag!=tag:row.content=None
    row.source=fingerprint;row.remote_tag=tag;row.checked_at=int(time.time())

def url(db,user):
    if not user or not user.emby_id:return ''
    row=db.get(UserPhoto,user.id)
    if not row or row.source!=source(db) or not row.remote_tag:return ''
    return '/avatars/'+str(user.id)+'?v='+digest(row.source+row.remote_tag)[:20]

def clean(raw):
    if raw.startswith(b'\x89PNG'):return clean_png(raw),'image/png'
    if len(raw)>MAX_BYTES or not raw.startswith(b'\xff\xd8') or not raw.endswith(b'\xff\xd9'):raise ValueError('Choose a PNG or JPEG photo up to 5 MB')
    # Bound dimensions; remove EXIF and comments before sending to the native server.
    out=bytearray(raw[:2]);pos=2;dimensions=False
    while pos<len(raw)-2:
        if raw[pos]!=255:raise ValueError('Invalid profile image')
        start=pos
        while pos<len(raw) and raw[pos]==255:pos+=1
        if pos>=len(raw):raise ValueError('Invalid profile image')
        marker=raw[pos];pos+=1
        if marker==0xda:
            if not dimensions:raise ValueError('Invalid profile image')
            out.extend(raw[start:]);return bytes(out),'image/jpeg'
        if marker in (0xd8,0xd9) or 0xd0<=marker<=0xd7:raise ValueError('Invalid profile image')
        if pos+2>len(raw):raise ValueError('Invalid profile image')
        length=int.from_bytes(raw[pos:pos+2],'big');end=pos+length
        if length<2 or end>len(raw):raise ValueError('Invalid profile image')
        if marker in (0xc0,0xc1,0xc2):
            if length<8:raise ValueError('Invalid profile image')
            height,width=struct.unpack('>HH',raw[pos+3:pos+7])
            if not 1<=width<=4096 or not 1<=height<=4096:raise ValueError('Invalid profile image')
            dimensions=True
        if marker not in (0xe1,0xfe):out.extend(raw[start:end])
        pos=end
    raise ValueError('Invalid profile image')

def native(db,user,method,content=None,mime=None):
    base=config(db,'emby_url');key=decrypt(config(db,'emby_api_key'))
    headers={'X-Emby-Token':key};kind=config(db,'media_server','emby')
    if kind=='jellyfin':headers={'Authorization':'MediaBrowser Client="Gatearr", Device="Portal", DeviceId="gatearr-portal", Version="1.0", Token="'+key+'"'}
    path='/Users/'+quote(user.emby_id,safe='')+'/Images/Primary'
    params={'maxWidth':256,'maxHeight':256,'format':'png'} if method=='GET' else {}
    if kind=='jellyfin' and method=='POST':path='/UserImage';params={'userId':user.emby_id}
    if mime:headers['Content-Type']=mime
    try:
        with httpx.Client(timeout=10,trust_env=False,follow_redirects=False) as client:
            with client.stream(method,base.rstrip('/')+path,headers=headers,params=params,content=base64.b64encode(content) if content is not None else None) as response:
                if response.status_code==404 and method=='GET':return None
                response.raise_for_status()
                if method=='POST':return True
                raw=bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw)>MAX_BYTES:raise ValueError('Profile image too large')
                return clean(bytes(raw))
    except (httpx.HTTPError,ValueError):raise HTTPException(502,'Profile photo could not be synchronized. Try again later.')

@router.get('/avatars/{uid}')
def image(request:Request,uid:int):
    from .main import require_user,emby
    actor=require_user(request);db=request.state.db;user=db.get(User,uid)
    if not user or not user.active or user.emby_missing or (actor.id!=uid and not actor.admin):raise HTTPException(404,'Photo unavailable')
    if actor.id!=uid:
        from .main import require_admin
        require_admin(request)
    row=db.get(UserPhoto,uid)
    if not row or row.source!=source(db) or int(time.time())-row.checked_at>60:
        try:observe(db,user,emby.user(user.emby_id));db.commit()
        except Exception:return Response(status_code=404,headers={'Cache-Control':'no-store'})
        row=db.get(UserPhoto,uid)
    if not row or not row.remote_tag:return Response(status_code=404,headers={'Cache-Control':'no-store'})
    if not row.content:
        result=native(db,user,'GET')
        if result is None:row.remote_tag='';db.commit();return Response(status_code=404,headers={'Cache-Control':'no-store'})
        row.content,row.mime=result;db.commit()
    return Response(row.content,media_type=row.mime,headers={'Cache-Control':'private, max-age=30','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox"})

@router.post('/account/photo')
@router.post('/admin/users/{uid}/photo')
def save(request:Request,uid:int|None=None,data=Depends(__import__('app.main',fromlist=['form']).form)):
    from .main import require_user,require_admin,emby,redirect,limit
    actor=require_admin(request) if uid is not None else require_user(request)
    db=request.state.db;user=db.get(User,uid) if uid is not None else actor
    if not user or not user.emby_id or not user.active or user.emby_missing:raise HTTPException(404,'User not found')
    remote=emby.user(user.emby_id)
    if remote.get('Policy',{}).get('IsDisabled'):raise HTTPException(403,'Native account access revoked')
    if uid is None and remote.get('Policy',{}).get('EnableUserPreferenceAccess') is False:raise HTTPException(403,'Profile changes are managed by your administrator')
    upload=data.get('icon_file')
    if not isinstance(upload,UploadFile) or not upload.filename:raise ValueError('Choose a PNG or JPEG photo up to 5 MB')
    limit(request,'profile_photo',str(user.id),maximum=10)
    raw=upload.file.read(MAX_BYTES+1);upload.file.close();content,mime=clean(raw)
    native(db,user,'POST',content,mime)
    updated=emby.user(user.emby_id)
    observe(db,user,updated);row=db.get(UserPhoto,user.id)
    if not row:row=UserPhoto(user_id=user.id,source=source(db));db.add(row)
    # Read-after-write native tag is authoritative. Cache bytes only after native success.
    row.content=content;row.mime=mime;row.remote_tag=str(updated.get('PrimaryImageTag') or digest(content))[:200];row.checked_at=int(time.time());db.commit()
    request.state.audit_subject=user.id;request.state.audit_detail='Profile photo updated'
    return redirect('/account?photo=saved' if uid is None else '/admin/users/'+str(uid)+'?photo=saved')
