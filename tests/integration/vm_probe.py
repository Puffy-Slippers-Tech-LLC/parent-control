"""Root commands in an owned maintenance guest, using its saved SSH identity.

Only the guest command is arbitrary. The host controller, domain, snapshot
credentials, transport flags, locks and observation remain fixed and guarded.
"""

import re
import os
import stat
import sys
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
from contextlib import contextmanager, nullcontext
import xml.etree.ElementTree as ET

import system_runner as system
from watch_activity import operation


CLOCK_PROBE = '''import hashlib,json,pathlib,time
print(json.dumps({'monotonic_ns':time.monotonic_ns(),
    'boot_sha256':hashlib.sha256(pathlib.Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()}))
'''

STARTUP_PROBE = '''import hashlib,json,os,pathlib,pwd,stat,subprocess,sys,time
account=pwd.getpwnam('oh-no-parent-control')
runtime=pathlib.Path('/run/user')/str(account.pw_uid)
for path,directory in ((runtime,True),(runtime/'bus',False)):
    info=path.lstat()
    assert info.st_uid==account.pw_uid
    assert stat.S_ISDIR(info.st_mode) if directory else stat.S_ISSOCK(info.st_mode)
boot=lambda:hashlib.sha256(pathlib.Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()
assert boot()==sys.argv[1]
os.initgroups(account.pw_name,account.pw_gid)
os.setgid(account.pw_gid)
os.setuid(account.pw_uid)
os.environ.clear()
os.environ.update(HOME=account.pw_dir,XDG_RUNTIME_DIR=str(runtime),
    DBUS_SESSION_BUS_ADDRESS='unix:path='+str(runtime/'bus'),LANG='C.UTF-8')
import gi
from gi.repository import Gio,GLib
connection=Gio.bus_get_sync(Gio.BusType.SESSION,None)
def call(destination,path,interface,method,parameters,signature):
    return connection.call_sync(destination,path,interface,method,parameters,
        GLib.VariantType.new(signature),Gio.DBusCallFlags.NO_AUTO_START,5000,None).unpack()
def bus(method,value,signature):
    return call('org.freedesktop.DBus','/org/freedesktop/DBus',
        'org.freedesktop.DBus',method,GLib.Variant('(s)',(value,)),signature)[0]
name='com.puffyslippers.OhNoParentControl'
owner=bus('GetNameOwner',name,'(s)')
pid=bus('GetConnectionUnixProcessID',owner,'(u)')
def identity():
    active=subprocess.check_output(['/usr/bin/systemctl','--user','show',
        'oh-no-parent-control-app.service','--property=MainPID','--value'],text=True,timeout=5).strip()
    assert active==str(pid) and pathlib.Path('/proc',str(pid)).stat().st_uid==account.pw_uid
    assert bus('GetNameOwner',name,'(s)')==owner
    assert bus('GetConnectionUnixProcessID',owner,'(u)')==pid
    assert boot()==sys.argv[1]
    return pathlib.Path('/proc',str(pid),'stat').read_text().rpartition(') ')[2].split()[19]
before=identity()
deadline=time.monotonic()+30
while True:
    assert identity()==before
    times=call(owner,'/com/puffyslippers/OhNoParentControl/Timing',
        'com.puffyslippers.OhNoParentControl.KioskTiming1','GetStartupTimings',None,'(ttt)')
    assert identity()==before
    if times[1] and (times[2] or time.monotonic_ns()-times[1]>=2_100_000_000):
        break
    assert time.monotonic()<deadline
    time.sleep(.05)
assert 0<times[0]<=times[1]<=time.monotonic_ns()
assert not times[2] or times[0]<=times[2]<=time.monotonic_ns()
print(json.dumps({'boot_sha256':sys.argv[1],'timings':times}))
'''


def clock_calibration(transport, boot):
    """Bound the guest-minus-host clock offset using the narrowest round trip."""
    import time
    bounds = []
    for _ in range(5):
        started = time.monotonic_ns()
        raw = transport.call(['/usr/bin/python3', '-I', '-c', CLOCK_PROBE])
        finished = time.monotonic_ns()
        value = json.loads(raw)
        system.require(type(value) is dict and set(value) == {'monotonic_ns', 'boot_sha256'}
            and value['boot_sha256'] == boot and type(value['monotonic_ns']) is int
            and value['monotonic_ns'] > 0, 'kiosk-latency:clock-proof')
        bounds.append((value['monotonic_ns'] - finished, value['monotonic_ns'] - started))
    return min(bounds, key=lambda pair: pair[1] - pair[0])


def startup_latency(transport, boot, started, submitted, before):
    """Correlate a pinned first-frame witness with the bounded host Enter call."""
    raw = transport.call(['/usr/bin/python3', '-I', '-c', STARTUP_PROBE, boot])
    value = json.loads(raw)
    system.require(type(value) is dict and set(value) == {'boot_sha256', 'timings'}
        and value['boot_sha256'] == boot and type(value['timings']) is list
        and len(value['timings']) == 3 and all(type(t) is int and t >= 0
            for t in value['timings']), 'kiosk-latency:startup-proof')
    python, painted, presented = value['timings']
    system.require(python > 0 and painted >= python and (not presented or presented >= python),
                   'kiosk-latency:startup-proof')
    after = clock_calibration(transport, boot)
    # Retain the union, including observed clock drift, rather than assume
    # host and guest monotonic clocks share an origin or subtract their values.
    # This assumes no unobserved clock excursion outside that envelope.
    low, high = min(before[0], after[0]), max(before[1], after[1])
    endpoint = presented or painted
    lower, upper = (endpoint - submitted - high) / 1e9, (endpoint - started - low) / 1e9
    system.require(lower <= upper < 120 and upper >= 0, 'kiosk-latency:entry-interval')
    raw_lower = lower
    lower = max(0, lower)
    return {'witness': 'presented' if presented else 'painted',
            'entry_lower_seconds': lower, 'entry_upper_seconds': upper,
            'entry_raw_lower_seconds': raw_lower,
            'bound_clipped_to_zero': raw_lower < 0,
            'entry_midpoint_seconds': (lower + upper) / 2,
            'entry_uncertainty_seconds': (upper - lower) / 2,
            'clock_before_ns': list(before), 'clock_after_ns': list(after),
            'input_interval_ns': [started, submitted], 'frame_timings_ns': value['timings'],
            'python_to_frame_seconds': (endpoint - python) / 1e9}


