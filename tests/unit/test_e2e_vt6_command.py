"""Fresh shell command completion; consumed input and stale markers cannot pass."""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from observation_transport import ReadOnlyObservations
from private_artifacts import EvidenceError
from vt6_command import CommandRoundTrip, READ_MARKER, WAIT_MARKER, keyboard_command


@pytest.fixture
def boundary():
    transport = Mock(config={'run': 'a' * 32, 'domain_id': 7})
    reader = ReadOnlyObservations(transport)
    reader._boot = 'a' * 64
    reader._vt6_recipient = ('a' * 64, 'b' * 64)
    reader._vt6_shell = 'c' * 64
    reader._vt6_recipient_stage = 4
    transport.call.return_value = (json.dumps(dict(boot='a' * 64, recipient='b' * 64,
                                                 shell='c' * 64), sort_keys=True) + '\n').encode()
    return reader.vt6_command_boundary(), transport


def test_command_receipts_are_ordered_private_and_once_only(boundary):
    command, transport = boundary
    prepared = command.prepare()
    assert prepared['vt6_command_input_authorized'] is True
    assert 'vt6_shell_ready_verified' not in prepared
    assert prepared['command_challenge'] == command.challenge
    assert command.complete()['vt6_shell_ready_verified'] is True
    assert transport.guard.call_count == 4
    for call in transport.call.call_args_list:
        args = call.args[0]
        assert args[:2] == ['/usr/bin/python3', '-c']
        compile(args[2], '<fixed-vt6-probe>', 'exec')
    with pytest.raises(EvidenceError):
        command.complete()
    with pytest.raises(EvidenceError, match='previous-failure'):
        command.observer.read('boot')


def test_command_boundary_survives_launcher_import_path_restoration(boundary, monkeypatch):
    command, transport = boundary
    reader = command.observer
    reader._vt6_recipient_stage = 4
    # The standalone controller restores sys.path after loading its modules.
    # Pytest's permanent E2E path and previously imported module hid a late
    # import failure exactly when the live shell reached command preparation.
    e2e_directory = Path(__file__).resolve().parents[1] / 'e2e'
    monkeypatch.setattr(sys, 'path', [entry for entry in sys.path
                                    if Path(entry).resolve() != e2e_directory])
    monkeypatch.delitem(sys.modules, 'vt6_command')
    prepared = reader.vt6_command_boundary().prepare()
    assert prepared['vt6_command_input_authorized'] is True
    assert 'vt6_shell_ready_verified' not in prepared
    transport.call.assert_called_once()


@pytest.mark.parametrize('fault', ['boot', 'recipient', 'shell', 'private', 'extra',
    'duplicate', 'noncanonical', 'configuration', 'before-guard', 'after-guard',
    'transport', 'interrupt', 'repinned-boot'])
@pytest.mark.parametrize('complete', [False, True])
def test_command_refusal_latches_without_exporting_output(boundary, fault, complete, capsys):
    command, transport = boundary
    if complete:
        command.prepare()
    if fault in ('boot', 'recipient', 'shell', 'extra'):
        data = json.loads(transport.call.return_value)
        data[fault] = 'd' * 64
        transport.call.return_value = (json.dumps(data, sort_keys=True) + '\n').encode()
    elif fault == 'private':
        transport.call.return_value = b'private-canary'
    elif fault == 'duplicate':
        transport.call.return_value = transport.call.return_value.replace(b'{', b'{"shell":"x",')
    elif fault == 'noncanonical':
        transport.call.return_value += b'\n'
    elif fault == 'configuration':
        transport.config['domain_id'] = 8
    elif fault == 'repinned-boot':
        command.observer._boot = 'd' * 64
    elif fault in ('before-guard', 'after-guard'):
        transport.guard.side_effect = ([RuntimeError('private-canary')] if fault == 'before-guard'
                                      else [None, RuntimeError('private-canary')])
    else:
        transport.call.side_effect = (KeyboardInterrupt('private-canary') if fault == 'interrupt'
                                      else RuntimeError('private-canary'))
    with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else EvidenceError) as caught:
        command.complete() if complete else command.prepare()
    assert 'private-canary' not in str(caught.value)
    calls = list(transport.mock_calls)
    for action in (command.prepare, command.complete, command.observer.vt6_command_boundary):
        with pytest.raises(EvidenceError, match='previous-failure'):
            action()
    assert transport.mock_calls == calls
    assert 'private-canary' not in str(capsys.readouterr())


