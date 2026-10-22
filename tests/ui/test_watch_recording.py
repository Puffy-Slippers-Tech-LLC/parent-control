"""Core recording integrity, credential masking and owned worker cleanup.

These integration checks need the recording compositor, not viewer UI actions.
"""

import json
import fcntl
import os
from pathlib import Path
import socket
import select
import signal
import subprocess
import threading
import time

import pytest

from tools.test_storage import scratch_descriptors
from tools.watch_recording_worker import launch_command, process_identity, stop_owned

pytestmark = pytest.mark.ui


def test_private_worker_renders_encodes_seals_and_closes(tmp_path):
    root = tmp_path / 'checkout'
    (root / 'config').mkdir(parents=True)
    (root / '.git').mkdir()
    (root / 'tools').mkdir()
    (root / 'tools/watch').touch()
    (root / 'config/test-vm.json').write_text(json.dumps({'vms': [
        dict(name='Recording-Fixture', id=1, enabled='false', disk_anchor='/unused/fixture.qcow2')]}))
    output = tmp_path / 'recording.webm'
    control, remote = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    control.settimeout(20)
    with (tmp_path / 'worker.log').open('wb') as log:
        process = subprocess.Popen(launch_command(root, remote.fileno(), output),
            pass_fds=(remote.fileno(), *scratch_descriptors()), stdout=log, stderr=log)
    identity = process_identity(process)
    remote.close()

    def receive(event):
        message = json.loads(control.recv(65536))
        assert message['event'] == event, (message, (tmp_path / 'worker.log').read_text())
        return message

    def command(operation, event, **fields):
        control.send(json.dumps(dict(op=operation, **fields)).encode())
        return receive(event)

    try:
        ready = receive('ready')
        assert ready['started_ns'] <= time.monotonic_ns()
        first = command('begin', 'begun', category='e2e', id=1)
        assert first['at_ns'] >= ready['started_ns']
        # Independent scopes cannot unseal another caller's authentication.
        assert command('seal', 'sealed', token='first', sealed=True)['sealed'] is True
        assert command('seal', 'sealed', token='second', sealed=True)['sealed'] is True
        assert command('seal', 'sealed', token='first', sealed=False)['sealed'] is True
        assert command('seal', 'sealed', token='second', sealed=False)['sealed'] is False
        time.sleep(.5)
        final = command('end', 'ended', category='e2e', id=1)
        assert final['at_ns'] > first['at_ns']
        summary = command('close', 'closed')
        assert summary['samples'] >= 1 and summary['render_ns'] > 0
        assert summary['duration_seconds'] > 0 and summary['vm_spans'] == []
        assert process.wait(timeout=15) == 0, (tmp_path / 'worker.log').read_text()
        stream = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams',
            '-of', 'json', str(output)], capture_output=True, text=True, check=True).stdout)['streams'][0]
        assert (stream['codec_name'], stream['width'], stream['height']) == ('vp9', 1400, 900)
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(output), '-f', 'null', '-'],
                       check=True, timeout=20)
    finally:
        control.close()
        stop_owned(process, identity)


def test_secret_frame_is_marked_and_large_span_summary_is_lossless():
    from tools.watch_recording_worker import secret_pixels, final_reply
    pixels = secret_pixels()
    assert len(pixels) == 1400 * 900 * 4
    assert len(set(pixels[0::4])) > 1  # Opaque omission includes readable text.
    assert pixels[0::4] == pixels[1::4] == pixels[2::4]
    assert set(pixels[3::4]) == {255}
    spans = [dict(vm='Synthetic-One', start_ns=index, end_ns=index + 1)
             for index in range(2000)]
    control, peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    errors = []

    def send():
        try:
            final_reply(control, dict(event='closed', vm_spans=spans))
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=send)
    thread.start()
    received = []
    try:
        peer.settimeout(5)
        while True:
            packet = json.loads(peer.recv(65536))
            if packet['event'] == 'closed':
                assert packet['vm_spans'] == []
                break
            assert packet['event'] == 'vm-spans' and len(packet['items']) <= 128
            received.extend(packet['items'])
        assert received == spans
    finally:
        peer.close()
        thread.join(timeout=6)
        control.close()
    assert not thread.is_alive() and not errors


