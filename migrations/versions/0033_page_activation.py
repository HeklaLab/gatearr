"""Keep page activation independent from draft/publication snapshots."""
from alembic import op
import sqlalchemy as sa
revision='0033'
down_revision='0032'
branch_labels=depends_on=None

def upgrade():
    op.add_column('content_pages',sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.true()))

def downgrade():
    op.drop_column('content_pages','enabled')