LOGOUT_IDENTITY_PROBE = '''import hashlib,json,os,pathlib,pwd,re,subprocess,sys
boot=lambda:hashlib.sha256(pathlib.Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()
assert boot()==sys.argv[1]
account=pwd.getpwnam('oh-no-parent-control')
os.initgroups(account.pw_name,account.pw_gid)
os.setgid(account.pw_gid)
os.setuid(account.pw_uid)
os.environ.clear()
os.environ.update(HOME=account.pw_dir,XDG_RUNTIME_DIR='/run/user/'+str(account.pw_uid),
    DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/'+str(account.pw_uid)+'/bus',LANG='C.UTF-8')
units={'app':'oh-no-parent-control-app.service','compositor':'org.gnome.Kiosk@wayland.service'}
def identity(unit):
    raw=subprocess.check_output(['systemctl','--user','show',unit,
        '--property=MainPID','--property=InvocationID'],text=True,timeout=5)
    props=dict(line.split('=',1) for line in raw.splitlines())
    assert re.fullmatch('[0-9a-f]{32}',props['InvocationID']) and props['InvocationID']!='0'*32
    pid=int(props['MainPID']); assert pid>1
    path=pathlib.Path('/proc',str(pid)); assert path.stat().st_uid==account.pw_uid
    return props['InvocationID'],pid,(path/'stat').read_text().rpartition(') ')[2].split()[19]
before={name:identity(unit) for name,unit in units.items()}
assert before=={name:identity(unit) for name,unit in units.items()} and boot()==sys.argv[1]
print(json.dumps({'boot_sha256':sys.argv[1],'invocations':{name:value[0] for name,value in before.items()}}))
'''


def logout_identity(transport, boot):
    value = json.loads(transport.call([
        '/usr/bin/python3', '-I', '-c', LOGOUT_IDENTITY_PROBE, boot]))
    system.require(type(value) is dict and set(value) == {'boot_sha256', 'invocations'}
        and value['boot_sha256'] == boot and type(value['invocations']) is dict
        and set(value['invocations']) == {'app', 'compositor'}
        and all(type(item) is str and re.fullmatch(r'[0-9a-f]{32}', item)
                and item != '0' * 32 for item in value['invocations'].values()),
        'kiosk-latency:logout-identity')
    return value['invocations']


LOGOUT_PROBE = '''import hashlib,json,pathlib,pwd,subprocess,sys
boot=lambda:hashlib.sha256(pathlib.Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()
assert boot()==sys.argv[1]
uid=str(pwd.getpwnam('oh-no-parent-control').pw_uid)
units={'oh-no-parent-control-app.service':'app','org.gnome.Kiosk@wayland.service':'compositor'}
raw=subprocess.check_output(['journalctl','--boot','--no-pager','--output=json','--lines=2000',
    'USER_UNIT=oh-no-parent-control-app.service','+','USER_UNIT=org.gnome.Kiosk@wayland.service'],timeout=15)
assert len(raw)<=4*1024*1024
started=float(sys.argv[2])
invocations=json.loads(sys.argv[3])
stops={name:[] for name in units.values()}
for line in raw.splitlines():
    record=json.loads(line)
    name=units.get(record.get('USER_UNIT'))
    if (name and record.get('_UID')==uid and record.get('_COMM')=='systemd'
            and record.get('USER_INVOCATION_ID')==invocations[name]
            and record.get('MESSAGE_ID')=='9d1aaa27d60140bd96365438aad20286'
            and record.get('JOB_TYPE')=='stop' and record.get('JOB_RESULT')=='done'):
        stamp=int(record['__MONOTONIC_TIMESTAMP'])/1000
        if stamp>=started: stops[name].append(stamp-started)
assert boot()==sys.argv[1]
print(json.dumps({name+'_stopped_ms':values[0] if len(values)==1 else None
                  for name,values in stops.items()}))
'''


def logout_latency(transport, boot, actions, invocations):
    """Keep journalled app/compositor exit separate from greeter readiness."""
    if len(actions) != 1 or len(actions[0].get('input_ms', ())) != 1:
        return {'app_stopped_ms': None, 'compositor_stopped_ms': None}
    action = actions[0]
    started = action['started_monotonic_ms'] + action['input_ms'][0]
    raw = transport.call(['/usr/bin/python3', '-I', '-c', LOGOUT_PROBE, boot,
                          str(started), json.dumps(invocations)])
    value = json.loads(raw)
    system.require(type(value) is dict and set(value) == {'app_stopped_ms', 'compositor_stopped_ms'}
        and all(item is None or type(item) in (int, float) and 0 <= item < 120000
                for item in value.values()), 'kiosk-latency:logout-proof')
    return value


