"""Restricted rich email fragments, sanitized before storage and again after interpolation."""
from html import escape,unescape
from html.parser import HTMLParser
from string import Template
from urllib.parse import urlsplit
import nh3

TAGS={'p','div','br','strong','b','em','i','u','s','h1','h2','h3','ul','ol','li','blockquote','a','img','span','hr'}

def attribute(tag,name,value):
    if name in ('href','src'):
        if tag=='a' and value=='${link}':return value
        parsed=urlsplit(value)
        if '${' in value or parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password or any(c in value for c in '\r\n'):return None
    if name in ('width','height') and (not value.isdigit() or not 1<=int(value)<=1200):return None
    return value

def clean(value):
    if len(value)>50000:raise ValueError('Template too long or invalid subject')
    return nh3.clean(value,tags=TAGS,attributes={'*':{'style'},'a':{'href','title'},'img':{'src','alt','width','height'}},attribute_filter=attribute,url_schemes={'https','http'},url_relative=lambda value:value if value=='${link}' else None,filter_style_properties={'color','background-color','text-align','font-size','font-weight','font-style','text-decoration','line-height','max-width'},clean_content_tags={'script','style','iframe','object','svg','math','form','template'})

class PlainText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ('p','div','br','li','h1','h2','h3','blockquote','hr'):self.parts.append('\n')
        if tag=='a' and attrs.get('href'):self.parts.append(' '+attrs['href']+' ')
        if tag=='img' and attrs.get('alt'):self.parts.append(attrs['alt'])
    def handle_endtag(self,tag):
        if tag in ('p','div','li','h1','h2','h3'):self.parts.append('\n')
    def handle_data(self,data):self.parts.append(data)

def plain(value):
    parser=PlainText();parser.feed(value)
    return unescape(''.join(parser.parts)).strip()

def interpolate(value,values):
    return clean(Template(value).substitute({key:escape(str(item),quote=True) for key,item in values.items()}))

def validate(value,html=False,subject=False):
    if len(value)>(50000 if html else 10000) or (subject and (not value.strip() or len(value)>300 or '\r' in value or '\n' in value)):
        raise ValueError('Template too long or invalid subject')
    try:Template(value).substitute(app_name='Gatearr',username='Member',link='https://example.com/verify-email?token=example',minutes='30')
    except (ValueError,KeyError):raise ValueError('Allowed variables: ${app_name}, ${username}, ${link}, ${minutes}')
    value=clean(value) if html else value
    if not subject and '${link}' not in (plain(value) if html else value):raise ValueError('The message body must contain ${link}')
    return value


def document(fragment):
    return '<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;padding:16px;background:#ffffff;color:#222222;font-family:Arial,sans-serif;line-height:1.6"><div style="max-width:640px;margin:0 auto">'+fragment+'</div></body></html>'
