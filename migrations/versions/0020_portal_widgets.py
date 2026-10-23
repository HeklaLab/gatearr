"""Add scoped widget snapshots, personal library events and Cap token accounting."""
import json
import sqlalchemy as sa
from alembic import op
from app.models import PortalCache,LibraryEvent,LibraryPreference,CaptchaToken,CaptchaMetric
revision='0020'
down_revision='0019'
branch_labels=depends_on=None
TABLES=(PortalCache,LibraryPreference,LibraryEvent,CaptchaToken,CaptchaMetric)
def upgrade():
    for model in TABLES:model.__table__.create(op.get_bind(),checkfirst=True)
    connection=op.get_bind();values=dict(connection.execute(sa.text('SELECT key,value FROM config')).all())
    if values.get('seerr_enabled')=='true':
        for key in ('portal_draft','portal_published'):
            if not values.get(key):continue
            layout=json.loads(values[key]);blocks=layout.get('blocks',[])
            if any(b.get('kind')=='widget_seerr' for b in blocks):continue
            if not any('access:seerr' in b.get('applications',[]) or b.get('kind')=='services' for b in blocks):continue
            additions=[]
            for role,visibility,metrics in [('admin','admins',['pending','processing']),('member','members',['movies_left','series_left'])]:
                if values.get('seerr_counts_'+role,'true')!='true' or len(blocks)+len(additions)>=50:continue
                identifier='seerr-widget-'+role
                if any(b.get('id')==identifier for b in blocks):continue
                additions.append({'id':identifier,'kind':'widget_seerr','region':'main','span':4,'order':max((b.get('order',0) for b in blocks),default=0)+10+len(additions),'title':'','visibility':visibility,'metrics':metrics,'show_logo':False,'groups':[]})
            layout['blocks']=blocks+additions
            connection.execute(sa.text('UPDATE config SET value=:value WHERE key=:key'),{'key':key,'value':json.dumps(layout)})
def downgrade():
    for model in reversed(TABLES):model.__table__.drop(op.get_bind(),checkfirst=True)