def reproduce_gdm_denial(lease):
    """Run the real shared denial journey, retaining the scene after Escape.

    This fixed maintenance route supplies no acceptance result. The same owner
    must inspect with exec and finish with test-vm stop.
    """
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from fresh_child_denied import FreshChildDeniedJourney
    return reproduce_denial(lease, FreshChildDeniedJourney, None, 'denied-returned', 'gdm')


def reproduce_kiosk_entry(lease):
    """Retain real station entry for root probes, without an acceptance claim."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from installed_journey import InstalledJourney
    from kiosk_entry import PLAN
    return reproduce_denial(lease, InstalledJourney, PLAN, 'request-form', 'kiosk-entry')


def latency_events(commands, after_sequence):
    """Read only this probe's finite, already retained command timing records."""
    events = []
    last = getattr(commands, 'sequence', after_sequence)
    system.require(0 <= last - after_sequence <= 128, 'kiosk-latency:command-bound')
    for sequence in range(after_sequence + 1, last + 1):
        path = commands.directory / f'command-{sequence:04d}-stderr.txt'
        if not path.exists():
            continue
        system.require(path.stat().st_size <= 256 * 1024, 'kiosk-latency:diagnostic-bound')
        for line in path.read_text().splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if type(value) is dict and value.get('event') in (
                    'ui-operation-timing', 'mate-prompt-latency'):
                events.append(value)
    return events


