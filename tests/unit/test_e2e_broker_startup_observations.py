"""Execute the fixed broker probe with real log files and bounded OS doubles."""

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from gi.repository import Gio, GLib
import pytest

from observation_transport import ReadOnlyObservations
from private_artifacts import EvidenceError
import startup_observations as startup


BOOT = '00000000-0000-0000-0000-000000000001\n'


def sample():
    return {'boot_sha256': hashlib.sha256(BOOT.encode()).hexdigest(),
            **{key: (index + 2) * 100000 for index, key in enumerate(startup.BROKER_TIMESTAMPS)}}


@pytest.mark.parametrize('fault,reason', [
    (None, None), ('boot', 'boot'), ('activation', 'activation'), ('inactive', 'unit'), ('restart', 'unit'),
    ('unit-field', 'unit'), ('owner', 'owner'), ('pid', 'witness'), ('stale', 'witness'),
    ('duplicate', 'witness'), ('missing', 'witness'), ('private-field', 'witness'),
    ('bool', 'witness'), ('nonroot', 'witness'), ('writable', 'witness'),
    ('symlink', 'witness'), ('old-record', 'witness'), ('object', 'object'),
    ('bus-replaced', 'continuity'), ('unit-replaced', 'continuity'),
    ('boot-replaced', 'continuity'), ('order', 'timestamps'),
    ('before-process', 'timestamps'), ('after-active', 'timestamps'),
])
def test_broker_guest_program_rejects_uncorrelated_or_unpublished_evidence(
        tmp_path, monkeypatch, capsys, fault, reason):
    data = sample()
    record = {k: data[k] for k in startup.BROKER_TIMESTAMPS}
    record.update(invocation_id='a' * 32, bus_owner=':1.9', pid=17)
    if fault == 'stale':
        record['invocation_id'] = 'b' * 32
    if fault == 'private-field':
        record['private'] = 'private-startup-canary'
    if fault == 'bool':
        record['policy_ready_ns'] = True
    if fault == 'order':
        record['policy_ready_ns'] = 900000
    log = tmp_path / '2026-09-09.log'
    content = '2026-09-09T00:00:00+00:00 INFO startup-witness ' + json.dumps(record) + '\n'
    if fault == 'duplicate':
        content *= 2
    if fault == 'old-record':
        content += 'unrelated log\n' * 50000
    log.write_text(content)
    log.chmod(0o640)
    if fault == 'symlink':
        link = tmp_path / '2026-09-08.log'
        link.symlink_to(log)
        log = link
    original_read = Path.read_text
    original_fstat = os.fstat
    reads = []
    calls = []
    units = []

    def read(path, *args, **kwargs):
        if str(path) != '/proc/sys/kernel/random/boot_id':
            return original_read(path, *args, **kwargs)
        reads.append(True)
        if fault == 'boot':
            raise OSError('private-startup-canary')
        return BOOT.replace('001', '002') if fault == 'boot-replaced' and len(reads) > 1 else BOOT

    def metadata(fd):
        meta = original_fstat(fd)
        return SimpleNamespace(st_size=meta.st_size, st_uid=1 if fault == 'nonroot' else 0,
                               st_mode=meta.st_mode | (0o020 if fault == 'writable' else 0))

    def paths(path):
        assert str(path) == '/var/log/oh-no-parent-control/broker'
        return iter([] if fault == 'missing' else [log])

    def run(args, **kwargs):
        assert args[:3] == ('systemctl', 'show', 'oh-no-parent-control-broker.service')
        assert kwargs['check'] and 0 < kwargs['timeout'] <= 5
        units.append(True)
        props = dict(ActiveState='inactive' if fault == 'inactive' else 'active',
                     SubState='running', InvocationID='a' * 32, MainPID='17',
                     NRestarts='1' if fault == 'restart' else '0',
                     ExecMainStartTimestampMonotonic='300' if fault == 'before-process' else '100',
                     ActiveEnterTimestampMonotonic='600' if fault == 'after-active' else '800')
        if fault == 'unit-field':
            del props['MainPID']
        if fault == 'unit-replaced' and len(units) > 1:
            props['InvocationID'] = 'b' * 32
        return Mock(stdout=''.join(k + '=' + v + '\n' for k, v in props.items()))

    def call(*args):
        method = args[3]
        calls.append(method)
        if args[0] == 'com.puffyslippers.OhNoParentControl1':
            assert method == 'Introspect' and args[6] == Gio.DBusCallFlags.NONE
            assert args[7] == 20000
            if fault == 'activation':
                raise RuntimeError('private-startup-canary')
            return GLib.Variant('(s)', ('<node/>',))
        assert args[6] == Gio.DBusCallFlags.NO_AUTO_START and 0 < args[7] <= 5000
        if method == 'GetNameOwner':
            if fault == 'owner':
                raise RuntimeError('private-startup-canary')
            owner = ':1.8' if fault == 'bus-replaced' and calls.count(method) > 1 else ':1.9'
            return GLib.Variant('(s)', (owner,))
        if method == 'GetConnectionUnixProcessID':
            return GLib.Variant('(u)', (18 if fault == 'pid' else 17,))
        assert method == 'Introspect' and args[0] == ':1.9'
        xml = '<node/>' if fault == 'object' else (
            '<node><interface name="com.puffyslippers.OhNoParentControl1">'
            '<method name="ListManagedUsers"/></interface></node>')
        return GLib.Variant('(s)', (xml,))

    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(Path, 'iterdir', paths)
    monkeypatch.setattr(os, 'fstat', metadata)
    monkeypatch.setattr('subprocess.run', run)
    monkeypatch.setattr(Gio, 'bus_get_sync', Mock(return_value=Mock(call_sync=call)))
    exec(compile(startup.BROKER, '<broker-startup-observation>', 'exec'), {})
    raw = capsys.readouterr().out.encode()
    assert b'private-startup-canary' not in raw and b':1.9' not in raw
    if reason:
        with pytest.raises(EvidenceError, match='startup-broker-' + reason):
            startup.parse_broker(raw)
    else:
        assert startup.parse_broker(raw) == {**data, 'reconciliation_before_publication': True}
        assert len(reads) == 2 and len(units) == 2 and calls.count('GetNameOwner') == 2


