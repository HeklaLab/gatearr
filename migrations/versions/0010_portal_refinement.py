"""English-only distribution, one user language and connection diagnostics."""
from alembic import op
import sqlalchemy as sa
revision='0010'
down_revision='0009'
branch_labels=depends_on=None

def upgrade():
    op.execute("DELETE FROM content_translations WHERE locale='fr'")
    op.execute("DELETE FROM config WHERE key LIKE 'ui_translation_fr_%'")
    op.execute("DELETE FROM languages WHERE code='fr'")
    op.execute("UPDATE users SET locale='en' WHERE locale NOT IN (SELECT code FROM languages WHERE enabled=1)")
    op.execute("UPDATE users SET preferences_version=preferences_version+1")
    op.drop_column('users','mail_locale')
    op.create_table('connection_checks',sa.Column('service',sa.String(20),primary_key=True),sa.Column('state',sa.String(20),nullable=False),sa.Column('detail',sa.String(100),nullable=False),sa.Column('checked_at',sa.Integer(),nullable=False))

def downgrade():
    op.drop_table('connection_checks')
    op.add_column('users',sa.Column('mail_locale',sa.String(10),nullable=False,server_default='en'))
    op.execute('UPDATE users SET mail_locale=locale')
