"""Real local frame transport and bounded display/reattachment contracts."""

import array
import fcntl
import mmap
import os
import socket
import time
from unittest.mock import Mock

import pytest

import e2e_watch_protocol as protocol
from e2e_watch_viewer import Feed


def test_controller_replaces_display_through_owned_descriptor(frames):
    from e2e_watch_collector import receive_progress
    server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    display, remote = socket.socketpair()
    with server, client, display, remote:
        remote.sendall(b'guarded display')
        client.sendmsg([b'display'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                     array.array('i', [display.fileno()]))])
        received = []
        attach = Mock(side_effect=lambda peer: received.append(peer.recv(32)))
        assert receive_progress(server, frames, attach)
        assert received == [b'guarded display']
        assert attach.call_args[0][0].fileno() == -1
        # Missing/excess descriptors fail closed, with no attachment.
        for descriptors in ([], [display.fileno(), display.fileno()]):
            controls = ([(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', descriptors))]
                        if descriptors else [])
            client.sendmsg([b'display'], controls)
            with pytest.raises(ValueError, match='display-descriptor'):
                receive_progress(server, frames, attach)
        assert attach.call_count == 1


@pytest.mark.parametrize('arguments', [['--vm', 'any-vm'], ['--vm=any-vm']])
def test_watcher_refuses_vm_selection_before_desktop_or_resource_access(monkeypatch, arguments):
    import watch_viewer as viewer
    launch = Mock(side_effect=AssertionError('Refused selector must not launch'))
    monkeypatch.setattr(viewer.subprocess, 'run', launch)
    monkeypatch.setattr(viewer.os, 'getuid', launch)
    with pytest.raises(SystemExit) as stopped:
        viewer.main(arguments)
    assert stopped.value.code == 2
    launch.assert_not_called()


def test_each_vm_discovers_only_its_own_display_and_progress_registrations(tmp_path, monkeypatch):
    import e2e_watch_viewer as viewer
    directory = tmp_path / str(os.getuid())
    directory.mkdir()
    monkeypatch.setattr(viewer, 'BASE', tmp_path)
    feeds = [Feed('First-VM'), Feed('Second-VM')]
    for kind in ('current', 'progress'):
        paths = [directory / (kind + '-' + feed.vm_name.encode('ascii').hex() + '.json')
                 for feed in feeds]
        for path in paths:
            path.touch()
        assert [feed.registration_path(kind) for feed in feeds] == paths
        paths[0].unlink()
        assert feeds[0].registration_path(kind) == directory / (kind + '.json')
        assert feeds[1].registration_path(kind) == paths[1]


def test_vm_feed_is_scoped_to_checkout_and_legacy_primary_only(tmp_path):
    from pathlib import Path
    import e2e_watch_viewer as viewer
    primary = Path(viewer.__file__).resolve().parents[1]
    other = tmp_path / 'other checkout'
    first, second = Feed('First-VM', root=primary), Feed('First-VM', root=other)
    assert first.matches_checkout({}) and not second.matches_checkout({})
    assert first.matches_checkout({'checkout': str(primary)})
    assert not first.matches_checkout({'checkout': str(other)})
    assert second.matches_checkout({'checkout': str(other)})
    assert not second.matches_checkout({'checkout': str(other / '..')})
    assert Feed('First-VM').matches_checkout({'checkout': str(other)})


def test_same_vm_frames_and_progress_follow_only_the_owning_checkout(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    import e2e_watch_viewer as viewer
    base = tmp_path / 'registry'
    directory = base / str(os.getuid())
    directory.mkdir(parents=True)
    base.chmod(0o755)
    directory.chmod(0o755)
    monkeypatch.setattr(viewer, 'BASE', base)
    original_lstat, original_fstat = Path.lstat, os.fstat
    def root_owned(info):
        fields = list(info)
        fields[4] = 0
        return os.stat_result(fields)
    monkeypatch.setattr(Path, 'lstat', lambda path: root_owned(original_lstat(path)))
    monkeypatch.setattr(os, 'fstat', lambda fd: root_owned(original_fstat(fd)))
    first = Feed('First-VM', root=tmp_path / 'main')
    second = Feed('First-VM', root=tmp_path / 'worktree')
    current, progress_path = (first.registration_path(kind) for kind in ('current', 'progress'))
    progress = dict(current=1, total=1, case_id='1', title='Owned test', step='Owned step', operation='')
    def publish(root):
        current.write_text(json.dumps(dict(vm=first.vm_name, run='a' * 32, checkout=str(root))))
        progress_path.write_text(json.dumps(dict(vm=first.vm_name, updated_ns=time.monotonic_ns(),
                                                checkout=str(root), progress=progress)))
        current.chmod(0o644)
        progress_path.chmod(0o644)
    peer = Mock()
    peer.__enter__ = Mock(return_value=peer)
    peer.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(viewer.socket, 'socket', Mock(return_value=peer))
    source = protocol.Frames('a' * 32)
    monkeypatch.setattr(viewer, 'receive_frames', lambda _peer: mmap.mmap(source.read_fd, protocol.SIZE,
                                                                       access=mmap.ACCESS_READ))
    try:
        source.publish(b'\0' * 16, state='live', width=2, height=2, stride=8, format=0x20020888)
        publish(first.root)
        first.connect()
        assert first.current_checkout('a' * 32)
        assert first.poll()[1]['run'] == 'a' * 32
        assert first.progress() == progress
        assert second.poll() == 'waiting' and second.progress() is None
        # Replacing the per-VM registration revokes the earlier checkout's
        # readable mapping even before its producer's heartbeat expires.
        publish(second.root)
        source.publish()
        assert first.poll() == 'waiting' and first.memory is None
        assert first.progress() is None
        second.next_connect = 0
        assert second.poll()[1]['run'] == 'a' * 32
        assert second.progress() == progress
    finally:
        first.close()
        second.close()
        source.close()


def test_snap_viewer_launch_uses_user_service_not_inherited_scope(monkeypatch):
    from watch_viewer import desktop_launch_command
    monkeypatch.setenv('WAYLAND_DISPLAY', 'wayland-test')
    monkeypatch.setenv('SNAP', '/snap/code/current')
    monkeypatch.setenv('LD_PRELOAD', '/editor/injected.so')
    command = desktop_launch_command()
    assert command[0] == '/usr/bin/systemd-run'
    assert '--user' in command and '--service-type=exec' in command
    assert '--scope' not in command
    assert '--wait' not in command and '--pipe' not in command and '--collect' in command
    assert '--setenv=WAYLAND_DISPLAY=wayland-test' in command
    assert not any('SNAP' in item or 'LD_PRELOAD' in item for item in command)
    assert command[-3] == '--'
    assert command[-2].endswith('/tools/watch')
    assert command[-1] == '--desktop-session'
    assert '--vm' not in command


def test_snap_launch_propagates_service_failure_without_opening_editor_owned_window(monkeypatch):
    import watch_viewer as viewer
    monkeypatch.setattr('sys.argv', ['watch'])
    monkeypatch.setattr(viewer.os, 'getuid', lambda: 1000)
    original_read = viewer.Path.read_text
    monkeypatch.setattr(viewer.Path, 'read_text', lambda self, *a, **kw:
        'snap.code.code (complain)\n' if str(self) == '/proc/self/attr/current' else original_read(self, *a, **kw))
    launch = Mock(return_value=Mock(returncode=7))
    window = Mock(side_effect=AssertionError('Viewer must start from the user manager'))
    monkeypatch.setattr(viewer.subprocess, 'run', launch)
    monkeypatch.setattr(viewer, 'application', window)
    assert viewer.main() == 7
    assert launch.call_count == 1
    window.assert_not_called()


def test_snap_identity_after_delegation_refuses_instead_of_launching_forever(monkeypatch):
    import watch_viewer as viewer
    monkeypatch.setattr('sys.argv', ['watch', '--desktop-session'])
    monkeypatch.setattr(viewer.os, 'getuid', lambda: 1000)
    original_read = viewer.Path.read_text
    monkeypatch.setattr(viewer.Path, 'read_text', lambda self, *a, **kw:
        'snap.code.code (complain)\n' if str(self) == '/proc/self/attr/current' else original_read(self, *a, **kw))
    launch = Mock(side_effect=AssertionError('Do not retry delegation'))
    monkeypatch.setattr(viewer.subprocess, 'run', launch)
    with pytest.raises(ValueError, match='desktop-session-still-has-snap-identity'):
        viewer.main()
    launch.assert_not_called()


@pytest.fixture
def frames():
    source = protocol.Frames('a' * 32)
    try:
        yield source
    finally:
        source.close()


def receive(source):
    server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    with server, client:
        server.sendmsg([b'ONPC-WATCH-1'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                         array.array('i', [source.read_fd]))])
        return protocol.receive_frames(client, owner=os.getuid())


@pytest.mark.parametrize('locked', [True, False])
def test_controller_lease_status_uses_read_only_frame_metadata(frames, locked):
    from e2e_watch_collector import receive_progress
    server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    with server, client:
        client.send(b'lease-locked' if locked else b'lease-unlocked')
        assert receive_progress(server, frames)
    assert protocol.read_frame(frames.memory)[1]['lease_locked'] is locked


def test_readers_cannot_modify_frames_even_by_reopening_fd(frames):
    with receive(frames) as memory:
        with pytest.raises(TypeError):
            memory[0] = 1
        with pytest.raises(PermissionError):
            mmap.mmap(frames.read_fd, protocol.SIZE, access=mmap.ACCESS_WRITE)
        # FUTURE_WRITE also blocks writes through a reopened writable handle.
        with pytest.raises(PermissionError):
            fcntl.fcntl(frames.fd, fcntl.F_ADD_SEALS, fcntl.F_SEAL_WRITE)
        with pytest.raises(PermissionError):
            os.pwrite(frames.fd, b'x', 0)
        os.fchmod(frames.fd, 0o600)
        reopened = os.open(f'/proc/self/fd/{frames.read_fd}', os.O_RDWR)
        try:
            with pytest.raises(PermissionError):
                os.pwrite(reopened, b'x', 0)
            with pytest.raises(PermissionError):
                mmap.mmap(reopened, protocol.SIZE, access=mmap.ACCESS_WRITE)
        finally:
            os.close(reopened)
        with pytest.raises(PermissionError):
            os.ftruncate(frames.fd, 1)
        frames.publish(state='waiting')
        assert protocol.read_frame(memory)[1]['state'] == 'waiting'


@pytest.mark.parametrize('values', [(2049, 1, 8196, protocol.FORMATS[0]),
                                   (2, 1, 4, protocol.FORMATS[0]), (1, 1, 4, 0)])
def test_unsupported_frames_refuse_without_allocating(values):
    with pytest.raises(ValueError):
        protocol.layout(*values)
