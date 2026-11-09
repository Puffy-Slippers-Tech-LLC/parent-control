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

    require(journey.plan.prefix in ('ordinary-daily-reset', 'ordinary-rest-of-day')
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


if __name__ == '__main__':
    # The maintained maintenance exec route can exercise the identical guest
    # preparation from this file, without importing controller dependencies.
    exec(ORDINARY_MIDNIGHT)
