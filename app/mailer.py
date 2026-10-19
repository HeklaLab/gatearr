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
DEFAULTS_BY_LOCALE = {"en": DEFAULTS}

def config(db, key, default=""):
    row = db.get(Config, key)
    return row.value if row else default

def compose(db, recipient, purpose, values):
    locale = values.get("_locale", "en")
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
        msg.add_alternative(document(rendered),subtype="html")
    return msg

def send(db, recipient, purpose, values):
    msg=compose(db,recipient,purpose,values)
    host = config(db, "smtp_host")
    if not host:
        raise ValueError('SMTP not configured')
    mode = config(db, "smtp_mode", "starttls")
    port = int(config(db, "smtp_port", "587"))
    if mode == "ssl":
        connection = smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context())
    else:
        connection = smtplib.SMTP(host, port, timeout=15)
    with connection as smtp:
        smtp.ehlo()
        if mode == "starttls":
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        username = config(db, "smtp_username")
        if username:
            smtp.login(username, decrypt(config(db, "smtp_password")))
        smtp.send_message(msg)


def html_source(db,purpose):
    from html import escape
    return config(db,purpose+'_html') or '<p>'+escape(config(db,purpose+'_body',DEFAULTS[purpose+'_body'])).replace('\n','<br>')+'</p>'

def mail_template(db,purpose,part,locale,allow_disabled=False):
    from . import i18n
    if locale not in i18n.languages(db,all=allow_disabled):locale='en'
    if part=='html':
        source=html_source(db,purpose)
        value=i18n.content(db,'mail:'+purpose+':html',source,locale)
        return value if value!=source else config(db,purpose+'_html')
    source=config(db,purpose+'_'+part,DEFAULTS[purpose+'_'+part])
    return i18n.content(db,'mail:'+purpose+':'+part,source,locale)
