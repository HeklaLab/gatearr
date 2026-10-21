"""Preserve existing administrator tool access when grants become explicit."""
from alembic import op
import sqlalchemy as sa
import json
revision='0016'
down_revision='0015'
branch_labels=depends_on=None

def upgrade():
    connection=op.get_bind()
    configured={row[0].removesuffix('_enabled') for row in connection.execute(sa.text("SELECT key FROM config WHERE value='true' AND key IN ('radarr_enabled','sonarr_enabled','bazarr_enabled')"))}
    for uid,raw in connection.execute(sa.text('SELECT id,tool_access FROM users WHERE admin=1')).all():
        grants=json.loads(raw or '[]')
        connection.execute(sa.text('UPDATE users SET tool_access=:grants WHERE id=:uid'),{'grants':json.dumps(sorted(set(grants)|configured)),'uid':uid})

def downgrade():
    pass
