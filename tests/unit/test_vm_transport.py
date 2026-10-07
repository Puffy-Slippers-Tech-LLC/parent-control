"""SSH quoting, archive confinement and reboot regressions; no live VM calls."""

import io
import hashlib
from contextlib import nullcontext
import shlex
import subprocess
import sys
import tarfile
from unittest.mock import Mock, call

import pytest

import system_runner  # Load the shared guards before per-test registry mocks.
import vm_transport as transport


def config():
    return {'directory': '/tmp/onpc-system-example', 'hostname': '192.168.122.20',
            'run': 'a' * 32, 'domain_uuid': 'f95890e1-88e7-4779-8ae3-53fdcc34330a', 'domain_id': 71}


def client():
    commands = Mock()
    commands.run.return_value = b''
    commands.last_returncode = 0
    return transport.Transport(config(), commands, guard=Mock())


@pytest.mark.parametrize('status', [0, 255, 1])
def test_customer_reboot_is_one_guarded_boot_bound_command(status):
    value = client()
    value.commands.last_returncode = status
    if status == 1:
        with pytest.raises(transport.Error, match='reboot-command-failed'):
            value.request_customer_reboot('a' * 64)
    else:
        value.request_customer_reboot('a' * 64)
    value.guard.assert_called_once_with(value.config)
    assert value.commands.run.call_count == 1
    remote = value.commands.run.call_args.args[0][-1]
    assert 'systemctl' in remote and '--no-ask-password' in remote
    assert 'boot_id' in remote and 'a' * 64 in remote


def test_customer_reboot_refuses_bad_boot_and_lost_ownership_without_input():
    value = client()
    with pytest.raises(transport.Error, match='invalid-previous-boot'):
        value.request_customer_reboot('bad')
    value.guard.side_effect = transport.Error('lost-owner')
    with pytest.raises(transport.Error, match='lost-owner'):
        value.request_customer_reboot('a' * 64)
    value.commands.run.assert_not_called()


@pytest.mark.parametrize('failure', [None, 'guard', 'command'])
def test_ui_stream_parser_is_scoped_to_ssh_stdout(failure):
    value = client()
    previous, parser = Mock(), Mock()
    value.commands.progress = previous
    def guard(_):
        assert value.commands.progress is previous
        # The real guard runs qemu-img info on this shared Commands object.
        previous(b'{\n  "format": "qcow2"\n}\n')
        if failure == 'guard': raise RuntimeError('guard failed')
    def run(*_, on_output, **__):
        assert value.commands.progress is previous
        if failure == 'command': raise RuntimeError('command failed')
        on_output(b'private diagnostic', 'stderr')
        on_output(b'fixed event\n', 'stdout')
        return b'fixed event\n'
    value.guard.side_effect = guard
    value.commands.run.side_effect = run
    if failure:
        with pytest.raises(RuntimeError): value.call(['true'], on_output=parser)
    else:
        assert value.call(['true'], on_output=parser) == b'fixed event\n'
        parser.assert_called_once_with(b'fixed event\n')
    assert value.commands.progress is previous
    assert value.commands.run.call_count == (0 if failure == 'guard' else 1)


def test_nested_ui_stream_keeps_guard_output_out_of_outer_parser():
    value = client()
    previous = Mock()
    value.commands.progress = previous
    events = []
    def guard(_):
        previous(b'{\n  "format": "qcow2"\n}\n')
    def run(args, *, on_output, **_):
        if 'outer' in args[-1]:
            on_output(b'READY\n', 'stdout')
            on_output(b'DONE\n', 'stdout')
        else:
            on_output(b'INPUT\n', 'stdout')
        return b''
    def outer(data):
        events.append(('outer', data))
        if data == b'READY\n':
            value.call(['inner'], on_output=lambda chunk: events.append(('inner', chunk)))
    value.guard.side_effect = guard
    value.commands.run.side_effect = run
    value.call(['outer'], on_output=outer)
    assert events == [('outer', b'READY\n'), ('inner', b'INPUT\n'),
                      ('outer', b'DONE\n')]
    assert value.commands.progress is previous
    assert previous.call_count == 2


@pytest.mark.parametrize('fault', [None, 'name', 'instance', 'connection', 'run',
                                  'channel', 'clipboard', 'hostdev'])