def test_completion_before_preparation_and_duplicate_boundary_refuse(boundary):
    command, transport = boundary
    with pytest.raises(EvidenceError):
        command.complete()
    transport.call.assert_not_called()
    with pytest.raises(EvidenceError):
        command.observer.vt6_command_boundary()


@pytest.mark.parametrize('value', [None, True, '', 'a' * 63, 'A' * 64, 'x; id'])
def test_command_grammar_refuses_non_nonce_values(value):
    with pytest.raises(EvidenceError):
        keyboard_command(value)


@pytest.mark.parametrize('mode', ['success', 'consumed', 'partial', 'collision'])
def test_real_bash_round_trip_requires_command_parsing(tmp_path, mode):
    nonce = 'a' * 64
    path = tmp_path / ('onpc-vt6-command-' + nonce)
    # Relocate only the fixed temporary marker for this host-side shell test.
    line = keyboard_command(nonce).replace('/tmp/', str(tmp_path) + '/')
    if mode == 'collision':
        path.write_text('sentinel')
    source = ('read -r ignored\n' if mode == 'consumed' else '') + (
        line[:-1] if mode == 'partial' else line) + '\n'
    result = subprocess.run(['/usr/bin/bash', '--noprofile', '--norc', '-s'],
        input=source + ('builtin printf "%s" "$$"\n' if mode != 'partial' else ''),
        text=True, capture_output=True, timeout=5, check=False)
    if mode == 'success':
        assert result.returncode == 0
        assert path.read_text() == nonce + '\n' + result.stdout + '\n'
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    elif mode == 'collision':
        assert path.read_text() == 'sentinel'
    else:
        assert not path.exists()


@pytest.mark.parametrize('fault', [None, 'nonce', 'pid', 'mode', 'owner', 'link',
    'symlink', 'directory', 'oversize', 'changed', 'late-lineage', 'late-boot', 'late-vt'])
def test_actual_marker_reader_checks_file_and_late_identity(tmp_path, fault):
    path = tmp_path / 'marker'
    nonce = 'a' * 64
    path.write_text(('b' * 64 if fault == 'nonce' else nonce) + '\n' +
                    ('99' if fault == 'pid' else '42') + '\n')
    path.chmod(0o644 if fault == 'mode' else 0o600)
    if fault == 'link':
        os.link(path, tmp_path / 'hardlink')
    if fault == 'symlink':
        path.rename(tmp_path / 'target')
        path.symlink_to(tmp_path / 'target')
    if fault == 'directory':
        path.unlink()
        path.mkdir()
    if fault == 'oversize':
        path.write_text('x' * 97)
    snapshot = Mock(side_effect=AssertionError if fault == 'late-lineage' else None)
    closed = Mock(wraps=os.close)
    fstat = os.fstat
    def metadata(fd):
        info = fstat(fd)
        if fault == 'changed':
            path.chmod(0o644)
        return info
    values = dict(os=os, stat=stat, marker=str(path), challenge=nonce, shell_pid=42,
        uid=os.getuid() + int(fault == 'owner'), snapshot=snapshot,
        recipient_boot='a', read_boot=lambda: 'b' if fault == 'late-boot' else 'a',
        check_active_terminal=Mock(side_effect=AssertionError if fault == 'late-vt' else None))
    with patch('os.close', closed), patch('os.fstat', metadata):
        if fault:
            with pytest.raises((AssertionError, OSError)):
                exec(READ_MARKER, values)
        else:
            exec(READ_MARKER, values)
            snapshot.assert_called_once()
    assert closed.call_count == (0 if fault == 'symlink' else 1)


