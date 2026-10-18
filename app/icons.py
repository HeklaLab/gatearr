"""Small, bounded PNG uploads stored with the portal's persistent database."""
import hashlib
import re
import struct
import zlib
from sqlalchemy.dialects.sqlite import insert
from starlette.datastructures import UploadFile
from .models import IconAsset
from .security import url_ok

MAX_BYTES=2*1024*1024
MAX_DIMENSION=1024
SIGNATURE=b'\x89PNG\r\n\x1a\n'


def clean_png(raw):
    def invalid():raise ValueError('Choose a valid PNG image (up to 2 MB and 1024 × 1024 pixels)')
    if len(raw)>MAX_BYTES or not raw.startswith(SIGNATURE):invalid()
    pos=8;chunks=[];compressed=[];header=None;ended=False;data_ended=False;palette=False
    while pos<len(raw):
        if pos+12>len(raw):invalid()
        size=struct.unpack('>I',raw[pos:pos+4])[0]
        kind=raw[pos+4:pos+8];end=pos+12+size
        if end>len(raw):invalid()
        body=raw[pos+8:pos+8+size]
        if zlib.crc32(kind+body)&0xffffffff!=struct.unpack('>I',raw[end-4:end])[0]:invalid()
        if header is None:
            if kind!=b'IHDR' or size!=13:invalid()
            header=struct.unpack('>IIBBBBB',body)
            width,height,depth,color,compression,filtering,interlace=header
            depths={0:(1,2,4,8,16),2:(8,16),3:(1,2,4,8),4:(8,16),6:(8,16)}
            if not 1<=width<=MAX_DIMENSION or not 1<=height<=MAX_DIMENSION or depth not in depths.get(color,()) or compression or filtering or interlace not in (0,1):invalid()
        elif kind==b'IHDR':invalid()
        if kind==b'PLTE':
            if palette or compressed or not 3<=size<=768 or size%3:invalid()
            palette=True
        if kind==b'IDAT':
            if data_ended or (header[3]==3 and not palette):invalid()
            compressed.append(body)
        elif compressed:data_ended=True
        if kind==b'IEND':
            if size or not compressed or end!=len(raw):invalid()
            ended=True
        # Retain image data and transparency only; drop comments and other metadata.
        if kind in (b'IHDR',b'PLTE',b'tRNS',b'IDAT',b'IEND'):
            if kind==b'tRNS' and compressed:invalid()
            chunks.append(raw[pos:end])
        elif kind[:1].isupper() or kind in (b'acTL',b'fcTL',b'fdAT'):invalid()
        pos=end
    if not ended:invalid()
    width,height,depth,color,_,_,interlace=header
    channels={0:1,2:3,3:1,4:2,6:4}[color]
    passes=[(0,0,1,1)] if not interlace else [(0,0,8,8),(4,0,8,8),(0,4,4,8),(2,0,4,4),(0,2,2,4),(1,0,2,2),(0,1,1,2)]
    rows=[]
    for x,y,dx,dy in passes:
        w=max(0,(width-x+dx-1)//dx);h=max(0,(height-y+dy-1)//dy)
        if w and h:rows.extend([(w*channels*depth+7)//8]*h)
    expected=sum(length+1 for length in rows)
    try:
        decoder=zlib.decompressobj()
        pixels=decoder.decompress(b''.join(compressed),expected+1)
    except zlib.error:invalid()
    if len(pixels)!=expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:invalid()
    offset=0
    for length in rows:
        if pixels[offset]>4:invalid()
        offset+=length+1
    return SIGNATURE+b''.join(chunks)


def icon_value(db,data):
    upload=data.get('icon_file')
    if isinstance(upload,UploadFile) and upload.filename:
        try:raw=upload.file.read(MAX_BYTES+1)
        finally:upload.file.close()
        png=clean_png(raw)
        identifier=hashlib.sha256(png).hexdigest()
        db.execute(insert(IconAsset).values(digest=identifier,content=png).on_conflict_do_nothing(index_elements=['digest']))
        return '/media/icons/'+identifier+'.png'
    value=str(data.get('icon_url','')).strip()
    if value.startswith('/media/icons/'):
        match=re.fullmatch(r'/media/icons/([a-f0-9]{64})\.png',value)
        if not match or not db.get(IconAsset,match[1]):raise ValueError('Invalid icon URL')
        return value
    return url_ok(value,optional=True)