@pytest.mark.parametrize('display_agent', [False, True])
def test_host_guard_uses_configured_vm_and_preserves_identity_checks(monkeypatch, fault, display_agent):
    configured = Mock(name='configuration')
    configured.name = 'custom-test-vm'
    configured.clipboard = False
    monkeypatch.setattr(transport.vm_config, 'selected', lambda **_: configured)
    domain = Mock()
    domain.ID.return_value = 72 if fault == 'instance' else 71
    domain.name.return_value = 'old-vm' if fault == 'name' else configured.name
    run = 'b' * 32 if fault == 'run' else config()['run']
    devices = '<graphics type="spice"><listen type="none"/>'
    devices += '<clipboard copypaste="no"/><filetransfer enable="no"/></graphics>'
    if display_agent:
        devices += ('<channel type="spicevmc"><target type="virtio" '
                    'name="com.redhat.spice.0" state="connected"/></channel>')
    if fault == 'channel':
        devices += '<channel type="unix"><source path="/host"/></channel>'
    elif fault == 'clipboard':
        # A channel-free legacy layout does not carry a guest agent. Add the
        # agent here to check its required transfer restrictions in both cases.
        if not display_agent:
            devices += ('<channel type="spicevmc"><target type="virtio" '
                        'name="com.redhat.spice.0"/></channel>')
        devices = devices.replace('copypaste="no"', 'copypaste="yes"')
    elif fault == 'hostdev':
        devices += '<hostdev/>'
    domain.XMLDesc.return_value = (
        f'<domain><description>onpc-system-run:{run}</description><devices>{devices}</devices></domain>')
    connection = Mock()
    connection.getURI.return_value = 'qemu:///session' if fault == 'connection' else 'qemu:///system'
    connection.lookupByUUIDString.return_value = domain
    api = Mock()
    api.open.return_value = connection
    monkeypatch.setitem(sys.modules, 'libvirt', api)
    if fault:
        with pytest.raises(transport.Error, match='domain-replaced-or-shared'):
            transport.guard_host(config())
    else:
        transport.guard_host(config())
    connection.lookupByUUIDString.assert_called_once_with(config()['domain_uuid'])
    connection.close.assert_called_once()


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


@pytest.mark.parametrize('probe', ['ready', 'boot-id', 'boot-change'])
def test_readiness_retries_timed_out_ssh_probe(probe, no_live_readiness_timer):
    value = client()
    value.commands.watch_command = None
    reports = []
    def result(args, **kwargs):
        if value.commands.run.call_count == 1:
            # A killed SSH process can leave a signal status, not SSH's 255.
            value.commands.last_returncode = -2
            raise subprocess.TimeoutExpired(args, kwargs['timeout'])
        value.commands.last_returncode = 0
        return b'b' * 64 + b'\n'
    value.commands.run.side_effect = result
    if probe == 'boot-change':
        # Host guards share Commands and can overwrite last_returncode.
        value.guard.side_effect = lambda _: setattr(value.commands, 'last_returncode', 0)
        assert value.wait_boot_change('a' * 64, on_diagnostic=reports.append) == b'b' * 64 + b'\n'
        assert reports == [{'old_boot': 0, 'ssh_unavailable': 1, 'changed_boot': 1,
                            'outcome': 'changed-boot'}]
    else:
        assert value.probe_ready(boot_id=probe == 'boot-id') == b'b' * 64 + b'\n'
    assert value.commands.run.call_count == 2
    assert value.guard.call_count == (4 if probe == 'boot-change' else 2)
    assert all(item.kwargs['timeout'] == 30 for item in value.commands.run.call_args_list)
    assert value.commands.watch_command is None
    no_live_readiness_timer.wait.assert_called_once()


@pytest.mark.parametrize('boot_change', [False, True])
def test_timed_out_readiness_probe_keeps_original_deadline(monkeypatch, boot_change):
    value = client()
    timeouts = []
    def result(args, **kwargs):
        timeouts.append(kwargs['timeout'])
        raise subprocess.TimeoutExpired(args, kwargs['timeout'])
    value.commands.run.side_effect = result
    times = iter([0, 0, 30, 30, 31, 31])
    monkeypatch.setattr(transport.time, 'monotonic', lambda: next(times))
    with pytest.raises(transport.Error, match='readiness-timeout'):
        if boot_change:
            value._probe_ready(boot_id=True, timeout=31,
                previous_boot_sha256='a' * 64, diagnostic={
                    'old_boot': 0, 'ssh_unavailable': 0, 'changed_boot': 0})
        else:
            value.probe_ready(timeout=31)
    assert timeouts == [30, 1]


