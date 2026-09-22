"""Concurrent read-only feeds, reconnects, stale rejection and no backpressure."""

import json
import os
import socket
import threading
import time
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from e2e_watch_protocol import PREFIX, read_frame, receive_frames
from tests.support.ui_watch import Observer
from ui_watch_transport import Feeds, Publication, label, registry
from ui_watch_capture import DISPLAY, Capture


@pytest.mark.parametrize('fails', [False, True])
def test_viewer_logs_native_output_and_restores_terminal(tmp_path, monkeypatch, capfd, fails):
    import ui_watch_viewer as viewer

    allocate = tempfile.mkdtemp
    monkeypatch.setattr(viewer.tempfile, 'mkdtemp',
                        lambda **kwargs: allocate(prefix=kwargs['prefix'], dir=tmp_path))

    def run(arguments):
        assert arguments == ['watch-ui']
        print('Python viewer output')
        os.write(1, b'native stdout\n')
        os.write(2, b'Gtk-WARNING: viewer measurement\n')
        if fails:
            raise RuntimeError('viewer failed')
        return 7

    monkeypatch.setattr(viewer, 'application', lambda: SimpleNamespace(run=run))
    if fails:
        with pytest.raises(RuntimeError, match='viewer failed'):
            viewer.run_viewer()
    else:
        assert viewer.run_viewer() == 7
    os.write(1, b'terminal stdout restored\n')
    os.write(2, b'terminal stderr restored\n')
    terminal = capfd.readouterr()
    directories = list(tmp_path.iterdir())
    assert len(directories) == 1
    directory = directories[0]
    assert directory.stat().st_mode & 0o777 == 0o700
    assert terminal.out == (f'UI viewer diagnostics: {directory / "viewer.log"}\n'
                            'terminal stdout restored\n')
    assert terminal.err == 'terminal stderr restored\n'
    logged = (directory / 'viewer.log').read_text()
    assert 'Python viewer output\n' in logged
    assert 'native stdout\n' in logged
    assert 'Gtk-WARNING: viewer measurement\n' in logged


def ready(feeds):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        value = feeds.poll()
        if len(value) == 4:
            return value
        time.sleep(.002)
    raise AssertionError('All four worker connections must complete')


@pytest.fixture
def publications():
    temporary = tempfile.TemporaryDirectory(prefix='onpc-ui-watch-test-', dir='/tmp')
    directory = Path(temporary.name)
    sources = [Publication(directory) for _ in range(4)]
    stop = threading.Event()

    def serve():
        while not stop.wait(.002):
            for source in sources:
                source.serve()

    thread = threading.Thread(target=serve)
    thread.start()
    try:
        yield directory, sources
    finally:
        stop.set()
        thread.join(timeout=2)
        assert not thread.is_alive()
        for source in sources:
            source.close()
        temporary.cleanup()


def test_four_workers_detach_reattach_and_independent_updates(publications):
    directory, sources = publications
    feeds = Feeds(directory)
    try:
        for index, source in enumerate(sources):
            source.frames.publish(test=f'case-{index}', phase='call')
        assert {frame[1]['test'] for frame in ready(feeds).values()} == {
            'case-0', 'case-1', 'case-2', 'case-3'}
        feeds.close()
        for source in sources:
            source.frames.publish(test='next case')
        feeds.next_scan = 0
        assert len(ready(feeds)) == 4
        assert all(frame[1]['test'] == 'next case' for frame in feeds.poll().values())
        # Reader close has no channel back to any producer.
        other = Feeds(directory)
        try:
            assert len(ready(other)) == 4
            feeds.close()
            sources[0].frames.publish(test='continues')
            assert other.poll()[sources[0].run][1]['test'] == 'continues'
        finally:
            other.close()
    finally:
        feeds.close()


