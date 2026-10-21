"""Collect English UI sources. Language packs are build-time assets, never fetched at runtime."""
import ast,json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1];path=root/'app/locales/en.json';catalog=json.loads(path.read_text())
def add(value):
    if isinstance(value,str) and value.strip() and len(value)<5001:catalog.setdefault(value,value)
for file in (root/'app/templates').glob('*.html'):
    for m in re.finditer(r"(['\"])((?:\\.|(?!\1).)*?)\1",file.read_text()):
        try:value=ast.literal_eval(m[0])
        except (ValueError,SyntaxError):continue
        if re.match(r'[A-Z][a-zA-Z ]',value) and '<' not in value and '=' not in value:add(value)
for file in [root/'app/static/studio.js',root/'app/static/visual-howto.js',root/'app/static/applications.js']:
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
for file in [root/'app/static/studio.js',root/'app/static/visual-howto.js',root/'app/static/applications.js']:
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
