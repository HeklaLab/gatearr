"""Status describes the latest locally observed synchronization, not a live probe."""
import time
from sqlalchemy import select
from .models import User, IntegrationJob
from .mailer import config
from .security import digest
from .integrations import enabled, sync_digest
from .connection_health import configured
from .i18n import translate, overrides

ERRORS = {
    'authentication':'Authentication rejected', 'not_found':'Remote account not found',
    'configuration':'Incomplete configuration', 'notifications_disabled':'Email notifications must be enabled in Seerr', 'identity_mismatch':'identity_mismatch',
    'ambiguous':'Multiple matching accounts', 'unsupported_api':'Unsupported API',
    'invalid_pagination':'Invalid remote pagination', 'verification_failed':'Remote verification failed',
    'remote_error':'remote_error', 'unavailable':'unavailable',
}

def user_statuses(db, locale):
    custom=overrides(db,locale)
    tr = lambda text: translate(text,locale,overrides=custom)
    def stamp(value):
        return time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime(value)) if value is not None else '—'
    jobs = {(job.user_id,job.service):job for job in db.scalars(select(IntegrationJob))}
    result = {}
    for user in db.scalars(select(User)):
        statuses = []
        for service,label in (('emby','Jellyfin' if config(db,'media_server')=='jellyfin' else 'Emby'),('seerr','Seerr')):
            if service!='emby' and not configured(db,service):continue
            if not user.emby_id:
                statuses.append({'service':label,'color':'neutral','label':tr('Not applicable'),'detail':tr('Local administrator account without an Emby link')})
                continue
            if service == 'emby':
                success = user.emby_seen_at
                error = config(db,'emby_sync_error')
                sync_at = int(config(db,'emby_sync_at','0'))
                current = success is not None and success == sync_at and not error and not user.emby_missing
                reason = tr('Emby import confirmed') if current else tr('Connection changed, verification required' if error=='configuration_changed' else 'unavailable' if error else 'Account missing from the latest import')
                attempt = stamp(int(config(db,'emby_sync_attempt_at','0'))) if config(db,'emby_sync_attempt_at') else '—'
            else:
                job = jobs.get((user.id,service))
                success = job.last_success_at if job else None
                current = bool(job and job.state == 'success' and user.email and job.email_digest == sync_digest(db,user,service) and enabled(db,service) and user.active)
                attempt = stamp(job.updated_at) if job else '—'
                if not enabled(db,service):
                    reason = tr('Synchronization disabled')
                elif not user.active:
                    reason = tr('Account disabled')
                elif not user.email:
                    reason = tr('Email address not verified')
                elif job and job.state == 'error':
                    reason = tr(ERRORS.get(job.error,'unavailable'))
                elif current:
                    reason = tr('Email address verified on the remote service')
                else:
                    reason = tr('Synchronization pending')
            color = 'green' if current else ('orange' if success is not None else 'red')
            state = tr({'green':'success','orange':'Out of date','red':'Never synchronized'}[color])
            detail = '\n'.join((label+' · '+state,reason,tr('Last success:')+' '+stamp(success),tr('Last attempt:')+' '+attempt,tr('Status reflects the latest Gatearr synchronization.')))
            statuses.append({'service':label,'color':color,'label':state,'detail':detail})
        result[user.id] = statuses
    return result
