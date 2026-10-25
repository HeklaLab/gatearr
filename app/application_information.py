"""Application-card metrics, including lossless legacy widget settings."""
from copy import deepcopy
from . import widgets

KINDS={'access:emby':'widget_media','access:seerr':'widget_seerr'}

def validate(settings):
    if not isinstance(settings,dict) or set(settings)-set(KINDS):raise ValueError('Invalid application information')
    for key,value in settings.items():
        if not isinstance(value,dict) or type(value.get('enabled',True)) is not bool:raise ValueError('Invalid application information')
        widgets.validate(dict(value,kind=KINDS[key]))
        rules=value.get('rules',[])
        if not isinstance(rules,list) or len(rules)>50:raise ValueError('Invalid application information rules')
        for rule in rules:
            if not isinstance(rule,dict) or rule.get('visibility','everyone') not in ('everyone','admins','members') or type(rule.get('order',10)) is not int:raise ValueError('Invalid application information audience')
            widgets.validate(dict(rule,kind=KINDS[key]))

def display(db,user,key,settings,editor=False):
    if key not in KINDS or not settings.get('enabled',True):return None
    options={k:v for k,v in settings.items() if k not in ('enabled','rules')}
    if 'rules' in settings:
        rules=[dict(rule,id='application-info-'+str(i),kind=KINDS[key],order=rule.get('order',10)) for i,rule in enumerate(settings['rules'])]
        chosen=widgets.choose(db,rules,user,editor)
        rule=next((r for r in rules if r['id'] in chosen),None)
        if not rule:return None
        # Current card controls supersede migrated defaults, while audiences stay intact.
        options={**rule,**options}
    result=widgets.display(db,user,dict(options,kind=KINDS[key]),editor)
    return result if result and (result.get('metrics') or result.get('message')) else None

def migrate(layout):
    index={b['id']:b for b in layout['blocks']}
    legacy={key:[b for b in layout['blocks'] if b['kind']==kind] for key,kind in KINDS.items()}
    # Keep audiences even if their application is temporarily absent from the layout.
    retained=layout.setdefault('application_information_defaults',{})
    for key,rows in legacy.items():
        if not rows:continue
        rules=[]
        for source in rows:
            rule=deepcopy(source);parent=rule.pop('parent',None);seen=set();hidden=False
            while parent and parent in index and parent not in seen:
                seen.add(parent);owner=index[parent];visibility=owner.get('visibility','everyone')
                if visibility!='everyone':
                    if rule.get('visibility','everyone') not in ('everyone',visibility):hidden=True
                    rule['visibility']=visibility
                parent=owner.get('parent')
            if not hidden:rules.append(rule)
        retained[key]={'enabled':True,'rules':rules}
    for block in layout['blocks']:
        if block['kind']!='applications':continue
        settings=block.setdefault('information',{})
        for key in block.get('applications',[]):
            if key in KINDS and key not in settings:settings[key]=deepcopy(retained.get(key,{'enabled':True}))
    removed={b['id'] for rows in legacy.values() for b in rows}
    parents={b.get('parent') for rows in legacy.values() for b in rows}
    layout['blocks']=[b for b in layout['blocks'] if b['id'] not in removed]
    # Only remove containers emptied by this migration, keeping authored empty columns.
    while parents:
        empty={p for p in parents if p in index and index[p]['kind']=='columns' and not any(b.get('parent')==p for b in layout['blocks'])}
        if not empty:break
        parents={index[p].get('parent') for p in empty}
        layout['blocks']=[b for b in layout['blocks'] if b['id'] not in empty]
    return layout