def test_handshake_never_waits_for_producer_on_the_same_event_loop():
    with tempfile.TemporaryDirectory(prefix='onpc-ui-watch-test-', dir='/tmp') as directory:
        source = Publication(Path(directory))
        feeds = Feeds(Path(directory))
        try:
            assert feeds.poll() == {}
            assert source.run in feeds.pending
            source.serve()
            assert feeds.poll()[source.run][1]['state'] == 'waiting'
        finally:
            feeds.close()
            source.close()


@pytest.mark.parametrize('state', ['stopped', 'old', 'odd', 'wrong-run'])
def test_stopped_stale_or_torn_writer_never_retains_pixels(publications, monkeypatch, state):
    directory, sources = publications
    feeds = Feeds(directory)
    source = sources[0]
    try:
        assert len(ready(feeds)) == 4
        if state == 'stopped':
            source.frames.publish(state='stopped')
        elif state == 'old':
            source.frames.publish()
            now = time.monotonic_ns()
            monkeypatch.setattr('ui_watch_transport.time.monotonic_ns', lambda: now + 4_000_000_000)
        elif state == 'wrong-run':
            source.frames.publish(run='0' * 32)
        else:
            source.frames.memory[:PREFIX.size] = PREFIX.pack(7, 100)
            feeds.connections[source.run][3] -= 4
        assert source.run not in feeds.poll()
    finally:
        feeds.close()


def test_viewer_receives_only_sealed_readonly_frames_and_cannot_send_commands(publications):
    directory, sources = publications
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
        peer.settimeout(1)
        peer.connect(str(sources[0].path))
        with receive_frames(peer, owner=os.getuid()) as memory:
            with pytest.raises(TypeError):
                memory[0] = 1
            with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as unwanted:
                unwanted.connect(str(sources[0].path))
                unwanted.send(b'STOP\nresize 800x600\n')
                # The kernel may reset an output-only handshake when its peer
                # closes with unread input. Existing readers are unaffected.
            sources[0].frames.publish(test='continues', phase='call')
            assert read_frame(memory)[1]['test'] == 'continues'


def test_optional_progress_never_blocks_or_propagates_capture_errors():
    observer = Observer.__new__(Observer)
    observer.control = Mock()
    observer.control.send.side_effect = BlockingIOError
    observer.update('case', 'call')
    observer.control.send.side_effect = BrokenPipeError
    observer.update('case', 'teardown')
    observer.control.send.side_effect = None
    observer.update('test\n' + 'a' * 10000, 'call')
    value = json.loads(observer.control.send.call_args.args[0])
    assert len(value['test']) == 700 and '\n' not in value['test']


def test_registry_is_checkout_specific(tmp_path):
    first = registry(tmp_path / 'one', create=True)
    second = registry(tmp_path / 'two', create=True)
    assert first != second
    assert first.stat().st_mode & 0o777 == 0o700
    first.rmdir()
    second.rmdir()


def test_labels_are_bounded_and_remove_terminal_controls():
    assert label('\nHello\x00') == 'Hello'
    assert len(label('x' * 10000)) == 700


@pytest.fixture
def capture(publications, monkeypatch):
    _directory, sources = publications
    collector = Capture.__new__(Capture)
    collector.publication = sources[0]
    collector.publication.frames.publish(
        b'\0' * 16, state='live', width=2, height=2, stride=8, format=0x20020888,
        branch='Layout and overflow', test='scaled form', phase='call', captured_ns=1)
    collector.stage = 'live'
    collector.generation = 1
    collector.display_serial = 1
    collector.next_display_check = 101
    collector.started = 0
    collector.retries = 0
    collector.retry_at = 0
    collector.pipeline = collector.sink = None
    collector.close = Mock()
    collector.begin = Mock()
    collector.Gst = Mock()
    collector.GstVideo = Mock()
    clock = SimpleNamespace(now=100.)
    monkeypatch.setattr('ui_watch_capture.time.monotonic', lambda: clock.now)
    return collector, clock


