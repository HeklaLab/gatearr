"""Published device guides and durable synchronization evidence."""
from alembic import op
import sqlalchemy as sa
revision = "0004"
down_revision = "0003"
branch_labels = depends_on = None

def upgrade():
    op.add_column("users", sa.Column("emby_missing", sa.Boolean, nullable=False, server_default="0"))
    op.add_column("users", sa.Column("emby_seen_at", sa.Integer, nullable=True))
    op.add_column("menu_items", sa.Column("access_service", sa.String(40), nullable=True))
    op.add_column("integration_jobs", sa.Column("last_success_at", sa.Integer, nullable=True))
    op.execute("UPDATE integration_jobs SET last_success_at = updated_at WHERE state = 'success'")
    op.create_table("access_services", sa.Column("key", sa.String(40), primary_key=True), sa.Column("name", sa.String(100), nullable=False), sa.Column("browser_url", sa.Text, nullable=False), sa.Column("server_url", sa.Text, nullable=False))
    op.bulk_insert(sa.table("access_services", sa.column("key"), sa.column("name"), sa.column("browser_url"), sa.column("server_url")), [{"key":"emby", "name":"Emby", "browser_url":"", "server_url":""}])
    op.create_table("guides", sa.Column("id", sa.Integer, primary_key=True), sa.Column("service_key", sa.String(40), sa.ForeignKey("access_services.key"), nullable=False), sa.Column("draft", sa.Text, nullable=False), sa.Column("published", sa.Text, nullable=True), sa.Column("version", sa.Integer, nullable=False))
    op.create_index("ix_guides_service_key", "guides", ["service_key"])

def downgrade():
    op.drop_table("guides")
    op.drop_table("access_services")
    op.drop_column("integration_jobs", "last_success_at")
    op.drop_column("menu_items", "access_service")
    op.drop_column("users", "emby_seen_at")
    op.drop_column("users", "emby_missing")
