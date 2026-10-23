"""One owning group; explicit group settings override individual controls."""
import json
from sqlalchemy import select,func
from fastapi import HTTPException
from .models import PermissionGroup,GroupMember,GroupBaseline,User

def group_for(db,user):
    return db.scalar(select(PermissionGroup).join(GroupMember).where(GroupMember.user_id==user.id)) if user else None

def unlocked(db,user):
    if group_for(db,user):raise HTTPException(409,'Permissions are managed by this user’s group. Edit the group instead.')

def access_values(user):return {'gatearr_admin':bool(user.admin),'tools':json.loads(user.tool_access),'seerr_access':True}

def seerr_allowed(db,user):
    if not user:return False
    from .mailer import config
    group=group_for(db,user)
    if group:return json.loads(group.access_policy).get('seerr_access',True)
    return config(db,'seerr_access_'+str(user.id),'true')=='true'

def apply_access(db,user,group):
    baseline=db.get(GroupBaseline,user.id)
    if not baseline and not group:return
    if not baseline:
        baseline=GroupBaseline(user_id=user.id,values=json.dumps(access_values(user)));db.add(baseline)
    values=json.loads(baseline.values);values.update(json.loads(group.access_policy) if group else {})
    grant=values.get('gatearr_admin',user.admin)
    if not grant and user.admin and user.active:
        count=db.scalar(select(func.count(User.id)).where(User.admin.is_(True),User.active.is_(True),User.emby_missing.is_(False)))
        if count<=1:raise HTTPException(409,'The last active administrator cannot be removed')
    tools=sorted(values.get('tools',json.loads(user.tool_access)))
    if user.admin!=grant or json.loads(user.tool_access)!=tools:
        user.admin=grant;user.tool_access=json.dumps(tools);user.version+=1
    if not group:db.delete(baseline)
    from .seerr_permissions import group_changed
    group_changed(db,user,group)
