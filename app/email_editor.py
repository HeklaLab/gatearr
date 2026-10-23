"""Localized email editor and unified account language settings."""
from html import escape
from fastapi import APIRouter,Request,Depends,HTTPException
from .main import form,require_admin,require_user,render,redirect,set_config,limit
from .models import User
from .mailer import config,DEFAULTS,mail_template,html_source,send
from .settings import settings
from .rich_mail import clean,validate,interpolate,plain,document
from . import i18n

router=APIRouter()
ALL_PURPOSES={'new_season':'New season notification'}
PURPOSES={'invite':'Invitation','verify':'Address verification','reset':'Password recovery','email_changed':'Email changed notification','password_changed':'Password changed notification'}

def purposes(db):
    from .tracearr import configured
    return {**PURPOSES,**(ALL_PURPOSES if configured(db) else {})}

def language(request,value,all=False):
    if value not in i18n.languages(request.state.db,all=all):raise ValueError('Invalid language')
    return value

def value(db,key,locale):
    purpose,part=key.rsplit('_',1)
    source=html_source(db,purpose) if part=='html' else config(db,key,DEFAULTS[key])
    return i18n.content(db,'mail:'+purpose+':'+part,source,locale)

def editor(request,purpose,locale,subject=None,html=None,notice=''):
    db=request.state.db
    subject=value(db,purpose+'_subject',locale) if subject is None else subject
    if html is None:
        html=value(db,purpose+'_html',locale)
    html=clean(html)
    sample={'app_name':config(db,'app_name',settings.app_name),'username':'Alex','minutes':'30','title':'Fargo','season':'5','link':config(db,'public_url',settings.public_url)+('/reset?token=preview' if purpose=='reset' else '/library/open/preview' if purpose=='new_season' else '/verify-email?token=preview')}
    preview=document(interpolate(html,sample))
    return render(request,'mail_editor.html',edit_locale=locale,mail_languages=i18n.languages(db),purpose=purpose,purposes=purposes(db),subject=subject,html=html,mail_preview=preview,notice=notice,edit_language_name=i18n.languages(db)[locale],source_stamp=i18n.source_hash(config(db,purpose+'_subject',DEFAULTS[purpose+'_subject'])+'\n'+html_source(db,purpose)))

@router.get('/admin/mail-editor')
def page(request:Request):
    require_admin(request)
    purpose=request.query_params.get('purpose','invite')
    if purpose not in purposes(request.state.db):raise HTTPException(404,'Template not found')
    locale=request.query_params.get('mail_locale',i18n.default_language(request.state.db))
    if locale not in i18n.languages(request.state.db):return redirect('/admin/mail-editor?purpose='+purpose+'&mail_locale='+i18n.default_language(request.state.db))
    return editor(request,purpose,locale)

@router.post('/admin/mail-editor')
def save(request:Request,data=Depends(form)):
    admin=require_admin(request)
    purpose=str(data.get('purpose','invite'))
    if purpose not in purposes(request.state.db):raise ValueError('Template not found')
    locale=language(request,data.get('mail_locale',i18n.default_language(request.state.db)),all=False)
    stamp=i18n.source_hash(config(request.state.db,purpose+'_subject',DEFAULTS[purpose+'_subject'])+'\n'+html_source(request.state.db,purpose))
    if data.get('source_hash') and data['source_hash']!=stamp:raise HTTPException(409,'The source text has changed. Reload the translation page.')
    subject=validate(str(data.get('subject','')),subject=True)
    html=validate(str(data.get('html','')),html=True)
    action=data.get('action','save')
    if action=='preview':return editor(request,purpose,locale,subject,html)
    if action=='test':
        limit(request,'mail_preview_test',str(admin.id),maximum=5)
        # Render without saving the draft or producing a real verification token.
        # Use a nested transaction so the regular SMTP path can send this unsaved draft.
        db=request.state.db
        with db.begin_nested() as transaction:
            if locale=='en' and i18n.default_language(request.state.db)=='en':
                set_config(db,purpose+'_subject',subject);set_config(db,purpose+'_html',html)
            else:
                i18n.store_content(db,'mail:'+purpose+':subject',config(db,purpose+'_subject',DEFAULTS[purpose+'_subject']),locale,subject)
                i18n.store_content(db,'mail:'+purpose+':html',html_source(db,purpose),locale,html)
            db.flush()
            try:send(db,admin.email,purpose,{'app_name':config(db,'app_name',settings.app_name),'username':admin.name,'link':config(db,'public_url',settings.public_url)+('/reset?token=preview' if purpose=='reset' else '/library/open/preview' if purpose=='new_season' else '/verify-email?token=preview'),'minutes':'30','title':'Fargo','season':'5','_locale':locale,'_allow_disabled':True})
            except Exception:raise HTTPException(503,'SMTP failed. Check host, TLS, credentials and sender.')
            finally:transaction.rollback()
        return editor(request,purpose,locale,subject,html,'Test email sent. The draft has not been saved.')
    if action!='save':raise ValueError('Invalid action')
    db=request.state.db
    if locale=='en' and i18n.default_language(request.state.db)=='en':
        for part,item in {'subject':subject,'html':html,'body':plain(html)}.items():set_config(db,purpose+'_'+part,item)
    else:
        for part,item in {'subject':subject,'html':html,'body':plain(html)}.items():
            source=html_source(db,purpose) if part=='html' else config(db,purpose+'_'+part,DEFAULTS[purpose+'_'+part])
            i18n.store_content(db,'mail:'+purpose+':'+part,source,locale,item)
    request.state.db.commit()
    return redirect('/admin/mail-editor?purpose='+purpose+'&mail_locale='+locale+'&saved=1')

@router.post('/account/language')
def account_language(request:Request,data=Depends(form)):
    user=require_user(request)
    user.locale=language(request,data.get('locale',i18n.default_language(request.state.db)))
    user.preferences_version+=1
    request.state.db.commit()
    from .integrations import queue_user
    queue_user(request.state.db,user,force=True)
    return redirect('/account?saved=language')

@router.post('/admin/users/{local_id}/language')
def member_language(request:Request,local_id:int,data=Depends(form)):
    require_admin(request)
    user=request.state.db.get(User,local_id)
    if not user or not user.emby_id:raise HTTPException(404,'Emby account not found')
    user.locale=language(request,data.get('locale',i18n.default_language(request.state.db)))
    user.preferences_version+=1
    request.state.db.commit()
    from .integrations import queue_user
    queue_user(request.state.db,user,force=True)
    return redirect('/admin/users/'+str(local_id)+'?saved=language')
