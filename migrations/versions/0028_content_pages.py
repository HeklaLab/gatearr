"""Independent content pages and page-level permissions."""
from alembic import op
import sqlalchemy as sa
revision='0028'
down_revision='0027'
branch_labels=depends_on=None

def upgrade():
    op.create_table('content_pages',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('slug',sa.String(80),nullable=False,unique=True),sa.Column('system_key',sa.String(100),unique=True),sa.Column('draft',sa.Text(),nullable=False),sa.Column('published',sa.Text()),sa.Column('version',sa.Integer(),nullable=False,server_default='0'),sa.Column('archived',sa.Boolean(),nullable=False,server_default='0'))
    # Seed envelopes without importing the application or changing existing layouts.
    import json
    from app.page_presets import guide_layout
    db=op.get_bind()
    for key,name,icon,icon_url in db.execute(sa.text('SELECT key,name,icon,icon_url FROM access_services')).all():
        value=guide_layout(key,name,icon,icon_url,fresh=False)
        db.execute(sa.text('INSERT INTO content_pages(slug,system_key,draft,published,version,archived) VALUES(:slug,:system,:raw,:raw,1,0)'),dict(slug='guide-'+key,system='guide:'+key,raw=json.dumps(value)))

def downgrade():
    op.drop_table('content_pages')
