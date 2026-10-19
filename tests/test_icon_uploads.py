import struct,zlib
import pytest
from sqlalchemy import select
from app.db import SessionLocal
from app.models import MenuItem,AccessService,IconAsset
from app.icons import clean_png,MAX_BYTES
from test_portal import setup,csrf,post,logout,login_user


def chunk(kind,data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)


def png(width=2,height=2):
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\x80\x40\xff\xff'*width)*height))+chunk(b'IEND',b'')


def upload(client,path='/admin/menu',data=None,raw=None,token=None):
    return client.post(path,data={'csrf':token or csrf(client,'/admin'),**(data or {'label':'Uploaded service','url':'https://example.com','icon':'x','position':'1'})},files={'icon_file':('icon.png',png() if raw is None else raw,'image/png')},follow_redirects=False)


def test_menu_upload_create_edit_keep_and_url_alternative(client):
    setup(client)
    assert upload(client).status_code==303
    with SessionLocal() as db:
        item=db.scalar(select(MenuItem));uid=item.id;url=item.icon_url
        assert url.startswith('/media/icons/') and db.scalar(select(IconAsset)).content==png()
    response=client.get(url)
    assert response.content==png() and response.headers['content-type']=='image/png'
    assert response.headers['x-content-type-options']=='nosniff'
    assert 'immutable' in response.headers['cache-control']
    fields={'id':uid,'label':'Updated','url':'https://example.com','icon':'x','position':'1','icon_url':url}
    assert post(client,'/admin/menu',fields,'/admin').status_code==303
    with SessionLocal() as db:assert db.get(MenuItem,uid).icon_url==url
    assert upload(client,data=fields,raw=png(3,3)).status_code==303
    with SessionLocal() as db:assert db.get(MenuItem,uid).icon_url!=url
    fields['icon_url']='https://example.com/remote.png'
    assert post(client,'/admin/menu',fields,'/admin').status_code==400
    with SessionLocal() as db:assert db.get(MenuItem,uid).icon_url!=fields['icon_url']


def test_guided_service_upload_add_and_edit(client):
    setup(client)
    fields={'key':'custom','name':'Custom','browser_url':'https://example.com','server_url':'','entry_mode':'direct'}
    assert upload(client,'/admin/guides/service',fields).status_code==303
    with SessionLocal() as db:url=db.get(AccessService,'custom').icon_url
    fields['icon_url']=url
    assert post(client,'/admin/guides/service',fields,'/admin/guides').status_code==303
    assert upload(client,'/admin/guides/service',fields,raw=png(3,3)).status_code==303
    with SessionLocal() as db:assert db.get(AccessService,'custom').icon_url!=url


def test_upload_rejects_fakes_corrupt_oversized_and_bad_urls(client):
    setup(client)
    for raw in (b'<svg onload="alert(1)"></svg>',png()[:-3],png()+b'<script>',png(1025,1),b'x'*(MAX_BYTES+1)):
        assert upload(client,raw=raw).status_code==400
    assert client.post('/admin/menu',data={'csrf':csrf(client,'/admin')},files={'icon_file':('big.png',b'x'*(MAX_BYTES+65536),'image/png')}).status_code==413
    assert post(client,'/admin/menu',{'label':'Bad','url':'https://example.com','icon':'x','position':'1','icon_url':'/media/icons/'+'a'*64+'.png'},'/admin').status_code==400
    assert client.get('/media/icons/'+'a'*64+'.png').status_code==404
    with SessionLocal() as db:
        assert db.scalar(select(IconAsset)) is None
        assert db.scalar(select(MenuItem)) is None


def test_upload_requires_admin_csrf_and_assets_are_public(client):
    setup(client)
    assert upload(client,token='wrong').status_code==403
    assert upload(client).status_code==303
    with SessionLocal() as db:url=db.scalar(select(MenuItem)).icon_url
    logout(client);login_user(client)
    assert upload(client,token=csrf(client,'/account')).status_code==403
    logout(client)
    assert client.get(url).content==png()


def test_png_metadata_stripped_deduplicated_and_image_data_bounded(client):
    original=png();tag=chunk(b'tEXt',b'comment\0private metadata')
    annotated=original[:-12]+tag+original[-12:]
    assert clean_png(annotated)==original
    bomb=original[:33]+chunk(b'IDAT',zlib.compress(b'\0'*1000000))+original[-12:]
    with pytest.raises(ValueError):clean_png(bomb)
    setup(client)
    assert upload(client,raw=annotated).status_code==303
    assert upload(client,raw=original).status_code==303
    with SessionLocal() as db:assert len(list(db.scalars(select(IconAsset))))==1
