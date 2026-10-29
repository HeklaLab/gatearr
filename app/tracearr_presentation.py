"""Separate member statistics from the native, administrator-only Tracearr interface."""
from copy import deepcopy


def admin_row(block):
    audience=block.get('audience')
    return (not audience.get('everyone') and audience.get('admins') and not audience.get('groups')) if audience else block.get('visibility')=='admins'


def statistics_block(ident='tracearr-statistics',order=30,**options):
    return dict(id=ident,kind='widget_tracearr',region='main',span=12,order=order,title='',body='',show_logo=True,metrics=options.get('metrics',['watch_time','favorite']),period=options.get('period','week'),**{k:v for k,v in options.items() if k in ('visibility','audience','groups','priority')})


def normalize(value,db):
    value=deepcopy(value)
    if value.get('page','home')!='home':return value
    rows=value['blocks'];used={b['id'] for b in rows};moved=False;old_info=None;old_audience={};old_behavior=None
    def unique(seed):
        base=seed;n=1
        while seed in used:n+=1;seed=base+'-'+str(n)
        used.add(seed);return seed
    for row in rows:
        if row['kind']!='applications' or 'tracearr' not in row.get('applications',[]):continue
        info=row.get('information',{}).pop('tracearr',None)
        if info is not None and old_info is None:old_info=info;old_audience={k:deepcopy(row[k]) for k in ('visibility','audience') if k in row}
        behavior=row.get('application_behaviors',{}).get('tracearr')
        if behavior and behavior.get('mode')=='guide':behavior['mode']='embedded'
        if old_behavior is None and behavior:old_behavior=deepcopy(behavior)
        if admin_row(row):continue
        row['applications']=[key for key in row['applications'] if key!='tracearr'];moved=True
        row['columns']=max(1,min(row.get('columns',3),len(row['applications'])))
    if moved:
        if not any(b['kind']=='applications' and admin_row(b) and 'tracearr' in b.get('applications',[]) for b in rows):
            target=next((b for b in rows if b['kind']=='applications' and admin_row(b) and len(b.get('applications',[]))<6),None)
            if target:
                target['applications'].append('tracearr');target['columns']=max(target.get('columns',1),len(target['applications']))
                if old_behavior:target.setdefault('application_behaviors',{})['tracearr']=old_behavior
            else:
                target=dict(id=unique('tracearr-admin'),kind='applications',region='main',span=12,order=50,columns=1,applications=['tracearr'],information={},visibility='admins',title='',body='')
                if old_behavior:target['application_behaviors']={'tracearr':old_behavior}
                idx=next((i for i,b in enumerate(rows) if b['kind']=='applications' and b.get('applications')==['account']),len(rows));rows.insert(idx,target)
        rows[:]=[b for b in rows if not (b['kind']=='applications' and not b.get('applications') and not b.get('title') and not b.get('body'))]
    from .tracearr import configured
    if (moved or old_info is not None) and configured(db) and not any(b['kind']=='widget_tracearr' for b in rows):
        options={**(old_info or {}),**old_audience};options.pop('enabled',None)
        stats=statistics_block(unique('tracearr-statistics'),**options)
        target=next((i for i,b in enumerate(rows) if b['kind']=='applications' and admin_row(b)),len(rows))
        rows.insert(target,stats)
    for i,b in enumerate(rows):b['order']=(i+1)*10
    return value
