"""Product terminology regressions; structural checks do not claim native proofreading."""
from collections import Counter
import re
import pytest
from app import i18n,main
from app.db import SessionLocal
from app.models import Language,User
from sqlalchemy import select
from test_portal import setup

EXPECTED_ACCOUNT={
 'ar':'الحساب','cs':'Účet','da':'Konto','de':'Konto','es':'Cuenta','fi':'Tili','fr':'Compte','he':'חשבון','it':'Account','ja':'アカウント','ko':'계정','nb':'Konto','nl':'Account','pl':'Konto','pt-br':'Conta','ru':'Учётная запись','sv':'Konto','tr':'Hesap','uk':'Обліковий запис','zh-cn':'账号',
}


def test_all_bundled_languages_use_reviewed_interface_terms_and_preserve_variables():
    assert set(i18n.CATALOGS)==set(EXPECTED_ACCOUNT)|{'en'}
    source=i18n.CATALOGS['en'];tokens=lambda value:Counter(re.findall(r'\$?\{[^{}]+\}',value))
    for code,catalog in i18n.CATALOGS.items():
        assert catalog.keys()==source.keys()
        for key,value in catalog.items():
            assert value.strip(),(code,key)
            assert tokens(key)==tokens(value),(code,key)
        if code!='en':
            assert catalog['Account']==EXPECTED_ACCOUNT[code]
            for key in ('Current version','Report an issue','Request a feature','Block settings','Image width (px)','Applications & API'):
                assert catalog[key]!=key,(code,key)
            assert '{name}' not in i18n.translate('Logged as {name}',code,name='Alex')
            assert 'Alex' in i18n.translate('View portal as {name}',code,name='Alex')


@pytest.mark.parametrize('code',EXPECTED_ACCOUNT)
def test_reviewed_labels_render_in_each_language_without_changing_user_overrides(client,code):
    setup(client)
    with SessionLocal() as db:
        if not db.get(Language,code):db.add(Language(code=code,name=code,enabled=True))
        else:db.get(Language,code).enabled=True
        db.flush()
        user=db.scalar(select(User).where(User.emby_id=='admin-1'));user.locale=code
        # An administrator's terminology must win over a revised bundled value.
        main.set_config(db,i18n.translation_key(code,'Branding'),'Custom appearance label')
        i18n.store_content(db,'mail:reset:subject','${app_name} — reset your password',code,'Custom ${app_name}')
        db.commit()
    updates=client.get('/admin/updates').text
    assert 'Custom appearance label' in updates
    assert i18n.translate('Current version',code) in updates
    assert ('dir="rtl"' in updates)==(code in ('ar','he'))
    with SessionLocal() as db:
        assert i18n.content(db,'mail:reset:subject','${app_name} — reset your password',code)=='Custom ${app_name}'
        assert i18n.overrides(db,code)['Branding']=='Custom appearance label'
