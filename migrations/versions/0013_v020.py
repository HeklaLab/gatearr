"""Gatearr 0.2: audit, assistance, themes, tool grants; retire Tracearr integration."""
import sqlalchemy as sa
from alembic import op
revision='0013'
down_revision='0012'
branch_labels=depends_on=None

def upgrade():
    op.add_column('seerr_tickets',sa.Column('actor_digest',sa.String(64),nullable=True))
    op.add_column('users',sa.Column('theme_preference',sa.String(10),nullable=False,server_default='auto'))
    op.add_column('users',sa.Column('tool_access',sa.Text,nullable=False,server_default='[]'))
    op.add_column('icon_assets',sa.Column('mime',sa.String(40),nullable=False,server_default='image/png'))
    op.drop_column('users','newsletter_opt_in')
    op.drop_column('users','newsletter_pending')
    db=op.get_bind()
    db.execute(sa.text("DELETE FROM config WHERE key LIKE 'tracearr_%'"))
    db.execute(sa.text("DELETE FROM integration_jobs WHERE service='tracearr'"))
    db.execute(sa.text("DELETE FROM connection_checks WHERE service='tracearr'"))
    db.execute(sa.text("UPDATE config SET value='tools' WHERE key='onboarding_step' AND value='tracearr'"))
    op.create_table('audit_events',sa.Column('id',sa.Integer,primary_key=True),sa.Column('at',sa.Integer,nullable=False,index=True),sa.Column('actor_id',sa.Integer),sa.Column('subject_id',sa.Integer),sa.Column('action',sa.String(200),nullable=False),sa.Column('outcome',sa.Integer,nullable=False),sa.Column('detail',sa.Text,nullable=False))
    op.create_table('media_sessions',sa.Column('session_digest',sa.String(64),sa.ForeignKey('sessions.digest',ondelete='CASCADE'),primary_key=True),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('payload',sa.Text,nullable=False),sa.Column('expires',sa.Integer,nullable=False))
    op.create_table('support_sessions',sa.Column('session_digest',sa.String(64),sa.ForeignKey('sessions.digest',ondelete='CASCADE'),primary_key=True),sa.Column('source_digest',sa.String(64),sa.ForeignKey('sessions.digest',ondelete='CASCADE'),nullable=False),sa.Column('target_id',sa.Integer,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('target_version',sa.Integer,nullable=False),sa.Column('expires',sa.Integer,nullable=False))
    op.create_table('tool_grants',sa.Column('digest',sa.String(64),primary_key=True),sa.Column('session_digest',sa.String(64),sa.ForeignKey('sessions.digest',ondelete='CASCADE'),nullable=False),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('tool',sa.String(20),nullable=False),sa.Column('expires',sa.Integer,nullable=False),sa.Column('redeemed',sa.Boolean,nullable=False))

def downgrade():
    for table in ('tool_grants','support_sessions','media_sessions','audit_events'):op.drop_table(table)
    op.add_column('users',sa.Column('newsletter_opt_in',sa.Boolean,nullable=True))
    op.add_column('users',sa.Column('newsletter_pending',sa.Boolean,nullable=False,server_default='0'))
    op.drop_column('seerr_tickets','actor_digest')
    op.drop_column('icon_assets','mime')
    op.drop_column('users','tool_access');op.drop_column('users','theme_preference')
