"""Persist Font Awesome choices for How to services."""
from alembic import op
import sqlalchemy as sa
revision='0014'
down_revision='0013'
branch_labels=depends_on=None
def upgrade():op.add_column('access_services',sa.Column('icon',sa.String(80),nullable=False,server_default='link'))
def downgrade():op.drop_column('access_services','icon')
