"""Live command output, private data and authenticated spectator delivery."""

import json
import io
import os
from pathlib import Path
import socket
import struct
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from owned_commands import Commands, CommandError
import watch_activity as activity
from e2e_watch_viewer import Feed


def intent(transcript):
    return json.loads(transcript.packet('a' * 32))['operation']


def test_intent_precedes_action_and_nested_work_restores_it(transcript):
    activity.event('Waiting for an experiment')
    with activity.operation('Restoring the VM snapshot'):
        assert intent(transcript) == 'Restoring the VM snapshot'
        command = activity.command(['qemu-img'])
        assert intent(transcript) == 'Restoring the VM snapshot'
        command.finish(0)
        with pytest.raises(RuntimeError), activity.operation('Checking restored VM'):
            assert intent(transcript) == 'Checking restored VM'
            raise RuntimeError
        assert intent(transcript) == 'Restoring the VM snapshot'
    assert intent(transcript) == 'Waiting for an experiment'


def test_failed_spawn_clears_command_intent(transcript, monkeypatch):
    commands = Commands()
    def spawn(*args, **kwargs):
        assert intent(transcript) == 'Host $ missing-command'
        raise FileNotFoundError
    monkeypatch.setattr('owned_commands.subprocess.Popen', spawn)
    with pytest.raises(FileNotFoundError):
        commands.run(['missing-command'])
    assert intent(transcript) == ''


def test_transport_publishes_before_ownership_probe_and_hides_private_input(transcript):
    from vm_transport import Transport
    def guard(_):
        assert intent(transcript) == 'SSH $ python3 [private program or transfer]'
        raise RuntimeError('refused')
    with pytest.raises(RuntimeError):
        Transport({}, guard=guard).call(['python3', '-c', 'private-source'], input=b'private-input')
    assert intent(transcript) == ''
    assert 'private-source' not in transcript.packet('a' * 32).decode()


def test_multiple_publishers_keep_live_output_and_surviving_intent(tmp_path, monkeypatch):
    import e2e_watch_viewer as viewer
    directory = tmp_path / str(os.getuid())
    directory.mkdir()
    for run in ('a' * 32, 'b' * 32):
        (directory / ('activity-' + run + '.json')).touch()
    # Crashed publishers must not exhaust the live producer bound.
    for number in range(129):
        (directory / f'activity-{number:032x}.json').touch()
    monkeypatch.setattr(viewer, 'BASE', tmp_path)
    first, second = activity.Transcript(), activity.Transcript()
    first.begin('Installing in the VM')
    first.append('installation started\n')
    token = second.begin('Observing the VM desktop')
    second.append('desktop ready\n')
    values = {'a' * 32: first, 'b' * 32: second}
    feed = Feed()
    def packet(directory, path):
        run = path.stem.removeprefix('activity-')
        return json.loads(values[run].packet(run)) if run in values else None
    monkeypatch.setattr(feed, 'activity_packet', packet)
    value = feed.activity()
    assert value['operation'] == 'Observing the VM desktop'
    assert value['text'] == 'installation started\ndesktop ready\n'
    second.end(token)
    first.append('installation finished\n')
    feed.next_activity = 0
    value = feed.activity()
    assert value['operation'] == 'Installing in the VM'
    assert value['text'].count('installation started') == 1
    assert value['text'].endswith('installation finished\n')
    values.pop('b' * 32)
    feed.next_activity = 0
    assert feed.activity()['operation'] == 'Installing in the VM'
    # Reconnection to the same producer resumes after its already seen output.
    values['b' * 32] = second
    second.append('desktop observed again\n')
    feed.next_activity = 0
    assert feed.activity()['text'].count('desktop ready') == 1
    assert feed.activity()['text'].endswith('desktop observed again\n')


def test_footer_shows_non_e2e_intent_and_preserves_newer_e2e_progress():
    from e2e_watch_viewer import activity_text
    value = dict(operation='VM maintenance: reboot', operation_started_ns=10_000_000_000)
    assert activity_text(value, now_ns=12_000_000_000) == 'VM maintenance: reboot - (2s)'
    assert activity_text(value, dict(operation_started_ns=11_000_000_000)) == ''


