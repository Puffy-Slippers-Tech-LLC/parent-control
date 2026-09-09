"""Fixed read-only startup evidence; guest identities stay private."""

import json
import re

from private_artifacts import require


# Read systemd's actual ExecStartPost result, including its monotonic completion
# time. Journal receipt timestamps can lag activation and cannot order this
# boundary. Bracket all reads against boot, unit and command replacement.
ENFORCEMENT = r'''import hashlib,json,pathlib,re,subprocess,time
from gi.repository import Gio, GLib
deadline = time.monotonic() + 30
def call(*args):
    remaining = deadline - time.monotonic()
    assert remaining > 0
    return subprocess.run(args, capture_output=True, text=True, check=True,
                          timeout=min(10, remaining)).stdout
def boot():
    # Match BOOT_SHA256_PROBE's complete kernel file, including its newline.
    value = pathlib.Path('/proc/sys/kernel/random/boot_id').read_text()
    assert re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\n', value)
    return value
def unit(name):
    fields = ('ActiveState', 'SubState', 'InvocationID', 'ExecMainStartTimestampMonotonic',
              'ActiveEnterTimestampMonotonic', 'NRestarts')
    raw = call('systemctl', 'show', name, '--no-pager', '--property=' + ','.join(fields))
    rows = [line.split('=', 1) for line in raw.splitlines()]
    result = dict(rows)
    assert len(rows) == len(fields) and set(result) == set(fields)
    assert result['ActiveState'] == 'active' and result['SubState'] == 'running'
    assert re.fullmatch(r'[0-9a-f]{32}', result['InvocationID'])
    assert result['NRestarts'] == '0'
    return result
def canary():
    remaining = deadline - time.monotonic()
    assert remaining > 0
    reply = bus.call_sync('org.freedesktop.systemd1',
        '/org/freedesktop/systemd1/unit/fapolicyd_2eservice',
        'org.freedesktop.DBus.Properties', 'Get',
        GLib.Variant('(ss)', ('org.freedesktop.systemd1.Service', 'ExecStartPost')),
        GLib.VariantType.new('(v)'), Gio.DBusCallFlags.NONE,
        max(1, int(min(10, remaining) * 1000)), None)
    commands = reply.unpack()[0]
    helper = '/usr/libexec/oh-no-parent-control-execution-policy-ready'
    matches = [row for row in commands if row[0] == helper]
    assert len(matches) == 1
    row = matches[0]
    assert len(row) == 10 and row[1] == [helper] and row[2] is False
    # a(sasbttttuii): path, argv, ignore-failure, start real/monotonic,
    # finish real/monotonic, PID, CLD code, exit status.
    assert row[7] > 1 and row[8] == 1 and row[9] == 0
    assert 0 < row[4] <= row[6]
    return row
stage = 'boot'
try:
    before = boot()
    stage = 'units'
    policy = unit('fapolicyd.service')
    display = unit('display-manager.service')
    stage = 'canary'
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    execution = canary()
    stage = 'continuity'
    assert canary() == execution
    assert unit('fapolicyd.service') == policy
    assert unit('display-manager.service') == display
    assert boot() == before
    stage = 'timestamps'
    values = {
        'policy_started_us': policy['ExecMainStartTimestampMonotonic'],
        'canary_started_us': str(execution[4]),
        'canary_ready_us': str(execution[6]),
        'policy_active_us': policy['ActiveEnterTimestampMonotonic'],
        'display_started_us': display['ExecMainStartTimestampMonotonic'],
        'display_active_us': display['ActiveEnterTimestampMonotonic'],
    }
    assert all(isinstance(v, str) and re.fullmatch(r'[1-9][0-9]{0,18}', v)
               for v in values.values())
    result = {key: int(value) for key, value in values.items()}
    result['boot_sha256'] = hashlib.sha256(before.encode()).hexdigest()
    print(json.dumps(result, sort_keys=True))
except Exception:
    # No exception text, journal fields, account or machine identities escape.
    print('startup-enforcement-rejected:' + stage)
'''

