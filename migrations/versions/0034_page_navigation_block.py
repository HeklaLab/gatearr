"""Replace the former forced content-page navigation with an editable block."""
from alembic import op
import sqlalchemy as sa
import json
revision='0034'
down_revision='0033'
branch_labels=depends_on=None

def upgrade():
    db=op.get_bind()
    for row in db.execute(sa.text('SELECT id,draft,published FROM content_pages')).mappings().all():
        values={}
        for field in ('draft','published'):
            if not row[field]:continue
            layout=json.loads(row[field]);blocks=layout.get('blocks',[])
            if any(b.get('kind')=='page_menu' for b in blocks):continue
            from app.page_presets import navigation_block
            menu=navigation_block();used={b['id'] for b in blocks}
            while menu['id'] in used:menu['id']+='-nav'
            menu['order']=min([b.get('order',10) for b in blocks]+[10])-10
            layout['blocks']=[*blocks,menu];values[field]=json.dumps(layout,ensure_ascii=False)
        if values:
            assignments=','.join(field+'=:'+field for field in values)
            db.execute(sa.text('UPDATE content_pages SET '+assignments+',version=version+1 WHERE id=:id'),dict(values,id=row['id']))

def downgrade():
    # Authored page-menu content is retained deliberately.
    pass
