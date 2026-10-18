"""Locales, multiple menus and persistent email synchronization."""
from alembic import op
import sqlalchemy as sa
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("locale", sa.String(10), nullable=False, server_default="fr"))
    op.add_column("menu_items", sa.Column("label_en", sa.String(100), nullable=True))
    op.add_column("menu_items", sa.Column("menu_key", sa.String(40), nullable=False, server_default="main"))
    op.create_table("integration_jobs", sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True), sa.Column("service", sa.String(20), primary_key=True), sa.Column("email_digest", sa.String(64), nullable=False), sa.Column("state", sa.String(20), nullable=False), sa.Column("attempts", sa.Integer, nullable=False), sa.Column("next_attempt", sa.Integer, nullable=False), sa.Column("updated_at", sa.Integer, nullable=False), sa.Column("error", sa.String(40), nullable=False))
    op.create_index("ix_integration_jobs_next_attempt", "integration_jobs", ["next_attempt"])

def downgrade():
    op.drop_table("integration_jobs")
    # Python 3.12 / modern SQLite support native DROP COLUMN. Avoid rebuilding
    # the referenced users table while foreign keys point to existing accounts.
    op.drop_column("menu_items", "menu_key")
    op.drop_column("menu_items", "label_en")
    op.drop_column("users", "locale")