@pytest.mark.parametrize('sealed', [False, True], ids=['live-frames', 'sealed-frames'])
def test_session_publishes_one_playable_case_and_replaces_vm_combination(tmp_path, monkeypatch, sealed):
    """Real Session/control/Store publication, with synthetic display sources."""
    import vm_recording
    import watch_recording_worker
    from vm_selection import vm_config
    root = tmp_path / 'checkout'
    (root / 'config').mkdir(parents=True)
    (root / '.git').mkdir()
    (root / 'tools').mkdir()
    (root / 'tools/watch').touch()
    config = root / 'config/test-vm.json'
    config.write_text(json.dumps({'vms': [
        dict(name='Synthetic-One', id=20, enabled='false', disk_anchor='/unused/one.qcow2'),
        dict(name='Synthetic-Two', id=3, enabled='false', disk_anchor='/unused/two.qcow2')]}))
    registry = vm_config.registry
    monkeypatch.setattr(vm_config, 'registry', lambda path=None: registry(config))
    original_launch = watch_recording_worker.launch_command

    def launch(checkout, descriptor, output, **kwargs):
        command = original_launch(checkout, descriptor, output, **kwargs)
        command[4] = str(Path(__file__).with_name('watch_recording_benchmark.py'))
        return command

    monkeypatch.setattr(watch_recording_worker, 'launch_command', launch)
    monkeypatch.setenv('ONPC_RECORDING_BENCHMARK', 'encoded-transient')
    previous = None
    for names, expected in (
            (['Synthetic-One', 'Synthetic-Two'], 'e2e-1-Synthetic-Two-Synthetic-One.webm'),
            (['Synthetic-One'], 'e2e-1-Synthetic-One.webm')):
        # Both feeds are active even when this runner selects only one. The
        # renderer must exclude the unselected VM from pixels and provenance.
        monkeypatch.setenv('ONPC_RECORDING_SYNTHETIC_NAMES',
                           json.dumps(['Synthetic-One', 'Synthetic-Two']))
        session = vm_recording.Session(root, vm_names=names)
        session.start()
        try:
            time.sleep(1)  # Allow the synthetic read-only feeds to publish frames.
            if sealed:
                vm_recording.request(session.endpoint, dict(op='seal', token='whole-case', sealed=True))
                # Include a masked keyframe before the case's extraction prelude.
                time.sleep(1.2)
            for vm in names:
                vm_recording.request(session.endpoint, dict(op='event', vm=vm, category='e2e',
                    id=1, kind='started', at_ns=time.monotonic_ns(), title='Synthetic case'))
            time.sleep(1)
            for vm in names:
                vm_recording.request(session.endpoint, dict(op='event', vm=vm, category='e2e',
                    id=1, kind='finished', at_ns=time.monotonic_ns()))
                vm_recording.request(session.endpoint,
                    dict(op='finished', vm=vm, at_ns=time.monotonic_ns()))
            if sealed:
                # Leave a full frame after the case end before revealing pixels.
                time.sleep(.6)
                vm_recording.request(session.endpoint, dict(op='seal', token='whole-case', sealed=False))
            session.close()
            assert session.finalized and len(session.paths) == 1
            assert session.summary['skipped_render_frames'] >= 3
            path, = session.paths
            assert path.name == expected and vm_recording.playable(path)
            assert list(path.parent.glob('e2e-1-*.webm')) == [path]
            if sealed:
                decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path),
                    '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1'],
                    capture_output=True, check=True, timeout=20).stdout
                assert decoded and decoded[0::4] == decoded[1::4] == decoded[2::4]
                assert set(decoded[3::4]) == {255}
            if previous is not None:
                assert not previous.exists()
            previous = path
        finally:
            if not session.finalized and session.process.poll() is None:
                session.close(publish=False)


def test_terminated_private_session_reaps_recorded_children_and_releases_lease(tmp_path):
    """Terminate the explicit bus-session parent, then await its recorded children."""
    from tools.watch_recording_worker import identity_for_pid
    root = tmp_path / 'checkout'
    (root / 'config').mkdir(parents=True)
    (root / '.git').mkdir()
    (root / 'tools').mkdir()
    (root / 'tools/watch').touch()
    (root / 'config/test-vm.json').write_text(json.dumps({'vms': [
        dict(name='Synthetic-One', id=1, enabled='false', disk_anchor='/unused/one.qcow2')]}))
    lock_path = tmp_path / 'controller.lock'
    owner = lock_path.open('w+b')
    os.chmod(lock_path, 0o600)
    fcntl.flock(owner, fcntl.LOCK_EX)
    control, remote = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    control.settimeout(20)
    with (tmp_path / 'forced-close.log').open('wb') as log:
        process = subprocess.Popen(launch_command(root, remote.fileno(), tmp_path / 'forced.webm',
            owner_fd=owner.fileno()), pass_fds=(owner.fileno(), remote.fileno(), *scratch_descriptors()),
            stdout=log, stderr=log)
    identity = process_identity(process)
    owner.close()
    remote.close()
    pidfds = []
    try:
        ready = json.loads(control.recv(65536))
        assert ready['event'] == 'ready', (ready, (tmp_path / 'forced-close.log').read_text())
        assert {child['role'] for child in ready['processes']} == {'worker', 'compositor', 'encoder'}
        for child in ready['processes']:
            assert identity_for_pid(child['pid']) == (child['pid'], child['start_ticks'])
            pidfds.append(os.pidfd_open(child['pid']))
        with lock_path.open('r+b') as probe:
            with pytest.raises(BlockingIOError):
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            assert process_identity(process) == identity
            process.terminate()
            process.wait(timeout=5)
            pending = set(pidfds)
            deadline = time.monotonic() + 20
            while pending and time.monotonic() < deadline:
                exited, _, _ = select.select(list(pending), [], [], max(0, deadline - time.monotonic()))
                pending.difference_update(exited)
            assert not pending, (tmp_path / 'forced-close.log').read_text()
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        control.close()
        stop_owned(process, identity)
        for descriptor in pidfds:
            if not select.select([descriptor], [], [], 0)[0]:
                try:
                    signal.pidfd_send_signal(descriptor, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        if pidfds:
            deadline = time.monotonic() + 5
            for descriptor in pidfds:
                if not select.select([descriptor], [], [], max(0, deadline - time.monotonic()))[0]:
                    try:
                        signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        for descriptor in pidfds:
            os.close(descriptor)