def probe_kiosk_latency(lease, samples=10, cold=False):
    """Measure bounded public entry/Cancel cycles in the present owned guest.

    Timings include guarded transport and observation overhead. They are useful
    for paired comparisons, not exact display-frame latency or acceptance.
    Cold mode reboots the owned guest before every sample; warm mode preserves
    the current boot. Neither mode restores snapshots between samples.
    """
    import time
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from kiosk_entry import enter_station
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    system.require(type(samples) is int and 1 <= samples <= 10, 'kiosk-latency:samples')
    system.require(type(cold) is bool, 'kiosk-latency:cold')
    with operation('Measuring request-station entry and Cancel cycles'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-kiosk-latency-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('kiosk-latency: evidence=' + str(directory), flush=True)
        transport = connect(lease)
        ui = UiObservations(transport)
        ui.boot_guard = ''
        results = []

        def observe(name):
            lease.guard()
            return ui.observe(name)

        for index in range(samples):
            if cold:
                transport.reboot()
                ui = UiObservations(transport)
                ui.boot_guard = ''
            sequence = getattr(lease.commands, 'sequence', 0)
            started = enter_station(lease, ui, observe)
            observe('station-default-entry')
            observe('kiosk-request-form')
            entry_seconds = (time.monotonic_ns() - started) / 1e9
            started = time.monotonic_ns()
            observe('kiosk-request-cancel')
            observe('gdm-station-returned')
            result = {'sample': index + 1, 'boot_sha256': ui.boot_proof, 'cold': cold,
                      'entry_seconds': entry_seconds,
                      'cancel_seconds': (time.monotonic_ns() - started) / 1e9}
            events = latency_events(lease.commands, sequence)
            result['guest_events'] = events
            actions = [event for event in events if event.get('operation') == 'kiosk-request-cancel']
            greeters = [event for event in events if event.get('operation') == 'gdm-station-returned']
            if len(actions) == len(greeters) == 1 and len(actions[0].get('input_ms', ())) == 1:
                action, greeter = actions[0], greeters[0]
                result['cancel_dispatch_to_observed_greeter_seconds'] = (
                    greeter['started_monotonic_ms'] + greeter['elapsed_ms']
                    - action['started_monotonic_ms'] - action['input_ms'][0]) / 1000
            results.append(result)
            (directory / 'timings.json').write_text(json.dumps(results, indent=2) + '\n')
            print('kiosk-latency: ' + json.dumps({key: value for key, value in result.items()
                  if key != 'guest_events'}, sort_keys=True), flush=True)
        lease.guard()


def reproduce_kiosk_preferences(lease):
    """Diagnose one Preferences operation and retain its scene, never acceptance."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from request_composition import KioskRequestJourney
    from kiosk_preferences_confinement import PLAN
    return reproduce_denial(lease, KioskRequestJourney, PLAN,
        'preferences-confined', 'kiosk-preferences',
        boundary_operation='kiosk-preferences-confinement')


def reproduce_kiosk_approval(lease):
    """Retain the real approval prompt before qualification or secret input."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from request_flow import RequestFlowJourney
    from kiosk_approved_flow import PLAN
    return reproduce_denial(lease, RequestFlowJourney, PLAN,
                            'approval-qualified', 'kiosk-approval', native_log=True)


def probe_kiosk_prompt_latency(lease, samples=10, cold=False):
    """Measure entry, first native prompt and exit in fresh station sessions.

    The shared operation records its request-to-prompt interval in private
    stderr. The prompt interval includes observation overhead, but excludes form
    setup, transport and the independent Cancel/result checks. Measured approval prompts
    receive no password; shared preparation authenticates the fixture Parent.
    """
    import time
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from request_flow import RequestFlowJourney
    from mate_prompt import PLAN
    from kiosk_entry import enter_station
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    system.require(type(samples) is int and 1 <= samples <= 10, 'kiosk-prompt-latency:samples')
    system.require(type(cold) is bool, 'kiosk-prompt-latency:cold')
    reproduce_denial(lease, RequestFlowJourney, PLAN, 'open-mate', 'kiosk-prompt-latency')
    with operation('Measuring Request to native approval prompt'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-kiosk-prompt-latency-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('kiosk-prompt-latency: evidence=' + str(directory), flush=True)
        transport = connect(lease)
        observer = UiObservations(transport)
        observer.boot_guard = ''
        results = []

        def observe(name):
            lease.guard()
            return observer.observe(name)

        if not cold:
            # Setup has already warmed this boot. Start every measured sample
            # at the greeter, including sample one, using the same public exit.
            observe('kiosk-request-cancel')
            observe('gdm-station-returned')
        for index in range(samples):
            if cold:
                transport.reboot()
                observer = UiObservations(transport)
                observer.boot_guard = ''
            sequence = getattr(lease.commands, 'sequence', 0)
            observe('gdm-station-list')
            observer.boot_guard = observer.boot_proof
            clock_before = clock_calibration(transport, observer.boot_proof)
            entry_input = []
            entry_started = enter_station(lease, observer, observe,
                on_input=lambda first, last: entry_input.extend((first, last)))
            system.require(len(entry_input) == 2 and entry_input[0] == entry_started,
                           'kiosk-latency:input-bracket')
            observe('station-default-entry')
            observe('kiosk-valid-fraction-soft-read')
            entry_seconds = (time.monotonic_ns() - entry_started) / 1e9
            startup = startup_latency(transport, observer.boot_proof,
                                      entry_started, entry_input[1], clock_before)
            observed = observe('kiosk-mate-cancel')
            invocations = logout_identity(transport, observer.boot_proof)
            cancel_started = time.monotonic_ns()
            observe('kiosk-request-cancel')
            observe('gdm-station-returned')
            cancel_seconds = (time.monotonic_ns() - cancel_started) / 1e9
            events = latency_events(lease.commands, sequence)
            result = {'sample': index + 1, 'cold': cold, 'entry_seconds': entry_seconds,
                      'cancel_seconds': cancel_seconds,
                      'boot_sha256': observer.boot_proof, 'observed': observed,
                      'guest_events': events, 'startup': startup,
                      'logout_invocations': invocations,
                      'logout': {'app_stopped_ms': None, 'compositor_stopped_ms': None}}
            actions = [event for event in events if event.get('operation') == 'kiosk-request-cancel']
            greeters = [event for event in events if event.get('operation') == 'gdm-station-returned']
            if len(actions) == len(greeters) == 1 and len(actions[0].get('input_ms', ())) == 1:
                action, greeter = actions[0], greeters[0]
                result['cancel_dispatch_to_observed_greeter_seconds'] = (
                    greeter['started_monotonic_ms'] + greeter['elapsed_ms']
                    - action['started_monotonic_ms'] - action['input_ms'][0]) / 1000
            results.append(result)
            (directory / 'observed.json').write_text(json.dumps(results, indent=2) + '\n')
            # Optional journal diagnostics must not erase the completed public
            # entry/prompt/Cancel observations if their own guarded read fails.
            result['logout'] = logout_latency(transport, observer.boot_proof, actions, invocations)
            (directory / 'observed.json').write_text(json.dumps(results, indent=2) + '\n')
            prompt = [event['request_to_observed_prompt_ms'] for event in results[-1]['guest_events']
                      if event.get('event') == 'mate-prompt-latency']
            print('kiosk-prompt-latency: ' + json.dumps({
                'sample': index + 1, 'cold': cold, 'request_to_observed_prompt_ms': prompt,
                'entry_seconds': entry_seconds, 'cancel_seconds': result['cancel_seconds'],
                'startup': startup,
                'logout': result['logout'],
                'cancel_dispatch_to_observed_greeter_seconds': result.get(
                    'cancel_dispatch_to_observed_greeter_seconds'),
            }, sort_keys=True), flush=True)
        lease.guard()


def probe_kiosk_approval(lease):
    """Refresh the exact failed form, then open one real native prompt."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    with operation('Opening the retained kiosk approval prompt'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-kiosk-approval-probe-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('kiosk-approval-probe: evidence=' + str(directory), flush=True)
        transport = connect(lease)
        observer = UiObservations(transport)
        results = []
        with kiosk_native_evidence(lease, transport, directory):
            # The shared refresh requires Request denied and the exact child,
            # approver, 75-second duration, soft-app choice and enabled owned
            # form. Two guarded public edits preserve that choice. The open leaf
            # repeats that check, rejects an existing prompt, invokes Request
            # once, then observes the service-owned native prompt. No secret
            # provisioning, challenge qualification or password action occurs.
            try:
                for item in ('kiosk-diagnostic-retry-estimate', 'kiosk-mate-open'):
                    lease.guard()
                    try:
                        results.append(observer.observe(item))
                    except Exception as error:
                        results.append({'operation': item, 'outcome': 'refused',
                                        'error_type': type(error).__name__})
                        raise
            finally:
                (directory / 'observed.json').write_text(json.dumps(results))
        print('kiosk-approval-probe: prompt retained before password input', flush=True)


@contextmanager
def kiosk_native_evidence(lease, transport, directory):
    """Keep capture failure separate from an existing public observer failure."""
    origin = json.loads(transport.call(['python3', '-I', '-c',
        'import json,pwd,time; print(json.dumps({"uid": '
        'pwd.getpwnam("oh-no-parent-control").pw_uid, "since": int(time.time())}))'],
        timeout=15))
    system.require(type(origin) is dict and set(origin) == {'uid', 'since'}
        and type(origin['uid']) is int and origin['uid'] >= 1000
        and type(origin['since']) is int and origin['since'] > 0,
        'kiosk-native-log:origin')
    try:
        yield
    finally:
        observer_error = sys.exc_info()[1]
        try:
            lease.guard()
            capture_kiosk_native_log(transport, directory, **origin)
            lease.guard()
        except Exception as error:
            (directory / 'native-log-result.json').write_text(json.dumps({
                'outcome': 'refused', 'error_type': type(error).__name__}))
            if observer_error is None:
                raise


def capture_kiosk_native_log(transport, directory, *, uid, since):
    """Retain finite native-agent and Glycin kernel/audit evidence, no verdict."""
    system.require(type(uid) is int and uid >= 1000 and type(since) is int and since > 0,
                   'kiosk-native-log:origin')
    unit = 'oh-no-parent-control-polkit-agent.service'
    label = r'(?<![\w-])(?:onpc_kiosk_glycin(?:_bwrap)?_t|onpc-kiosk-glycin(?:-bwrap)?)(?![\w-])'
    base = ['journalctl', '--quiet', '--no-pager', '--output=json', '--lines=256',
        '--since=@' + str(since),
        '--output-fields=__REALTIME_TIMESTAMP,MESSAGE,_UID,_SYSTEMD_USER_UNIT,_TRANSPORT']
    queries = [('agent', ['_SYSTEMD_USER_UNIT=' + unit, '_UID=' + str(uid)]),
               ('kernel-audit', ['_TRANSPORT=kernel', '+', '_TRANSPORT=audit'])]
    records = []
    for source, query in queries:
        raw = transport.call(base + query, timeout=30)
        system.require(type(raw) is bytes and len(raw) <= 1024 * 1024,
                       'kiosk-native-log:output-limit')
        lines = raw.splitlines()
        system.require(len(lines) <= 256, 'kiosk-native-log:record-limit')
        for line in lines:
            value = json.loads(line)
            system.require(type(value) is dict, 'kiosk-native-log:record')
            message, stamp = value.get('MESSAGE'), value.get('__REALTIME_TIMESTAMP')
            # journalctl JSON encodes nonprintable native ANSI trace as bytes.
            if type(message) is list:
                system.require(len(message) <= 8192 and all(type(item) is int and
                    0 <= item <= 255 for item in message), 'kiosk-native-log:message-bytes')
                message = bytes(message).decode('utf-8')
            system.require(type(message) is str and len(message) <= 8192
                and type(stamp) is str and stamp.isdecimal() and int(stamp) >= since * 1000000,
                'kiosk-native-log:record')
            agent = value.get('_SYSTEMD_USER_UNIT') == unit and value.get('_UID') == str(uid)
            kernel = value.get('_TRANSPORT') in ('kernel', 'audit') and re.search(label, message) is not None
            if (agent if source == 'agent' else kernel):
                records.append({'realtime_us': stamp, 'source': source, 'message': message})
    (directory / 'native-log.json').write_text(json.dumps(records))
    (directory / 'native-log-result.json').write_text(json.dumps({
        'outcome': 'captured', 'uid': uid, 'since': since, 'records': len(records),
        'limit_records_per_source': 256, 'limit_bytes_per_source': 1024 * 1024}))


def reproduce_lock_denial(lease):
    """Retain the actual child's lock scene immediately after guarded reveal."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from desktop_session import RetainedDenialJourney, CHILD_DENIAL_PLAN
    return reproduce_denial(lease, RetainedDenialJourney, CHILD_DENIAL_PLAN, 'time-denied', 'lock')


def reproduce_retained_entry(lease):
    """Retain the two-child activity history before the restricted curtain read."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from retained_entry import RetainedEntryJourney, PLAN
    return reproduce_denial(lease, RetainedEntryJourney, PLAN,
                            'riley-restricted-curtain', 'retained-entry')


def reproduce_revoke_cancel(lease):
    """Retain the real second Cancel before its controller balance comparison."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from time_explanation import RevokeCancelJourney, REVOKE_PLAN
    return reproduce_denial(lease, RevokeCancelJourney, REVOKE_PLAN,
                            'second-balances', 'revoke-cancel',
                            boundary_operation='revoke-balances')


def reproduce_countdown_minutes(lease):
    """Retain the real daily-only child desktop before minute sampling."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from countdown_qualification import CountdownMinutesJourney, MINUTE_PLAN
    return reproduce_denial(lease, CountdownMinutesJourney, MINUTE_PLAN,
                            'minute-progression', 'countdown-minutes',
                            boundary_operation='child-countdown-present')


def reproduce_natural_expiry(lease):
    """Retain the naturally owned child lock before any harmless lock input."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from natural_expiry import NaturalExpiryJourney, PLAN
    from tools.test_storage import named_input
    assets = named_input(vm_source=True, fixture_source=True)
    if not assets.is_dir():
        print('natural-expiry-diagnosis: prepare fixture inputs with '
              'tools/run-tests artifacts prepare --for-vm --vm NAME --output ' + str(assets),
              flush=True)
    return reproduce_denial(lease, NaturalExpiryJourney, PLAN,
                            'lock-input-ready', 'natural-expiry', assets=assets)


def reproduce_countdown_resume(lease):
    """Inspect countdown use/pause/return through the qualified lock journey."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from dataclasses import replace
    from desktop_session import RetainedUnlockJourney, CHILD_UNLOCK_PLAN
    from real_interval import interval_action
    from ui_observations import UiObservations
    from tools.test_storage import named_input

    def active_interval(journey, guard):
        observed = UiObservations(journey.transport).observe('child-countdown-present')
        elapsed = interval_action(20)(journey, guard)
        return {'countdown': observed, 'elapsed_seconds': elapsed}

    plan = replace(CHILD_UNLOCK_PLAN, stage_actions={
        'lock-ready': 'active-interval', 'independent-challenge': 'inactive-interval'})
    assets = named_input(vm_source=True, fixture_source=True)
    if not assets.is_dir():
        print('countdown-resume-diagnosis: prepare fixture inputs with '
              'tools/run-tests artifacts prepare --for-vm --vm NAME --output ' + str(assets),
              flush=True)
    system.require(assets.is_dir(), 'diagnosis:fixture-inputs-required')
    return reproduce_denial(lease, RetainedUnlockJourney, plan,
        'returned-activity', 'countdown-resume',
        assets=assets,
        boundary_operation='child-countdown-present',
        actions={'active-interval': active_interval,
                 'inactive-interval': interval_action(70)})


def probe_revoke_balances(lease):
    """Exercise the maintained fresh public read on the retained Parent scene."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    with operation('Reading fresh balances in the retained Parent window'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-revoke-balance-probe-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('revoke-balance-probe: evidence=' + str(directory), flush=True)
        observed = UiObservations(connect(lease)).observe('revoke-balances')
        (directory / 'observed.json').write_text(json.dumps(observed))
        lease.guard()
        print('revoke-balance-probe: fresh public read passed', flush=True)


def reproduce_retained_app_visits(lease):
    """Retain 047a's actual Parent capture and Riley entry before command launch."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from retained_app_visits import RetainedAppVisitsJourney, PLAN
    from tools.test_storage import named_input
    return reproduce_denial(lease, RetainedAppVisitsJourney, PLAN,
                            'riley-activity-command', 'retained-app-visits',
                            assets=named_input(vm_source=True, fixture_source=True),
                            boundary_operation='overlay-native-command-launch')


def probe_retained_app_launch(lease):
    """Probe the native launch and independent usable result in retained Riley."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    with operation('Probing the retained Riley native launch'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-retained-app-launch-probe-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('retained-app-launch-probe: evidence=' + str(directory), flush=True)
        transport = connect(lease)
        observer = UiObservations(transport)
        results = []
        for item in ('command-launch', 'opened', 'submit', 'submitted'):
            try:
                results.append(observer.observe('overlay-native-' + item))
            except Exception as error:
                results.append({'operation': item, 'outcome': 'refused', 'error_type': type(error).__name__})
                break
        (directory / 'observed.json').write_text(json.dumps(results))
        lease.guard()
        print('retained-app-launch-probe: ' + results[-1]['outcome'], flush=True)


def reproduce_transfer_refusal(lease):
    """Retain the shared transfer history before the overlay's wrong-surface read."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from choices_overlay_to_kiosk import ChoicesOverlayToKioskJourney, PLAN
    return reproduce_denial(lease, ChoicesOverlayToKioskJourney, PLAN,
                            'riley-refused', 'transfer-refusal')


def reproduce_riley_native_grid(lease):
    """Retain Riley's second grid entry after the actual first launch/use/close."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from riley_native_grid import RileyNativeGridJourney, PLAN
    from tools.test_storage import named_input
    assets = named_input(vm_source=True, fixture_source=True)
    if not assets.is_dir():
        print('riley-native-grid-diagnosis: prepare fixture inputs with '
              'tools/run-tests artifacts prepare --for-vm --vm NAME --output ' + str(assets),
              flush=True)
    return reproduce_denial(lease, RileyNativeGridJourney, PLAN,
                            'repeat-refusals', 'riley-native-grid',
                            assets=assets, boundary_operation='overlay-native-grid-refusals')


def probe_riley_native_grid(lease):
    """Exercise the shared refusal observer on the retained Riley session bus."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    with operation('Probing Riley second native grid refusal'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-riley-native-grid-probe-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('riley-native-grid-probe: evidence=' + str(directory), flush=True)
        observed = UiObservations(connect(lease)).observe('overlay-native-grid-refusals')
        (directory / 'observed.json').write_text(json.dumps(observed))
        lease.guard()
        print('riley-native-grid-probe: guarded refusal passed', flush=True)


def reproduce_remembered_return(lease):
    """Retain the historical return scene, separate from current case 58."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from remembered_choices import DIAGNOSTIC_PLAN as PLAN
    from request_composition import KioskRequestJourney
    return reproduce_denial(lease, KioskRequestJourney, PLAN,
                            'jordan-return-entry-desktop', 'remembered-return',
                            boundary_operation='standard-desktop')


def probe_remembered_return(lease):
    """Read the same desktop adapter on the retained Jordan session's bus."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    with operation('Reading the retained Jordan desktop'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-remembered-return-probe-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('remembered-return-probe: evidence=' + str(directory), flush=True)
        observed = UiObservations(connect(lease)).observe('standard-desktop')
        (directory / 'observed.json').write_text(json.dumps(observed))
        lease.guard()
        print('remembered-return-probe: guarded desktop read passed', flush=True)


def repeat_remembered_return(lease):
    """Repeat only the Riley/station/Jordan return in the already reproduced scene."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from remembered_choices import DIAGNOSTIC_PLAN as PLAN
    from installed_journey import JourneyPlan
    from request_composition import KioskRequestJourney
    screens = {'repeat-desktop': 'ui:standard-desktop',
               'switch-user': 'system:standard-switch-user', 'gdm-switched': 'ui:gdm-returned'}
    screens.update({stage: tag for stage, tag in PLAN.screen_tags.items()
                    if stage.startswith('riley-return-')})
    screens.update({'riley-return-exit': 'ui:kiosk-request-cancel',
                    'riley-return-greeter': 'ui:gdm-station-returned'})
    screens.update({stage: tag for stage, tag in PLAN.screen_tags.items()
                    if stage.startswith('jordan-return-entry-')})
    plan = JourneyPlan(prefix='remembered-return', worker_mode='remembered_return_diagnosis',
        screen_tags=screens, phases={}, invocations=tuple(stage for stage in screens
                                                         if stage in PLAN.invocations),
        challenges={name: binding for name, binding in PLAN.challenges.items()
                    if name in ('riley-return-entry', 'jordan-return-entry')},
        request_transfer_checks={'riley-return-transfer-read': 'riley-return-source'})
    return reproduce_denial(lease, KioskRequestJourney, plan,
                            'jordan-return-entry-desktop', 'remembered-return',
                            boundary_operation='standard-desktop')


def enter_remembered_return(lease):
    """A new guarded Jordan challenge from the owned reproduced greeter scene."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from remembered_choices import DIAGNOSTIC_PLAN as PLAN
    from installed_journey import JourneyPlan
    from request_composition import KioskRequestJourney
    screens = {stage: tag for stage, tag in PLAN.screen_tags.items()
               if stage.startswith('jordan-return-entry-')}
    plan = JourneyPlan(prefix='remembered-return', worker_mode='remembered_return_entry_diagnosis',
        screen_tags=screens, phases={}, invocations=tuple(stage for stage in screens
                                                         if stage in PLAN.invocations),
        challenges={'jordan-return-entry': PLAN.challenges['jordan-return-entry']})
    return reproduce_denial(lease, KioskRequestJourney, plan,
                            'jordan-return-entry-desktop', 'remembered-return',
                            boundary_operation='standard-desktop')


def probe_transfer_refusal(lease):
    """Run the original read-only refusal in the retained child's actual session."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    with operation('Reading the retained overlay wrong-surface refusal'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-transfer-refusal-probe-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('transfer-refusal-probe: evidence=' + str(directory), flush=True)
        observed = UiObservations(connect(lease)).observe('transfer-overlay-riley-refused')
        (directory / 'observed.json').write_text(json.dumps(observed))
        lease.guard()
        print('transfer-refusal-probe: guarded refusal read passed', flush=True)


def probe_lock_curtain(lease):
    """Read the same guarded child curtain in a retained maintenance scene."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    with operation('Reading the locked child surface for engineering diagnosis'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-lock-probe-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('lock-probe: evidence=' + str(directory), flush=True)
        observed = UiObservations(connect(lease)).observe('child-lock-curtain')
        (directory / 'observed.json').write_text(json.dumps(observed))
        lease.guard()
        print('lock-probe: guarded curtain read passed', flush=True)


def reproduce_denial(lease, journey_type, plan, boundary, surface, *, boundary_operation=None,
                     assets=None, actions=None, native_log=False):
    """Shared maintenance envelope; fixed callers own the finite history/boundary."""
    from fixture_credentials import FixtureCredentials
    from observation_transport import ReadOnlyObservations
    import e2e_worker
    from qualification_storage import recovery_session, allocate
    system.require(type(native_log) is bool and (not native_log or (
        surface == 'kiosk-approval' and boundary == 'approval-qualified')),
        'kiosk-native-log:caller')

    with operation('Reproducing the child ' + surface + ' boundary for live diagnosis'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-' + surface + '-diagnosis-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        transport = connect(lease)
        credentials = FixtureCredentials()
        credentials.provision_online(lease, transport)
        context = SimpleNamespace(directory=directory, lease=lease)
        expected_inputs = {}
        if assets is not None:
            from provenance import VerifiedInputs, preflight_source
            staged = directory / 'input'
            system.stage_assets(system.artifact_source(assets), staged, lease.commands)
            staged.chmod(0o700)
            preflight_source(staged)
            context.verified = VerifiedInputs(lease=lease, assets=staged)
            expected_inputs = context.verified.source_files

        class Reproduction(journey_type):
            def _step(self, guard):
                stage = self.plan.stages[len(self.steps)]
                if stage != 'setup-detached':
                    return super()._step(guard)
                # The maintenance snapshot already owns the installed package
                # and transport. All actual journey observations still use the
                # current shared source bundled by UiObservations.
                request = directory / 'setup-detached.request.json'
                if not request.exists():
                    return
                system.require(not request.is_symlink() and request.stat().st_size <= 1024
                    and json.loads(request.read_bytes()) ==
                    {'stage': stage, 'screenshot': None}, 'diagnosis:setup-request')
                guard()
                self.transport = transport
                self.vm = ReadOnlyObservations(transport)
                observed = {'stage': stage, 'outcome': 'diagnostic'}
                self.steps.append(observed)
                self.progress(stage, observed)
                pending = directory / 'setup-detached.reply.tmp'
                destination = directory / 'setup-detached.reply.json'
                system.require(not destination.exists(), 'diagnosis:reply-replay')
                with pending.open('x') as stream:
                    json.dump({'setup_complete': True}, stream)
                guard()
                pending.rename(destination)

        def progress(stage, observed):
            # Fixed stage names and the shared sanitized observation only.
            with (directory / 'observations.jsonl').open('a') as stream:
                stream.write(json.dumps({'stage': stage, 'observed': observed}) + '\n')
            print(surface + '-diagnosis: ' + stage, file=sys.stderr, flush=True)

        journey = Reproduction(context, progress,
                               **({'plan': plan} if plan is not None else {}),
                               **({'actions': actions} if actions is not None else {}))

        def validate():
            validate_boundary(journey, directory, boundary)

        def observe(guard):
            if (directory / (boundary + '.request.json')).exists():
                guard()
                validate()
                if boundary_operation is not None:
                    from ui_observations import UiObservations
                    try:
                        observed = UiObservations(transport).observe(boundary_operation)
                    except Exception as error:
                        observed = {'outcome': 'refused', 'error_type': type(error).__name__}
                    (directory / 'boundary-observation.json').write_text(json.dumps(observed))
                    guard()
                return True
            journey.step(guard)
            return False

        with kiosk_native_evidence(lease, transport, directory) if native_log else nullcontext():
            result = e2e_worker.run_distribution(directory, lease, system.RunLedger(),
                expected_inputs=expected_inputs, observe=lambda: None, validate=validate,
                guarded_observe=observe, credentials=credentials, maintenance=True, timeout=900)
            system.require(result['worker_stopped'] and result['callback_closed'],
                           'diagnosis:cleanup-incomplete')
            lease.guard()
        print(surface + '-diagnosis: scene retained; evidence=' + str(directory), flush=True)


def validate_boundary(journey, directory, boundary):
    """Retain only a complete verified prefix, never a failed or advanced scene."""
    system.require(not journey.failed and [s['stage'] for s in journey.steps]
                   == list(journey.plan.stages[:journey.plan.stages.index(boundary)]),
                   'diagnosis:incomplete-history')
    request = directory / (boundary + '.request.json')
    system.require(not request.is_symlink() and request.stat().st_size <= 1024
        and json.loads(request.read_bytes()) ==
        {'stage': boundary, 'screenshot': None}, 'diagnosis:boundary-request')


def prepare_maintenance_transport(lease):
    """Reuse offline SSH bootstrap without installing a product or fixture."""
    from qualification_storage import recovery_session, allocate
    from online_snapshot import publish_maintenance
    with operation('Preparing SSH access for the owned baseline maintenance VM'), recovery_session():
        lease.guard(off=True)
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-maintenance-ssh-'))
        (directory / 'input').mkdir(mode=0o700)
        (directory / 'input/selected-inputs.json').write_bytes(system.baseline.encode({
            'schema_version': 1, 'scope': 'maintenance-ssh', 'run': lease.state['run']}))
        import guestfs
        host_key = system.bootstrap(lease.commands, lease, directory, guestfs,
                                    observation_only=True)
        publish_maintenance(lease, directory, host_key)


def connect(lease):
    """Bind a probe to the current owned online snapshot, without restoring it."""
    from online_snapshot import load, load_maintenance, connect_saved_transport, validate_saved_snapshot
    lease.guard()
    record = load_maintenance(lease)
    if record is not None:
        hostname = system.address(lease.source)
        return connect_saved_transport(lease, lease.commands.directory, record, hostname)
    snapshot = lease.source.domain.snapshotCurrent(0)
    name, xml = snapshot.getName(), snapshot.getXMLDesc(0)
    system.require(re.fullmatch(r'onpc-v[0-9]+(?:\.[0-9]+)*', name) is not None,
                   'vm-probe:online-appsnapshot-required')
    tree = ET.fromstring(xml)
    memory, domain = tree.find('memory'), tree.find('domain')
    system.require(tree.findtext('state') == 'running' and memory is not None and
                   memory.get('snapshot') == 'internal' and domain is not None,
                   'vm-probe:online-appsnapshot-required')
    record = load(lease.source, name, xml)
    system.require(record is not None, 'vm-probe:snapshot-credentials-missing')
    validate_saved_snapshot(lease, xml, record)
    hostname = system.address(lease.source)
    return connect_saved_transport(lease, lease.commands.directory, record, hostname)


def execute(lease, command, timeout, *, input_stream=False):
    """Probe the present instance; never boot, restore, rekey or correct time."""
    # The caller has resumed the shared maintenance lease. Existing detached
    # display observation stays attached throughout and outlives this command.
    with operation('Running a root command in the owned guest'):
        payload = None
        if input_stream:
            # The unprivileged launcher opened the source. Never open a host
            # pathname as root, or block reading an interactive/pipe descriptor.
            info = os.fstat(0)
            limit = 64 * 1024 * 1024
            system.require(stat.S_ISREG(info.st_mode) and info.st_size <= limit and
                           os.lseek(0, 0, os.SEEK_CUR) == 0, 'vm-probe:invalid-input')
            payload = sys.stdin.buffer.read(limit + 1)
            system.require(len(payload) == info.st_size, 'vm-probe:input-changed')
        transport = connect(lease)

        def output(data, stream):
            destination = sys.stdout.buffer if stream == 'stdout' else sys.stderr.buffer
            destination.write(data)
            destination.flush()

        transport.call(command, timeout=timeout, check=False, on_stream=output,
                       **({'input': payload} if input_stream else {}))
        # Guard probes can replace Commands.last_returncode; capture it first.
        status = transport.commands.last_returncode
        lease.guard()
        system.require(type(status) is int and 0 <= status <= 255, 'vm-probe:invalid-exit-status')
        return status
