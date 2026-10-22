"""Centralize the public media URL in application settings."""
from alembic import op
import sqlalchemy as sa
revision='0019'
down_revision='0018'
branch_labels=depends_on=None

def upgrade():
    connection=op.get_bind()
    legacy=connection.execute(sa.text("SELECT value FROM config WHERE key='emby_link'")).scalar()
    if legacy:
        existing=connection.execute(sa.text("SELECT browser_url FROM access_services WHERE key='emby'")).first()
        if existing is None:
            connection.execute(sa.text("INSERT INTO access_services (key,name,browser_url,server_url,icon_url,icon,entry_mode,access_version) VALUES ('emby',:name,:url,'','','link','direct',0)"),{'name':'Jellyfin' if connection.execute(sa.text("SELECT value FROM config WHERE key='media_server'")).scalar()=='jellyfin' else 'Emby','url':legacy})
        elif not existing[0]:
            connection.execute(sa.text("UPDATE access_services SET browser_url=:url WHERE key='emby'"),{'url':legacy})
    connection.execute(sa.text("DELETE FROM config WHERE key='emby_link'"))

def downgrade():
    connection=op.get_bind()
    value=connection.execute(sa.text("SELECT browser_url FROM access_services WHERE key='emby'")).scalar()
    if value:
        connection.execute(sa.text("INSERT OR REPLACE INTO config (key,value) VALUES ('emby_link',:url)"),{'url':value})
