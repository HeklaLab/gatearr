import smtplib
import ssl
from email.message import EmailMessage
from string import Template
from .models import Config
from .security import decrypt
from .rich_mail import interpolate,plain,document

DEFAULTS = {'invite_subject': '${app_name} — welcome!', 'invite_body': 'Hello ${username},\n\nWelcome to ${app_name}. Confirm your email to access your account:\n${link}\n\nThis link expires in ${minutes} minutes.\n\n${app_name}', 'reset_subject': '${app_name} — reset your password', 'reset_body': 'Hello ${username},\n\nChoose a new password:\n${link}\n\nThis link expires in ${minutes} minutes. If you did not request it, ignore this message.\n\n${app_name}', 'verify_subject': '${app_name} — verify your email address', 'verify_body': 'Hello ${username},\n\nConfirm your email address:\n${link}\n\nThis link expires in ${minutes} minutes.\n\n${app_name}'}
DEFAULTS.update({
    'email_changed_subject':'${app_name} — email address changed',
    'email_changed_body':'Hello ${username},\n\nAn administrator changed the email address on your account. If you did not expect this change, contact your administrator.\n${link}',
    'password_changed_subject':'${app_name} — password changed',
    'password_changed_body':'Hello ${username},\n\nAn administrator changed your account password. If you did not expect this change, contact your administrator.\n${link}'})
DEFAULTS.update({'new_season_subject':'${app_name} — ${title}: a new season is available','new_season_body':'Hello ${username},\n\nSeason ${season} of ${title} is now available. Some episodes may still be arriving.\n${link}\n\n${app_name}'})
INVITE_BODY_V040 = 'Hello ${username},\n\nWelcome to ${app_name}. Confirm your email to access your account:\n${link}\n\nThis link expires in ${minutes} minutes.\n\n${app_name}'
DEFAULTS['invite_body'] = 'Hello ${username},\n\nWelcome to ${app_name}. Confirm your email to access your account:\n${link}\n\nThis link expires in ${minutes} minutes.\n\nOne portal, all your services.\nUse your existing Emby/Jellyfin password to sign in, change it yourself or recover access by email.\nFind guides to connect your media account on your phone, TV and other devices.\n\n${app_name}'
DEFAULTS_BY_LOCALE = {"en": DEFAULTS}

def config(db, key, default=""):
    row = db.get(Config, key)
    if key=='invite_body' and row and row.value==INVITE_BODY_V040:return DEFAULTS['invite_body']
    return row.value if row else default

def compose(db, recipient, purpose, values):
    from .i18n import default_language
    locale = values.get("_locale", default_language(db))
    def template(key):
        purpose,part=key.rsplit('_',1)
        return mail_template(db,purpose,part,locale,values.get("_allow_disabled",False))
    msg = EmailMessage()
    msg["Subject"] = Template(template(purpose + "_subject")).substitute(values)
    msg["From"] = config(db, "smtp_from")
    msg["To"] = recipient
    msg.set_content(Template(template(purpose + "_body")).substitute(values))
    html = mail_template(db,purpose,"html",locale,values.get("_allow_disabled",False))
    if html:
        rendered=interpolate(html,values)
        msg.set_content(plain(rendered))
        from .image_sources import local_path
        from html import escape
        import re
        base=config(db,'public_url').rstrip('/')
        def image(match):
            path=local_path(match.group(1),db)
            return 'src="'+escape(base+path,quote=True)+'"' if path and base else match.group(0)
        rendered=re.sub(r'src="([^"]+)"',image,rendered)
        msg.add_alternative(document(rendered),subtype="html")
    return msg

def send(db, recipient, purpose, values):
    from .mail_log import record
    msg=None;accepted=False;error='other'
    try:
        msg=compose(db,recipient,purpose,values)
        host=config(db,"smtp_host")
        if not host:
            error='configuration';raise ValueError('SMTP not configured')
        mode=config(db,"smtp_mode","starttls");port=int(config(db,"smtp_port","587"))
        connection=smtplib.SMTP_SSL(host,port,timeout=15,context=ssl.create_default_context()) if mode=='ssl' else smtplib.SMTP(host,port,timeout=15)
        with connection as smtp:
            smtp.ehlo()
            if mode=='starttls':smtp.starttls(context=ssl.create_default_context());smtp.ehlo()
            username=config(db,"smtp_username")
            if username:smtp.login(username,decrypt(config(db,"smtp_password")))
            refused=smtp.send_message(msg)
            if refused:raise smtplib.SMTPRecipientsRefused(refused)
            accepted=True
    except Exception as exc:
        if not accepted:
            if isinstance(exc,smtplib.SMTPAuthenticationError):error='authentication'
            elif isinstance(exc,smtplib.SMTPRecipientsRefused):error='recipients'
            elif isinstance(exc,smtplib.SMTPSenderRefused):error='sender'
            elif isinstance(exc,smtplib.SMTPDataError):error='data'
            elif isinstance(exc,(OSError,smtplib.SMTPConnectError,smtplib.SMTPServerDisconnected)):error='connection'
            elif isinstance(exc,(ValueError,KeyError)):error='configuration'
            raise
        # An error during QUIT does not undo SMTP acceptance or justify a resend.
    finally:
        record(db,recipient,purpose,msg['Subject'] if msg else '',values,'accepted' if accepted else 'failed','' if accepted else error)


def html_source(db,purpose):
    from html import escape
    return config(db,purpose+'_html') or '<p>'+escape(config(db,purpose+'_body',DEFAULTS[purpose+'_body'])).replace('\n','<br>')+'</p>'

def mail_template(db,purpose,part,locale,allow_disabled=False):
    from . import i18n
    if locale not in i18n.languages(db,all=allow_disabled):locale=i18n.default_language(db)
    if part=='html':
        source=html_source(db,purpose)
        value=i18n.content(db,'mail:'+purpose+':html',source,locale)
        return value if value!=source else config(db,purpose+'_html')
    source=config(db,purpose+'_'+part,DEFAULTS[purpose+'_'+part])
    return i18n.content(db,'mail:'+purpose+':'+part,source,locale)
