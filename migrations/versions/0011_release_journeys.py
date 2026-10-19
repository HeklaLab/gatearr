"""Seed default guides for previously installed portals without existing content."""
import json
from pathlib import Path
import sqlalchemy as sa
from alembic import op
revision='0011'
down_revision='0010'
branch_labels=depends_on=None

def upgrade():
    db=op.get_bind()
    if not db.execute(sa.text("SELECT 1 FROM config WHERE key='setup_complete'")).first():return
    service=db.execute(sa.text("SELECT access_draft,access_published FROM access_services WHERE key='emby'")).first()
    if not service or json.loads(service[0] or '[]') or json.loads(service[1] or '[]') or db.execute(sa.text("SELECT 1 FROM guides WHERE service_key='emby'")).first():return
    kind=db.execute(sa.text("SELECT value FROM config WHERE key='media_server'")).scalar() or 'emby'
    preset=json.loads((Path(__file__).resolve().parents[1]/'data/0011_default_journeys.json').read_text())[kind]
    for article in preset['guides']:
        key=article.pop('key')
        gid=db.execute(sa.text("INSERT INTO guides(service_key,draft,published,version) VALUES('emby','{}',NULL,0)")).lastrowid
        article['_i18n_key']='guide:'+str(gid)
        for step in article['steps']:step['_i18n_key']=article['_i18n_key']+':'+step['id']
        db.execute(sa.text('UPDATE guides SET draft=:value,published=:value WHERE id=:id'),{'id':gid,'value':json.dumps(article)})
        for node in preset['nodes']:
            if node.get('guide_key')==key:node.pop('guide_key');node['guide_id']=gid
    for node in preset['nodes']:node['_i18n_key']='journey:emby:'+node['id']
    db.execute(sa.text("UPDATE access_services SET access_draft=:value,access_published=:value,access_version=access_version+1 WHERE key='emby'"),{'value':json.dumps(preset['nodes'])})

def downgrade():
    # Guide content may have been edited after seeding. Preserve it on downgrade.
    pass