@pytest.mark.parametrize('boot_change', [False, True])
def test_readiness_never_retries_host_guard_timeout(boot_change, no_live_readiness_timer):
    value = client()
    failure = subprocess.TimeoutExpired(['qemu-img', 'info'], 30)
    value.guard.side_effect = failure
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        if boot_change:
            value.wait_boot_change('a' * 64)
        else:
            value.probe_ready()
    assert caught.value is failure
    value.commands.run.assert_not_called()
    no_live_readiness_timer.wait.assert_not_called()


def test_state_changing_command_timeout_is_never_replayed():
    value = client()
    def result(args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs['timeout'])
    value.commands.run.side_effect = result
    with pytest.raises(subprocess.TimeoutExpired):
        value.call(['systemctl', 'reboot'])
    assert value.commands.run.call_count == value.guard.call_count == 1


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


def test_root_probe_streams_both_channels_through_the_existing_observed_transport():
    value = client()
    value.commands.watch_command = None
    output = Mock()
    def run(args, *, on_output, **kwargs):
        assert args[-2] == 'root@192.168.122.20'
        assert kwargs['merge_stderr'] is False
        on_output(b'guest output\n', 'stdout')
        on_output(b'guest error\n', 'stderr')
        return b'guest output\n'
    value.commands.run.side_effect = run
    value.call(['journalctl', '--no-pager'], check=False, on_stream=output)
    assert output.call_args_list == [
        call(b'guest output\n', 'stdout'), call(b'guest error\n', 'stderr')]
    value.guard.assert_called_once_with(value.config)
    assert value.commands.watch_command is None


def test_stream_callback_refuses_ambiguous_selection_before_any_guest_access():
    value = client()
    with pytest.raises(transport.Error, match='ambiguous-output'):
        value.call(['id'], on_stream=Mock(), on_output=Mock())
    value.guard.assert_not_called()
    value.commands.run.assert_not_called()


def test_replaced_domain_cannot_receive_any_command():
    value = client()
    value.guard.side_effect = transport.Error('transport:domain-replaced-or-shared')
    with pytest.raises(transport.Error):
        value.call(['true'])
    value.commands.run.assert_not_called()


def test_reboot_requires_observed_boot_id_change():
    value = client()
    value.commands.run.side_effect = [b'a' * 64 + b'\n', b'', b'b' * 64 + b'\n']
    value.reboot()
    assert value.guard.call_count == 4


def test_reboot_waits_for_old_boot_to_finish(no_live_readiness_timer):
    value = client()
    responses = iter([(0, b'a' * 64 + b'\n'), (255, b''),
                      (0, b'a' * 64 + b'\n'), (255, b''), (0, b'b' * 64 + b'\n')])
    def result(*args, **kwargs):
        value.commands.last_returncode, raw = next(responses)
        return raw
    value.commands.run.side_effect = result
    value.reboot()
    assert value.commands.run.call_count == 5
    assert no_live_readiness_timer.wait.call_count == 2


def test_reboot_never_observed_fails_at_transition_deadline(monkeypatch):
    value = client()
    value.commands.run.side_effect = [b'a' * 64 + b'\n', b'', b'a' * 64 + b'\n']
    times = iter([0, 0, 1, 330])
    monkeypatch.setattr(transport.time, 'monotonic', lambda: next(times))
    with pytest.raises(transport.Error, match='readiness-timeout'):
        value.reboot()
    assert value.commands.run.call_count == 3


def test_reboot_command_failure_does_not_start_observation():
    value = client()
    def result(*args, **kwargs):
        value.commands.last_returncode = 0 if value.commands.run.call_count == 1 else 1
        return b'a' * 64 + b'\n'
    value.commands.run.side_effect = result
    with pytest.raises(transport.Error, match='reboot-command-failed'):
        value.reboot()
    assert value.commands.run.call_count == 2


