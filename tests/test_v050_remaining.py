import json
from copy import deepcopy
import pytest
from sqlalchemy import select
from app import main,portal,visual_builder,page_builder,mailer
from app.db import SessionLocal
from app.models import User,PermissionGroup,GroupMember,ContentPage,Config
from app.block_audience import eligible
from app.rich_mail import clean
from test_portal import setup,post,logout,reset_token


def test_multiline_mail_alignment_survives_sanitization():
    raw='<p style="text-align:center">Contact<div>support@example.test</div><div>Next line</div></p>'
    result=clean(raw)
    assert result.startswith('<div style="text-align:center">')
    assert '<div>Next line</div></div>' in result
    assert clean(result)==result


@pytest.mark.parametrize('src',['/static/gatearr-logo.png','http://testserver/static/gatearr-logo.png','/media/icons/'+('a'*64)+'.png'])
def test_logo_template_real_send_path_with_smtp_capture(client,monkeypatch,src):
    setup(client);captured=[]
    class SMTP:
        def __init__(self,*a,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def ehlo(self):pass
        def send_message(self,message):captured.append(message);return {}
    monkeypatch.setattr(mailer.smtplib,'SMTP',SMTP)
    with SessionLocal() as db:
        for k,v in {'smtp_host':'capture','smtp_mode':'plain','smtp_from':'gatearr@example.test'}.items():main.set_config(db,k,v)
        db.commit()
    payload={'purpose':'invite','mail_locale':'en','subject':'Welcome','html':'<img src="'+src+'" width="200" alt="Gatearr"><p>Edited text</p><a href="${link}">Open</a>','action':'test'}
    response=post(client,'/admin/mail-editor',payload,'/admin/mail-editor')
    assert response.status_code==200
    assert len(captured)==1
    html=captured[0].get_body(preferencelist=('html',)).get_content()
    assert ('http://testserver'+src if src.startswith('/') else src) in html and 'Edited text' in html


def test_system_pages_independent_drafts_forms_captcha_and_reset_security(client):
    setup(client)
    with SessionLocal() as db:
        for k in ['captcha_login','captcha_forgot']:main.set_config(db,k,'true')
        db.commit()
    for page,form in [('login','/login'),('forgot','/forgot'),('reset','/reset')]:
        with SessionLocal() as db:value=visual_builder.load(db,page,True);version=visual_builder.version(db,page)
        preview=post(client,'/admin/design/'+page+'/preview',{'payload':json.dumps(value)},'/admin')
        assert preview.status_code==200 and 'action="'+form+'"' in preview.text
        assert ('captcha-preview' in preview.text)==(page!='reset')
        assert '<cap-widget' not in preview.text
        value['blocks'][-1]['title']='Custom '+page
        assert post(client,'/admin/design/'+page+'/publish',{'payload':json.dumps(value),'version':version},'/admin').status_code==200
        with SessionLocal() as db:assert visual_builder.load(db,page)['blocks'][-1]['title']=='Custom '+page
        value['blocks']=[]
        assert post(client,'/admin/design/'+page+'/save',{'payload':json.dumps(value),'version':version+1},'/admin').status_code==400
    assert client.get('/reset?token=invalid').status_code==400
    assert 'Custom forgot' in client.get('/forgot').text


def test_page_unpublish_delete_restore_and_duplicate_address(client):
    setup(client)
    response=post(client,'/admin/pages',{'title':'Unique','slug':'unique','preset':'blank'},'/admin/pages');assert response.status_code==303
    key=response.headers['location'].split('/')[-1]
    with SessionLocal() as db:
        row=page_builder.row_for(db,key);value=json.loads(row.draft);version=row.version
    assert post(client,'/admin/design/'+key+'/publish',{'payload':json.dumps(value),'version':version},'/admin').status_code==200
    assert client.get('/pages/unique').status_code==200
    assert post(client,'/admin/pages/'+key+'/unpublish',{'version':version+1},'/admin/pages').status_code==303
    assert client.get('/pages/unique').status_code==404
    with SessionLocal() as db:assert not page_builder.row_for(db,key).enabled and page_builder.row_for(db,key).published and page_builder.row_for(db,key).draft
    assert post(client,'/admin/pages/'+key+'/archive',{'version':version+2},'/admin/pages').status_code==303
    assert post(client,'/admin/pages/'+key+'/restore',{'version':version+3},'/admin/pages').status_code==303
    assert client.get('/pages/unique').status_code==404
    # Home is never a deletable ContentPage.
    assert post(client,'/admin/pages/home/archive',{'version':0},'/admin/pages').status_code==404


def test_combined_audiences_ordinary_blocks_and_widgets(client):
    setup(client)
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.admin.is_(True)))
        group=PermissionGroup(name='Audience group');db.add(group);db.flush()
        # Administrator status alone does not bypass a group-only audience.
        block={'audience':{'everyone':False,'admins':False,'groups':[group.id]}}
        assert not eligible(db,owner,block)
        block['audience']['admins']=True;assert eligible(db,owner,block)
        block['audience']={'everyone':False,'admins':False,'groups':[]};assert not eligible(db,owner,block)
        block['audience']['everyone']=True;assert eligible(db,owner,block)
        layout=portal.load(db,True);layout['blocks']=[dict(id='private',kind='text',title='Audience secret',body='',span=12,region='main',order=10,audience={'everyone':False,'admins':False,'groups':[]})]
        assert not any(b['id']=='private' for b in portal.for_display(layout,'en',owner,db)['main'])
        assert any(b['id']=='private' for b in portal.for_display(layout,'en',owner,db,True)['main'])


