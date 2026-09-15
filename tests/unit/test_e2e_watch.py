"""Real local frame transport and bounded display/reattachment contracts."""

import array
import fcntl
import mmap
import os
import socket
from unittest.mock import patch

import pytest

import e2e_watch_protocol as protocol
from e2e_watch_collector import Display
from e2e_watch_viewer import Feed


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
