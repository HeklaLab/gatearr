"""English source content and database-managed languages, preserving legacy translations."""
import json,hashlib
from html import escape
from pathlib import Path
from alembic import op
import sqlalchemy as sa
revision='0007'
down_revision='0006'
branch_labels=depends_on=None

SNAPSHOT=json.loads((Path(__file__).parent.parent/'data/0007_legacy.json').read_text())
def hashed(value):return hashlib.sha256(value.encode()).hexdigest()

def upgrade():
    op.create_table('languages',sa.Column('code',sa.String(10),primary_key=True),sa.Column('name',sa.String(80),nullable=False),sa.Column('enabled',sa.Boolean,nullable=False))
    op.create_table('content_translations',sa.Column('locale',sa.String(10),sa.ForeignKey('languages.code',ondelete='CASCADE'),primary_key=True),sa.Column('resource',sa.String(240),primary_key=True),sa.Column('source_hash',sa.String(64),primary_key=True),sa.Column('value',sa.Text,nullable=False))
    db=op.get_bind()
    db.execute(sa.text("INSERT INTO languages VALUES ('en','English',1),('fr','Français',1)"))
    configs={key:value for key,value in db.execute(sa.text('SELECT key,value FROM config'))}
    backup={'configs':{key:value for key,value in configs.items() if key.startswith(('portal_','login_text','default_locale','invite_','reset_','verify_','ui_translation_','account_'))},'guides':[dict(row) for row in db.execute(sa.text('SELECT id,draft,published FROM guides')).mappings()],'services':[dict(row) for row in db.execute(sa.text('SELECT key,access_draft,access_published FROM access_services')).mappings()],'menus':[dict(row) for row in db.execute(sa.text('SELECT id,label,label_en FROM menu_items')).mappings()]}
    def config(key,value):db.execute(sa.text('INSERT INTO config (key,value) VALUES (:key,:value) ON CONFLICT(key) DO UPDATE SET value=:value'),{'key':key,'value':value})
    def put(key,source,value):
        if source and value and source!=value:db.execute(sa.text('INSERT OR IGNORE INTO content_translations (locale,resource,source_hash,value) VALUES (:locale,:resource,:hash,:value)'),{'locale':'fr','resource':key,'hash':hashed(source),'value':value})
    def fields(obj,key,names):
        for name in names:
            source=obj.get(name+'_en') or obj.get(name) or obj.get(name+'_fr') or ''
            put(key+':'+name,source,obj.get(name+'_fr',''))
            obj[name]=source;obj.pop(name+'_fr',None);obj.pop(name+'_en',None)
        return obj
    for key in ('portal_draft','portal_published'):
        layout=json.loads(configs[key]) if configs.get(key) else json.loads(json.dumps(SNAPSHOT['portal']))
        for block in layout['blocks']:fields(block,'block:'+block['id'],('title','body','alt'))
        # Persist only existing layouts; defaults in source remain canonical English.
        if configs.get(key):config(key,json.dumps(layout,ensure_ascii=False))
    for row in backup['menus']:
        source=row['label_en'] or row['label'];put('menu:'+str(row['id'])+':label',source,row['label'])
        db.execute(sa.text('UPDATE menu_items SET label=:label,label_en=NULL WHERE id=:id'),{'id':row['id'],'label':source})
    for row in backup['services']:
        for column in ('access_draft','access_published'):
            if not row[column]:continue
            nodes=json.loads(row[column])
            for node in nodes:
                node['_i18n_key']='journey:'+row['key']+':'+node['id'];fields(node,node['_i18n_key'],('title',))
            db.execute(sa.text('UPDATE access_services SET '+column+'=:value WHERE key=:key'),{'key':row['key'],'value':json.dumps(nodes,ensure_ascii=False)})
    for row in backup['guides']:
        for column in ('draft','published'):
            if not row[column]:continue
            article=json.loads(row[column]);article['_i18n_key']='guide:'+str(row['id']);fields(article,article['_i18n_key'],('title','summary'))
            for index,step in enumerate(article['steps']):
                step['id']=step.get('id') or 'step-'+str(index);step['_i18n_key']=article['_i18n_key']+':'+step['id'];fields(step,step['_i18n_key'],('title','body','link_label'))
            db.execute(sa.text('UPDATE guides SET '+column+'=:value WHERE id=:id'),{'id':row['id'],'value':json.dumps(article,ensure_ascii=False)})
    english=configs.get('login_text_en') or SNAPSHOT['keys']['Retrouvez vos services et gérez votre compte en toute simplicité.']
    put('branding:login_text',english,configs.get('login_text_fr') or configs.get('login_text',''))
    config('login_text',english)
    db.execute(sa.text("DELETE FROM config WHERE key IN ('login_text_fr','login_text_en')"))
    for purpose in ('invite','verify','reset'):
        for part in ('subject','body','html'):
            key=purpose+'_'+part
            old_fr=configs.get(key+'_fr',configs.get(key,SNAPSHOT['mail']['fr'].get(key,'')))
            english=configs.get(key+'_en',SNAPSHOT['mail']['en'].get(key,''))
            if part=='html' and old_fr and not english:
                body=configs.get(purpose+'_body_en',SNAPSHOT['mail']['en'][purpose+'_body'])
                english='<p>'+escape(body).replace('\n','<br>')+'</p>'
            put('mail:'+purpose+':'+part,english,old_fr)
            config(key,english)
            db.execute(sa.text('DELETE FROM config WHERE key IN (:fr,:en)'),{'fr':key+'_fr','en':key+'_en'})
    for old,english in SNAPSHOT['keys'].items():
        for code in ('en','fr'):
            old_key='ui_translation_'+code+'_'+hashed(old)
            if old_key in configs:config('ui_translation_'+code+'_'+hashed(english),configs[old_key])
    for code in ('en','fr'):
        for name,old in {'newsletter':'Recevoir la newsletter','requests':'Recevoir les notifications par rapport à mes demandes'}.items():
            value=configs.get('account_'+name+'_label_'+code)
            if value:config('ui_translation_'+code+'_'+hashed(SNAPSHOT['keys'][old]),value)
    config('default_locale','en')
    config('_i18n_migration_0007',json.dumps(backup,ensure_ascii=False))

def downgrade():
    db=op.get_bind();raw=db.execute(sa.text("SELECT value FROM config WHERE key='_i18n_migration_0007'")).scalar()
    if raw:
        backup=json.loads(raw)
        generated=['login_text','default_locale']+[purpose+'_'+part for purpose in ('invite','reset','verify') for part in ('subject','body','html')]
        for key in generated:
            if key not in backup['configs']:db.execute(sa.text('DELETE FROM config WHERE key=:key'),{'key':key})
        for key,value in backup['configs'].items():db.execute(sa.text('INSERT INTO config (key,value) VALUES (:key,:value) ON CONFLICT(key) DO UPDATE SET value=:value'),{'key':key,'value':value})
        for row in backup['menus']:db.execute(sa.text('UPDATE menu_items SET label=:label,label_en=:label_en WHERE id=:id'),row)
        for row in backup['guides']:db.execute(sa.text('UPDATE guides SET draft=:draft,published=:published WHERE id=:id'),row)
        for row in backup['services']:db.execute(sa.text('UPDATE access_services SET access_draft=:access_draft,access_published=:access_published WHERE key=:key'),row)
    db.execute(sa.text("DELETE FROM config WHERE key='_i18n_migration_0007'"))
    op.drop_table('content_translations');op.drop_table('languages')
