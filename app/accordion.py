"""Small rich-text vocabulary for FAQ answers; media belongs outside the answer."""
import re
import nh3
from .icons import font_icon
from .image_sources import require_image

TAGS={'p','div','br','strong','b','em','i','u','ul','ol','li','span','font'}

def clean_answer(value):
    if not isinstance(value,str) or len(value)>10000:raise ValueError('Accordion text is too long')
    def attribute(tag,name,value):
        if name=='color':return value if re.fullmatch(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?',value) else None
        return value
    return nh3.clean(value,tags=TAGS,attributes={'*':{'style'},'font':{'color'}},attribute_filter=attribute,filter_style_properties={'color','font-weight','font-style','text-decoration'},clean_content_tags={'script','style','iframe','object','svg','math','form','template','video','audio','picture'})

def validate_item(item,db=None):
    if type(item.get('rich',False)) is not bool or type(item.get('watermark',False)) is not bool:raise ValueError('Invalid accordion appearance')
    if not isinstance(item.get('icon',''),str) or not isinstance(item.get('icon_url',''),str):raise ValueError('Invalid accordion icon')
    if item.get('icon'):font_icon(item['icon'])
    item['icon_url']=require_image(item.get('icon_url',''),db,optional=True)
    if item.get('rich'):item['answer']=clean_answer(item.get('answer',''))
    return item
