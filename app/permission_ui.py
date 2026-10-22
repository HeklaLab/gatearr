"""Typed policy controls. Server DTOs stay on the server, never in textareas."""
from copy import deepcopy
import re
from decimal import Decimal,InvalidOperation
from .emby import EmbyError

DAYS=('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Everyday','Weekday','Weekend')
UNRATED=('Movie','Trailer','Series','Music','Book','LiveTvChannel','LiveTvProgram','ChannelContent','Other')
CATEGORIES=(('libraries','Libraries and folders'),('playback','Playback and streaming'),('parental','Parental controls'),('devices','Devices and remote control'),('schedule','Access schedules'),('management','Media management'),('security','Account security'),('advanced','Advanced settings'))
LIST_SOURCES={'EnabledFolders':'libraries','EnableContentDeletionFromFolders':'libraries','ExcludedSubFolders':'folders','BlockedMediaFolders':'folders','EnabledDevices':'devices','EnabledChannels':'channels','BlockedChannels':'channels'}
ENUMS={'SyncPlayAccess':('CreateAndJoinGroups','JoinGroups','None')}

def category(key):
    if key=='AccessSchedules':return 'schedule'
    if key in ('IsAdministrator','IsDisabled') or key.startswith('IsHidden'):return 'security'
    if any(x in key for x in ('Rating','Unrated','Tags','TagBlocking')):return 'parental'
    if any(x in key for x in ('Device','Control','SyncPlay')):return 'devices'
    if any(x in key for x in ('Folder','Channel','LiveTv')) and 'Deletion' not in key:return 'libraries'
    if any(x in key for x in ('Playback','Transcod','RemoteAccess','Bitrate','StreamLimit','ActiveSessions','Remux')):return 'playback'
    if any(x in key for x in ('Deletion','Download','Subtitle','Management','Sharing','Upload','Conversion','PersonalItems')):return 'management'
    return 'advanced'

def metadata(api,policy,libraries):
    """Failure of an optional capability disables its control, never empties a selection."""
    result={'libraries':libraries,'errors':[],'policy':policy}
    sources=set(LIST_SOURCES[k] for k in policy if k in LIST_SOURCES)
    if any(k in policy for k in ('MaxParentalRating','MaxParentalSubRating')):sources.add('ratings')
    for source in sources-{'libraries'}:
        try:
            loader=getattr(api,'permission_options',None)
            if loader is None:raise ValueError('Unavailable')
            result[source]=loader(source)
        except (ValueError,EmbyError):
            result[source]=None;result['errors'].append(source)
    return result

def controls(items,meta):
    grouped={key:[] for key,_ in CATEGORIES}
    for source in items:
        field=deepcopy(source);key=field['key'];value=field['value']
        field.update(editor=field['kind'],options=[],unavailable=False)
        if field['kind']=='bool':field['access_color']='green' if value != (key=='IsDisabled') else 'red'
        if key=='RemoteClientBitrateLimit':field.update(editor='bitrate',display_value=str(Decimal(value)/1000000),label='Remote bitrate limit (Mbps; 0 = unlimited)')
        if key in LIST_SOURCES:
            field['editor']='choices';field['options']=deepcopy(meta.get(LIST_SOURCES[key]) or [])
            flag={'EnabledFolders':'EnableAllFolders','EnabledDevices':'EnableAllDevices','EnabledChannels':'EnableAllChannels'}.get(key)
            field['effective_all']=bool(meta.get('policy',{}).get(flag)) if flag else False
            known={str(x['Id']) for x in field['options']}
            # Preserve references no longer listed, without exposing opaque IDs.
            for n,identifier in enumerate(value or []):
                if str(identifier) not in known:field['options'].append({'Id':identifier,'Name':f'Previously selected item {n+1} (unavailable)'})
            field['unavailable']=meta.get(LIST_SOURCES[key]) is None
        elif key=='BlockUnratedItems':field.update(editor='choices',options=[{'Id':x,'Name':re.sub(r'(?<=[a-z])(?=[A-Z])',' ',x)} for x in dict.fromkeys((*UNRATED,*(value or [])))])
        elif key=='AccessSchedules':
            field['editor']='schedules';field['schedules']=[]
            for i,row in enumerate(value or []):
                field['schedules'].append({'index':i,'day':row.get('DayOfWeek','Monday'),'start':hour_text(row.get('StartHour',0)),'end':hour_text(row.get('EndHour',24))})
        elif key in ENUMS:field.update(editor='enum',options=list(dict.fromkeys((*ENUMS[key],value))))
        elif key in ('MaxParentalRating','MaxParentalSubRating'):
            field.update(editor='rating',options=meta.get('ratings') or [],unavailable=meta.get('ratings') is None)
            if value is not None and not any(x['Id']==value for x in field['options']):field['options'].append({'Id':value,'Name':'Current server rating'})
        elif isinstance(value,list) and all(isinstance(x,str) for x in value):field.update(editor='tokens',text='\n'.join(value))
        elif field['kind']=='json':field.update(editor='readonly',editable=False)
        if not field['editable']:field['editor']='readonly'
        field['display']='Yes' if value is True else 'No' if value is False else 'No restriction' if value is None else f'{len(value)} configured items' if isinstance(value,(list,dict)) else str(value)
        if not field['editable']:field['display']='Managed by the media server'
        grouped[category(key)].append(field)
    return [{'id':key,'title':title,'fields':grouped[key],'can_edit':any(f['editable'] and not f['unavailable'] for f in grouped[key])} for key,title in CATEGORIES if grouped[key]]

