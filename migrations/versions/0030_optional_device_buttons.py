"""Replace fixed guide navigation with editable default button blocks."""
from alembic import op
import sqlalchemy as sa
import json
revision='0030'
down_revision='0029'
branch_labels=depends_on=None

def upgrade():
    db=op.get_bind()
    def convert(raw):
        if not raw:return raw
        try:value=json.loads(raw)
        except (ValueError,TypeError):return raw
        blocks=value.get('blocks',[])
        if any(b.get('button_action')=='choose_device' for b in blocks):return raw
        guide=next((b for b in blocks if b.get('kind')=='guide_embed'),None)
        if not guide:return raw
        from app.page_presets import device_button
        ordered=sorted(blocks,key=lambda b:(b['order'],b['id']));index=ordered.index(guide)
        used={b['id'] for b in blocks};buttons=[]
        for side in ('top','bottom'):
            ident='choose-device-'+side;counter=0
            while ident in used:
                counter+=1;ident='choose-device-'+side+'-'+str(counter)
            used.add(ident);button=device_button(ident,0)
            for k in ('parent','slot','region'):
                if k in guide:button[k]=guide[k]
            buttons.append(button)
        ordered[index:index+1]=[buttons[0],guide,buttons[1]]
        for i,b in enumerate(ordered):b['order']=(i+1)*10
        value['blocks']=ordered
        return json.dumps(value,ensure_ascii=False)
    for row in db.execute(sa.text("SELECT id,draft,published FROM content_pages WHERE system_key LIKE 'guide:%'")).mappings().all():
        draft=convert(row['draft']);published=convert(row['published'])
        if draft!=row['draft'] or published!=row['published']:
            db.execute(sa.text('UPDATE content_pages SET draft=:draft,published=:published,version=version+1 WHERE id=:id'),dict(id=row['id'],draft=draft,published=published))

def downgrade():
    # Preserve editable choices; their removal belongs to the administrator.
    pass
