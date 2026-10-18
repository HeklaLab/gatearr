"""Initial portal schema."""
from alembic import op
import sqlalchemy as sa
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer, primary_key=True), sa.Column("emby_id", sa.String(128), unique=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("email", sa.String(320), unique=True), sa.Column("admin", sa.Boolean, nullable=False), sa.Column("active", sa.Boolean, nullable=False), sa.Column("password_hash", sa.Text), sa.Column("version", sa.Integer, nullable=False))
    op.create_table("config", sa.Column("key", sa.String(100), primary_key=True), sa.Column("value", sa.Text, nullable=False))
    op.create_table("sessions", sa.Column("digest", sa.String(64), primary_key=True), sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")), sa.Column("csrf", sa.String(100), nullable=False), sa.Column("expires", sa.Integer, nullable=False), sa.Column("version", sa.Integer, nullable=False))
    op.create_table("tokens", sa.Column("digest", sa.String(64), primary_key=True), sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False), sa.Column("purpose", sa.String(20), nullable=False), sa.Column("email", sa.String(320)), sa.Column("expires", sa.Integer, nullable=False), sa.Column("used", sa.Boolean, nullable=False), sa.Column("version", sa.Integer, nullable=False))
    op.create_table("menu_items", sa.Column("id", sa.Integer, primary_key=True), sa.Column("label", sa.String(100), nullable=False), sa.Column("url", sa.Text, nullable=False), sa.Column("icon", sa.String(30), nullable=False), sa.Column("position", sa.Integer, nullable=False), sa.Column("new_tab", sa.Boolean, nullable=False))
    op.create_table("rate_buckets", sa.Column("key", sa.String(64), primary_key=True), sa.Column("count", sa.Integer, nullable=False), sa.Column("expires", sa.Integer, nullable=False))
    for table in ("sessions", "tokens", "rate_buckets"):
        op.create_index("ix_" + table + "_expires", table, ["expires"])

def downgrade():
    for table in ("rate_buckets", "menu_items", "tokens", "sessions", "config", "users"):
        op.drop_table(table)
