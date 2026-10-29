"""Explicit guide identities for member-facing Tracearr and custom URL applications."""
import json,secrets
from .models import AccessService
from .mailer import config


def tracearr_service(db):
    row=db.get(AccessService,'tracearr')
    if not row:
        browser=[dict(id='browser',kind='browser',title='Browser',position=10,icon='globe')]
        row=AccessService(key='tracearr',name='Tracearr',browser_url=config(db,'tracearr_public_url'),server_url='',icon='chart-line',icon_url='/static/services/tracearr.png',entry_mode='direct',access_draft=json.dumps(browser),access_published=json.dumps(browser),access_version=0)
        db.add(row);db.flush()
    return row


def custom_service(db,item):
    """Use the saved link ID, never its name or URL, as the guide identity."""
    if not item.access_service:
        key='service-'+str(item.id)
        while db.get(AccessService,key):key='service-'+str(item.id)+'-'+secrets.token_hex(4)
        browser=[dict(id='browser',kind='browser',title='Browser',position=10,icon='globe')]
        row=AccessService(key=key,name=item.label,browser_url=item.url,server_url=item.url,icon=item.icon,icon_url=item.icon_url,entry_mode='direct',access_version=0,access_draft=json.dumps(browser),access_published=json.dumps(browser))
        db.add(row);db.flush()
        item.access_service=key
    return db.get(AccessService,item.access_service)
