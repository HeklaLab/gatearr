"""Bounded audit metadata: never request bodies, query strings, headers or credentials."""
import time,json,logging
from fastapi import APIRouter,Request
from sqlalchemy import select,delete
from .models import AuditEvent,User
from .db import SessionLocal
from .mailer import config
log=logging.getLogger('gatearr.audit')
router=APIRouter()
def record(actor,subject,action,outcome,detail=''):
    with SessionLocal() as db:
        actor_name=db.get(User,actor).name if actor and db.get(User,actor) else 'Guest'
        subject_name=db.get(User,subject).name if subject and db.get(User,subject) else ''
        payload=json.dumps({'actor':actor_name,'user':subject_name,'changes':detail},ensure_ascii=False)
        db.add(AuditEvent(at=int(time.time()),actor_id=actor,subject_id=subject,action=action.replace('\n',' ').replace('\r',' ')[:200],outcome=outcome,detail=payload[:10000]))
        db.execute(delete(AuditEvent).where(AuditEvent.at<int(time.time())-90*86400))
        cutoff=db.scalar(select(AuditEvent.id).order_by(AuditEvent.id.desc()).offset(99999).limit(1))
        if cutoff:db.execute(delete(AuditEvent).where(AuditEvent.id<cutoff))
        db.commit()
    log.info('action=%s actor=%s user=%s status=%s changes=%s',action.replace('\n',' ').replace('\r',' '),actor_name,subject_name,outcome,detail.replace('\n',' ')[:1000])

@router.get('/admin/activity')
def activity(request:Request):
    from .main import require_admin,render
    require_admin(request)
    before=int(request.query_params.get('before','2147483647'))
    query=select(AuditEvent).where(AuditEvent.id<before).order_by(AuditEvent.id.desc()).limit(100)
    if request.query_params.get('all')!='1':query=query.where(~AuditEvent.action.like('GET %'),~AuditEvent.action.like('HEAD %'))
    events=list(request.state.db.scalars(query))
    names={u.id:u.name for u in request.state.db.scalars(select(User))}
    from . import i18n
    overrides={}  # Audit labels always use the bundled administration translations.
    tr=lambda text:i18n.translate(text,request.state.locale,overrides=overrides)
    entries=[]
    for event in events:
        try:detail=json.loads(event.detail)
        except (ValueError,TypeError):detail={'changes':event.detail}
        entries.append({'id':event.id,'at':event.at,'actor':detail.get('actor') or names.get(event.actor_id,'Guest'),'user':detail.get('user') or names.get(event.subject_id,'—'),'action':' · '.join(tr(part) for part in action_label(event.action).split(' · ')),'changes':friendly_changes(detail.get('changes',''),tr),'outcome':event.outcome})
    return render(request,'activity.html',events=entries)


def action_label(action):
    direct={'account.username':'Username updated','account.deactivate':'Account deactivated and passwords rotated','account.reactivate':'Account reactivated; recovery allowed','permissions.seerr':'Seerr permissions updated','seerr.quotas':'Request quotas updated','content.reset':'Customized content reset','auth.login':'Signed in','assistance.start':'Started user assistance','assistance.stop':'Ended user assistance','account.email':'Updated account email','account.password':'Changed account password','account.invite':'Sent verification invitation','account.reset':'Sent password reset link'}
    if action in direct:return direct[action]
    if action.startswith('tool.'):return 'Tool request · '+action[5:].replace('.',' · ')
    method,_,path=action.partition(' ')
    labels={'/account/subtitles/language':'Subtitle preferences saved.','/admin/bazarr/subtitles':'Subtitle languages','/admin/assets':'Uploaded portal image','/reset':'Password reset','/verify-email':'Email verified','/account/preferences':'Notification preferences updated','/admin/groups':'User group created','/admin/import':'Media users imported','/admin/user-email':'User email updated','/admin/mail-editor':'Email template updated','/admin/mail-templates':'Email templates updated','/admin/updates/settings':'Update notification settings changed','/admin/updates/check':'Checked for updates','/admin/settings':'Portal identity updated','/admin/smtp':'SMTP settings updated','/admin/tools':'Tool connections updated','/admin/integrations':'API connection updated','/admin/menu':'Service saved','/admin/menu/delete':'Service deleted','/admin/footer':'Footer updated','/admin/branding/themes':'Theme updated','/admin/emby/libraries':'Library access updated','/admin/emby/clone':'Media account created/cloned','/admin/emby/copy':'User settings copied','/account/email':'Email confirmation requested','/account/password':'Password changed','/account/language':'Language updated','/logout':'Signed out','/forgot':'Account recovery requested'}
    if method=='POST':
        if path.startswith('/admin/design/'):
            page={'login':'Login screen','home':'Portal','footer':'Footer'}.get(path.split('/')[3],'Portal')
            verb={'save':'Draft saved','publish':'Page published','restore':'Published page restored'}.get(path.split('/')[-1],'Settings updated')
            return page+' · '+verb
        if path.startswith('/admin/visual-howto/') or path.startswith('/admin/visual-guide/'):return 'Access guide updated'
        if path in labels:return labels[path]
        if path.endswith('/permission'):return 'User permission updated'
        if path.endswith('/role'):return 'User admin/tool permissions updated'
        if path.startswith('/admin/groups/'):return 'User group updated'
        if path.startswith('/admin/access/'):return 'Access guide choices updated'
        if path.startswith('/admin/guides/'):return 'Access guide tutorial updated'
        if path.startswith('/admin/portal/'):return 'Portal layout updated'
        if path.startswith('/admin/translations'):return 'Translations updated'
    return 'Viewed a page' if method in ('GET','HEAD') else 'Settings updated'

