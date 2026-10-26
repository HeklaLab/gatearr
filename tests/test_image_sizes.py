import json
import pytest
from app.image_blocks import normalize,validate
from app.visual_builder import load
from app.db import SessionLocal
from test_portal import setup,post


def test_old_image_columns_become_percent_sizes_without_changing_saved_source():
    original={'blocks':[{'id':'logo','kind':'image','span':4,'style':{'align':'right'}},{'id':'text','kind':'text','span':6}]}
    result=normalize(original)
    assert result['blocks'][0]=={'id':'logo','kind':'image','span':12,'style':{'align':'right'},'image_width':33.33,'image_unit':'%'}
    assert original['blocks'][0]['span']==4 and 'image_width' not in original['blocks'][0]
    assert result['blocks'][1]==original['blocks'][1]
    assert normalize(result)==result


@pytest.mark.parametrize('width,unit',[(1,'px'),(4096,'px'),(25.5,'%'),(100,'%')])
def test_explicit_image_size_is_preserved(width,unit):
    block={'kind':'image','span':4,'image_width':width,'image_unit':unit}
    validate(block)
    assert normalize({'blocks':[block]})['blocks'][0]=={**block,'span':12}


@pytest.mark.parametrize('width,unit',[(0,'%'),(101,'%'),(4097,'px'),(10**400,'px'),(True,'px'),('50','%'),(float('nan'),'%'),(float('inf'),'px'),(50,'vw'),(50,'%;color:red')])
def test_invalid_sizes_are_rejected(width,unit):
    with pytest.raises(ValueError):validate({'image_width':width,'image_unit':unit})


def test_image_size_roundtrip_uses_a_full_width_zone(client):
    setup(client)
    with SessionLocal() as db:layout=load(db,'home',True)
    layout['blocks'].append({'id':'sized-image','kind':'image','span':4,'region':'main','order':999,'url':'','image_width':180,'image_unit':'px','style':{'align':'right'}})
    response=post(client,'/admin/design/home/save',{'version':0,'payload':json.dumps(layout)},'/admin/design/home')
    assert response.status_code==200
    with SessionLocal() as db:block=next(b for b in load(db,'home',True)['blocks'] if b['id']=='sized-image')
    assert block['span']==12 and block['image_width']==180 and block['image_unit']=='px'
