"""Remove application-menu blocks and narrow page-specific builder controls."""
from alembic import op
import sqlalchemy as sa
import json
revision='0031'
down_revision='0030'
branch_labels=depends_on=None

def upgrade():
    db=op.get_bind()
    def convert(raw,home=False,access=False,slug=None):
        if not raw:return raw
        try:value=json.loads(raw)
        except (ValueError,TypeError):return raw
        if not isinstance(value,dict):return raw
        layout=value.get('design',value)
        if not isinstance(layout,dict) or not isinstance(layout.get('blocks'),list):return raw
        before=json.dumps(value,sort_keys=True)
        layout['blocks']=[b for b in layout['blocks'] if b.get('kind')!='menu' and not (not home and b.get('kind') in ('applications','application','services','account')) and not (access and b.get('kind','').startswith('widget_'))]
        for b in layout['blocks']:
            if b.get('kind')=='button' and b.get('button_action')=='choose_device' and not access:
                b['button_action']='link';b['url']='/pages/'+slug if slug else '/home';b['new_tab']=False;b.pop('after_device',None)
        return raw if json.dumps(value,sort_keys=True)==before else json.dumps(value,ensure_ascii=False)
    changed=set()
    for key,raw in db.execute(sa.text("SELECT key,value FROM config WHERE key IN ('portal_draft','portal_published','login_draft','login_published','footer_draft','footer_published')")).all():
        new=convert(raw,home=key.startswith('portal_'))
        if new!=raw:
            db.execute(sa.text('UPDATE config SET value=:raw WHERE key=:key'),dict(raw=new,key=key));changed.add(key.split('_')[0])
    for prefix in changed:db.execute(sa.text("UPDATE config SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE key=:key"),dict(key=prefix+'_version'))
    for row in db.execute(sa.text('SELECT id,slug,system_key,draft,published FROM content_pages')).mappings().all():
        access=(row['system_key'] or '').startswith('guide:')
        draft=convert(row['draft'],access=access,slug=row['slug']);published=convert(row['published'],access=access,slug=row['slug'])
        if draft!=row['draft'] or published!=row['published']:
            db.execute(sa.text('UPDATE content_pages SET draft=:draft,published=:published,version=version+1 WHERE id=:id'),dict(id=row['id'],draft=draft,published=published))

def downgrade():pass
