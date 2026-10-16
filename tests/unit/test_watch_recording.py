"""Encoder lifetime and bounded frame handoff, without a desktop or guest."""

import json
import shutil
import subprocess
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
