"""Encoder lifetime and bounded frame handoff, without a desktop or guest."""

import json
import shutil
import subprocess
import sys
import time
from unittest.mock import Mock, patch
from types import SimpleNamespace

import pytest

import watch_recording_worker as recording


def test_launch_is_a_private_session_and_inherited_control_endpoint(tmp_path):
    command = recording.launch_command(tmp_path, 23, tmp_path / 'recording.webm')
    assert command[:4] == ['dbus-run-session', '--', '/usr/bin/python3', '-B']
    assert command[-6:] == ['--control', '23', '--root', str(tmp_path),
                            '--output', str(tmp_path / 'recording.webm')]
    scoped = recording.launch_command(tmp_path, 23, tmp_path / 'recording.webm', vm_names=('Owned',))
    assert scoped[-2:] == ['--vms', '["Owned"]']


def test_cleanup_refuses_reused_process_identity():
    process = Mock()
    process.poll.return_value = None
    with patch.object(recording, 'process_identity', return_value=(123, 8)):
        with pytest.raises(RuntimeError, match='identity changed'):
            recording.stop_owned(process, (123, 7))
    process.terminate.assert_not_called()
    process.kill.assert_not_called()


def test_encoder_produces_decodable_webm_and_reaps_child(tmp_path):
    assert shutil.which('ffmpeg') and shutil.which('ffprobe'), 'missing recording prerequisites'
    output = tmp_path / 'capture.webm'
    encoder = recording.Encoder(output, width=32, height=24, fps=5)
    try:
        encoder.submit(bytes((255, 0, 0, 255)) * (32 * 24), names=('Red',))
        time.sleep(.22)
        encoder.submit(bytes((0, 0, 255, 255)) * (32 * 24), names=('Blue',))
        time.sleep(.22)
    finally:
        summary = encoder.close()
    assert encoder.process.poll() == 0
    assert summary['frames'] >= 2 and summary['duration_seconds'] >= .4
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(output)],
                           capture_output=True, check=True, text=True)
    stream = json.loads(probe.stdout)['streams'][0]
    assert (stream['codec_name'], stream['width'], stream['height']) == ('vp9', 32, 24)
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(output), '-f', 'rawvideo',
        '-pix_fmt', 'rgba', 'pipe:1'], capture_output=True, check=True).stdout
    assert len(decoded) == summary['frames'] * 32 * 24 * 4
    first, last = decoded[:4], decoded[-4:]
    assert first[0] > 240 and first[2] < 20
    assert last[2] > 240 and last[0] < 20
    assert {span['vm'] for span in summary['vm_spans']} == {'Red', 'Blue'}
    assert all(encoder.started_ns <= span['start_ns'] < span['end_ns']
               <= encoder.started_ns + summary['frames'] * 200_000_000
               for span in summary['vm_spans'])


def test_encoder_latest_frame_handoff_is_bounded():
    encoder = recording.Encoder.__new__(recording.Encoder)
    import queue
    encoder.frames = queue.Queue(maxsize=1)
    encoder.width = encoder.height = 1
    encoder.started = time.monotonic()
    encoder.fps = 5
    encoder.dropped_capture_frames = 0
    for value in range(100):
        encoder.submit(bytes((value, 0, 0, 255)))
    assert encoder.frames.qsize() == 1
    assert encoder.frames.get_nowait()[1] == bytes((99, 0, 0, 255))
    with pytest.raises(ValueError, match='frame size'):
        encoder.submit(b'bad')


def test_dropped_vm_frame_never_enters_encoded_visibility_intervals():
    import queue
    import threading
    encoder = recording.Encoder.__new__(recording.Encoder)
    encoder.width = encoder.height = 1
    encoder.fps = 5
    encoder.started = encoder.started_ns = 0
    encoder.count = encoder.dropped_capture_frames = 0
    encoder.vm_spans, encoder.shown_vms = [], {}
    encoder.frames = queue.Queue(maxsize=1)
    encoder.stopping = threading.Event()
    encoder.finished = threading.Event()
    encoder.error = None
    encoder.process = Mock()
    encoder.process.poll.return_value = encoder.process.wait.return_value = 0
    encoder.identity = (123, 456)
    with patch.object(recording.time, 'monotonic', side_effect=(.01, .21)):
        encoder.submit(b'aaaa', names=('Dropped',))
        encoder.submit(b'bbbb', names=('Encoded',))
    encoder.ended = .4
    encoder.stopping.set()
    encoder.run()
    summary = encoder.close()
    assert summary['dropped_capture_frames'] == 1
    assert summary['vm_spans'] == [dict(vm='Encoded', start_ns=200_000_000, end_ns=400_000_000)]


