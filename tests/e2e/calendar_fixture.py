"""Developer-authorized, attempt-owned clock preparation before customer input.

Set a future ordinary day before customer input, then let real seconds elapse.
The normal owned snapshot restoration removes the clock/synchronization changes.
"""

ORDINARY_CLOCK = '''import datetime,json,os,subprocess,time
from zoneinfo import ZoneInfo
assert os.geteuid()==0
def clock_property(name):
    return subprocess.run(['timedatectl','show','--property='+name,'--value'],
        check=True,capture_output=True,text=True,timeout=15).stdout.strip()
zone=clock_property('Timezone')
tz=ZoneInfo(zone)
before=time.time_ns()
today=datetime.datetime.fromtimestamp(before/1e9,tz).date()
for days in range(1,8):
    day=today+datetime.timedelta(days=days)
    start=datetime.datetime.combine(day,datetime.time(),tz)
    end=start+datetime.timedelta(days=1)
    if end.timestamp()-start.timestamp()==86400 and start.utcoffset()==end.utcoffset():
        target=start.replace(hour=PRESET_HOUR,minute=PRESET_MINUTE)
        break
else:
    raise RuntimeError('calendar-fixture:no-ordinary-day')
previous_ntp=clock_property('NTP')
assert previous_ntp in ('yes','no')
subprocess.run(['timedatectl','set-ntp','false'],check=True,timeout=30)
assert clock_property('NTP')=='no'
subprocess.run(['timedatectl','set-time',target.strftime('%Y-%m-%d %H:%M:%S')],
    check=True,timeout=30)
assert clock_property('Timezone')==zone and clock_property('NTP')=='no'
after=time.time_ns()
target_ns=int(target.timestamp())*1000000000
assert before<target_ns and 0<=after-target_ns<30000000000
print(json.dumps({'timezone':zone,'before_epoch_ns':before,'target_epoch_ns':target_ns,
    'readback_epoch_ns':after,'target_local_time':target.isoformat(),
    'previous_ntp':previous_ntp,'ntp_enabled':False},sort_keys=True))
'''

ORDINARY_MIDNIGHT = 'PRESET_HOUR,PRESET_MINUTE=23,35\n' + ORDINARY_CLOCK
ORDINARY_DAYTIME = 'PRESET_HOUR,PRESET_MINUTE=12,0\n' + ORDINARY_CLOCK


def preset_ordinary_midnight(journey, guard):
    """One fixed preparation, after restore/setup and before any parent input."""
    return _preset_ordinary(journey, guard, ORDINARY_MIDNIGHT,
        ('ordinary-daily-reset', 'ordinary-rest-of-day', 'ordinary-fixed-grant'))


def preset_ordinary_daytime(journey, guard):
    """Start a declared non-calendar journey at noon, independent of host time."""
    return _preset_ordinary(journey, guard, ORDINARY_DAYTIME,
                            ('homework-game', 'game-permission', 'riley-game-permission',
                             'family-routines', 'lunar-denial', 'minecraft-access'))


def _preset_ordinary(journey, guard, program, prefixes):
    import json
    from private_artifacts import require
    import watch_activity

    require(journey.plan.prefix in prefixes
            and [step['stage'] for step in journey.steps] == ['ready']
            and journey.transport is not None
            and journey.transport.lease is journey.context.lease,
            'calendar-fixture:entry')
    guard()
    with watch_activity.operation('Preparing the test clock before parent or child actions'):
        raw = journey.transport.call(['/usr/bin/python3', '-I', '-c', program],
                                     timeout=120)
    guard()
    value = json.loads(raw)
    require(value['ntp_enabled'] is False
            and value['before_epoch_ns'] < value['target_epoch_ns']
            <= value['readback_epoch_ns'] < value['target_epoch_ns'] + 30_000_000_000,
            'calendar-fixture:readback')
    return value