TIMESTAMPS = ('policy_started_us', 'canary_started_us', 'canary_ready_us', 'policy_active_us',
              'display_started_us', 'display_active_us')
REFUSALS = ('boot', 'units', 'canary', 'continuity', 'timestamps')

BROKER_TIMESTAMPS = ('started_ns', 'policy_ready_ns', 'extensions_ready_ns',
                     'caps_attempted_ns', 'register_started_ns', 'register_finished_ns')
BROKER_REFUSALS = ('boot', 'activation', 'unit', 'owner', 'witness', 'object', 'continuity', 'timestamps')

# The record is written by the broker after successful object registration.
# Neither log receipt time nor a later introspection alone proves phase order.
BROKER = r'''import hashlib,json,os,pathlib,re,stat,subprocess,time
import xml.etree.ElementTree as ET
from gi.repository import Gio, GLib
deadline = time.monotonic() + 30
name = 'com.puffyslippers.OhNoParentControl1'
keys = ('started_ns','policy_ready_ns','extensions_ready_ns','caps_attempted_ns',
        'register_started_ns','register_finished_ns')
def timeout():
    remaining = deadline - time.monotonic()
    assert remaining > 0
    return min(5, remaining)
def boot():
    value = pathlib.Path('/proc/sys/kernel/random/boot_id').read_text()
    assert re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\n', value)
    return value
def unit():
    fields = ('ActiveState','SubState','InvocationID','MainPID','NRestarts',
              'ExecMainStartTimestampMonotonic','ActiveEnterTimestampMonotonic')
    raw = subprocess.run(('systemctl','show','oh-no-parent-control-broker.service',
        '--no-pager','--property=' + ','.join(fields)), check=True,
        capture_output=True, text=True, timeout=timeout()).stdout
    rows = [line.split('=', 1) for line in raw.splitlines()]
    result = dict(rows)
    assert len(rows) == len(fields) and set(result) == set(fields)
    assert result['ActiveState'] == 'active' and result['SubState'] == 'running'
    assert result['NRestarts'] == '0'
    assert re.fullmatch(r'[0-9a-f]{32}', result['InvocationID'])
    for key in ('MainPID','ExecMainStartTimestampMonotonic','ActiveEnterTimestampMonotonic'):
        assert re.fullmatch(r'[1-9][0-9]{0,18}', result[key])
    return result
def call(destination, path, interface, method, args, signature):
    return bus.call_sync(destination, path, interface, method, args,
        GLib.VariantType.new(signature), Gio.DBusCallFlags.NO_AUTO_START,
        max(1, int(timeout()*1000)), None).unpack()[0]
def owner():
    value = call('org.freedesktop.DBus','/org/freedesktop/DBus',
        'org.freedesktop.DBus','GetNameOwner',GLib.Variant('(s)',(name,)),'(s)')
    assert re.fullmatch(r':[0-9]+\.[0-9]+', value)
    pid = call('org.freedesktop.DBus','/org/freedesktop/DBus',
        'org.freedesktop.DBus','GetConnectionUnixProcessID',GLib.Variant('(s)',(value,)),'(u)')
    assert type(pid) is int and pid > 1
    return value, pid
def witness():
    directory = pathlib.Path('/var/log/oh-no-parent-control/broker')
    paths = [p for p in directory.iterdir() if re.fullmatch(r'\d{4}-\d{2}-\d{2}\.log',p.name)]
    assert 0 < len(paths) <= 10
    matches = []
    for path in paths:
        timeout()
        # Bound reads of normal retained daily logs; never follow a replacement
        # symlink or export unrelated diagnostics. Missing/truncated proof fails.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            meta = os.fstat(stream.fileno())
            assert stat.S_ISREG(meta.st_mode) and meta.st_uid == 0
            assert not meta.st_mode & 0o022
            offset = max(0, meta.st_size - 524288)
            stream.seek(offset)
            lines = stream.read(524288).splitlines()
            if offset:
                lines = lines[1:]
        for line in lines:
            marker = b' INFO startup-witness '
            if marker not in line:
                continue
            record = json.loads(line.split(marker,1)[1])
            if record.get('invocation_id') == service['InvocationID']:
                matches.append(record)
    assert len(matches) == 1
    record = matches[0]
    assert set(record) == set(keys) | {'invocation_id','pid','bus_owner'}
    assert record['bus_owner'] == identity[0]
    assert type(record['pid']) is int and record['pid'] == identity[1] == int(service['MainPID'])
    assert all(type(record[k]) is int and 0 < record[k] < 10**19 for k in keys)
    return record
stage = 'boot'
try:
    before = boot()
    stage = 'activation'
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    # A static D-Bus service need not already run at GDM. One normal read-only
    # request activates it; subsequent evidence cannot activate a replacement.
    bus.call_sync(name,'/com/puffyslippers/OhNoParentControl1',
        'org.freedesktop.DBus.Introspectable','Introspect',None,
        GLib.VariantType.new('(s)'),Gio.DBusCallFlags.NONE,20000,None)
    stage = 'unit'
    service = unit()
    stage = 'owner'
    identity = owner()
    stage = 'witness'
    record = witness()
    stage = 'object'
    xml = call(identity[0],'/com/puffyslippers/OhNoParentControl1',
        'org.freedesktop.DBus.Introspectable','Introspect',None,'(s)')
    assert len(xml) <= 65536
    interfaces = [item for item in ET.fromstring(xml).findall('interface')
                  if item.get('name') == name]
    assert len(interfaces) == 1
    assert any(item.get('name') == 'ListManagedUsers' for item in interfaces[0].findall('method'))
    stage = 'continuity'
    assert owner() == identity and unit() == service and boot() == before
    stage = 'timestamps'
    values = [record[k] for k in keys]
    assert values == sorted(values)
    assert int(service['ExecMainStartTimestampMonotonic'])*1000 <= values[0]
    # systemd rounds to microseconds; compare at that precision.
    assert values[-1]//1000 <= int(service['ActiveEnterTimestampMonotonic'])
    print(json.dumps({**{k: record[k] for k in keys},
        'boot_sha256': hashlib.sha256(before.encode()).hexdigest()}, sort_keys=True))
except Exception:
    print('startup-broker-rejected:' + stage)
'''


