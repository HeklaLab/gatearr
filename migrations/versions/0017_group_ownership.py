"""Single group ownership without discarding effective permissions."""
from alembic import op
import sqlalchemy as sa
import json
revision='0017'
down_revision='0016'
branch_labels=depends_on=None

def upgrade():
    # Validate before any SQLite DDL: an aborted upgrade must be retryable.
    connection=op.get_bind()
    missing=connection.execute(sa.text('SELECT gm.user_id FROM group_members gm LEFT JOIN policy_states p ON p.user_id=gm.user_id GROUP BY gm.user_id HAVING count(*)>1 AND max(p.user_id) IS NULL')).first()
    if missing:raise RuntimeError('A multi-group user has no observed policy snapshot; open that user in Gatearr 0.3.1 before retrying the upgrade.')
    op.add_column("users",sa.Column("portal_disabled",sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column("users",sa.Column("disable_status",sa.Text(),nullable=False,server_default="{}"))
    op.add_column('permission_groups',sa.Column('access_policy',sa.Text(),nullable=False,server_default='{}'))
    op.create_table('group_baselines',sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='CASCADE'),primary_key=True),sa.Column('values',sa.Text(),nullable=False))
    c=op.get_bind()
    for uid,name,admin,tools in c.execute(sa.text('SELECT id,name,admin,tool_access FROM users')).all():
        groups=c.execute(sa.text('SELECT group_id FROM group_members WHERE user_id=:uid'),{'uid':uid}).all()
        if not groups:continue
        row=c.execute(sa.text('SELECT desired,overrides FROM policy_states WHERE user_id=:uid'),{'uid':uid}).first()
        overrides=json.loads(row[1]) if row else {}
        if len(groups)>1 or overrides:
            if len(groups)>1 and not row:raise RuntimeError('A multi-group user has no observed policy snapshot; open that user in Gatearr 0.3.1 before retrying the upgrade.')
            policy={k:v for k,v in json.loads(row[0] or '{}').items() if k not in ('IsAdministrator','IsDisabled')} if row else {}
            values={'gatearr_admin':bool(admin),'tools':json.loads(tools or '[]'),'seerr_access':True}
            gid=c.execute(sa.text('SELECT coalesce(max(id),0)+1 FROM permission_groups')).scalar()
            c.execute(sa.text('INSERT INTO permission_groups(id,name,policy,version,access_policy) VALUES (:gid,:name,:policy,0,:access)'),{'gid':gid,'name':'Migrated #'+str(uid)+' · '+name[:65],'policy':json.dumps(policy),'access':json.dumps(values)})
            c.execute(sa.text('DELETE FROM group_members WHERE user_id=:uid'),{'uid':uid})
            c.execute(sa.text('INSERT INTO group_members VALUES (:gid,:uid)'),{'gid':gid,'uid':uid})
        if row:c.execute(sa.text("UPDATE policy_states SET overrides='{}' WHERE user_id=:uid"),{'uid':uid})
    op.create_index('uq_group_members_user','group_members',['user_id'],unique=True)
    op.create_table('seerr_policy_states',sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='CASCADE'),primary_key=True),*[sa.Column(k,sa.Integer(),nullable=True) for k in ('baseline','individual','desired','observed')],sa.Column('version',sa.Integer(),nullable=False,server_default='0'),sa.Column('pending',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('error',sa.String(120),nullable=False,server_default=''),sa.Column('checked_at',sa.Integer(),nullable=True),sa.Column('connection',sa.String(64),nullable=False,server_default=''))
    op.create_table('seerr_summaries',sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='CASCADE'),primary_key=True),sa.Column('role',sa.String(10),primary_key=True),sa.Column('data',sa.Text(),nullable=False),sa.Column('checked_at',sa.Integer(),nullable=False),sa.Column('connection',sa.String(64),nullable=False))

def downgrade():
    c=op.get_bind()
    if c.execute(sa.text('SELECT count(*) FROM users WHERE portal_disabled=1')).scalar():
        raise RuntimeError('Reactivation or a pre-upgrade backup is required before downgrading disabled accounts.')
    op.drop_table('seerr_summaries')
    op.drop_table('seerr_policy_states')
    op.drop_index('uq_group_members_user',table_name='group_members')
    op.drop_table('group_baselines')
    op.drop_column('permission_groups','access_policy')
    op.drop_column('users','portal_disabled')
    op.drop_column('users','disable_status')
