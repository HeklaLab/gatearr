"""Build the explicit public-label inventory from reviewed public entry points.

Run after changing public UI copy. Admin pages and builder configuration are not
entry points. Shared public navigation is listed explicitly and translated through
_public when rendered on admin pages. Runtime loads the generated inventory only.
"""
import ast,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'app'
catalog=json.loads((ROOT/'locales/en.json').read_text());legacy=json.loads((ROOT/'legacy_i18n.json').read_text());keys=set()
def include(value):
    value=legacy.get(value,value)
    if value in catalog and not re.fullmatch(r'[a-z]+(?:_[a-z]+)+',value):keys.add(value)
for name in ('header_brand','header_navigation','header_account','account_intro','account_email','account_password','account_language','forgot_form','reset_form','account_form','bazarr_subtitles_account','managed_language','application_information','access_content','guide_content','account','account_notifications','access','avatar','blocks','captcha_field','error','footer','forgot','guide','home','login','login_form','message','page_layout','password_rules','photo_editor','reset','verify','widget','seerr_handoff'):
    source=(ROOT/'templates'/f'{name}.html').read_text()
    for match in re.finditer(r"(['\"])((?:\\.|(?!\1).)*?)\1",source):
        try:include(ast.literal_eval(match[0]))
        except (ValueError,SyntaxError):pass
    # HTML attribute quotes can surround Jinja calls: inspect their literals
    # separately so accessible navigation names are not swallowed by the HTML.
    for match in re.finditer(r"\b(?:_|_public)\(\s*('(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")",source):
        try:include(ast.literal_eval(match[1]))
        except (ValueError,SyntaxError):pass
functions={
 'main.py':{'login','logout','account','change_password','change_email','verify_page','verify_email','forgot','reset_page','reset','change_language','require_user','limit'},
 'widgets.py':{'media_metrics','seerr_metrics','tracearr_period','tracearr_metrics','library_events','display'},
 'preferences.py':{'preferences','notifications'},
 'library_updates.py':{'account_preference','save_preference','open_event'},
 'security.py':{'password_ok','email_ok'},
 'captcha.py':{'verify'},
}
for file,names in functions.items():
    tree=ast.parse((ROOT/file).read_text())
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names or file=='widgets.py' and isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='METRICS' for t in node.targets):
            for value in ast.walk(node):
                if isinstance(value,ast.Constant) and isinstance(value.value,str):include(value.value)
keys.update({'Home','My account','Language','Sign out','Sign in','Appearance','Automatic','Dark','Light','Save','Cancel','Receive notifications about my requests','ACCOUNT RECOVERY','A fresh start.','Hello, {name}.','{app_name} · Your services, one place.','Choose an image','Replace image','No image selected','Choose an image up to 5 MB.','Saving…','Saved','Failed','Form expired. Reload the page.'})
keys-= {'Select pages in the block settings.','Shown when this feature is available to the user.','Preview only','Local administrator account.','Administration','Administrator','Admin tools'}
(ROOT/'public_interface_keys.json').write_text(json.dumps(sorted(keys),ensure_ascii=False,indent=2)+'\n')
print(f'{len(keys)} public labels cataloged')