def describe_form(request,data):
    """Explicit safe metadata only; never copy arbitrary request fields or secrets."""
    db=request.state.db;path=request.url.path
    uid=request.path_params.get('uid') or request.path_params.get('local_id') or (data.get('id') if path in ('/admin/emby/libraries','/admin/emby/copy','/admin/user-email') else None)
    if uid:
        try:request.state.audit_subject=int(uid)
        except (ValueError,TypeError):pass
    fields={'action','field','access_mode','library_mode','position','order','span','region','kind','nav_position','sidebar_position','mode','palette','angle','count','locale','language','notification_mode','service','admin','enabled','new_tab','include_emby','name','label','title','app_name','menu_key','edit_locale','scope','key','code','permission'}
    if path.endswith('/role'):fields.update({'tools'})
    details=[]
    for key in sorted(fields & set(data)):
        values=data.getlist(key);value=', '.join(values)
        previous=config(db,key) if key in ('app_name','login_text') else None
        details.append(key.replace('_',' ')+': '+((previous+' → ') if previous is not None else '')+value[:200])
    if path.endswith('/permission'):
        value=str(data.get('value',''))
        if value in ('true','false','null') or value.replace('.','',1).isdigit():details.append('new value: '+value[:30])
    if 'libraries' in data:details.append('libraries: '+', '.join(data.getlist('libraries'))[:300])
    if 'members' in data:
        ids=[int(x) for x in data.getlist('members') if x.isdigit()]
        details.append('members: '+', '.join(db.scalars(select(User.name).where(User.id.in_(ids))))[:500])
    if path.endswith('/role'):details.append('Gatearr administrator: '+str(data.get('admin')=='on')+'; tools: '+(', '.join(data.getlist('tools')) or 'none'))
    for key in ('smtp_password','api_key','password'):
        if data.get(key):details.append(key.replace('_',' ')+': [hidden]')
    for tool in ('radarr','sonarr','bazarr','tracearr','tdarr'):
        if tool+'_url' in data:
            details.append(tool+': '+('enabled' if data.get(tool+'_enabled')=='on' else 'disabled')+'; private connection edited')
    changed=[key.replace('_',' ') for key in data if key.endswith('_api_key') and data.get(key)]
    if changed:details.append('secrets updated: '+', '.join(changed))
    content=[key for key in data if key.startswith('column_') or key in ('body','html','login_text')]
    if content:details.append('content edited: '+', '.join(content))
    for key in ('email',):
        if data.get(key):
            previous=db.get(User,int(uid)).email if uid and str(uid).isdigit() and db.get(User,int(uid)) else None
            details.append('email: '+(previous or '—')+' → '+str(data[key])[:254])
    request.state.audit_detail='\n'.join(details)


def friendly_changes(value,translate=lambda text:text):
    import re
    match=re.fullmatch(r'(Saved draft|Published): (login|home|footer) page, (\d+) blocks',value)
    if match:return ' · '.join((translate({'login':'Login screen','home':'Portal','footer':'Footer'}[match[2]]),translate('Draft saved' if match[1]=='Saved draft' else 'Page published'),match[3]+' '+translate('blocks')))
    for page in ('Login screen','Portal','Footer'):
        if value.startswith(page+' · '):return translate(page)+' · '+value.split(' · ',1)[1]
    return value
