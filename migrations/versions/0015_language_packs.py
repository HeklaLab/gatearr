"""Install disabled language packs, retaining existing language choices and overrides."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert
revision='0015'
down_revision='0014'
branch_labels=depends_on=None
LANGUAGES={'fr':'Français','es':'Español','de':'Deutsch','it':'Italiano','pt-br':'Português (Brasil)','nl':'Nederlands','pl':'Polski','ru':'Русский','uk':'Українська','cs':'Čeština','sv':'Svenska','da':'Dansk','nb':'Norsk bokmål','fi':'Suomi','tr':'Türkçe','ar':'العربية','he':'עברית','ja':'日本語','ko':'한국어','zh-cn':'简体中文'}
def upgrade():
    table=sa.table('languages',sa.column('code',sa.String),sa.column('name',sa.String),sa.column('enabled',sa.Boolean))
    for code,name in LANGUAGES.items():op.get_bind().execute(insert(table).values(code=code,name=name,enabled=False).on_conflict_do_nothing(index_elements=['code']))
def downgrade():
    # These are editable user data; retain them on downgrade.
    pass
