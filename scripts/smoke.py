"""Full browser-form smoke against a fresh isolated demo + Mailpit. Requires httpx."""
import argparse
import re
import time
import httpx


def csrf(client, path):
    response = client.get(path)
    response.raise_for_status()
    match = re.search(r'name="csrf" value="([^"]+)"', response.text)
    assert match, f'No CSRF field on {path}'
    return match[1]

def submit(client, path, data, page):
    response = client.post(path, data={'csrf': csrf(client, page), **data})
    assert response.status_code in (200, 303), f'{path}: {response.status_code}'
    return response

def wait_mail(mailpit, purpose):
    deadline = time.monotonic() + 40
    with httpx.Client(base_url=mailpit, timeout=5, trust_env=False) as mail:
        while time.monotonic() < deadline:
            result = mail.get('/api/v1/messages')
            result.raise_for_status()
            for summary in result.json().get('messages', []):
                message = mail.get('/api/v1/message/' + summary['ID']).json()
                match = re.search(r'http[^\s]+/' + purpose + r'\?token=([\w-]+)', message.get('Text', ''))
                if match:
                    return match[1]
            time.sleep(1)
    raise AssertionError('Email not received')

def run(base='http://localhost:8000', mailpit='http://localhost:8025', smtp_host='mailpit', smtp_port='1025', reader=None, services_base='http://mock-services:8097',media_base='http://mock-emby:8096/emby'):
    reader = reader or (lambda purpose: wait_mail(mailpit, purpose))
    with httpx.Client(base_url=base, follow_redirects=False, timeout=20, trust_env=False) as client:
        deadline = time.monotonic() + 60
        while True:
            try:
                if client.get('/healthz').status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() >= deadline:
                raise AssertionError('Portal not healthy')
            time.sleep(1)
        assert client.get('/setup').status_code == 200, 'Smoke requires fresh demo volumes'
        assert '<html lang="en">' in client.get('/setup').text
        submit(client, '/setup', {'app_name':'Gatearr','public_url':base,'media_server':'emby','url':media_base,'api_key':'demo-emby-key'}, '/setup')
        submit(client,'/setup/admin',{'user_id':'demo-admin-1','password':'AdminPassword123!'},'/setup/admin')
        for step in ('seerr','tools','smtp'):
            submit(client,'/admin/setup/'+step,{'action':'skip'},'/admin/setup/'+step)
        submit(client,'/admin/setup/finish',{},'/admin/setup/finish')
        submit(client, '/admin/smtp', {'smtp_host': smtp_host, 'smtp_port': smtp_port, 'smtp_mode': 'plain', 'smtp_from': 'portal@example.com', 'smtp_username': '', 'smtp_password': ''}, '/admin')
        submit(client, '/admin/settings', {'app_name': 'Gatearr', 'login_text': 'Your media world, all in one place.', 'logo_url': '', 'public_url': base, 'emby_link': 'https://emby.example.com'}, '/admin')
        submit(client, '/admin/menu', {'label': 'Seerr', 'url': 'https://requests.example.com', 'icon': 'link', 'position': '10', 'new_tab': 'on'}, '/admin')
        submit(client, '/admin/sync', {}, '/admin')
        assert 'disabled' in client.get('/admin/users').text
        submit(client, '/admin/emby/clone', {'source_id':'demo-user-1','name':'cloned-demo','password':'ClonedPassword123!','copy_options':['Policy','Configuration','DisplayPreferences']}, '/admin/emby')
        admin_page=client.get('/admin/users').text
        cloned_id=re.search(r'href="/admin/users/(\d+)">cloned-demo',admin_page)[1]
        submit(client, '/admin/emby/libraries', {'id':cloned_id,'libraries':['22222222222222222222222222222222']}, '/admin/users/'+cloned_id)
        assert 'Films' in client.get('/admin/users/'+cloned_id).text
        submit(client, '/admin/emby/copy', {'id':cloned_id,'source_id':'demo-user-1','copy_options':['Configuration','DisplayPreferences'],'acknowledge':'on'}, '/admin/users/'+cloned_id)
        submit(client, '/admin/integrations', {'service':'seerr','enabled':'on','url':services_base+'/seerr','api_key':'demo-seerr-key','notification_mode':'optional'}, '/admin/integrations')
        def layout_version():
            return re.search(r'name="version" value="(\d+)"',client.get('/admin/portal').text)[1]
        submit(client, '/admin/portal/block', {'version':layout_version(),'kind':'text','region':'main','order':'11','span':'12','title':'Welcome to Gatearr','body':'Your movie night starts here. Find your films, shows and requests in one place.'}, '/admin/portal')
        submit(client, '/admin/portal/theme', {'version':layout_version(),'nav_position':'left','accent':'#c9a7ff','bg':'#10151b','surface':'#1a222c','text':'#edf3f9','muted':'#aab8c9'}, '/admin/portal')
        assert 'Welcome to Gatearr' not in client.get('/home').text
        assert 'Welcome to Gatearr' in client.get('/admin/portal/preview').text
        submit(client, '/admin/portal/publish', {'version':layout_version()}, '/admin/portal')
        assert 'Welcome to Gatearr' in client.get('/home').text
        submit(client, '/admin/guides/service', {'key':'emby','name':'Emby','browser_url':'https://emby.example.com','server_url':'https://media.example.com:8920'}, '/admin/guides')
        assert 'Emby on Windows' in client.get('/admin/guides').text
        assert 'Emby on Android' in client.get('/admin/guides').text
        assert 'Gatearr 0.2.0' in client.get('/admin/updates').text
        submit(client,'/admin/footer',{'version':0,'kind':'link','text':'Community','url':'https://community.example.com','position':20},'/admin/footer')
        assert 'community.example.com' not in client.get('/forgot').text
        assert 'community.example.com' in client.get('/admin/footer/preview').text
        submit(client,'/admin/footer',{'version':1,'action':'publish'},'/admin/footer')
        assert 'community.example.com' in client.get('/forgot').text
        users_page=client.get('/admin/users').text
        demo_id=re.search(r'href="/admin/users/(\d+)">demo(?: |<)',users_page)[1]
        group=client.post('/admin/groups',data={'csrf':csrf(client,'/admin/groups'),'name':'Demo members'})
        assert group.status_code==303
        group_path=group.headers['location']
        submit(client,group_path,{'version':0,'members':demo_id,'permission':['SimultaneousStreamLimit','EnableSubtitleDownloading'],'value_SimultaneousStreamLimit':'2','value_EnableSubtitleDownloading':'false','library_mode':'selected','libraries':['11111111111111111111111111111111']},group_path)
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            detail=client.get('/admin/users/'+demo_id).text
            if 'sync-green' in detail and 'name="value" min="0" max="2147483647" value="2"' in detail:break
            time.sleep(1)
        else:raise AssertionError('Group permission readback did not complete')
        guide_ids={}
        for device,fr,en in [('desktop','Emby sur Mac','Emby on Mac'),('desktop','Emby sur Windows','Emby on Windows'),('mobile','Emby sur Android','Emby on Android'),('mobile','Emby sur iPhone','Emby on iPhone'),('tv','Emby sur TV','Emby on TV')]:
            created=client.post('/admin/guides/create',data={'csrf':csrf(client,'/admin/guides'),'service_key':'emby','title':en},follow_redirects=False)
            assert created.status_code==303
            editor=created.headers['location']
            guide_id=editor.rsplit('/',1)[1]
            guide_ids[en]=guide_id
            assert client.get('/help/'+guide_id).status_code==404
            submit(client,editor,{'version':'0','action':'publish','device':device,'position':'10','title':en,'summary':'Connect your device in three steps.','step_count':'3',
                'step_0_title':'Install the app','step_0_body':'Find Emby in your device’s app store.','step_0_link_url':'https://emby.media/download.html','step_0_link_label':'Download Emby',
                'step_1_title':'Add the server','step_1_body':'Address: {server_host} — port: {server_port}. Full address: {server_url}',
                'step_2_title':'Sign in','step_2_body':'Use your username {username} and your Emby password.'},editor)
            assert 'media.example.com' in client.get('/help/'+guide_id).text
        counter=0
        def add_node(kind,fr,en,parent='',**fields):
            nonlocal counter
            counter+=10
            version=re.search(r'name="version" value="(\d+)"',client.get('/admin/access/emby').text)[1]
            submit(client,'/admin/access/emby',{'action':'save','version':version,'kind':kind,'title':en,'parent':parent,'position':str(counter),**fields},'/admin/access/emby')
            return re.findall(r'name="id" value="([^"]+)"',client.get('/admin/access/emby').text)[-1]
        add_node('browser','Navigateur','Browser')
        desktop=add_node('group','Emby sur ordinateur','Emby on a computer')
        mobile=add_node('group','Emby sur mobile','Emby on mobile')
        for label,parent in [('Mac',desktop),('Windows',desktop),('Android',mobile),('iPhone',mobile),('TV','')]:
            add_node('guide',label,label,parent,guide_id=guide_ids['Emby on '+label])
        version=re.search(r'name="version" value="(\d+)"',client.get('/admin/access/emby').text)[1]
        submit(client,'/admin/access/emby',{'action':'publish','version':version},'/admin/access/emby')
        submit(client,'/admin/guides/service',{'key':'emby','name':'Emby','entry_mode':'structured','icon_url':base+'/static/demo-emby.png','browser_url':'https://emby.example.com','server_url':'https://media.example.com:8920'},'/admin/guides')
        assert 'href="/access/emby"' in client.get('/home').text
        assert 'Browser' in client.get('/access/emby').text
        submit(client, '/language', {'locale':'en','next':'/home'}, '/home')
        assert 'Welcome to Gatearr' in client.get('/home').text
        submit(client, '/logout', {}, '/account')
        submit(client, '/login', {'name': 'demo', 'password': 'DemoPassword123!'}, '/login')
        assert 'Seerr' in client.get('/account').text
        assert client.get('/admin').status_code == 403
        assert 'Emby on mobile' in client.get('/access/emby').text
        assert client.get('/help/'+guide_id+'?preview=1').status_code == 403
        submit(client, '/account/email', {'email': 'demo@example.com', 'current': 'DemoPassword123!'}, '/account')
        verify = reader('verify-email')
        submit(client, '/verify-email', {'token': verify}, '/verify-email?token=' + verify)
        submit(client, '/account/preferences', {'service':'seerr','enabled':'on'}, '/account')
        submit(client, '/account/password', {'current': 'DemoPassword123!', 'password': 'ChangedPassword123!', 'confirm': 'ChangedPassword123!'}, '/account')
        assert client.get('/account').status_code == 401
        submit(client, '/login', {'name': 'demo', 'password': 'ChangedPassword123!'}, '/login')
        submit(client, '/logout', {}, '/account')
        submit(client, '/forgot', {'email': 'demo@example.com'}, '/forgot')
        reset = reader('reset')
        token_csrf = csrf(client, '/reset?token=' + reset)
        payload = {'csrf': token_csrf, 'token': reset, 'password': 'ResetPassword123!', 'confirm': 'ResetPassword123!'}
        assert client.post('/reset', data=payload).status_code == 200
        assert client.post('/reset', data=payload).status_code == 400
        submit(client, '/login', {'name': 'demo', 'password': 'ResetPassword123!'}, '/login')
        assert 'demo@example.com' in client.get('/account').text
        assert client.get('/home').status_code == 200
        submit(client, '/logout', {}, '/account')
        submit(client, '/login', {'name':'portal-admin','password':'AdminPassword123!'}, '/login')
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            page=client.get('/admin/integrations').text
            if page.count('Synchronized') >= 1:
                break
            time.sleep(1)
        else:
            raise AssertionError('Email not propagated to Seerr')
        statuses=client.get('/admin/users').text
        assert statuses.count('sync-green') >= 3 and 'Last success:' in statuses
    print('Smoke passed: setup, native clone, library access, settings copy, English block builder, draft/publish, nested application journeys, PNG icons and Seerr preferences, hover sync indicators, email proof, password change/reset and automatic Seerr propagation.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8000')
    parser.add_argument('--mailpit', default='http://localhost:8025')
    args = parser.parse_args()
    run(args.url, args.mailpit)
