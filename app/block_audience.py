"""One inclusive audience model for every member-page block and widget."""
from sqlalchemy import select
from .models import PermissionGroup,GroupMember

def validate(value,db=None):
    if not isinstance(value,dict) or set(value)-{'everyone','admins','groups'}:raise ValueError('Invalid block audience')
    if any(type(value.get(k,False)) is not bool for k in ('everyone','admins')):raise ValueError('Invalid block audience')
    groups=value.get('groups',[])
    if not isinstance(groups,list) or len(groups)>500 or any(type(g) is not int or g<=0 for g in groups):raise ValueError('Invalid block audience')
    if db is not None and not set(groups)<=set(db.scalars(select(PermissionGroup.id))):raise ValueError('A selected group no longer exists. Reload page settings.')
    return value

def eligible(db,user,block):
    a=block.get('audience')
    if a is not None:
        if a.get('everyone'):return True
        if not user:return False
        groups=set(db.scalars(select(GroupMember.group_id).where(GroupMember.user_id==user.id)))
        return bool(a.get('admins') and user.admin or groups.intersection(a.get('groups',[])))
    # Legacy data retains its exact semantics until explicitly edited.
    v=block.get('visibility','everyone')
    if v=='admins' and (not user or not user.admin) or v=='members' and (not user or user.admin):return False
    if block.get('groups'):
        return bool(user and set(db.scalars(select(GroupMember.group_id).where(GroupMember.user_id==user.id))).intersection(block['groups']))
    return True

def specificity(block):
    a=block.get('audience')
    if a is not None:return 0 if a.get('everyone') else 2 if a.get('groups') else 1
    return 2 if block.get('groups') else 1 if block.get('visibility','everyone')!='everyone' else 0
