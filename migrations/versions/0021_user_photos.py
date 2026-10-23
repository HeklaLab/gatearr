"""Private native-profile photo cache; existing designs and consent are preserved."""
from alembic import op
import sqlalchemy as sa
from app.models import UserPhoto
revision='0021'
down_revision='0020'
branch_labels=depends_on=None
def upgrade():
    UserPhoto.__table__.create(op.get_bind(),checkfirst=True)
    # This was a portal-display switch in the old UI. Widgets are now admin-owned.
    # Email opt-outs must stay opted out; do not turn them into subscriptions.
    op.execute(sa.text('UPDATE library_preferences SET email=0 WHERE seasons=0'))
    op.execute(sa.text('UPDATE library_preferences SET seasons=1'))
def downgrade():UserPhoto.__table__.drop(op.get_bind(),checkfirst=True)