def hour_text(value):
    minutes=round(float(value)*60)
    return f'{minutes//60:02}:{minutes%60:02}'

def parse_hour(text,end=False):
    if text=='24:00' and end:return 24
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',text):raise ValueError('Enter a valid time')
    h,m=map(int,text.split(':'));return h+m/60

def parse(field,data,prefix=''):
    key=field['key'];name=prefix+key;editor=field['editor'];old=field['value']
    if not field['editable'] or field['unavailable']:raise ValueError('This control is unavailable. Refresh the server information.')
    raw=str(data.get(name,''))
    if editor=='bool':return data.get(name)=='on'
    if editor=='bitrate':
        try:value=Decimal(raw)*1000000
        except InvalidOperation:raise ValueError('Enter a valid bitrate')
        if not value.is_finite() or value!=value.to_integral_value() or not 0<=value<=2147483647:raise ValueError('Enter a valid bitrate')
        return int(value)
    if editor=='int':
        try:value=int(raw)
        except ValueError:raise ValueError('Enter a whole number')
        if not 0<=value<=2147483647:raise ValueError('Use a number between 0 and 2147483647')
        return value
    if editor=='rating':
        if not raw:return None
        if raw not in {str(x['Id']) for x in field['options']}:raise ValueError('Choose a rating from the server')
        return int(raw)
    if editor=='enum':
        if raw not in field['options']:raise ValueError('Choose a supported option')
        return raw
    if editor=='choices':
        selected=list(dict.fromkeys(data.getlist(name)))
        if not set(selected)<={str(x['Id']) for x in field['options']}:raise ValueError('Unknown selection. Reload the page.')
        return selected
    if editor=='tokens':
        values=list(dict.fromkeys(x.strip() for x in raw.splitlines() if x.strip()))
        if len(values)>200 or any(len(x)>200 or any(ord(c)<32 for c in x) for x in values):raise ValueError('Invalid list of values')
        return values
    if editor=='schedules':
        result=[];seen=set()
        for index in data.getlist(name+'_row'):
            if not re.fullmatch(r'\d{1,6}',index) or index in seen or len(seen)>=50:raise ValueError('Invalid schedule')
            seen.add(index);stem=name+'_'+index+'_';day=str(data.get(stem+'day',''))
            if day not in DAYS:raise ValueError('Choose a day')
            start=parse_hour(str(data.get(stem+'start','')));end=parse_hour(str(data.get(stem+'end','')),True)
            if end<=start:raise ValueError('The end time must be after the start time. Split overnight access into two schedules.')
            # Keep native IDs and future metadata of existing schedules.
            row=deepcopy(old[int(index)]) if int(index)<len(old or []) else {}
            row.update(DayOfWeek=day,StartHour=start,EndHour=end);result.append(row)
        return result
    if editor=='str' and len(raw)<=2000:return raw
    raise ValueError('This field is managed by the media server')
