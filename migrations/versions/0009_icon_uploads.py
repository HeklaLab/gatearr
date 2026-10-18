"""Persist uploaded service icons in the portal database."""
from alembic import op
import sqlalchemy as sa
revision='0009'
down_revision='0008'
branch_labels=depends_on=None

def upgrade():
    op.create_table('icon_assets',sa.Column('digest',sa.String(64),primary_key=True),sa.Column('content',sa.LargeBinary(),nullable=False))

def downgrade():
    op.drop_table('icon_assets')
