"""Real local frame transport and bounded display/reattachment contracts."""

import array
import fcntl
import mmap
import os
import socket
import threading
import time
from unittest.mock import Mock, patch

import pytest

import e2e_watch_protocol as protocol
from e2e_watch_collector import Display
from e2e_watch_viewer import AsyncFeed, Feed


def test_lease_collector_keeps_the_same_live_mapping_without_a_guest(tmp_path):
    """Run the actual collector on private sockets; no VM or desktop is used."""
    import subprocess
    import sys
    from pathlib import Path
    worker = tmp_path / 'collector.py'
    directory = Path(__file__).resolve().parents[1] / 'integration'
    worker.write_text(f'import sys, os\nsys.path.insert(0, {str(directory)!r})\n'
                      'import e2e_watch_collector as collector\n'
                      'collector.os.geteuid = lambda: 0\ncollector.main()\n')
    qemu_worker = tmp_path / 'display.py'
    qemu_worker.write_text('''import os, socket, sys
from gi.repository import Gio, GLib
loop = GLib.MainLoop()
connections = []
XML = ''' + repr('''<node><interface name="org.freedesktop.DBus.Properties">
<method name="Get"><arg type="s" direction="in"/><arg type="s" direction="in"/>
<arg type="v" direction="out"/></method></interface>
<interface name="org.qemu.Display1.Console"><method name="RegisterListener">
<arg type="h" direction="in"/></method></interface></node>''') + '''
def listener_ready(_source, result):
    connection = Gio.DBusConnection.new_finish(result)
    connections.append(connection)
    connection.set_exit_on_close(False)
    connection.start_message_processing()
    connection.call(None, '/org/qemu/Display1/Listener', 'org.qemu.Display1.Listener',
        'Scanout', GLib.Variant('(uuuuay)', (1, 1, 4, 0x20020888, sys.argv[2].encode())),
        None, Gio.DBusCallFlags.NONE, 3000, None, None)
def method(_connection, _sender, _path, _interface, name, parameters, invocation):
    if name == 'Get':
        invocation.return_value(GLib.Variant('(v)', (GLib.Variant('au', [0]),)))
    else:
        fd = invocation.get_message().get_unix_fd_list().get(parameters.unpack()[0])
        transport = Gio.Socket.new_from_fd(fd).connection_factory_create_connection()
        Gio.DBusConnection.new(transport, Gio.dbus_generate_guid(),
            Gio.DBusConnectionFlags.AUTHENTICATION_SERVER |
            Gio.DBusConnectionFlags.AUTHENTICATION_REQUIRE_SAME_USER |
            Gio.DBusConnectionFlags.DELAY_MESSAGE_PROCESSING,
            None, None, listener_ready)
        invocation.return_value(GLib.Variant('()', ()))
def ready(_source, result):
    connection = Gio.DBusConnection.new_finish(result)
    connections.append(connection)
    connection.set_exit_on_close(False)
    connection.connect('closed', lambda *_: loop.quit())
    interfaces = Gio.DBusNodeInfo.new_for_xml(XML).interfaces
    for path, interface in zip(('/org/qemu/Display1/VM', '/org/qemu/Display1/Console_0'), interfaces):
        connection.register_object_with_closures2(path, interface, method, None, None)
    connection.start_message_processing()
transport = Gio.Socket.new_from_fd(int(sys.argv[1])).connection_factory_create_connection()
Gio.DBusConnection.new(transport, Gio.dbus_generate_guid(),
    Gio.DBusConnectionFlags.AUTHENTICATION_SERVER |
    Gio.DBusConnectionFlags.AUTHENTICATION_REQUIRE_SAME_USER |
    Gio.DBusConnectionFlags.DELAY_MESSAGE_PROCESSING,
    None, None, ready)
GLib.timeout_add_seconds(15, lambda: loop.quit() or False)
loop.run()
for connection in connections:
    if not connection.is_closed(): connection.close_sync(None)
''')
    control, remote_control = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    listener, remote_listener = socket.socketpair()
    from tools.test_storage import runtime_directory
    with runtime_directory(prefix='onpc-watch-test-') as runtime:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        server.bind(str(runtime / 'frames.sock'))
        server.listen(4)
        descriptors = [remote_control.fileno(), -1, listener.fileno(),
                       remote_listener.fileno(), server.fileno()]
        argv = [sys.executable, '-B', str(worker)]
        for name, fd in zip(('control', 'display', 'listener', 'remote', 'server'), descriptors):
            argv.extend(['--' + name, str(fd)])
        argv.extend(['--uid', str(max(1, os.getuid())), '--run', 'a' * 32])
        with (tmp_path / 'collector.log').open('wb') as log:
            child = subprocess.Popen(argv, pass_fds=tuple(fd for fd in descriptors if fd >= 0),
                                     stdout=log, stderr=log)
        memory = None
        displays = []
        try:
            remote_control.close()
            listener.close()
            remote_listener.close()
            server.close()
            control.settimeout(5)
            control.send(b'start')
            assert control.recv(16) == b'ready'
            with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
                peer.settimeout(5)
                peer.connect(str(runtime / 'frames.sock'))
                memory = protocol.receive_frames(peer, owner=os.getuid())
            first = protocol.read_frame(memory)
            assert first[1]['lease_locked'] is True
            # Multiple heartbeats must keep the very same mapping current during
            # offline inspection/restoration and between preparation steps.
            for _ in range(3):
                assert control.recv(16) == b'beat'
            latest = protocol.read_frame(memory, first[0])
            assert latest is not None and latest[1]['lease_locked'] is True
            assert latest[1]['state'] == 'waiting'
            assert time.monotonic_ns() - latest[1]['updated_ns'] < 1_000_000_000
            for pixels in ('boot', 'next'):
                display, remote_display = socket.socketpair()
                with display, remote_display, (tmp_path / (pixels + '.log')).open('wb') as log:
                    producer = subprocess.Popen([sys.executable, '-B', str(qemu_worker),
                        str(remote_display.fileno()), pixels], pass_fds=(remote_display.fileno(),),
                        stdout=log, stderr=log)
                    displays.append(producer)
                    remote_display.close()
                    control.sendmsg([b'display'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                                 array.array('i', [display.fileno()]))])
                    display.close()
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        frame = protocol.read_frame(memory)
                        if frame[1]['state'] == 'live' and frame[2] == pixels.encode():
                            break
                        time.sleep(.01)
                    else:
                        pytest.fail((tmp_path / 'collector.log').read_text() +
                                    (tmp_path / (pixels + '.log')).read_text())
                    assert frame[1]['run'] == first[1]['run']
                    assert frame[1]['lease_locked'] is True
                    # End only this fake display; the collector must survive it.
                    producer.terminate()
                    producer.wait(timeout=5)
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        if protocol.read_frame(memory)[1]['state'] == 'waiting':
                            break
                        time.sleep(.01)
                    assert protocol.read_frame(memory)[1]['state'] == 'waiting'
                    assert child.poll() is None
            control.close()
            assert child.wait(timeout=5) == 0, (tmp_path / 'collector.log').read_text()
            assert protocol.read_frame(memory)[1]['state'] == 'stopped'
        finally:
            control.close()
            server.close()
            remote_control.close()
            listener.close()
            remote_listener.close()
            if memory is not None:
                memory.close()
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            for producer in displays:
                if producer.poll() is None:
                    producer.kill()
                    producer.wait(timeout=5)


