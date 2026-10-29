"""Independent personal-account functions; presence does not grant feature permissions."""
from copy import deepcopy
import hashlib

BLOCKS=(('account_intro','My account','user'),('account_email','Email address','envelope'),('account_password','Password','key'),('account_notifications','Email notifications','bell'),('account_language','Language','language'),('account_subtitles','Subtitle languages','closed-captioning'),('account_photo','Profile photo','user-circle'))
KINDS={kind for kind,_,_ in BLOCKS}
OPTIONAL={'account_intro','account_notifications','account_language','account_photo'}

def default_blocks():
    return [dict(id=kind.replace('_','-'),kind=kind,region='main',order=(i+1)*10,span=6 if kind in ('account_email','account_password') else 12,title='Hello, {name}.' if kind=='account_intro' else label,body='Your services at your fingertips.' if kind=='account_intro' else '') for i,(kind,label,_) in enumerate(BLOCKS)]

def normalize(value):
    """Split legacy monoliths in memory, retaining independent draft/public snapshots."""
    value=deepcopy(value);result=[];used={b['id'] for b in value['blocks']}
    for old in value['blocks']:
        if old['kind']!='account_form':result.append(old);continue
        children=default_blocks()
        wrapper=bool(old.get('parent') or old.get('style') or old['span']!=12)
        if wrapper:result.append({**old,'kind':'columns','columns':1,'title':'','body':''})
        for i,b in enumerate(children):
            seed=old['id']+':'+b['kind'];ident='acct-'+hashlib.sha256(seed.encode()).hexdigest()[:24]
            while ident in used:ident='acct-'+hashlib.sha256(ident.encode()).hexdigest()[:24]
            used.add(ident);b['id']=ident;b['region']=old['region']
            if wrapper:b.update(parent=old['id'],slot=0)
            if b['kind']=='account_intro':b.update(title=old.get('title','Hello, {name}.'),body=old.get('body','Your services at your fingertips.'))
            result.append(b)
    for i,b in enumerate(result):b['order']=(i+1)*10
    value['blocks']=result
    return value

def builder_data(db):
    from .bazarr_subtitles import offered
    required={'account_email','account_password'}
    if offered(db):required.add('account_subtitles')
    return [dict(kind=kind,label=label,icon=icon,required=kind in required) for kind,label,icon in BLOCKS]

def missing_required(db,value):
    present={b['kind'] for b in value['blocks'] if b.get('region')!='login'}
    return [entry for entry in builder_data(db) if entry['required'] and entry['kind'] not in present]

def visible(db,user,kind):
    if kind=='account_language':
        from .i18n import languages
        return len(languages(db))>1
    if kind=='account_notifications':
        from .preferences import available_notifications
        return any(available_notifications(db,user).values())
    if kind=='account_subtitles':
        from .bazarr_subtitles import offered
        return bool(user and user.bazarr_subtitles and offered(db))
    return True
