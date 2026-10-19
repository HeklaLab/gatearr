"""Group permissions, verified policy snapshots and one-use Seerr login bridge."""
import json
import sqlalchemy as sa
from alembic import op
revision='0012'
down_revision='0011'
branch_labels=depends_on=None

def upgrade():
    op.create_table('permission_groups',sa.Column('id',sa.Integer,primary_key=True),sa.Column('name',sa.String(100),nullable=False,unique=True),sa.Column('policy',sa.Text,nullable=False),sa.Column('version',sa.Integer,nullable=False))
    op.create_table('group_members',sa.Column('group_id',sa.Integer,sa.ForeignKey('permission_groups.id',ondelete='CASCADE'),primary_key=True),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id',ondelete='CASCADE'),primary_key=True))
    op.create_table('policy_states',sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id',ondelete='CASCADE'),primary_key=True),*[sa.Column(k,sa.Text,nullable=False) for k in ('baseline','overrides','desired','observed','confirmed')],sa.Column('version',sa.Integer,nullable=False),sa.Column('pending',sa.Boolean,nullable=False),sa.Column('error',sa.String(100),nullable=False),sa.Column('checked_at',sa.Integer))
    op.create_table('seerr_sessions',sa.Column('session_digest',sa.String(64),sa.ForeignKey('sessions.digest',ondelete='CASCADE'),primary_key=True),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('payload',sa.Text,nullable=False),sa.Column('expires',sa.Integer,nullable=False))
    op.create_table('seerr_tickets',sa.Column('digest',sa.String(64),primary_key=True),sa.Column('session_digest',sa.String(64),sa.ForeignKey('seerr_sessions.session_digest',ondelete='CASCADE'),nullable=False),sa.Column('expires',sa.Integer,nullable=False))
    db=op.get_bind()
    old={'accent':'#b9f479','button_hover':'#ccff96','bg':'#10151b','surface':'#1a222c','text':'#edf3f9','muted':'#aab8c9'}
    new={'accent':'#159eff','button_hover':'#45cdf4','bg':'#edf4ff','surface':'#ffffff','text':'#12234a','muted':'#526789','ink':'#051c40'}
    for key,raw in db.execute(sa.text("SELECT key,value FROM config WHERE key IN ('portal_draft','portal_published')")):
        value=json.loads(raw)
        if all(value.get('theme',{}).get(k,v)==v for k,v in old.items()):
            value['theme']=new;db.execute(sa.text('UPDATE config SET value=:value WHERE key=:key'),{'key':key,'value':json.dumps(value)})
    db.execute(sa.text("INSERT INTO access_services(key,name,browser_url,server_url,icon_url,entry_mode,access_draft,access_published,access_version) SELECT 'seerr','Seerr','','','','structured',NULL,NULL,0 WHERE NOT EXISTS (SELECT 1 FROM access_services WHERE key='seerr')"))
    nodes=json.dumps([{'id':'browser','kind':'browser','parent':'','title':'Open Seerr','position':0,'icon_url':''}])
    db.execute(sa.text("UPDATE access_services SET access_draft=:nodes,access_published=:nodes WHERE key='seerr' AND access_draft IS NULL AND access_published IS NULL"),{'nodes':nodes})

def downgrade():
    for table in ('seerr_tickets','seerr_sessions','policy_states','group_members','permission_groups'):op.drop_table(table)
