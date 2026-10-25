"""Personal subtitle choices and per-user/group capacity."""
from alembic import op
import sqlalchemy as sa
revision='0025'
down_revision='0024'
branch_labels=depends_on=None

def upgrade():
    op.add_column('users',sa.Column('bazarr_subtitle_limit',sa.Integer(),nullable=False,server_default='3'))
    op.add_column('users',sa.Column('bazarr_subtitle_languages',sa.Text(),nullable=False,server_default='[]'))
    op.add_column('users',sa.Column('bazarr_subtitle_version',sa.Integer(),nullable=False,server_default='0'))

def downgrade():
    for name in ('bazarr_subtitle_version','bazarr_subtitle_languages','bazarr_subtitle_limit'):op.drop_column('users',name)
