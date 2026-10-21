"""Observed and group-managed Seerr request quotas."""
from alembic import op
import sqlalchemy as sa
revision='0018'
down_revision='0017'
branch_labels=depends_on=None

def upgrade():
    op.create_table('seerr_quota_states',sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='CASCADE'),primary_key=True),*[sa.Column(k,sa.Text(),nullable=False,server_default='{}') for k in ('baseline','individual','desired','observed')],sa.Column('version',sa.Integer(),nullable=False,server_default='0'),sa.Column('pending',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('error',sa.String(120),nullable=False,server_default=''),sa.Column('checked_at',sa.Integer(),nullable=True),sa.Column('connection',sa.String(64),nullable=False,server_default=''))
    # Upgrade only the untouched former Seerr factory guide; customized guides stay intact.
    import json
    connection=op.get_bind()
    row=connection.execute(sa.text("SELECT entry_mode,access_draft,access_published FROM access_services WHERE key='seerr'")).first()
    if row and row[0]=='structured':
        try:
            draft=json.loads(row[1] or '[]');published=json.loads(row[2] or '[]')
            untouched=lambda nodes:len(nodes)==1 and nodes[0].get('id')=='browser' and nodes[0].get('kind')=='browser' and nodes[0].get('title')=='Open Seerr' and not nodes[0].get('parent')
            authored=connection.execute(sa.text("SELECT count(*) FROM guides WHERE service_key='seerr'")).scalar()
            if not authored and untouched(draft) and untouched(published):
                connection.execute(sa.text("UPDATE access_services SET entry_mode='direct',access_draft='[]',access_published='[]',access_version=access_version+1 WHERE key='seerr'"))
        except (ValueError,TypeError,AttributeError):pass
def downgrade():op.drop_table('seerr_quota_states')