def test_capture_reconnect_clears_pixels_and_resumes_same_branch(capture):
    collector, clock = capture
    source = collector.publication

    def check_outage_during_teardown():
        frame = read_frame(source.frames.memory)
        assert frame[1]['state'] == 'waiting' and frame[2] == b''
        assert frame[1]['captured_ns'] == 0
        assert collector.stage == 'retry'

    collector.close.side_effect = check_outage_during_teardown
    collector.recover(RuntimeError('all buffers have been removed'))
    collector.close.assert_called_once()
    frame = read_frame(source.frames.memory)
    assert frame[1]['state'] == 'waiting' and frame[2] == b''
    assert frame[1]['captured_ns'] == 0
    assert frame[1]['branch'] == 'Layout and overflow'
    assert frame[1]['test'] == 'scaled form' and frame[1]['phase'] == 'call'
    collector.tick()
    collector.begin.assert_not_called()

    clock.now += .5
    collector.tick()
    collector.begin.assert_called_once()
    collector.pipeline, collector.sink = Mock(), Mock()
    collector.pipeline.get_bus.return_value.pop_filtered.return_value = None
    collector.GstVideo.VideoInfo.new_from_caps.return_value = SimpleNamespace(
        width=2, height=2, stride=[8])
    sample = collector.sink.emit.return_value
    sample.get_buffer.return_value.extract_dup.return_value = b'\x01' * 16
    collector.tick()
    resumed = read_frame(source.frames.memory)
    assert resumed[1]['run'] == frame[1]['run']
    assert resumed[1]['state'] == 'live' and resumed[1]['captured_ns'] > 1
    assert resumed[1]['capture_generation'] == collector.generation
    assert resumed[2] == b'\x01' * 16


def test_capture_monitor_signal_recovers_with_same_serial_and_new_wrapper(capture):
    collector, clock = capture
    collector.call = Mock(return_value=(collector.display_serial, [object()], [object()], {}))

    collector.monitors_changed(Mock())

    collector.call.assert_not_called()
    collector.close.assert_called_once()
    frame = read_frame(collector.publication.frames.memory)
    assert collector.stage == 'retry'
    assert frame[1]['state'] == 'waiting' and frame[2] == b''
    assert frame[1]['detail'] == 'Reconnecting capture'
    assert collector.retry_at == clock.now + .5


def test_capture_poll_recovers_when_monitor_signal_is_lost(capture):
    collector, clock = capture
    collector.call = Mock(return_value=(2, [object()], [object()], {}))
    collector.next_display_check = clock.now

    collector.tick()

    collector.close.assert_called_once()
    assert collector.stage == 'retry'


def test_capture_poll_leaves_current_monitor_stream_running(capture):
    collector, clock = capture
    collector.call = Mock(return_value=(1, [object()], [object()], {}))
    collector.next_display_check = clock.now

    collector.tick()

    collector.close.assert_not_called()
    assert collector.stage == 'live'
    assert collector.next_display_check == clock.now + .25


def test_capture_repeated_failure_stops_after_three_retries(capture):
    collector, clock = capture
    collector.begin.side_effect = RuntimeError('stream unavailable')
    collector.recover(RuntimeError('disconnected'))
    for _ in range(3):
        clock.now += .5
        collector.tick()
    assert collector.begin.call_count == 3
    assert collector.stage == 'failed'
    frame = read_frame(collector.publication.frames.memory)
    assert frame[1]['state'] == 'unavailable' and frame[2] == b''
    clock.now += 30
    collector.tick()
    assert collector.begin.call_count == 3


def test_capture_recovery_deadline_covers_missing_stream_signal(capture):
    collector, clock = capture
    collector.recover(RuntimeError('disconnected'))
    clock.now += .5
    collector.tick()
    clock.now += 15
    collector.tick()
    assert collector.stage == 'failed'
    collector.begin.assert_called_once()