def test_secret_omission_labels_are_cached_by_public_vm_names():
    first = recording.secret_pixels(names=('Synthetic-One', 'Synthetic-Two'))
    assert first is recording.secret_pixels(names=('Synthetic-Two', 'Synthetic-One', 'Synthetic-One'))
    assert first != recording.secret_pixels(names=('Synthetic-One',))
    assert first[0::4] == first[1::4] == first[2::4]
    assert set(first[3::4]) == {255}


def test_unseal_keeps_stale_secret_texture_opaque_until_fresh_frame_and_paint():
    gate = recording.CaptureGate()
    screen = SimpleNamespace(texture=object(), meta={'updated_ns': 10})
    panel = SimpleNamespace(screen=screen)
    gate.seal('input', True, 10)
    assert gate.masked([panel], 20)
    gate.seal('input', False, 30)
    # A controller's safe-result proof does not refresh a cached GTK texture.
    assert gate.masked([panel], 1_000_000_000)
    screen.meta['updated_ns'] = 40
    assert gate.masked([panel], 1_000_000_001)
    assert gate.masked([panel], 1_000_000_002)
    assert not gate.masked([panel], 1_200_000_001)


def test_unseal_waits_for_every_visible_vm_and_preserves_other_tokens():
    gate = recording.CaptureGate()
    panels = [SimpleNamespace(screen=SimpleNamespace(texture=object(), meta={'updated_ns': at}))
              for at in (100, 10)]
    gate.seal('first', True, 1)
    gate.seal('second', True, 2)
    gate.seal('first', False, 20)
    assert gate.masked(panels, 300_000_000)
    gate.seal('second', False, 30)
    assert gate.masked(panels, 600_000_000)
    panels[1].screen.texture = None  # A stopped feed has no cached pixels.
    assert gate.masked(panels, 700_000_000)
    assert not gate.masked(panels, 900_000_000)


@pytest.fixture
def recording_gi(monkeypatch):
    repository = SimpleNamespace(Gtk=Mock(), Graphene=Mock(), Gdk=Mock(), GLib=Mock())
    monkeypatch.setitem(sys.modules, 'gi', SimpleNamespace(require_version=Mock()))
    monkeypatch.setitem(sys.modules, 'gi.repository', repository)
    return repository


def test_widget_pixels_recovers_after_a_missing_render_node(recording_gi):
    window = Mock()
    node = object()
    recording_gi.Gtk.Snapshot.return_value.to_node.side_effect = [None, node]
    downloader = recording_gi.Gdk.TextureDownloader.new.return_value
    downloader.download_bytes.return_value = (SimpleNamespace(get_data=lambda: b'rgba'), 4)

    assert recording.widget_pixels(window, width=1, height=1) is None
    window.get_renderer.assert_not_called()
    recording_gi.Gdk.TextureDownloader.new.assert_not_called()

    assert recording.widget_pixels(window, width=1, height=1) == b'rgba'
    assert window.get_renderer.return_value.render_texture.call_args.args[0] is node
    assert recording_gi.Gtk.WidgetPaintable.new.call_count == 2


@pytest.fixture
def render_rig(tmp_path, monkeypatch, recording_gi):
    clock = SimpleNamespace(now=0)
    app = SimpleNamespace(window=Mock(), checkouts={}, viewer_layout=None,
                          run=Mock(), quit=Mock(), discovery=None)
    app.window.get_width.return_value = recording.WIDTH
    encoder = SimpleNamespace(started_ns=0, error=None, submit=Mock(),
                              close=Mock(return_value={'dropped_capture_frames': 0}))
    discovery = Mock()
    monkeypatch.setitem(sys.modules, 'watch_viewer',
                        SimpleNamespace(application=Mock(return_value=app)))
    monkeypatch.setitem(sys.modules, 'watch_checkouts',
                        SimpleNamespace(Discovery=Mock(return_value=discovery)))
    monkeypatch.setattr(recording, 'Encoder', Mock(return_value=encoder))
    monkeypatch.setattr(recording, 'time', SimpleNamespace(monotonic_ns=lambda: clock.now))
    monkeypatch.setattr(recording, '_stop_requested', SimpleNamespace(is_set=lambda: False))
    monkeypatch.setattr(recording, 'identity_for_pid', Mock(return_value=(123, 456)))
    pixels = Mock()
    monkeypatch.setattr(recording, 'widget_pixels', pixels)
    control = Mock()
    control.recv.side_effect = BlockingIOError
    return SimpleNamespace(root=tmp_path, app=app, encoder=encoder, control=control,
                           clock=clock, pixels=pixels, glib=recording_gi.GLib,
                           discovery=discovery)


