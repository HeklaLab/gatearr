"""Opt-in subtitle-language permission, independent of Bazarr interface access."""
from alembic import op
import sqlalchemy as sa
revision='0024'
down_revision='0023'
branch_labels=depends_on=None

def upgrade():
    op.add_column('users',sa.Column('bazarr_subtitles',sa.Boolean(),nullable=False,server_default=sa.false()))

def downgrade():
    op.drop_column('users','bazarr_subtitles')
