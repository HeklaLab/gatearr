"""Add Tracearr guide identity without granting any member application access."""
from alembic import op
import sqlalchemy as sa
import json
revision='0032'
down_revision='0031'
branch_labels=depends_on=None

def upgrade():
    db=op.get_bind()
    if not db.execute(sa.text("SELECT key FROM access_services WHERE key='tracearr'")).first():
        public=db.execute(sa.text("SELECT value FROM config WHERE key='tracearr_public_url'")).scalar() or ''
        nodes=json.dumps([dict(id='browser',kind='browser',title='Browser',position=10,icon='globe')])
        db.execute(sa.text("INSERT INTO access_services(key,name,browser_url,server_url,icon_url,icon,entry_mode,access_draft,access_published,access_version) VALUES('tracearr','Tracearr',:public,'','/static/services/tracearr.png','chart-line','direct',:nodes,:nodes,0)"),dict(public=public,nodes=nodes))
    if not db.execute(sa.text("SELECT id FROM content_pages WHERE system_key='guide:tracearr'")).first():
        from app.page_presets import guide_layout
        value=guide_layout('tracearr','Tracearr','chart-line','/static/services/tracearr.png',True)
        slug='guide-tracearr';counter=1
        while db.execute(sa.text('SELECT id FROM content_pages WHERE slug=:slug'),dict(slug=slug)).first():
            counter+=1;slug='guide-tracearr-'+str(counter)
        value['page_settings']['slug']=slug
        db.execute(sa.text("INSERT INTO content_pages(slug,system_key,draft,published,version,archived) VALUES(:slug,'guide:tracearr',:raw,:raw,1,0)"),dict(slug=slug,raw=json.dumps(value)))

def downgrade():
    # Keep authored instructions and explicit user permissions across rollback.
    pass