@pytest.mark.parametrize('startup_gap', (True, False), ids=('startup', 'steady'))
def test_render_recovers_from_transient_paint_gaps(render_rig, startup_gap):
    rig = render_rig

    def run(_arguments):
        tick = rig.glib.timeout_add.call_args.args[1]
        if startup_gap:
            rig.clock.now = 9_000_000_000
            rig.pixels.return_value = None
            assert tick() is True
            rig.control.send.assert_not_called()
            rig.encoder.submit.assert_not_called()
        rig.pixels.return_value = b'safe'
        assert tick() is True
        assert [json.loads(call.args[0])['event'] for call in rig.control.send.call_args_list] == ['ready']
        submitted = list(rig.encoder.submit.call_args_list)
        rig.clock.now += 2_000_000_000
        rig.pixels.return_value = None
        assert tick() is True
        # A missing node must leave the encoder's last safe pixels untouched.
        assert rig.encoder.submit.call_args_list == submitted
        rig.app.quit.assert_not_called()
        rig.clock.now += 500_000_000
        rig.pixels.return_value = b'fresh'
        assert tick() is True
        rig.encoder.submit.assert_called_with(b'fresh', names=set())
        rig.clock.now += 2_500_000_000
        rig.pixels.return_value = None
        assert tick() is True  # Recovery starts a fresh steady-state stall window.
        rig.encoder.submit.assert_called_with(b'fresh', names=set())
        rig.control.recv.side_effect = [b'{"op":"close"}']
        assert tick() is False

    rig.app.run.side_effect = run
    assert recording.render(rig.control, rig.root, rig.root / 'unused.webm') == 0
    summary = json.loads(rig.control.sendall.call_args.args[0])
    assert summary['event'] == 'closed'
    assert summary['skipped_render_frames'] == (3 if startup_gap else 2)
    assert summary['dropped_capture_frames'] == 0
    assert summary['samples'] == 3
    rig.encoder.close.assert_called_once_with()
    rig.discovery.close.assert_called_once_with()
    rig.app.quit.assert_called_once_with()


@pytest.mark.parametrize('startup,limit,message', (
    (True, 10_000_000_000, 'recording window never painted'),
    (False, 3_000_000_000, 'recording window stopped painting'),
), ids=('startup', 'steady'))
def test_render_refuses_a_sustained_paint_stall(render_rig, capsys, startup, limit, message):
    rig = render_rig

    def run(_arguments):
        tick = rig.glib.timeout_add.call_args.args[1]
        if not startup:
            rig.pixels.return_value = b'safe'
            assert tick() is True
        submitted = list(rig.encoder.submit.call_args_list)
        rig.pixels.return_value = None
        rig.clock.now = limit
        assert tick() is True
        rig.app.quit.assert_not_called()
        rig.clock.now += 1
        assert tick() is False
        assert rig.encoder.submit.call_args_list == submitted

    rig.app.run.side_effect = run
    assert recording.render(rig.control, rig.root, rig.root / 'unused.webm') == 1
    summary = json.loads(rig.control.sendall.call_args.args[0])
    assert (summary['event'], summary['code']) == ('error', 'RuntimeError')
    assert summary['skipped_render_frames'] == 2
    assert summary['dropped_capture_frames'] == 0
    assert summary['samples'] == (0 if startup else 2)
    assert message in capsys.readouterr().err
    assert len(rig.control.send.call_args_list) == (0 if startup else 1)
    rig.encoder.close.assert_called_once_with()
    rig.discovery.close.assert_called_once_with()
    rig.app.quit.assert_called_once_with()
