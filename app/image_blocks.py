"""Image size belongs to the image, while columns arrange the surrounding blocks."""
from copy import deepcopy


def validate(block):
    unit=block.get('image_unit','%')
    width=block.get('image_width',100)
    if unit not in ('px','%') or type(width) not in (int,float) or not 1<=width<=(100 if unit=='%' else 4096):
        raise ValueError('Invalid image width')


def normalize(layout):
    value=deepcopy(layout)
    for block in value['blocks']:
        if block['kind']!='image':continue
        if 'image_width' not in block:
            block['image_width']=round(block.get('span',12)/12*100,2)
            block['image_unit']='%'
        block['span']=12
    return value
