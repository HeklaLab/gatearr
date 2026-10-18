"""Encrypted persistent mail delivery queue."""
from alembic import op
import sqlalchemy as sa
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("mail_jobs", sa.Column("id", sa.Integer, primary_key=True), sa.Column("payload", sa.Text, nullable=False), sa.Column("attempts", sa.Integer, nullable=False), sa.Column("next_attempt", sa.Integer, nullable=False), sa.Column("expires", sa.Integer, nullable=False))
    op.create_index("ix_mail_jobs_next_attempt", "mail_jobs", ["next_attempt"])

def downgrade():
    op.drop_table("mail_jobs")