def test_marker_first_read_after_provenance_delay_preserves_identity():
    # Match the live command's /tmp placement and delayed first read. Whole
    # stat_result equality hides read-driven atime changes within one second.
    with tempfile.TemporaryDirectory(prefix='onpc-vt6-marker-', dir='/tmp') as directory:
        path = Path(directory) / 'marker'
        nonce = 'a' * 64
        path.write_text(nonce + '\n42\n')
        path.chmod(0o600)
        time.sleep(1.05)
        values = dict(os=os, stat=stat, marker=str(path), challenge=nonce, shell_pid=42,
            uid=os.getuid(), snapshot=Mock(), recipient_boot='a', read_boot=lambda: 'a',
            check_active_terminal=Mock())
        exec(READ_MARKER, values)
        values['snapshot'].assert_called_once()


@pytest.mark.parametrize('view', ['descriptor', 'path'])
@pytest.mark.parametrize('field', ['st_dev', 'st_ino', 'st_mode', 'st_nlink',
    'st_uid', 'st_gid', 'st_size', 'st_mtime_ns', 'st_ctime_ns'])
def test_marker_reader_refuses_changed_stable_metadata(tmp_path, monkeypatch, view, field):
    path = tmp_path / 'marker'
    nonce = 'a' * 64
    path.write_text(nonce + '\n42\n')
    path.chmod(0o600)
    original_read, original_stat = os.read, os.fstat
    closed = Mock(wraps=os.close)
    snapshot = Mock()

    def read_then_change(fd, size):
        content = original_read(fd, size)
        info = original_stat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_uid', 'st_gid',
                  'st_size', 'st_mtime_ns', 'st_ctime_ns')
        changed = SimpleNamespace(**{name: getattr(info, name) for name in fields})
        setattr(changed, field, getattr(changed, field) + 1)
        # A one-nanosecond write/change would be invisible to tuple equality.
        scoped.setattr(os, 'fstat' if view == 'descriptor' else 'stat',
                       lambda *args, **kwargs: changed)
        return content

    values = dict(os=os, stat=stat, marker=str(path), challenge=nonce, shell_pid=42,
        uid=os.getuid(), snapshot=snapshot, recipient_boot='a', read_boot=lambda: 'a',
        check_active_terminal=Mock())
    with monkeypatch.context() as scoped:
        scoped.setattr(os, 'read', read_then_change)
        scoped.setattr(os, 'close', closed)
        with pytest.raises(AssertionError):
            exec(READ_MARKER, values)
    snapshot.assert_not_called()
    closed.assert_called_once()


@pytest.mark.parametrize('appears,child_exits', [(True, True), (False, True), (True, False)])
def test_completion_wait_is_bounded_and_requires_subshell_exit(appears, child_exits):
    clock = Mock()
    clock.monotonic.side_effect = range(100)
    child = Mock()
    child.read_text.side_effect = lambda: '' if child_exits and clock.sleep.call_count else '44'
    def path(value):
        item = Mock()
        # The guest only follows this selected unit's explicitly read lineage.
        item.__truediv__ = lambda self, part: path(value + '/' + part)
        item.read_text = (Mock(return_value='43') if value == '/proc/42/task/42/children'
                          else child.read_text)
        return item
    with patch('os.path.lexists', return_value=appears), patch('pathlib.Path', path), \
            patch('time.monotonic', clock.monotonic), patch('time.sleep', clock.sleep):
        scope = dict(marker='/tmp/fixed', subprocess=Mock(run=Mock(return_value=SimpleNamespace(stdout='42'))))
        if appears and child_exits:
            exec(WAIT_MARKER, scope)
            assert clock.sleep.call_count == 1
        else:
            with pytest.raises(AssertionError):
                exec(WAIT_MARKER, scope)
            assert clock.sleep.call_count <= 30