def test_publishers_preserve_explicit_intent_over_child_commands(tmp_path, monkeypatch):
    import e2e_watch_viewer as viewer
    directory = tmp_path / str(os.getuid())
    directory.mkdir()
    parent, child = activity.Transcript(), activity.Transcript()
    values = {'a' * 32: parent, 'b' * 32: child}
    for run in values:
        (directory / ('activity-' + run + '.json')).touch()
    monkeypatch.setattr(viewer, 'BASE', tmp_path)
    feed = Feed()
    def packet(_, path):
        run = path.stem.removeprefix('activity-')
        return json.loads(values[run].packet(run)) if run in values else None
    monkeypatch.setattr(feed, 'activity_packet', packet)
    parent.begin('Restoring the VM snapshot', priority=2)
    child.begin('Host $ qemu-img')
    assert feed.activity()['operation'] == 'Restoring the VM snapshot'
    nested = child.begin('Checking restored VM', priority=2)
    feed.next_activity = 0
    assert feed.activity()['operation'] == 'Checking restored VM'
    child.end(nested)
    feed.next_activity = 0
    assert feed.activity()['operation'] == 'Restoring the VM snapshot'


def test_footer_restores_explicit_intent_and_clears_completed_events(transcript):
    from e2e_watch_viewer import activity_text
    with activity.operation('Restoring the VM snapshot'):
        parent = json.loads(transcript.packet('a' * 32))
        with activity.operation('Checking restored VM'):
            progress = dict(operation='Checking restored VM',
                operation_started_ns=json.loads(transcript.packet('a' * 32))['operation_started_ns'])
        restored = json.loads(transcript.packet('a' * 32))
        assert activity_text(restored, progress).startswith('Restoring the VM snapshot - (')
        assert restored['operation_started_ns'] == parent['operation_started_ns']
        activity.event('Snapshot restoration complete')
    assert 'Snapshot restoration complete' in transcript.text
    assert activity_text(json.loads(transcript.packet('a' * 32))) == ''


@pytest.fixture
def transcript(monkeypatch):
    value = activity.Transcript()
    monkeypatch.setattr(activity, 'current', lambda: value)
    monkeypatch.setattr(activity, '_secrets', set())
    return value


def test_running_command_streams_both_channels_before_exit(tmp_path, transcript):
    # The child cannot finish until its stderr is visible. This catches a
    # communicate-at-exit implementation and interference with progress parsing.
    release = tmp_path / 'release'
    script = tmp_path / 'command.py'
    script.write_text('''import pathlib, sys, time
print('installed test 201 passed', flush=True)
print('stderr while running', file=sys.stderr, flush=True)
deadline = time.monotonic() + 5
while not pathlib.Path(sys.argv[1]).exists():
    if time.monotonic() > deadline: raise SystemExit(9)
    time.sleep(.01)
print('finished', flush=True)
raise SystemExit(7)
''')
    append = transcript.append
    def observe(text):
        append(text)
        if 'stderr while running' in transcript.text and not release.exists():
            assert '[exit' not in transcript.text
            release.touch()
    transcript.append = observe
    commands = Commands()
    commands.watch_command = ('SSH $ installed-tests', True)
    progress = []
    commands.progress = progress.append
    commands.directory = tmp_path
    with pytest.raises(CommandError, match='command:failed'):
        commands.run([sys.executable, '-u', str(script), str(release)],
                     timeout=8, merge_stderr=False)
    assert commands.last_returncode == 7
    assert b''.join(progress) == b'installed test 201 passed\nfinished\n'
    assert 'stderr while running' in transcript.text
    assert '[exit 7]' in transcript.text
    assert (tmp_path / 'command-0001-stderr.txt').read_text() == 'stderr while running\n'


