"""Timestamp current subtitle selections before optional replacement locks."""
from alembic import op
import sqlalchemy as sa
import json,time
revision='0026'
down_revision='0025'
branch_labels=depends_on=None

def upgrade():
    op.add_column('users',sa.Column('bazarr_subtitle_locks',sa.Text(),nullable=False,server_default='{}'))
    users=sa.table('users',sa.column('id',sa.Integer()),sa.column('bazarr_subtitle_languages',sa.Text()),sa.column('bazarr_subtitle_locks',sa.Text()))
    db=op.get_bind();stamp=int(time.time())
    for uid,raw in db.execute(sa.select(users.c.id,users.c.bazarr_subtitle_languages)):
        codes=json.loads(raw or '[]')
        if codes:db.execute(users.update().where(users.c.id==uid).values(bazarr_subtitle_locks=json.dumps({code:stamp for code in codes})))

def downgrade():op.drop_column('users','bazarr_subtitle_locks')