def test_customer_reboot_waits_through_old_boot_and_connection_reset(no_live_readiness_timer):
    value = client()
    responses = iter([(0, b'a'*64 + b'\n'), (255, b'private-canary'),
                      (0, b'b'*64 + b'\n')])
    def result(*args, **kwargs):
        value.commands.last_returncode, raw = next(responses)
        return raw
    value.commands.run.side_effect = result
    assert value.wait_boot_change('a'*64) == b'b'*64 + b'\n'
    assert value.guard.call_count == 6
    assert no_live_readiness_timer.wait.call_count == 2
    for call in value.commands.run.call_args_list:
        command = call.args[0][-1].split(' && exec ', 1)[1]
        assert shlex.split(command) == ['/usr/bin/python3', '-c', transport.BOOT_SHA256_PROBE]


@pytest.mark.parametrize('ssh_status', [255, 1, 127, -15])
@pytest.mark.parametrize('raw', [b'', b'b' * 64 + b'\n'])
def test_customer_reboot_guard_cannot_replace_ssh_status(ssh_status, raw, no_live_readiness_timer):
    value = client()
    responses = iter([(ssh_status, raw), (0, b'b' * 64 + b'\n')])
    def result(*args, **kwargs):
        value.commands.last_returncode, raw = next(responses)
        return raw
    value.commands.run.side_effect = result
    # The real Lease guard calls Capture.revalidate -> Commands.info using
    # this same Commands instance. Its successful qemu-img call overwrites
    # last_returncode after SSH returned. Model that actual shared state.
    value.guard.side_effect = lambda _: setattr(value.commands, 'last_returncode', 0)
    reports = []
    if ssh_status == 255:
        assert value.wait_boot_change('a' * 64, on_diagnostic=reports.append) == b'b' * 64 + b'\n'
        assert value.commands.run.call_count == 2
        no_live_readiness_timer.wait.assert_called_once()
        assert reports == [{'old_boot': 0, 'ssh_unavailable': 1, 'changed_boot': 1,
                            'outcome': 'changed-boot'}]
    else:
        with pytest.raises(transport.Error, match='guest-probe-failed'):
            value.wait_boot_change('a' * 64, on_diagnostic=reports.append)
        assert value.commands.run.call_count == 1
        no_live_readiness_timer.wait.assert_not_called()
        assert reports[0]['outcome'] == 'guest-probe-failed'


@pytest.mark.parametrize('raw', [b'', b'b'*64, b'b'*64 + b'\r\n',
                               b'B'*64 + b'\n', b'private-canary\n'])
def test_customer_reboot_malformed_output_is_terminal(raw, no_live_readiness_timer):
    value = client()
    value.commands.run.return_value = raw
    with pytest.raises(transport.Error, match='invalid-boot-output'):
        value.wait_boot_change('a'*64)
    assert value.commands.run.call_count == 1
    no_live_readiness_timer.wait.assert_not_called()


@pytest.mark.parametrize('status', [1, 127, -15])
def test_customer_reboot_guest_failure_is_not_transient(status, no_live_readiness_timer):
    value = client()
    value.commands.last_returncode = status
    with pytest.raises(transport.Error, match='guest-probe-failed'):
        value.wait_boot_change('a'*64)
    assert value.commands.run.call_count == 1
    no_live_readiness_timer.wait.assert_not_called()


@pytest.mark.parametrize('status,raw', [(0, b'a'*64 + b'\n'), (255, b'')])
def test_customer_reboot_old_boot_and_disconnect_share_deadline(monkeypatch, status, raw):
    value = client()
    value.commands.last_returncode = status
    value.commands.run.return_value = raw
    times = iter([0, 0, 1, 330])
    monkeypatch.setattr(transport.time, 'monotonic', lambda: next(times))
    with pytest.raises(transport.Error, match='readiness-timeout'):
        value.wait_boot_change('a'*64)
    assert value.commands.run.call_count == 1


@pytest.mark.parametrize('when', ['before', 'after', 'next-poll'])
def test_customer_reboot_ownership_loss_never_accepts_or_retries(when):
    value = client()
    value.commands.run.side_effect = [b'a'*64 + b'\n', b'b'*64 + b'\n']
    guards = {'before': 0, 'after': 1, 'next-poll': 2}[when]
    value.guard.side_effect = [None]*guards + [transport.Error('transport:domain-replaced')]
    with pytest.raises(transport.Error, match='domain-replaced'):
        value.wait_boot_change('a'*64)
    assert value.commands.run.call_count == (0 if when == 'before' else 1)