def test_text_style_safe_and_persistent(client):
    setup(client)
    with SessionLocal() as db:value=visual_builder.load(db,'home',True);version=visual_builder.version(db,'home')
    value['blocks']=[dict(id='formatted',kind='text',title='Styled',body='<u><span style="color:#ff0000">Hello</span></u>',rich=True,span=12,order=10,region='main',style=dict(background_mode='gradient',gradient_start='#123456',gradient_end='#abcdef',border_mode='color',border_color='#654321',border_width=2,align='right'))]
    assert post(client,'/admin/design/home/publish',{'payload':json.dumps(value),'version':version},'/admin').status_code==200
    page=client.get('/home').text
    assert 'linear-gradient(135deg,#123456,#abcdef)' in page and 'border:2px solid #654321' in page and '<u>' in page
    value['blocks'][0]['style']['background_image']='https://evil.test/image.png'
    assert post(client,'/admin/design/home/save',{'payload':json.dumps(value),'version':version+1},'/admin').status_code==400


def test_duplicate_address_json_is_specific_and_no_page_created(client):
    from test_portal import csrf
    setup(client)
    client.get('/admin/pages')
    with SessionLocal() as db:before=len(list(db.scalars(select(ContentPage))))
    response=client.post('/admin/pages',data={'csrf':csrf(client,'/admin/pages'),'title':'Duplicate','slug':'help','preset':'blank'},headers={'Accept':'application/json'},follow_redirects=False)
    assert response.status_code==400 and response.json()['field']=='slug'
    assert 'already in use' in response.json()['error']
    with SessionLocal() as db:assert len(list(db.scalars(select(ContentPage))))==before


def test_unpublished_guide_is_hidden_from_alias_and_article_routes(client):
    setup(client);client.get('/admin/pages')
    with SessionLocal() as db:
        guide=page_builder.guide_row(db,'emby');key='p-'+str(guide.id);version=guide.version
    assert post(client,'/admin/pages/'+key+'/unpublish',{'version':version},'/admin/pages').status_code==303
    assert client.get('/access/emby?view=guide').status_code==404
    assert client.get('/pages/guide-emby').status_code==404


def test_audience_demonstration_is_admin_only_and_does_not_save(client):
    setup(client)
    with SessionLocal() as db:before=portal.load(db,True)
    assert client.get('/admin/audience-demo').status_code==200
    with SessionLocal() as db:assert portal.load(db,True)==before
    logout(client)
    assert client.get('/admin/audience-demo',follow_redirects=False).status_code in (303,401,403)
