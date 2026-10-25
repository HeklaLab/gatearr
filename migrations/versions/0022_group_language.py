"""Optional group language; existing personal choices remain intact."""
from alembic import op
import sqlalchemy as sa
revision = '0022'
down_revision = '0021'
branch_labels = depends_on = None

def upgrade():
    op.add_column('permission_groups', sa.Column('locale', sa.String(10), nullable=True))

def downgrade():
    op.drop_column('permission_groups', 'locale')