@pytest.mark.parametrize('status', [0, 100])
def test_guest_apt_reaches_spectator_before_exit(tmp_path, transcript, monkeypatch, capsys, status):
    import system_guest as guest
    release = tmp_path / 'release'
    script = tmp_path / 'apt_fixture.py'
    script.write_text('''import os, pathlib, sys, time
assert os.isatty(1) and os.isatty(2)
assert os.environ['TERM'] == 'xterm-256color'
print('Unpacking package...', flush=True)
print('APT diagnostic', file=sys.stderr, flush=True)
deadline = time.monotonic() + 5
while not pathlib.Path(sys.argv[1]).exists():
    if time.monotonic() > deadline: raise SystemExit(9)
    time.sleep(.01)
print('\\033[1;31mREBOOT REQUIRED\\033[0m', flush=True)
raise SystemExit(int(sys.argv[2]))
''')
    observer = activity.command(['ssh'], activity.remote_command(
        ['/usr/bin/python3', '/var/tmp/onpc-system-input/system_guest.py', 'install-suite'], False))
    # Model the two SSH streams. The package child cannot exit until both have
    # traversed the guest helper and the host's actual spectator line handling.
    class Stream(io.BytesIO):
        def __init__(self, channel):
            super().__init__()
            self.channel = channel

        def write(self, data):
            observer.output(data, self.channel)
            if ('Unpacking package...' in transcript.text and
                    'APT diagnostic' in transcript.text and not release.exists()):
                assert '[exit' not in transcript.text
                release.touch()
            return super().write(data)

    class PackageCommands(Commands):
        def run(self, argv, **kwargs):
            assert argv == ['apt-get', 'update']
            return super().run([sys.executable, str(script), str(release), str(status)], **kwargs)

    commands = PackageCommands()
    commands.directory = tmp_path
    monkeypatch.setattr(guest, 'commands', commands)
    monkeypatch.setattr(guest, 'sys', SimpleNamespace(
        stdout=SimpleNamespace(buffer=Stream('stdout')),
        stderr=SimpleNamespace(buffer=Stream('stderr'))))
    monkeypatch.setattr(activity, 'current', lambda: None)
    if status:
        with pytest.raises(CommandError, match='command:failed'):
            guest.run(['apt-get', 'update'], timeout=8)
    else:
        assert guest.run(['apt-get', 'update'], timeout=8) == (
            'Unpacking package...\r\nAPT diagnostic\r\n\x1b[1;31mREBOOT REQUIRED\x1b[0m')
    observer.finish(commands.last_returncode)
    assert commands.last_returncode == status
    assert '\x1b[1;31mREBOOT REQUIRED\x1b[0m' in transcript.text
    assert f'[exit {status}]' in transcript.text
    assert capsys.readouterr().out == f'$ apt-get update\n[exit {status}]\n'
    assert (tmp_path / 'command-0001.txt').read_bytes() == (
        b'Unpacking package...\r\nAPT diagnostic\r\n\x1b[1;31mREBOOT REQUIRED\x1b[0m\r\n')


def test_guest_private_probe_does_not_forward_output(monkeypatch, capsys):
    import system_guest as guest
    commands = Mock()
    commands.run.return_value = b'private probe reply\n'
    monkeypatch.setattr(guest, 'commands', commands)
    assert guest.run(['dpkg-query', '-W']) == 'private probe reply'
    commands.run.assert_called_once_with(['dpkg-query', '-W'], timeout=120, merge_stderr=False)
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('failed', [False, True])
def test_ui_qualification_without_recorder_uses_existing_command_pane(transcript, failed):
    from ui_observations import UiObservations
    result = {'operation': 'gdm-list', 'outcome': 'passed', 'interface': 'AT-SPI', 'focused': True}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
    if failed:
        transport.call.side_effect = RuntimeError('private transport exception')
    observer = UiObservations(transport)
    if failed:
        with pytest.raises(RuntimeError):
            observer.observe('gdm-list')
    else:
        assert observer.observe('gdm-list') == result
    assert 'SSH UI: Reading the greeter account list' in transcript.text
    assert 'SSH UI observation ' + ('failed' if failed else 'passed') + ': gdm-list' in transcript.text
    assert 'private transport exception' not in transcript.text


def test_validated_kiosk_diagnostic_uses_existing_transcript_only(transcript, capsys):
    from accessible_ui import KioskDiagnostic
    from ui_observations import UiObservations
    from private_artifacts import EvidenceError

    KioskDiagnostic().emit('public-tree')
    value = json.loads(capsys.readouterr().out)
    UiObservations.retain_kiosk_diagnostic(value)
    assert 'public-tree' in transcript.text
    before = transcript.text
    value['private-field'] = 'private UI label'
    with pytest.raises(EvidenceError):
        UiObservations.retain_kiosk_diagnostic(value)
    assert transcript.text == before


def test_secrets_split_across_chunks_and_private_stdin_never_reach_viewer(transcript):
    activity.secret('fixture-canary-123456')
    command = activity.command(['ssh'], ('SSH $ test', True))
    command.output(b'fixture-canary-', 'stdout')
    assert 'fixture-canary' not in transcript.text
    command.output(b'123456\npassword=unknown-value\n', 'stdout')
    command.finish(0)
    assert 'fixture-canary' not in transcript.text and 'unknown-value' not in transcript.text
    command = activity.command(['ssh'], activity.remote_command(['python3', '-c', 'private-script'], True))
    command.output(b'private-reply\x00', 'stdout')
    command.finish(0)
    assert 'private-script' not in transcript.text and 'private-reply' not in transcript.text


def test_registered_test_names_and_run_redaction(transcript):
    args = ['env', 'ONPC_EXPECTED_RUN=' + 'a' * 32, 'python3', '-m', 'pytest',
            '-c', '/tmp/pytest.ini', 'test_authorization.py::test_password_denied']
    selection = activity.remote_command(args, False)
    command = activity.command(['ssh'], selection)
    command.output(b'test_authorization.py::test_password_denied PASSED\n', 'stdout')
    command.finish(0)
    assert selection[1]
    assert 'a' * 32 not in transcript.text
    assert 'test_authorization.py::test_password_denied PASSED' in transcript.text


