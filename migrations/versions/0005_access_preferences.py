"""Explicit nested application journeys, icons and user preferences."""
import json
from alembic import op
import sqlalchemy as sa
revision = "0005"
down_revision = "0004"
branch_labels = depends_on = None

def upgrade():
    op.add_column("users",sa.Column("newsletter_opt_in",sa.Boolean,nullable=True))
    op.add_column("users",sa.Column("newsletter_pending",sa.Boolean,nullable=False,server_default="0"))
    op.add_column("users",sa.Column("seerr_notifications",sa.Boolean,nullable=True))
    op.add_column("users",sa.Column("preferences_version",sa.Integer,nullable=False,server_default="0"))
    op.add_column("menu_items",sa.Column("icon_url",sa.Text,nullable=False,server_default=""))
    op.add_column("access_services",sa.Column("icon_url",sa.Text,nullable=False,server_default=""))
    op.add_column("access_services",sa.Column("entry_mode",sa.String(20),nullable=False,server_default="direct"))
    op.add_column("access_services",sa.Column("access_draft",sa.Text,nullable=True))
    op.add_column("access_services",sa.Column("access_published",sa.Text,nullable=True))
    op.add_column("access_services",sa.Column("access_version",sa.Integer,nullable=False,server_default="0"))
    db=op.get_bind()
    for key, in db.execute(sa.text("SELECT key FROM access_services")):
        guides=list(db.execute(sa.text("SELECT id,published FROM guides WHERE service_key=:key AND published IS NOT NULL"),{"key":key}))
        if not guides: continue
        nodes=[{"id":"browser","parent":"","kind":"browser","title_fr":"Navigateur","title_en":"Browser","position":0,"icon_url":""}]
        for gid,raw in guides:
            guide=json.loads(raw)
            nodes.append({"id":"guide_"+str(gid),"parent":"","kind":"guide","guide_id":gid,"title_fr":guide.get("title_fr",""),"title_en":guide.get("title_en",""),"position":guide.get("position",10),"icon_url":""})
        encoded=json.dumps(nodes,ensure_ascii=False)
        db.execute(sa.text("UPDATE access_services SET entry_mode='structured',access_draft=:tree,access_published=:tree WHERE key=:key"),{"tree":encoded,"key":key})

def downgrade():
    for name in ("access_version","access_published","access_draft","entry_mode","icon_url"):op.drop_column("access_services",name)
    op.drop_column("menu_items","icon_url")
    for name in ("preferences_version","seerr_notifications","newsletter_pending","newsletter_opt_in"):op.drop_column("users",name)
