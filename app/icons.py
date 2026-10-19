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
        svg=raw.lstrip().startswith(b'<')
        content=clean_svg(raw) if svg else clean_png(raw)
        mime='image/svg+xml' if svg else 'image/png'
        identifier=hashlib.sha256(content).hexdigest()
        db.execute(insert(IconAsset).values(digest=identifier,content=content,mime=mime).on_conflict_do_nothing(index_elements=['digest']))
        return '/media/icons/'+identifier+('.svg' if svg else '.png')
    value=str(data.get('icon_url','')).strip()
    if value.startswith('/media/icons/'):
        match=re.fullmatch(r'/media/icons/([a-f0-9]{64})\.(?:png|svg)',value)
        if not match or not db.get(IconAsset,match[1]):raise ValueError('Invalid icon URL')
        return value
    return url_ok(value,optional=True)


FA_ICONS={'user-circle':'f2bd','users':'f0c0','palette':'f53f','envelope':'f0e0','plug':'f1e6','layer-group':'f5fd','language':'f1ab','clock-rotate-left':'f1da','arrows-rotate':'f021','gears':'f085','film':'f008','tv':'f26c','music':'f001','book':'f02d','house':'f015','globe':'f0ac','circle-question':'f059','download':'f019','play':'f04b','link':'f0c1','mobile-screen':'f3cf','desktop':'f390','shield-halved':'f3ed'}

def font_icon(value):
    value=str(value or 'link')
    if value.startswith('fa-'):value=value[3:]
    if value not in FA_ICONS:raise ValueError('Choose a Font Awesome icon or upload PNG/SVG')
    return value

def clean_svg(raw):
    import xml.etree.ElementTree as ET
    raw=re.sub(br'^\s*<\?xml[^?]*\?>',b'',raw,count=1)
    if len(raw)>MAX_BYTES or b'<!' in raw or b'<?' in raw:raise ValueError('Invalid SVG image')
    try:root=ET.fromstring(raw)
    except ET.ParseError:raise ValueError('Invalid SVG image')
    allowed={'svg','g','path','rect','circle','ellipse','line','polyline','polygon','title','desc','defs','linearGradient','radialGradient','stop'}
    attrs={'xmlns','viewBox','width','height','d','x','y','x1','x2','y1','y2','cx','cy','r','rx','ry','points','fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','opacity','fill-opacity','stroke-opacity','transform','offset','stop-color','stop-opacity','gradientUnits','id'}
    nodes=list(root.iter())
    if len(nodes)>2000 or root.tag.split('}')[-1]!='svg':raise ValueError('Invalid SVG image')
    stack=[(root,0)]
    while stack:
        node,depth=stack.pop()
        if depth>32:raise ValueError('Invalid SVG image')
        stack.extend((child,depth+1) for child in node)
    for node in nodes:
        if node.tag.split('}')[-1] not in allowed:raise ValueError('Invalid SVG image')
        for key,value in node.attrib.items():
            if key not in attrs or len(value)>100000 or any(v in value.lower() for v in ('url(', 'javascript:', 'data:', 'http:', 'https:', '//')):raise ValueError('Invalid SVG image')
    return ET.tostring(root,encoding='utf-8')