def test_display_end_preserves_lease_publication_and_clears_old_pixels(frames):
    from e2e_watch_collector import Attachment
    display = Display(frames)
    frames.publish(lease_locked=True)
    attachment = Attachment(display, Mock())
    connection = Mock()
    connection.is_closed.return_value = False
    attachment.connections.append(connection)
    display.update('Scanout', [1, 1, 4, protocol.FORMATS[0]], b'abcd')
    display.publish()
    first = receive(frames)
    try:
        assert protocol.read_frame(first)[2] == b'abcd'
        attachment.close()
        connection.close.assert_called_once()
        meta = protocol.read_frame(first)[1]
        assert meta['state'] == 'waiting' and meta['lease_locked'] is True
        with receive(frames) as reconnected:
            assert protocol.read_frame(reconnected)[1]['run'] == meta['run']
        display.update('Scanout', [1, 1, 4, protocol.FORMATS[0]], b'next')
        display.publish()
        assert protocol.read_frame(first)[2] == b'next'
    finally:
        first.close()


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


def test_headless_feed_import_needs_no_checkout_or_desktop_environment():
    import subprocess
    import sys
    from pathlib import Path
    directory = Path(__file__).resolve().parents[2] / 'tools'
    result = subprocess.run([sys.executable, '-IB', '-c',
        f'import sys; sys.path.insert(0, {str(directory)!r}); '
        'from e2e_watch_viewer import Feed; Feed()'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('argument', ['-h', '--help'])
def test_help_exits_before_inspecting_or_launching_the_desktop(monkeypatch, capsys, argument):
    import watch_viewer as viewer
    monkeypatch.setattr(viewer.os, 'getuid', Mock(
        side_effect=AssertionError('Help must not inspect the desktop user')))
    monkeypatch.setattr(viewer.Path, 'read_text', Mock(
        side_effect=AssertionError('Help must not inspect the security profile')))
    monkeypatch.setattr(viewer.subprocess, 'run', Mock(
        side_effect=AssertionError('Help must not delegate a viewer launch')))
    monkeypatch.setattr(viewer, 'application', Mock(
        side_effect=AssertionError('Help must not construct the viewer')))

    with pytest.raises(SystemExit) as stopped:
        viewer.main([argument])

    assert stopped.value.code == 0
    output = capsys.readouterr()
    assert 'Watch test output, UI tests and VM activity.' in output.out
    assert output.err == ''


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


def test_slow_vm_transport_cannot_block_another_cell_or_the_renderer():
    release, entered, healthy_polled = threading.Event(), threading.Event(), threading.Event()
    def stalled(*, pixels):
        entered.set()
        assert release.wait(5)
        return 'waiting'
    slow_source = Mock(vm_name='slow', poll=stalled)
    slow_source.progress.return_value = slow_source.activity.return_value = None
    def ready(*, pixels):
        healthy_polled.set()
        return 'waiting'
    fast_source = Mock(vm_name='fast', poll=ready)
    fast_source.progress.return_value = {'step': 'fast VM'}
    fast_source.activity.return_value = None
    slow, fast = AsyncFeed(slow_source), AsyncFeed(fast_source)
    try:
        assert slow.poll() is None
        assert entered.wait(2)
        fast.poll()
        assert healthy_polled.wait(2)
        deadline = time.monotonic() + 2
        while fast.progress() is None and time.monotonic() < deadline:
            fast.poll()
            time.sleep(.005)
        assert fast.progress() == {'step': 'fast VM'}
        assert not release.is_set()
        # Poll and close remain immediate even while this VM's socket is stuck.
        assert slow.poll() is None
        slow.close()
        assert slow.thread.is_alive()
        assert slow.requests.qsize() <= 1 and fast.updates.qsize() <= 1
    finally:
        slow.close()
        fast.close()
        release.set()
        slow.thread.join(2)
        fast.thread.join(2)
    assert not slow.thread.is_alive() and not fast.thread.is_alive()
    slow_source.close.assert_called_once()
    fast_source.close.assert_called_once()


def test_latest_vm_snapshot_queue_is_bounded_and_preserves_changed_frames():
    source = Mock(vm_name='isolated')
    source.progress.return_value = source.activity.return_value = None
    source.poll.side_effect = [('frame', {'run': 'first'}, b'pixels', b''), None,
                               ('frame', {'run': 'last'}, b'new pixels', b'')]
    feed = AsyncFeed(source)
    try:
        for count in range(1, 4):
            feed.replace(feed.requests, True)
            deadline = time.monotonic() + 2
            while source.poll.call_count < count and time.monotonic() < deadline:
                time.sleep(.005)
            assert source.poll.call_count == count
        deadline = time.monotonic() + 2
        while feed.updates.empty() and time.monotonic() < deadline:
            time.sleep(.005)
        frame, _, _, pixels = feed.updates.get(timeout=2)
        assert frame[1]['run'] == 'last' and pixels is True
        assert feed.updates.empty()
    finally:
        feed.close()
        feed.thread.join(2)
    assert not feed.thread.is_alive()


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


def test_hidden_feed_reads_only_metadata_and_resumes_current_pixels(frames):
    frames.publish(b'\x01\x02\x03\0' * 4, state='live', width=2, height=2,
                   stride=8, format=0x20020888)
    class HeaderOnly:
        def __getitem__(self, key):
            assert key.stop <= protocol.HEADER, 'hidden viewer copied pixels'
            return frames.memory[key]
    hidden = protocol.read_frame(HeaderOnly(), pixels=False)
    assert hidden[1]['state'] == 'live' and hidden[2:] == (b'', b'')
    feed = Feed()
    feed.memory = receive(frames)
    try:
        assert feed.poll(pixels=False)[2:] == (b'', b'')
        assert feed.poll()[2] == b'\x01\x02\x03\0' * 4
    finally:
        feed.close()


def test_tab_reopen_retries_pixels_after_a_torn_header(frames, monkeypatch):
    import e2e_watch_viewer as viewer
    frames.publish(b'\x01\x02\x03\0' * 4, state='live', width=2, height=2,
                   stride=8, format=0x20020888)
    feed = Feed()
    feed.memory = receive(frames)
    try:
        assert feed.poll(pixels=False)[2:] == (b'', b'')
        with monkeypatch.context() as scope:
            scope.setattr(viewer, 'read_frame', Mock(return_value=None))
            assert feed.poll(pixels=True) is None
        assert feed.poll(pixels=True)[2] == b'\x01\x02\x03\0' * 4
    finally:
        feed.close()


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


def test_viewer_disconnect_does_not_stop_writer_or_other_readers(frames):
    first, second = receive(frames), receive(frames)
    first.close()
    try:
        for _ in range(25):
            receive(frames).close()
            frames.publish()
        assert protocol.read_frame(second)[0] == frames.sequence
    finally:
        second.close()


def test_partial_updates_and_cursor_match_full_frame(frames):
    display = Display(frames)
    display.update('Scanout', [3, 2, 16, protocol.FORMATS[0]], b'a' * 32)
    display.update('Update', [1, 0, 1, 2, 8, protocol.FORMATS[0]], b'bbbbPAD!ccccPAD!')
    display.update('CursorDefine', [1, 1, 0, 0], b'\xff' * 4)
    display.update('MouseSet', [2, 1, 1])
    display.publish()
    _, meta, pixels, cursor = protocol.read_frame(frames.memory)
    assert pixels == b'aaaabbbbaaaaaaaa' + b'aaaaccccaaaaaaaa'
    assert (meta['cursor_x'], meta['cursor_y'], meta['cursor_on']) == (2, 1, True)
    assert cursor == b'\xff' * 4
    with pytest.raises(ValueError, match='update-bounds'):
        display.update('Update', [-1, 0, 1, 1, 4, protocol.FORMATS[0]], b'bad!')
    assert bytes(display.pixels) == pixels
    display.update('Disable', [])
    display.publish()
    assert protocol.read_frame(frames.memory)[2:] == (b'', b'')


def test_early_vga_damage_waits_for_full_scanout(frames):
    display = Display(frames)
    display.update('Update', [0, 0, 1, 1, 4, protocol.FORMATS[0]], b'\0' * 4)
    assert not display.publish()
    assert protocol.read_frame(frames.memory)[1]['state'] == 'waiting'
    display.update('Scanout', [1, 1, 4, protocol.FORMATS[0]], b'\xff' * 4)
    display.publish()
    assert protocol.read_frame(frames.memory)[1]['state'] == 'live'
    display.update('Update', [0, 0, 2, 1, 8, protocol.FORMATS[0]], b'\0' * 8)
    display.publish()
    assert protocol.read_frame(frames.memory)[1]['state'] == 'waiting'
    display.update('Scanout', [2, 1, 8, protocol.FORMATS[0]], b'\xff' * 8)
    display.publish()
    assert protocol.read_frame(frames.memory)[1]['width'] == 2


@pytest.mark.parametrize('values', [(2049, 1, 8196, protocol.FORMATS[0]),
                                   (2, 1, 4, protocol.FORMATS[0]), (1, 1, 4, 0)])
def test_unsupported_frames_refuse_without_allocating(values):
    with pytest.raises(ValueError):
        protocol.layout(*values)


def test_stopped_feed_can_follow_a_new_attempt(frames):
    feed = Feed()
    feed.memory = receive(frames)
    assert feed.poll()[1]['state'] == 'waiting'
    frames.publish(state='stopped')
    assert feed.poll() == 'waiting'
    assert feed.memory is None
    frames.publish(state='waiting')
    with patch.object(feed, 'connect', side_effect=lambda: setattr(feed, 'memory', receive(frames))):
        assert feed.poll()[1]['state'] == 'waiting'
    feed.close()


def test_frozen_writer_never_keeps_stale_image_forever(frames):
    feed = Feed()
    feed.memory = receive(frames)
    feed.poll()
    frames.memory[:16] = protocol.PREFIX.pack(9, 100)
    with patch('e2e_watch_viewer.time.monotonic', return_value=feed.last_frame + 4):
        assert feed.poll() == 'waiting'
    assert feed.memory is None


def test_torn_metadata_retries_instead_of_disconnecting():
    class ChangingMemory:
        reads = 0
        def __getitem__(self, key):
            self.reads += 1
            return {1: protocol.PREFIX.pack(2, 50), 2: b'{torn json',
                    3: protocol.PREFIX.pack(4, 40)}[self.reads]
    assert protocol.read_frame(ChangingMemory()) is None


def test_public_dbus_listener_decodes_real_wire_frames(frames):
    from gi.repository import Gio, GLib
    from e2e_watch_collector import export_listener
    loop = GLib.MainLoop()
    peers = socket.socketpair()
    transports = [Gio.Socket.new_from_fd(peer.detach()).connection_factory_create_connection()
                  for peer in peers]
    connections, results, failures = [], [], []
    display = Display(frames)
    def reply(connection, result):
        try:
            results.append(connection.call_finish(result).unpack())
        except Exception as error:
            failures.append(error)
        loop.quit()
    def ready(_source, result, server):
        try:
            connection = Gio.DBusConnection.new_finish(result)
            connections.append(connection)
            connection.set_exit_on_close(False)
            if server:
                export_listener(connection, display, lambda: failures.append('invalid frame'))
                connection.start_message_processing()
            else:
                connection.call(None, '/org/qemu/Display1/Listener', 'org.qemu.Display1.Listener',
                    'Scanout', GLib.Variant('(uuuuay)', (2, 1, 8, protocol.FORMATS[0], b'abcdefgh')),
                    None, Gio.DBusCallFlags.NONE, 2000, None, reply)
        except Exception as error:
            failures.append(error)
            loop.quit()
    Gio.DBusConnection.new(transports[0], Gio.dbus_generate_guid(),
        Gio.DBusConnectionFlags.AUTHENTICATION_SERVER | Gio.DBusConnectionFlags.AUTHENTICATION_REQUIRE_SAME_USER
        | Gio.DBusConnectionFlags.DELAY_MESSAGE_PROCESSING,
        None, None, ready, True)
    Gio.DBusConnection.new(transports[1], None, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT,
        None, None, ready, False)
    timer = GLib.timeout_add(3000, lambda: loop.quit() or False)
    try:
        loop.run()
        assert not failures and results == [()]
        display.publish()
        assert protocol.read_frame(frames.memory)[2] == b'abcdefgh'
    finally:
        GLib.source_remove(timer)
        for connection in connections:
            if not connection.is_closed():
                connection.close_sync(None)
