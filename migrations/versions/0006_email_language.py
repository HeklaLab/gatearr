"""Independent per-user email language, preserving each existing language."""
from alembic import op
import sqlalchemy as sa
revision='0006'
down_revision='0005'
branch_labels=depends_on=None

def upgrade():
    op.add_column('users',sa.Column('mail_locale',sa.String(10),nullable=False,server_default='fr'))
    op.execute("UPDATE users SET mail_locale=CASE WHEN locale='en' THEN 'en' ELSE 'fr' END")

def downgrade():
    op.drop_column('users','mail_locale')
