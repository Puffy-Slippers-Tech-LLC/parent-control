"""Developer-authorized, attempt-owned clock preparation for calendar cases.

Set a future ordinary day before customer input, then let real seconds elapse.
The normal owned snapshot restoration removes the clock/synchronization changes.
"""

ORDINARY_MIDNIGHT = '''import datetime,json,os,subprocess,time
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
        target=start.replace(hour=23,minute=35)
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


def preset_ordinary_midnight(journey, guard):
    """One fixed preparation, after restore/setup and before any parent input."""
    import json
    from private_artifacts import require
    import watch_activity

    require(journey.plan.prefix in ('ordinary-daily-reset', 'ordinary-rest-of-day',
                                   'ordinary-fixed-grant')
            and [step['stage'] for step in journey.steps] == ['ready']
            and journey.transport is not None
            and journey.transport.lease is journey.context.lease,
            'calendar-fixture:entry')
    guard()
    with watch_activity.operation('Preparing the test clock before parent or child actions'):
        raw = journey.transport.call(['/usr/bin/python3', '-I', '-c', ORDINARY_MIDNIGHT],
                                     timeout=120)
    guard()
    value = json.loads(raw)
    require(value['ntp_enabled'] is False
            and value['before_epoch_ns'] < value['target_epoch_ns']
            <= value['readback_epoch_ns'] < value['target_epoch_ns'] + 30_000_000_000,
            'calendar-fixture:readback')
    return value


SPRING_FORWARD = '''import datetime,json,os,subprocess,time
from zoneinfo import ZoneInfo
assert os.geteuid()==0
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
    if offset(current)-offset(previous)==3600:
        low,high=previous,current
        while high-low>1:
            middle=(low+high)//2
            if offset(middle)==offset(previous): low=middle
            else: high=middle
        boundary=high
        break
    previous=current
else:
    raise RuntimeError('calendar-fixture:no-spring-forward-window')
target=boundary-1800
local=datetime.datetime.fromtimestamp(target,tz)
midnight=datetime.datetime.combine(local.date()+datetime.timedelta(days=1),datetime.time(),tz)
day_start=datetime.datetime.combine(local.date(),datetime.time(),tz)
assert midnight.timestamp()-day_start.timestamp()==23*3600
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
    import json
    from private_artifacts import require
    import watch_activity

    require(journey.plan.prefix == 'spring-forward-paired-grants'
            and [step['stage'] for step in journey.steps] == ['ready']
            and journey.transport is not None
            and journey.transport.lease is journey.context.lease,
            'calendar-fixture:entry')
    guard()
    with watch_activity.operation('Preparing the spring clock change before parent or child actions'):
        raw = journey.transport.call(['/usr/bin/python3', '-I', '-c', SPRING_FORWARD], timeout=120)
    guard()
    value = json.loads(raw)
    require(value['ntp_enabled'] is False
            and value['before_epoch_ns'] < value['target_epoch_ns']
            <= value['readback_epoch_ns'] < value['target_epoch_ns'] + 30_000_000_000
            and value['offset_after_seconds'] - value['offset_before_seconds'] == 3600
            and value['transition_epoch_ns'] - value['target_epoch_ns'] == 1800_000_000_000,
            'calendar-fixture:readback')
    return value


if __name__ == '__main__':
    # The maintained maintenance exec route can exercise the identical guest
    # preparation from this file, without importing controller dependencies.
    exec(ORDINARY_MIDNIGHT)
