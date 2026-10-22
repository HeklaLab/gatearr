"""Collect English UI sources. Language packs are build-time assets, never fetched at runtime."""
import ast,json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1];path=root/'app/locales/en.json';catalog=json.loads(path.read_text())
def add(value):
    if isinstance(value,str) and value.strip() and value not in ('HR','IMG','Alex') and len(value)<5001:catalog.setdefault(value,value)
for file in (root/'app/templates').glob('*.html'):
    for m in re.finditer(r"(['\"])((?:\\.|(?!\1).)*?)\1",file.read_text()):
        try:value=ast.literal_eval(m[0])
        except (ValueError,SyntaxError):continue
        if re.match(r'[A-Z][a-zA-Z ]',value) and '<' not in value and '=' not in value:add(value)
for file in [root/'app/static/studio.js',root/'app/static/visual-howto.js',root/'app/static/applications.js',root/'app/static/mail-editor.js']:
    if not file.exists():continue
    for m in re.finditer(r"'((?:\\.|[^'\\])*)'",file.read_text()):
        try:value=ast.literal_eval(m[0])
        except (ValueError,SyntaxError):continue
        if re.match(r'[A-Z][a-zA-Z ]',value) and '<' not in value and '=' not in value:add(value)
for file in (root/'app').glob('*.py'):
    tree=ast.parse(file.read_text())
    for n in ast.walk(tree):
        if isinstance(n,ast.Raise) and isinstance(n.exc,ast.Call):
            for a in n.exc.args:
                if isinstance(a,ast.Constant) and isinstance(a.value,str):add(a.value)
        if file.name=='mailer.py' and isinstance(n,ast.Dict):
            for k,v in zip(n.keys,n.values):
                if isinstance(k,ast.Constant) and isinstance(k.value,str) and re.fullmatch(r'(invite|reset|verify|email_changed|password_changed)_(subject|body)',k.value) and isinstance(v,ast.Constant):add(v.value)
def authored(value):
    if isinstance(value,dict):
        for k,v in value.items():
            if k in ('title','summary','body','link_label') and isinstance(v,str):add(v)
            else:authored(v)
    elif isinstance(value,list):
        for v in value:authored(v)
authored(json.loads((root/'app/journey_defaults.json').read_text()))
# Named permission flags and statistic labels are displayed dynamically.
for file in [root/'app/seerr_permissions.py']:
    for node in ast.walk(ast.parse(file.read_text())):
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FLAGS' for t in node.targets):
            for v in node.value.values:
                if isinstance(v,ast.Constant):add(v.value)
# Typed permission categories and field labels are also dynamic UI sources.
for name in ('permissions.py','permission_ui.py'):
    tree=ast.parse((root/'app'/name).read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.Dict):
            for value in node.values:
                if isinstance(value,ast.Constant) and isinstance(value.value,str) and ' ' in value.value and value.value[:1].isupper():add(value.value)
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('CATEGORIES','DAYS') for t in node.targets):
            for value in ast.walk(node.value):
                if isinstance(value,ast.Constant) and isinstance(value.value,str) and value.value[:1].isupper():add(value.value)
for value in ('Processing','Awaiting approval','Movies left','Seasons left','Approved','Available','changed','not configured','not imported','failed — retry required','pending'):add(value)
path.write_text(json.dumps(catalog,indent=2,ensure_ascii=False)+'\n');print('English sources:',len(catalog))

# Only actual UI literals belong in the fixed-interface editor. Preserve the full
# catalog for legacy overrides and default authored-content fallback translations.
from jinja2 import Environment,nodes
interface=set()
def ui(value):
    if isinstance(value,str) and value in catalog and re.match(r'[A-Z][A-Za-z ]',value) and '${' not in value and not any(x in value for x in ('<','=', '\n','" if ',"' if ")):interface.add(value)
for file in (root/'app/templates').glob('*.html'):
    for node in Environment().parse(file.read_text()).find_all(nodes.Const):ui(node.value)
for file in [root/'app/static/studio.js',root/'app/static/visual-howto.js',root/'app/static/applications.js',root/'app/static/mail-editor.js']:
    for m in re.finditer(r"'((?:\\.|[^'\\])*)'",file.read_text()):
        try:ui(ast.literal_eval(m[0]))
        except (ValueError,SyntaxError):pass
for file in (root/'app').glob('*.py'):
    for n in ast.walk(ast.parse(file.read_text())):
        if isinstance(n,ast.Raise) and isinstance(n.exc,ast.Call):
            for arg in n.exc.args:
                if isinstance(arg,ast.Constant):ui(arg.value)
(root/'app/interface_keys.json').write_text(json.dumps(sorted(interface),indent=2,ensure_ascii=False)+'\n')
print('Fixed interface keys:',len(interface))

interface.update(['Processing','Awaiting approval','Movies left','Seasons left','Approved','Available','changed','not configured','not imported','failed — retry required','pending'])
for node in ast.walk(ast.parse((root/'app/seerr_permissions.py').read_text())):
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FLAGS' for t in node.targets):
        interface.update(v.value for v in node.value.values if isinstance(v,ast.Constant))
interface.difference_update(('ArrowUp','ArrowDown','Enter'))
(root/'app/interface_keys.json').write_text(json.dumps(sorted(interface),indent=2,ensure_ascii=False)+'\n')

# Expose dynamically generated permission labels in the translation editor too.
for filename in ('permissions.py','permission_ui.py'):
    tree=ast.parse((root/'app'/filename).read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.Dict):
            for value in node.values:
                if isinstance(value,ast.Constant) and isinstance(value.value,str) and ' ' in value.value:ui(value.value)
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('CATEGORIES','DAYS') for t in node.targets):
            for value in ast.walk(node.value):
                if isinstance(value,ast.Constant):ui(value.value)
(root/'app/interface_keys.json').write_text(json.dumps(sorted(interface),indent=2,ensure_ascii=False)+'\n')