def parse_broker(raw):
    """Accept only the fixed, identity-correlated broker startup witness."""
    for stage in BROKER_REFUSALS:
        require(raw != ('startup-broker-rejected:' + stage + '\n').encode(),
                'observation:startup-broker-' + stage)
    result = json.loads(raw)
    require(isinstance(result, dict) and set(result) == {*BROKER_TIMESTAMPS, 'boot_sha256'}
            and isinstance(result['boot_sha256'], str)
            and re.fullmatch(r'[0-9a-f]{64}', result['boot_sha256'])
            and all(type(result[key]) is int and 0 < result[key] < 10**19
                    for key in BROKER_TIMESTAMPS)
            and raw == (json.dumps(result, sort_keys=True) + '\n').encode(),
            'observation:invalid-output')
    times = [result[key] for key in BROKER_TIMESTAMPS]
    require(times == sorted(times), 'observation:startup-broker-order')
    return {**result, 'reconciliation_before_publication': True}


def parse_enforcement(raw):
    """Reject stale/missing canary evidence and premature GDM activation."""
    for stage in REFUSALS:
        require(raw != ('startup-enforcement-rejected:' + stage + '\n').encode(),
                'observation:startup-enforcement-' + stage)
    result = json.loads(raw)
    require(isinstance(result, dict) and set(result) == {*TIMESTAMPS, 'boot_sha256'}
            and isinstance(result['boot_sha256'], str)
            and re.fullmatch(r'[0-9a-f]{64}', result['boot_sha256'])
            and all(type(result[key]) is int and 0 < result[key] < 10**19
                    for key in TIMESTAMPS)
            and raw == (json.dumps(result, sort_keys=True) + '\n').encode(),
            'observation:invalid-output')
    times = [result[key] for key in TIMESTAMPS]
    require(times == sorted(times), 'observation:startup-enforcement-order')
    return {**result, 'canary_before_graphical_start': True}