@pytest.mark.parametrize('when', ['command', 'wait'])
def test_customer_reboot_configuration_cannot_change_between_probes(when, no_live_readiness_timer):
    value = client()
    value.commands.run.return_value = b'a'*64 + b'\n'
    def replace(*args, **kwargs):
        value.config['hostname'] = 'replaced.invalid'
        return b'b'*64 + b'\n'
    if when == 'command':
        value.commands.run.side_effect = replace
    else:
        no_live_readiness_timer.wait.side_effect = replace
    with pytest.raises(transport.Error, match='configuration-changed'):
        value.wait_boot_change('a'*64)
    assert value.commands.run.call_count == 1


@pytest.mark.parametrize('before', [None, True, 'a'*63, 'A'*64, 'a'*64 + '\n'])
def test_customer_reboot_invalid_previous_identity_cannot_open_transport(before):
    value = client()
    with pytest.raises(transport.Error, match='invalid-previous-boot'):
        value.wait_boot_change(before)
    value.commands.run.assert_not_called()


@pytest.mark.parametrize('fault,expected', [
    ('old', 'readiness-timeout'), ('ssh', 'readiness-timeout'),
    ('malformed', 'invalid-boot-output'), ('guest', 'guest-probe-failed'),
    ('ownership', 'domain-replaced-or-shared'), ('unknown', 'unknown-error'),
    ('interrupt', 'interrupted'),
])
def test_reboot_diagnostics_retain_fixed_counts_and_terminal_cause(monkeypatch, fault, expected):
    value = client()
    reports = []
    value.commands.run.return_value = b'a'*64 + b'\n'
    if fault in ('old', 'ssh'):
        times = iter([0, 0, 1, 330])
        monkeypatch.setattr(transport.time, 'monotonic', lambda: next(times))
        value.commands.last_returncode = 255 if fault == 'ssh' else 0
    elif fault == 'malformed':
        value.commands.run.return_value = b'private-canary'
    elif fault == 'guest':
        value.commands.last_returncode = 1
    elif fault == 'ownership':
        value.guard.side_effect = transport.Error('transport:domain-replaced-or-shared')
    else:
        value.commands.run.side_effect = (KeyboardInterrupt('private-canary') if fault == 'interrupt'
                                          else RuntimeError('private-canary'))
    with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else RuntimeError):
        value.wait_boot_change('a'*64, on_diagnostic=reports.append)
    assert reports == [{'old_boot': int(fault == 'old'), 'ssh_unavailable': int(fault == 'ssh'),
                        'changed_boot': 0, 'outcome': expected}]


def test_reboot_diagnostic_checkpoint_failure_cannot_return_success():
    value = client()
    value.commands.run.return_value = b'b'*64 + b'\n'
    with pytest.raises(RuntimeError, match='checkpoint-failed'):
        value.wait_boot_change('a'*64,
            on_diagnostic=Mock(side_effect=RuntimeError('checkpoint-failed')))


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


@pytest.mark.parametrize('directory', [False, True])
def test_copyup_keeps_payload_once_and_fingerprints_command_diagnostics(tmp_path, directory):
    payload = b'private transferred bytes\x00\xff' * 1024
    raw = payload
    if directory:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            entry = tarfile.TarInfo('result.bin')
            entry.size = len(payload)
            archive.addfile(entry, io.BytesIO(payload))
        raw = stream.getvalue()
    value = client()
    value.config['directory'] = str(tmp_path)
    value.commands.run.return_value = raw
    destination = tmp_path / 'received'
    value.copy(True, '/guest/results' + ('/' if directory else ''),
               str(destination) + ('/' if directory else ''))
    assert (destination / 'result.bin' if directory else destination).read_bytes() == payload
    options = value.commands.run.call_args.kwargs
    assert options['merge_stderr'] is False
    diagnostic = options['diagnostic_stdout'](raw)
    assert diagnostic == (
        f'transfer_bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}\n'.encode())
    assert len(diagnostic) < 128 and b'private transferred bytes' not in diagnostic
    value.guard.assert_called_once_with(value.config)
