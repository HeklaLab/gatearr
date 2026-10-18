"""Use only linked media accounts for portal administration."""
from alembic import op
import sqlalchemy as sa
revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('sessions',sa.Column('setup_expires',sa.Integer(),nullable=True))
    op.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE emby_id IS NULL)")
    op.execute("UPDATE tokens SET used=1 WHERE user_id IN (SELECT id FROM users WHERE emby_id IS NULL)")
    op.execute("UPDATE users SET admin=0, active=0, email=NULL, password_hash=NULL, version=version+1 WHERE emby_id IS NULL")
    op.execute("DELETE FROM config WHERE key='setup_complete' AND NOT EXISTS (SELECT 1 FROM users WHERE emby_id IS NOT NULL AND admin=1 AND active=1 AND emby_missing=0)")

def downgrade():
    # Removed local passwords cannot and must not be reconstructed.
    op.drop_column('sessions','setup_expires')
