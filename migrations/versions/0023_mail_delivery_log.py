"""SMTP delivery metadata, separate from transient queue jobs and message bodies."""
from alembic import op
import sqlalchemy as sa
revision='0023'
down_revision='0022'
branch_labels=depends_on=None


def upgrade():
    op.create_table('mail_deliveries',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('at',sa.Integer(),nullable=False),sa.Column('recipient',sa.String(320),nullable=False),sa.Column('subject',sa.String(1000),nullable=False),sa.Column('purpose',sa.String(60),nullable=False),sa.Column('context',sa.String(30),nullable=False),sa.Column('state',sa.String(20),nullable=False),sa.Column('error',sa.String(40),nullable=False))
    op.create_index('ix_mail_deliveries_at','mail_deliveries',['at'])


def downgrade():
    op.drop_index('ix_mail_deliveries_at',table_name='mail_deliveries')
    op.drop_table('mail_deliveries')
