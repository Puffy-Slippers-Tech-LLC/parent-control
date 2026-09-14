"""No sandbox relaxation, foreign drop-in removal, or unguarded worker dispatch."""

import errno
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_probe_sandbox as sandbox


@pytest.mark.parametrize('entry', ['stage_inputs', 'native_probe_broker_sandbox', 'worker'])
def test_guest_refusal_precedes_sandbox_writes(monkeypatch, tmp_path, entry):
    monkeypatch.setattr(sandbox, 'INPUT', tmp_path / 'input')
    monkeypatch.setattr(sandbox.guest, 'PAYLOAD', tmp_path / 'original')
    monkeypatch.setattr(sandbox, 'DROPIN', tmp_path / 'dropin')
    monkeypatch.setattr(sandbox.guest, 'guard', Mock(side_effect=RuntimeError('guard-refused')))
    with pytest.raises(RuntimeError, match='guard-refused'):
        getattr(sandbox, entry)(*([Mock()] if entry == 'native_probe_broker_sandbox' else []))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('fault', ['none', 'collision', 'traversal', 'symlink'])
def test_staging_copies_only_verified_input_closure(monkeypatch, tmp_path, fault):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'package.deb').write_bytes(b'package')
    (source / 'private').mkdir()
    (source / 'private/secret').write_bytes(b'must not copy')
    relative = '../escape' if fault == 'traversal' else 'package.deb'
    (source / 'transfer-sha256.json').write_text(json.dumps({relative: 'digest'}))
    if fault == 'symlink':
        (source / 'package.deb').unlink()
        (source / 'package.deb').symlink_to(source / 'private/secret')
    target = tmp_path / 'target'
    if fault == 'collision':
        target.mkdir()
        (target / 'foreign').write_bytes(b'preserve')
    monkeypatch.setattr(sandbox.guest, 'guard', Mock())
    monkeypatch.setattr(sandbox.guest, 'PAYLOAD', source)
    monkeypatch.setattr(sandbox, 'INPUT', target)
    if fault == 'none':
        sandbox.stage_inputs()
        assert (target / 'package.deb').read_bytes() == b'package'
        assert not (target / 'private').exists()
    else:
        with pytest.raises((FileExistsError, sandbox.guest.GuestError)):
            sandbox.stage_inputs()
        if fault == 'collision':
            assert (target / 'foreign').read_bytes() == b'preserve'


@pytest.mark.parametrize('fault', ['none', 'restart', 'reload', 'interrupt', 'short-write',
                                   'replacement', 'mutation', 'directory-replacement',
                                   'worker-missing', 'worker-failed', 'restriction-change'])
