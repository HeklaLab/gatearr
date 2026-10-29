"""Pure page presets, also safe to import from migrations."""
from copy import deepcopy

def block(kind,ident,order=10,**values):
    return dict(dict(id=ident,kind=kind,region='main',span=12,order=order,title='',body=''),**values)

def layout(title,slug,icon='file-lines',icon_url='',blocks=None):
    return dict(nav_position='top',sidebar_position='left',theme={},colors={},show_header=True,page_settings=dict(title=title,slug=slug,description='',icon=icon,icon_url=icon_url,navigation=True,audience=dict(everyone=True,admins=True,groups=[])),blocks=[*(blocks or []),navigation_block()])

def guide_layout(key,name,icon='book-open',icon_url='',fresh=True):
    blocks=[device_button('choose-device-top',15),block('guide_embed','journey',20,service_key=key),device_button('choose-device-bottom',25)]
    if fresh:
        blocks.insert(0,block('text','introduction',10,title=name+' access guides',body='Choose your device and follow the steps to get started.'))
        blocks.append(block('accordion','help',30,title='Need help?',items=[dict(id='credentials',question='Which account should I use?',answer='Use the account provided by your server administrator.')],multiple=False))
    value=layout(name+' access guides','guide-'+key,icon or 'book-open',icon_url or ('/static/services/'+key+'.png' if key in ('emby','seerr') else ''),blocks)
    value['page_settings']['navigation']=False
    return value

def faq_layout(slug='help'):
    return layout('Help & FAQ',slug,'circle-question',blocks=[block('text','intro',10,title='How can we help?',body='Find answers to common questions about your media library.'),block('accordion','faq',20,items=[dict(id='start',question='How do I start watching?',answer='Open Access media on the home page, choose your device and follow the guide.'),dict(id='requests',question='How do I request a movie or series?',answer='Open the requests application from the home page. Available requests depend on your account permissions.')],multiple=False)])


def device_button(ident,order):
    return block('button',ident,order,title='Choose another device',url='',new_tab=False,button_action='choose_device',after_device=True)


def navigation_block():
    return block('page_menu','page-navigation',0,menu_layout='pills',menu_source='navigation',page_ids=[],show_back=True)