SEASONAL_TRANSITION = '''import datetime,json,os,subprocess,sys,time
from zoneinfo import ZoneInfo
assert os.geteuid()==0
change=int(sys.argv[1])
assert change in (-3600,3600)
def clock_property(name):
    return subprocess.run(['timedatectl','show','--property='+name,'--value'],
        check=True,capture_output=True,text=True,timeout=15).stdout.strip()
zone=clock_property('Timezone')
tz=ZoneInfo(zone)
before=time.time_ns()
start=before//1000000000+3600
offset=lambda epoch: int(datetime.datetime.fromtimestamp(epoch,tz).utcoffset().total_seconds())
previous=start
for current in range(start+3600,start+370*86400,3600):
    if offset(current)-offset(previous)==change:
        low,high=previous,current
        while high-low>1:
            middle=(low+high)//2
            if offset(middle)==offset(previous): low=middle
            else: high=middle
        boundary=high
        break
    previous=current
else:
    raise RuntimeError('calendar-fixture:no-seasonal-window')
target=boundary-1800
local=datetime.datetime.fromtimestamp(target,tz)
midnight=datetime.datetime.combine(local.date()+datetime.timedelta(days=1),datetime.time(),tz)
day_start=datetime.datetime.combine(local.date(),datetime.time(),tz)
assert midnight.timestamp()-day_start.timestamp()==86400-change
previous_ntp=clock_property('NTP')
assert previous_ntp in ('yes','no') and target*1000000000>before
subprocess.run(['timedatectl','set-ntp','false'],check=True,timeout=30)
assert clock_property('NTP')=='no'
subprocess.run(['timedatectl','set-time','@'+str(target)],check=True,timeout=30)
assert clock_property('Timezone')==zone and clock_property('NTP')=='no'
after=time.time_ns()
assert 0<=after-target*1000000000<30000000000
print(json.dumps({'timezone':zone,'before_epoch_ns':before,'target_epoch_ns':target*1000000000,
    'readback_epoch_ns':after,'target_local_time':local.isoformat(),
    'transition_epoch_ns':boundary*1000000000,'midnight_epoch_ns':int(midnight.timestamp())*1000000000,
    'offset_before_seconds':offset(boundary-1),'offset_after_seconds':offset(boundary),
    'previous_ntp':previous_ntp,'ntp_enabled':False},sort_keys=True))
'''


def preset_spring_forward(journey, guard):
    """Prepare the next actual one-hour spring jump in the unchanged guest zone."""
    return _preset_seasonal(journey, guard, 'spring-forward', 3600)


def preset_fall_back(journey, guard):
    """Prepare the next actual one-hour fall jump in the unchanged guest zone."""
    return _preset_seasonal(journey, guard, 'fall-back', -3600)


def _preset_seasonal(journey, guard, direction, change):
    import json
    from private_artifacts import require
    import watch_activity

    require((direction, change) in (('spring-forward', 3600), ('fall-back', -3600))
            and journey.plan.prefix == direction + '-paired-grants'
            and [step['stage'] for step in journey.steps] == ['ready']
            and journey.transport is not None
            and journey.transport.lease is journey.context.lease,
            'calendar-fixture:entry')
    guard()
    with watch_activity.operation('Preparing the seasonal clock change before parent or child actions'):
        raw = journey.transport.call(['/usr/bin/python3', '-I', '-c', SEASONAL_TRANSITION, str(change)],
                                     timeout=120)
    guard()
    value = json.loads(raw)
    require(value['ntp_enabled'] is False
            and value['before_epoch_ns'] < value['target_epoch_ns']
            <= value['readback_epoch_ns'] < value['target_epoch_ns'] + 30_000_000_000
            and value['offset_after_seconds'] - value['offset_before_seconds'] == change
            and value['transition_epoch_ns'] - value['target_epoch_ns'] == 1800_000_000_000,
            'calendar-fixture:readback')
    return value


if __name__ == '__main__':
    # The maintained maintenance exec route can exercise the identical guest
    # preparation from this file, without importing controller dependencies.
    exec(ORDINARY_MIDNIGHT)