def test_dropin_restoration_keeps_foreign_state_and_closes_descriptors(
        monkeypatch, tmp_path, fault):
    target = tmp_path / 'input'
    target.mkdir()
    dropin = tmp_path / 'dropin'
    config = dropin / '90-onpc-probe-qualification.conf'
    monkeypatch.setattr(sandbox, 'INPUT', target)
    monkeypatch.setattr(sandbox, 'DROPIN', dropin)
    monkeypatch.setattr(sandbox.guest, 'guard', Mock(return_value={'run': 'a' * 32}))
    monkeypatch.setattr(sandbox.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(sandbox, 'stage_inputs', Mock())
    snapshots = iter([{'protected': True}, {'protected': fault != 'restriction-change'},
                      {'protected': True}])
    monkeypatch.setattr(sandbox, 'restrictions', lambda: next(snapshots))
    opened = []
    real_open, real_write = os.open, os.write

    def opened_file(*args):
        fd = real_open(*args)
        opened.append(fd)
        return fd

    def write(fd, data):
        return real_write(fd, data[:8] if fault == 'short-write' else data)

    calls = []
    def run(args, **kwargs):
        calls.append(args[1])
        if args[1] == 'is-active':
            return 'active'
        if args[1] == 'daemon-reload' and calls.count('daemon-reload') == 1 and fault == 'reload':
            raise RuntimeError('reload-failed')
        if args[1] != 'restart' or calls.count('restart') > 1:
            return ''
        if not config.exists():  # Restoration after failure before first restart.
            return ''
        body = config.read_text()
        assert body.startswith('[Service]\nExecStartPost=/usr/bin/env ')
        assert len(body.splitlines()) == 2 and ' --worker\n' in body
        assert 'ONPC_EXPECTED_RUN=' + 'a' * 32 in body
        if fault == 'replacement':
            config.rename(dropin / 'saved')
            config.write_bytes(b'foreign')
        elif fault == 'mutation':
            config.write_bytes(b'foreign')
        elif fault == 'directory-replacement':
            dropin.rename(tmp_path / 'saved-dir')
            dropin.mkdir()
            config.write_bytes(b'foreign')
        elif fault == 'restart':
            raise RuntimeError('restart-failed')
        elif fault == 'interrupt':
            raise KeyboardInterrupt
        if fault != 'worker-missing':
            (target / 'sandbox-result.json').write_text(json.dumps({
                'onpc.probe.sandbox.passed': fault != 'worker-failed'}))
        return ''

    monkeypatch.setattr(sandbox.os, 'open', opened_file)
    monkeypatch.setattr(sandbox.os, 'write', write)
    monkeypatch.setattr(sandbox.guest, 'run', run)
    records = {}
    if fault == 'none':
        sandbox.native_probe_broker_sandbox(records.__setitem__)
    else:
        with pytest.raises((RuntimeError, KeyboardInterrupt)):
            sandbox.native_probe_broker_sandbox(records.__setitem__)
    if fault in {'replacement', 'mutation', 'directory-replacement'}:
        assert config.read_bytes() == b'foreign'
        assert calls.count('restart') == calls.count('daemon-reload') == 1
        assert 'onpc.probe.sandbox.restored' not in records
    else:
        assert not dropin.exists()
        assert records['onpc.probe.sandbox.restored']
    for fd in opened:
        with pytest.raises(OSError):
            os.fstat(fd)


@pytest.mark.parametrize('fault', ['none', 'second-stage'])
def test_worker_retains_each_stage_and_failure_evidence(monkeypatch, tmp_path, fault):
    monkeypatch.setattr(sandbox, 'INPUT', tmp_path)
    monkeypatch.setattr(sandbox.guest, 'PAYLOAD', Path('/unavailable-private-tmp'))
    monkeypatch.setattr(sandbox.guest, 'guard', Mock())
    monkeypatch.setattr(sandbox, 'observe_process', Mock())
    calls = []
    def lifecycle(record, *, refuse_admission):
        calls.append(refuse_admission)
        record('onpc.probe.cleanup-complete', True)
        if fault == 'second-stage' and refuse_admission:
            raise RuntimeError('native-failed')
    monkeypatch.setattr(sandbox, 'native_probe_lifecycle', lifecycle)
    if fault == 'none':
        sandbox.worker()
        assert calls == [False, True, False]
    else:
        with pytest.raises(RuntimeError, match='native-failed'):
            sandbox.worker()
        assert calls == [False, True]
    records = json.loads((tmp_path / 'sandbox-result.json').read_text())
    assert records['onpc.probe.cleanup-complete.success']
    assert records['onpc.probe.cleanup-complete.refusal']
    assert records.get('onpc.probe.sandbox.passed', False) == (fault == 'none')
    assert sandbox.guest.PAYLOAD == tmp_path


@pytest.mark.parametrize('fault', ['none', 'capability', 'no-new-privileges', 'seccomp',
                                   'cgroup', 'writable', 'inet', 'socket-error', 'pid'])
def test_process_observation_refuses_missing_effective_restrictions(monkeypatch, fault):
    monkeypatch.setattr(sandbox.guest, 'run', Mock(return_value='0' if fault == 'pid' else '12'))
    fields = dict(CapBnd='abc', CapEff='abc', CapAmb='c', NoNewPrivs='1', Seccomp='2')
    own = dict(fields)
    if fault == 'capability':
        own['CapEff'] = 'fff'
    elif fault == 'no-new-privileges':
        own['NoNewPrivs'] = fields['NoNewPrivs'] = '0'
    elif fault == 'seccomp':
        own['Seccomp'] = fields['Seccomp'] = '0'
    def read_text(path):
        return '\n'.join(f'{key}:\t{value}' for key, value in
                         (own if str(path) == '/proc/self/status' else fields).items())
    def read_bytes(path):
        return b'foreign' if fault == 'cgroup' and str(path) == '/proc/self/cgroup' else b'owned'
    monkeypatch.setattr(Path, 'read_text', read_text)
    monkeypatch.setattr(Path, 'read_bytes', read_bytes)
    monkeypatch.setattr(os, 'statvfs', Mock(return_value=SimpleNamespace(
        f_flag=0 if fault == 'writable' else os.ST_RDONLY)))
    connection = Mock()
    opened = Mock(return_value=connection, side_effect=None if fault == 'inet' else
                  OSError(errno.EIO if fault == 'socket-error' else errno.EAFNOSUPPORT, 'refused'))
    monkeypatch.setattr(sandbox.socket, 'socket', opened)
    if fault == 'none':
        records = {}
        sandbox.observe_process(records.__setitem__)
        assert records['onpc.probe.sandbox.inet-refused']
    else:
        with pytest.raises(sandbox.guest.GuestError):
            sandbox.observe_process(Mock())
    if fault == 'inet':
        connection.close.assert_called_once()
    elif fault not in {'none', 'socket-error'}:
        opened.assert_not_called()