@pytest.mark.parametrize('fault', [None, 'extra', 'missing', 'bool', 'zero', 'huge', 'digest',
    'duplicate', 'format', *startup.BROKER_TIMESTAMPS[:-1], *startup.BROKER_REFUSALS])
def test_broker_capability_validates_safe_schema_and_latches_refusal(fault, capsys):
    data = sample()
    if fault == 'extra':
        data['account'] = 'private-startup-canary'
    elif fault == 'missing':
        del data['boot_sha256']
    elif fault in ('bool', 'zero', 'huge'):
        data['policy_ready_ns'] = {'bool': True, 'zero': 0, 'huge': 10**19}[fault]
    elif fault == 'digest':
        data['boot_sha256'] = 'private-startup-canary'
    elif fault in startup.BROKER_TIMESTAMPS[:-1]:
        data[fault] = 900000
    raw = (json.dumps(data, sort_keys=True) + '\n').encode()
    if fault == 'duplicate':
        raw = raw.replace(b'{', b'{"policy_ready_ns":300000,', 1)
    if fault == 'format':
        raw += b'\n'
    if fault in startup.BROKER_REFUSALS:
        raw = ('startup-broker-rejected:' + fault + '\n').encode()
    transport = Mock(config={}, call=Mock(return_value=raw))
    observer = ReadOnlyObservations(transport)
    if fault:
        with pytest.raises(EvidenceError) as error:
            observer.read('startup-broker')
        assert 'private-startup-canary' not in str(error.value) + capsys.readouterr().err
        with pytest.raises(EvidenceError, match='previous-failure'):
            observer.read('boot')
    else:
        assert observer.read('startup-broker') == {**data, 'reconciliation_before_publication': True}
    transport.call.assert_called_once_with(['/usr/bin/python3', '-c', startup.BROKER], timeout=40)
    assert transport.guard.call_count == 2
