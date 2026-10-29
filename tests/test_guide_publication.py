"""Publication dependencies must stay visible without exposing guide drafts."""
import json
import re
import pytest
from sqlalchemy import select
from app import main,visual_howto
from app.db import SessionLocal
from app.models import AccessService,Guide,User
from test_portal import setup,post,logout,login_user


def boot(client,path):
    return json.loads(re.search(r'<script id="howto-data" type="application/json">(.*?)</script>',client.get(path).text)[1])


def journey(client,key,action,value,version=None):
    if version is None:
        with SessionLocal() as db:version=db.get(AccessService,key).access_version
    return post(client,f'/admin/visual-howto/{key}/{action}',{'version':str(version),'payload':json.dumps(value)},'/admin')


def article(client,gid,action,value):
    with SessionLocal() as db:version=db.get(Guide,gid).version
    return post(client,f'/admin/visual-guide/{gid}/{action}',{'version':str(version),'payload':json.dumps(value)},'/admin')


def test_shared_guide_formatting_survives_save_preview_and_reopen_safely(client):
    setup(client)
    created=journey(client,'emby','new-guide',{'title':'Formatting'})
    assert created.status_code==200
    gid=created.json()['id']
    body='<ol><li style="text-align:right"><b><i><u style="color:rgb(204,51,119)">Formatted instructions</u></i></b></li></ol><script>unsafe()</script>'
    value=dict(title='Formatting',summary='',position=10,device='other',steps=[dict(id='one',title='One',body=body,rich=True,link_label='',link_url='',image_url='')])
    assert article(client,gid,'save',value).status_code==200
    reopened=boot(client,'/admin/design/home/guide/'+str(gid))['article']
    saved=reopened['steps'][0]['body']
    assert '<ol>' in saved and '<ustyle="color:rgb(204,51,119)">' in re.sub(r'\s+','',saved)
    assert 'text-align:right' in saved and '<b><i>' in saved and 'unsafe()' not in saved
    preview=article(client,gid,'preview',reopened)
    assert preview.status_code==200 and saved in preview.text


def prepare(client,key):
    setup(client)
    with SessionLocal() as db:
        if not db.get(AccessService,key):db.add(AccessService(key=key,name=key.title(),browser_url='https://example.com',server_url='https://example.com',entry_mode='structured',access_version=0))
        db.commit()
    return {'mode':'choices','browser_url':'https://example.com','nodes':[{'id':'browser','parent':'','kind':'browser','position':10,'title':'Browser'},{'id':'phone','parent':'','kind':'group','position':20,'title':'Phone'},{'id':'computer','parent':'','kind':'group','position':30,'title':'Computer'}]}


def content(body='First public instructions'):
    return {'title':'Phone setup','summary':'','device':'mobile','steps':[{'id':'install','title':'Install','body':body,'link_label':'','link_url':'','image_url':''}]}


@pytest.mark.parametrize('key',['emby','seerr','discord'])
def test_publication_blockers_identify_every_branch_and_do_not_publish_drafts(client,key):
    value=prepare(client,key)
    assert journey(client,key,'publish',value).status_code==200
    created=journey(client,key,'new-guide',{'title':'Phone setup'}).json();gid=created['id']
    assert created['publication_state']=='unpublished'
    value['nodes'].extend([{'id':'phone-guide','parent':'phone','kind':'guide','position':40,'title':'Install phone','guide_id':gid},{'id':'computer-guide','parent':'computer','kind':'guide','position':50,'title':'Install desktop','guide_id':gid}])
    assert journey(client,key,'save',value).status_code==200
    with SessionLocal() as db:
        before=(db.get(AccessService,key).access_published,db.get(AccessService,key).access_version)
    response=journey(client,key,'publish',value)
    assert response.status_code==400
    error=response.json();assert error['code']=='unpublished_guides'
    assert [b['path'] for b in error['blockers']]==[[key.title() if key!='emby' else 'Emby','Phone','Install phone'],[key.title() if key!='emby' else 'Emby','Computer','Install desktop']]
    assert all(b['guide_id']==gid and b['url']==f'/admin/design/home/guide/{gid}' for b in error['blockers'])
    with SessionLocal() as db:
        assert (db.get(AccessService,key).access_published,db.get(AccessService,key).access_version)==before
        assert db.get(Guide,gid).published is None
    assert article(client,gid,'save',content()).json()['publication_state']=='unpublished'
    assert journey(client,key,'publish',value).status_code==400
    assert article(client,gid,'publish',content()).json()['publication_state']=='published'
    result=journey(client,key,'publish',value);assert result.status_code==200
    assert next(g for g in result.json()['guides'] if g['id']==gid)['publication_state']=='published'
    assert 'First public instructions' in client.get(f'/access/{key}/guide/{gid}').text
    assert article(client,gid,'save',content('Unpublished new instructions')).json()['publication_state']=='changes'
    editor=boot(client,f'/admin/design/home/guide/{gid}');assert editor['publication_state']=='changes'
    assert journey(client,key,'publish',value).status_code==200
    page=client.get(f'/access/{key}/guide/{gid}').text
    assert 'First public instructions' in page and 'Unpublished new instructions' not in page
    assert article(client,gid,'publish',content('Unpublished new instructions')).json()['publication_state']=='published'
    assert 'Unpublished new instructions' in client.get(f'/access/{key}/guide/{gid}').text


def test_root_guide_blocker_is_localized_and_unused_guides_do_not_block_links(client):
    value=prepare(client,'seerr')
    gid=journey(client,'seerr','new-guide',{'title':'Instructions téléphone'}).json()['id']
    with SessionLocal() as db:
        db.scalar(select(User).where(User.emby_id=='admin-1')).locale='fr';db.commit()
    value.update(mode='guide',guide_id=gid)
    response=journey(client,'seerr','publish',value);assert response.status_code==400
    error=response.json()
    assert error['detail']=='Publiez les guides ci-dessous avant de publier ce parcours.'
    assert error['blockers'][0]['title']=='Instructions téléphone'
    value.update(mode='link')
    assert journey(client,'seerr','publish',value).status_code==200


def test_publication_state_compares_content_and_authorization_is_retained(client):
    value=prepare(client,'seerr')
    gid=journey(client,'seerr','new-guide',{'title':'Private draft'}).json()['id']
    assert article(client,gid,'publish',content()).status_code==200
    with SessionLocal() as db:
        row=db.get(Guide,gid);row.draft=json.dumps(json.loads(row.published),sort_keys=True,indent=2);db.commit()
        assert visual_howto.publication_state(row)=='published'
    editor=client.get(f'/admin/design/home/guide/{gid}').text
    assert 'Publish guide' in editor and 'howto-publication' in editor
    assert 'Publish journey' in client.get('/admin/design/home/howto/seerr').text
    assert article(client,gid,'unpublish',content()).json()['publication_state']=='unpublished'
    logout(client);login_user(client)
    assert client.get('/admin/design/home/howto/seerr').status_code==403
    denied=post(client,'/admin/visual-howto/seerr/publish',{'version':'0','payload':json.dumps(value)},'/home')
    assert denied.status_code==403 and 'blockers' not in denied.text
