"""Execute fixed startup reads against OS fixtures; never touch the host bus."""

import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

from gi.repository import Gio, GLib
import pytest

from observation_transport import ReadOnlyObservations
from private_artifacts import EvidenceError
from vm_transport import BOOT_SHA256_PROBE
import startup_observations as startup


BOOT = '00000000-0000-0000-0000-000000000001'
HELPER = '/usr/libexec/oh-no-parent-control-execution-policy-ready'


def sample():
    return {'boot_sha256': hashlib.sha256((BOOT + '\n').encode()).hexdigest(),
            **{key: (index + 1) * 100 for index, key in enumerate(startup.TIMESTAMPS)}}


def encode(result):
    return (json.dumps(result, sort_keys=True) + '\n').encode()


@pytest.mark.parametrize('fault,reason', [
    (None, None), ('boot-read', 'boot'), ('inactive', 'units'), ('restarting', 'units'),
    ('missing-property', 'units'), ('duplicate-property', 'units'),
    ('bus', 'canary'), ('missing-helper', 'canary'), ('duplicate-helper', 'canary'),
    ('arguments', 'canary'), ('ignored-failure', 'canary'), ('failed-helper', 'canary'),
    ('killed-helper', 'canary'), ('not-run', 'canary'), ('unfinished', 'canary'),
    ('unit-replaced', 'continuity'), ('display-replaced', 'continuity'),
    ('command-replaced', 'continuity'), ('boot-replaced', 'continuity'),
    ('bad-timestamp', 'timestamps'), ('premature-gdm', 'order'),
    ('stale-canary', 'order'),
])
def test_actual_guest_program_correlates_current_boot_units_and_completed_canary(
        monkeypatch, capsys, fault, reason):
    counts = {}
    boot_reads = []

    def read(path, *args, **kwargs):
        assert path == Path('/proc/sys/kernel/random/boot_id')
        boot_reads.append(True)
        if fault == 'boot-read':
            raise OSError('private-canary')
        value = BOOT if fault != 'boot-replaced' or len(boot_reads) == 1 else BOOT[:-1] + '2'
        return value + '\n'

    def run(args, **kwargs):
        assert args[:2] == ('systemctl', 'show')
        assert kwargs['check'] and 0 < kwargs['timeout'] <= 10
        name = args[2]
        assert name in ('fapolicyd.service', 'display-manager.service')
        counts[name] = counts.get(name, 0) + 1
        policy = name == 'fapolicyd.service'
        props = {'ActiveState': 'active', 'SubState': 'running', 'InvocationID': 'a' * 32,
                 'NRestarts': '0', 'ExecMainStartTimestampMonotonic': '100' if policy else '500',
                 'ActiveEnterTimestampMonotonic': '400' if policy else '600'}
        if fault == 'inactive':
            props['ActiveState'] = 'activating'
        if fault == 'restarting':
            props['NRestarts'] = '1'
        if fault == 'missing-property':
            del props['SubState']
        if (fault == 'unit-replaced' and policy or fault == 'display-replaced' and not policy
                ) and counts[name] == 2:
            props['InvocationID'] = 'b' * 32
        if fault == 'bad-timestamp':
            props['ActiveEnterTimestampMonotonic'] = 'private-canary'
        if fault == 'premature-gdm' and not policy:
            props['ExecMainStartTimestampMonotonic'] = '250'
        raw = ''.join(key + '=' + value + '\n' for key, value in props.items())
        if fault == 'duplicate-property':
            raw += 'ActiveState=active\n'
        return Mock(stdout=raw)

    commands = [[HELPER, [HELPER], False, 10_000, 200, 10_100, 300, 17, 1, 0]]
    changes = {'arguments': (1, [HELPER, 'private-canary']), 'ignored-failure': (2, True),
               'failed-helper': (9, 1), 'killed-helper': (8, 2), 'not-run': (7, 0),
               'unfinished': (6, 0), 'stale-canary': (4, 50)}
    if fault in changes:
        key, value = changes[fault]
        commands[0][key] = value
    if fault == 'missing-helper':
        commands = []
    if fault == 'duplicate-helper':
        commands *= 2
    bus_calls = []

    def call(*args):
        bus_calls.append(args)
        assert args[:4] == ('org.freedesktop.systemd1',
            '/org/freedesktop/systemd1/unit/fapolicyd_2eservice',
            'org.freedesktop.DBus.Properties', 'Get')
        assert args[4].unpack() == ('org.freedesktop.systemd1.Service', 'ExecStartPost')
        assert 0 < args[7] <= 10000
        if fault == 'bus':
            raise RuntimeError('private-canary')
        result = copy.deepcopy(commands)
        if fault == 'command-replaced' and len(bus_calls) == 2:
            result[0][7] += 1
        return GLib.Variant('(v)', (GLib.Variant('a(sasbttttuii)', result),))

    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr('subprocess.run', run)
    monkeypatch.setattr(Gio, 'bus_get_sync', Mock(return_value=Mock(call_sync=call)))
    exec(compile(startup.ENFORCEMENT, '<startup-observation>', 'exec'), {})
    raw = capsys.readouterr().out.encode()
    assert b'private-canary' not in raw
    if reason:
        with pytest.raises(EvidenceError, match='startup-enforcement-' + reason):
            startup.parse_enforcement(raw)
    else:
        assert startup.parse_enforcement(raw) == {**sample(), 'canary_before_graphical_start': True}
        assert len(boot_reads) == 2 and len(bus_calls) == 2
        assert counts == {'fapolicyd.service': 2, 'display-manager.service': 2}
        exec(compile(BOOT_SHA256_PROBE, '<reboot-observation>', 'exec'), {})
        assert capsys.readouterr().out.strip() == startup.parse_enforcement(raw)['boot_sha256']


@pytest.mark.parametrize('fault', [None, 'extra', 'missing', 'bool', 'zero', 'huge', 'digest',
    'duplicate', 'format', *startup.TIMESTAMPS[:-1], *startup.REFUSALS])
def test_capability_boundary_validates_order_redaction_and_latches_failure(fault, capsys):
    data = sample()
    if fault == 'extra':
        data['account'] = 'private-canary'
    elif fault == 'missing':
        del data['boot_sha256']
    elif fault in ('bool', 'zero', 'huge'):
        data['canary_ready_us'] = {'bool': True, 'zero': 0, 'huge': 10**19}[fault]
    elif fault == 'digest':
        data['boot_sha256'] = 'private-canary'
    elif fault in startup.TIMESTAMPS[:-1]:
        data[fault] = 601
    raw = encode(data)
    if fault == 'duplicate':
        raw = raw.replace(b'{', b'{"canary_ready_us":300,', 1)
    elif fault == 'format':
        raw += b'\n'
    elif fault in startup.REFUSALS:
        raw = ('startup-enforcement-rejected:' + fault + '\n').encode()
    transport = Mock(config={}, call=Mock(return_value=raw))
    observer = ReadOnlyObservations(transport)
    if fault:
        with pytest.raises(EvidenceError) as error:
            observer.read('startup-enforcement')
        assert 'private-canary' not in str(error.value) + capsys.readouterr().err
        with pytest.raises(EvidenceError, match='previous-failure'):
            observer.read('boot')
    else:
        assert observer.read('startup-enforcement') == {
            **data, 'canary_before_graphical_start': True}
    transport.call.assert_called_once_with(['/usr/bin/python3', '-c', startup.ENFORCEMENT], timeout=40)
    assert transport.guard.call_count == 2
