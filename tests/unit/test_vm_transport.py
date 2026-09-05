"""SSH quoting, archive confinement and reboot regressions; no live VM calls."""

import io
from contextlib import nullcontext
from pathlib import Path
import shlex
import sys
import tarfile
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests/integration'))
import vm_transport as transport
sys.path.pop(0)


def config():
    return {'directory': '/tmp/onpc-system-example', 'hostname': '192.168.122.20',
            'run': 'a' * 32, 'domain_uuid': 'f95890e1-88e7-4779-8ae3-53fdcc34330a', 'domain_id': 71}


def client():
    commands = Mock()
    commands.run.return_value = b''
    commands.last_returncode = 0
    return transport.Transport(config(), commands, guard=Mock())


@pytest.fixture(autouse=True)
def no_live_readiness_timer(monkeypatch):
    event = Mock()
    monkeypatch.setattr(transport, 'readiness_events', lambda: nullcontext(event))
    return event


def test_readiness_waits_through_ssh_handshake_reset(no_live_readiness_timer):
    value = client()
    def result(*args, **kwargs):
        value.commands.last_returncode = 255 if value.commands.run.call_count == 1 else 0
        return b'ready'
    value.commands.run.side_effect = result
    assert value.probe_ready() == b'ready'
    assert value.commands.run.call_count == value.guard.call_count == 2
    no_live_readiness_timer.wait.assert_called_once()


def test_guest_guard_failure_is_not_retried():
    value = client()
    value.commands.last_returncode = 1
    with pytest.raises(transport.Error, match='guest-probe-failed'):
        value.probe_ready()
    assert value.commands.run.call_count == 1


def test_readiness_transport_failure_has_one_bounded_deadline(monkeypatch):
    value = client()
    value.commands.last_returncode = 255
    times = iter([0, 0, 1, 2])
    monkeypatch.setattr(transport.time, 'monotonic', lambda: next(times))
    with pytest.raises(transport.Error, match='readiness-timeout'):
        value.probe_ready(timeout=1)
    assert value.commands.run.call_count == 1


def test_replaced_domain_during_readiness_is_not_retried():
    value = client()
    value.guard.side_effect = transport.Error('transport:domain-replaced-or-shared')
    with pytest.raises(transport.Error, match='domain-replaced'):
        value.probe_ready()
    value.commands.run.assert_not_called()


def test_shell_metacharacters_remain_literal_arguments():
    args = ['printf', '%s', "x; touch /danger $(echo no) 'value'\n"]
    command = transport.remote(config(), args).split(' && exec ', 1)[1]
    assert shlex.split(command) == args


def test_ssh_uses_only_run_key_and_pinned_host_key():
    args = transport.ssh(config())
    for option in ('StrictHostKeyChecking=yes', 'BatchMode=yes', 'IdentitiesOnly=yes',
                   'GlobalKnownHostsFile=/dev/null'):
        assert option in args
    assert args[-1] == 'root@192.168.122.20'


def test_replaced_domain_cannot_receive_any_command():
    value = client()
    value.guard.side_effect = transport.Error('transport:domain-replaced-or-shared')
    with pytest.raises(transport.Error):
        value.call(['true'])
    value.commands.run.assert_not_called()


def test_reboot_requires_observed_boot_id_change():
    value = client()
    value.commands.run.side_effect = [b'00000000-0000-0000-0000-000000000001', b'',
                                      b'00000000-0000-0000-0000-000000000002']
    value.reboot()
    assert value.guard.call_count == 3


def test_unchanged_boot_id_fails_without_assertion_retry():
    value = client()
    value.commands.run.side_effect = [b'00000000-0000-0000-0000-000000000001', b'',
                                      b'00000000-0000-0000-0000-000000000001']
    with pytest.raises(transport.Error, match='reboot-not-observed'):
        value.reboot()
    assert value.commands.run.call_count == 3


@pytest.mark.parametrize('name', ['../../escape', '/etc/escape'])
def test_archive_path_escape_is_refused_before_extraction(tmp_path, name):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        archive.addfile(tarfile.TarInfo(name), io.BytesIO())
    with pytest.raises(transport.Error, match='archive-path'):
        transport.extract(stream.getvalue(), tmp_path / 'output')


@pytest.mark.parametrize('kind', [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE])
def test_archive_links_devices_and_fifos_are_refused(tmp_path, kind):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        entry = tarfile.TarInfo('unexpected')
        entry.type, entry.linkname = kind, '/etc/passwd'
        archive.addfile(entry)
    with pytest.raises(transport.Error, match='archive-special-file'):
        transport.extract(stream.getvalue(), tmp_path / 'output')


def test_copyup_cannot_escape_owned_run_directory():
    value = client()
    with pytest.raises(transport.Error, match='host-path'):
        value.copy(True, '/etc/passwd', '/etc/host-overwrite')
    value.commands.run.assert_not_called()


def test_plain_files_round_trip_through_safe_archive(tmp_path):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        entry = tarfile.TarInfo('results.xml')
        entry.size = 7
        archive.addfile(entry, io.BytesIO(b'<test/>'))
    transport.extract(stream.getvalue(), tmp_path / 'output')
    assert (tmp_path / 'output/results.xml').read_bytes() == b'<test/>'
