"""Remove the intermediate guide directory and keep Home's identity fixed."""
from alembic import op
import sqlalchemy as sa
import json
revision='0029'
down_revision='0028'
branch_labels=depends_on=None

def upgrade():
    db=op.get_bind()
    directory_ids={'p-'+str(i) for i, in db.execute(sa.text("SELECT id FROM content_pages WHERE system_key='directory'"))}
    services=dict(db.execute(sa.text('SELECT key,name FROM access_services')).all())
    def update_layout(raw,home=False,service=None):
        if not raw:return raw
        try:value=json.loads(raw)
        except (ValueError,TypeError):return raw
        if not isinstance(value,dict):return raw
        layout=value.get('design',value)
        if not isinstance(layout,dict) or not isinstance(layout.get('blocks'),list):return raw
        layout['blocks']=[b for b in layout['blocks'] if b.get('kind')!='guides' and not (home and b.get('kind')=='guide_embed')]
        for b in layout['blocks']:
            if b.get('kind')=='page_menu':b['page_ids']=[k for k in b.get('page_ids',[]) if k not in directory_ids]
        meta=layout.get('page_settings')
        if home and meta:meta.update(title='Home',slug='home')
        if service and meta and meta.get('title') in (service+' · Access guide',service+' · Access guides'):
            meta['title']=service+' access guides'
        return json.dumps(value,ensure_ascii=False)
    changed=set()
    for key,raw in db.execute(sa.text("SELECT key,value FROM config WHERE key IN ('portal_draft','portal_published','login_draft','login_published','footer_draft','footer_published')")).all():
        new=update_layout(raw,key.startswith('portal_'))
        if new!=raw:
            db.execute(sa.text('UPDATE config SET value=:raw WHERE key=:key'),dict(raw=new,key=key));changed.add(key.split('_')[0])
    for prefix in changed:
        db.execute(sa.text("UPDATE config SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE key=:key"),dict(key=prefix+'_version'))
    for row in db.execute(sa.text('SELECT id,system_key,draft,published FROM content_pages')).mappings().all():
        if row['system_key']=='directory':
            db.execute(sa.text('UPDATE content_pages SET archived=1,version=version+1 WHERE id=:id'),dict(id=row['id']));continue
        key=row['system_key'] or '';name=services.get(key[6:]) if key.startswith('guide:') else None
        draft=update_layout(row['draft'],service=name);published=update_layout(row['published'],service=name)
        if draft!=row['draft'] or published!=row['published']:
            db.execute(sa.text('UPDATE content_pages SET draft=:draft,published=:published,version=version+1 WHERE id=:id'),dict(id=row['id'],draft=draft,published=published))

def downgrade():
    # Keep administrator content and retained directory snapshots rather than reconstructing it.
    pass