def test_transcript_is_bounded_and_preserves_utf8(transcript):
    transcript.begin('😀' * 500)
    transcript.append('😀' * 20000)
    packet = transcript.packet('a' * 32)
    assert len(packet) < 100000
    assert len(json.loads(packet)['text']) == 8000
    assert json.loads(packet)['offset'] == 12000
    assert len(json.loads(packet)['operation']) == 384


def test_terminal_controls_colors_and_redaction_survive_chunk_boundaries(transcript):
    activity.secret('fixture-canary')
    command = activity.command(['ssh'], ('SSH $ apt-get', True))
    command.output(b'\x1b[1;', 'stdout')
    command.output(b'31mREBOOT REQUIRED\x1b[0m\r\n', 'stdout')
    command.output(b'10%\r\x1b[2K20%\r', 'stdout')
    assert '10%\r\x1b[2K20%\r' in transcript.text
    command.output(b'\x1b]52;c;private-', 'stdout')
    command.output(b'clipboard\x07\x1bPprivate-dcs\x1b\\', 'stdout')
    command.output(b'fixt\x1b[31mure-canary\x1b[0m\npass\x1b[32mword=hidden\n', 'stdout')
    command.finish(0)
    assert '\x1b[1;31mREBOOT REQUIRED\x1b[0m\r\n' in transcript.text
    assert all(value not in transcript.text for value in
               ('private-', 'clipboard', 'canary', 'hidden', '\x1b]52', '\x1bP'))


@pytest.mark.parametrize('authorized', [True, False])
def test_real_socket_sends_only_to_authenticated_caller(authorized):
    publisher = activity.Publication.__new__(activity.Publication)
    publisher.uid = os.getuid() if authorized else os.getuid() + 1
    publisher.transcript = activity.Transcript()
    publisher.transcript.append('installed test 201 passed\n')
    publisher.registry = SimpleNamespace(run='a' * 32)
    server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    with server, client:
        publisher.serve_peer(server)
        server.close()
        value = client.recv(100000)
        if authorized:
            assert json.loads(value)['text'] == 'installed test 201 passed\n'
        else:
            assert value == b''


def test_viewer_validates_activity_packet_and_server_without_frames(tmp_path, monkeypatch):
    base = tmp_path / 'watch'
    directory = base / str(os.getuid())
    directory.mkdir(parents=True)
    (directory / 'activity.json').write_text(json.dumps({'run': 'a' * 32}))
    base.chmod(0o755)
    directory.chmod(0o755)
    (directory / 'activity.json').chmod(0o644)
    original = Path.lstat
    def root_owned(path):
        fields = list(original(path))
        fields[4] = 0
        return os.stat_result(fields)
    monkeypatch.setattr(Path, 'lstat', root_owned)
    monkeypatch.setattr('e2e_watch_viewer.BASE', base)
    peer = Mock()
    peer.__enter__ = Mock(return_value=peer)
    peer.__exit__ = Mock(return_value=False)
    peer.getsockopt.return_value = struct.pack('3i', 1, 0, 0)
    packet = dict(run='a' * 32, sequence=1, text='SSH $ pytest\n201 passed\n')
    peer.recvmsg.return_value = (json.dumps(packet).encode(), [], 0, None)
    monkeypatch.setattr('e2e_watch_viewer.socket.socket', Mock(return_value=peer))
    feed = Feed()
    assert feed.activity()['text'] == packet['text'] and feed.memory is None
    peer.send.assert_not_called()
    peer.sendall.assert_not_called()
    packet.update(offset=0, operation='Inspecting the VM', operation_started_ns=1,
                  operation_active=True, operation_priority=2)
    peer.recvmsg.return_value = (json.dumps(packet).encode(), [], 0, None)
    feed.next_activity = 0
    assert feed.activity()['operation'] == 'Inspecting the VM'
    assert feed.activity_value['operation_priority'] == 2
    assert feed.activity_value['operation_active'] is True
    for priority in (-1, 3, True, '2'):
        peer.recvmsg.return_value = (json.dumps({**packet, 'operation_priority': priority}).encode(), [], 0, None)
        feed.next_activity = 0
        assert feed.activity() is None
    peer.recvmsg.return_value = (json.dumps(packet).encode(), [], 0, None)
    feed.next_activity = 0
    peer.getsockopt.return_value = struct.pack('3i', 1, 1234, 0)
    assert feed.activity() is None
    feed.next_activity = 0
    peer.getsockopt.return_value = struct.pack('3i', 1, 0, 0)
    peer.recvmsg.return_value = (b'{}', [], socket.MSG_TRUNC, None)
    assert feed.activity() is None
