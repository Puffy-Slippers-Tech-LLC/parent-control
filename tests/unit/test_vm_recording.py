"""Shared recording boundaries use private metadata and process-local doubles."""
import json
import subprocess
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path

import pytest

from tools import vm_recording as recording


@pytest.fixture(autouse=True)
def isolated_tokens(monkeypatch):
    monkeypatch.setattr(recording, '_capture_tokens', defaultdict(dict))


def test_concurrent_same_case_and_lifecycle_phases_share_one_window():
    timeline = recording.Timeline()
    timeline.event('Ubuntu', 'e2e', 150, 'started', 10)
    timeline.event('Fedora', 'e2e', 150, 'started', 12)
    timeline.event('Ubuntu', 'e2e', 150, 'finished', 20)
    timeline.event('Fedora', 'e2e', 150, 'failure', 22)
    timeline.event('Fedora', 'e2e', 150, 'finished', 25)
    timeline.finish_vm('Ubuntu', 30)
    timeline.finish_vm('Fedora', 35)
    assert len(timeline.windows) == 1
    window = timeline.windows['e2e', 150]
    assert (window.start_ns, window.end_ns) == (10, 35)
    assert window.failed and not window.interrupted
    assert window.vms == {'Ubuntu', 'Fedora'}


def test_different_concurrent_cases_remain_distinct_and_interruption_retained():
    timeline = recording.Timeline()
    timeline.event('Ubuntu', 'system', 3, 'started', 10)
    timeline.event('Fedora', 'e2e', 3, 'started', 12)
    timeline.event('Ubuntu', 'system', 3, 'finished', 20)
    timeline.event('Ubuntu', 'system', 3, 'started', 30)
    timeline.close(40)
    assert len(timeline.windows) == 2
    assert all(window.interrupted for window in timeline.windows.values())
    assert timeline.windows['system', 3].start_ns == 10


def test_lost_completion_is_retained_and_vm_cleanup_boundary_is_idempotent():
    timeline = recording.Timeline()
    timeline.event('Ubuntu', 'e2e', 1, 'prepared', 5)
    timeline.event('Ubuntu', 'e2e', 1, 'started', 10)
    timeline.event('Ubuntu', 'e2e', 2, 'started', 20)
    assert timeline.windows['e2e', 1].interrupted
    assert timeline.windows['e2e', 1].end_ns == 20
    timeline.finish_vm('Ubuntu', 30)
    timeline.finish_vm('Ubuntu', 50)
    assert timeline.windows['e2e', 2].end_ns == 30


@pytest.mark.parametrize('reply', [
    {'event': 'sealed', 'token': 'old', 'sealed': True},
    {'event': 'sealed', 'token': 'new', 'sealed': False},
    {'event': 'ended', 'token': 'new', 'sealed': True},
    {'event': 'sealed', 'token': 'new', 'sealed': 'true'}])
def test_mismatched_secret_ack_permanently_revokes_channel(reply):
    session = recording.Session()
    session.control = Mock()
    session.control.recv.return_value = json.dumps(reply).encode()
    with pytest.raises(RuntimeError, match='mismatched'):
        session.exchange(dict(op='seal', token='new', sealed=True))
    with pytest.raises(RuntimeError, match='channel failed'):
        session.exchange(dict(op='seal', token='new', sealed=True))
    assert session.control.sendall.call_count == 1


def test_large_capture_span_summary_is_reassembled():
    session = recording.Session()
    session.control = Mock()
    span = dict(vm='Ubuntu', start_ns=1, end_ns=2)
    session.control.recv.side_effect = [
        json.dumps(dict(event='vm-spans', items=[span])).encode(),
        json.dumps(dict(event='closed', vm_spans=[])).encode()]
    assert session.exchange(dict(op='close'))['vm_spans'] == [span]


@pytest.mark.parametrize('category,identifier,kind,at_ns', [
    ('unit', 1, 'started', 1), ('e2e', True, 'started', 1),
    ('system', 0, 'started', 1), ('e2e', 1, 'unknown', 1),
    ('e2e', 1, 'started', -1)])
def test_untrusted_case_events_refuse(category, identifier, kind, at_ns):
    with pytest.raises(ValueError):
        recording.Timeline().event('Ubuntu', category, identifier, kind, at_ns)


def test_seal_ack_precedes_secret_and_release_follows_success(monkeypatch):
    calls = []
    monkeypatch.setattr(recording, 'protected_endpoint', lambda _: {'test': True})
    monkeypatch.setattr(recording, 'request', lambda endpoint, value: calls.append(value))
    with recording.protect_capture():
        assert calls[-1]['sealed'] is True
        calls.append({'secret': 'delivered through existing protected API'})
    assert [value.get('sealed') for value in calls] == [True, None, False]
    assert calls[0]['token'] == calls[-1]['token']


def test_uncertain_secret_stays_sealed(monkeypatch):
    calls = []
    monkeypatch.setattr(recording, 'protected_endpoint', lambda _: {})
    monkeypatch.setattr(recording, 'request', lambda endpoint, value: calls.append(value))
    with pytest.raises(RuntimeError), recording.protect_capture():
        raise RuntimeError('uncertain delivery')
    assert len(calls) == 1 and calls[0]['sealed'] is True


def test_no_recording_does_not_require_watch_or_control_socket(monkeypatch):
    monkeypatch.setattr(recording, 'protected_endpoint', lambda _: None)
    monkeypatch.setattr(recording, 'request', lambda *_: pytest.fail('unexpected control request'))
    with recording.protect_capture():
        pass


def test_real_public_case_ids_are_resolved_without_changing_nodeids():
    root = Path(__file__).resolve().parents[2]
    assert recording.case_identity(root, 'e2e', {'nodeid': 'E2E-001/gdm-observation'})[0] == 1
    first = recording.case_identity(root, 'system', {'nodeid': 'installed::test_installed_package'})
    second = recording.case_identity(root, 'system', {'nodeid': 'rebooted::test_installed_package'})
    assert first == second and type(first[0]) is int


def test_pytest_environment_does_not_leak_parent_recording_control(monkeypatch):
    from tools import test_launcher
    monkeypatch.setenv(recording.VARIABLE, json.dumps({'socket': 'private', 'nonce': 'test'}))
    root = Path(__file__).resolve().parents[2]
    assert recording.VARIABLE in test_launcher.environment(root)
    assert recording.VARIABLE not in test_launcher.test_environment(root)


def test_session_pins_runner_queue_before_starting_renderer(monkeypatch, tmp_path):
    import recording_control
    import recording_storage
    from vm_selection import vm_config
    import vm_selection
    registry = {'Owned': SimpleNamespace(id=2), 'Other': SimpleNamespace(id=1)}
    monkeypatch.setattr(vm_config, 'registry', lambda _: registry)
    monkeypatch.setattr(vm_selection, 'execution_binding', lambda: {'vms': ['Owned']})
    # Stop before any process or storage allocation; the resolved queue must
    # already exclude unrelated configured VMs when capture startup begins.
    monkeypatch.setattr(recording_storage, 'Store', lambda **_: object())
    monkeypatch.setattr(recording_control, 'Publication', Mock(side_effect=RuntimeError('startup boundary')))
    session = recording.Session(tmp_path)
    with pytest.raises(RuntimeError, match='startup boundary'):
        session.start()
    assert session.configured == {'Owned': registry['Owned']}


def test_keyframe_boundaries_use_sorted_packet_presentation_times(monkeypatch, tmp_path):
    probe = Mock(return_value=SimpleNamespace(stdout=json.dumps({'packets': [
        dict(pts_time='3.0', dts_time='0.0', flags='K_'),
        dict(pts_time='1.0', dts_time='1.0', flags='__'),
        dict(pts_time='0.0', dts_time='2.0', flags='K_'),
        dict(pts_time='2.0', dts_time='3.0', flags='K_')]})))
    monkeypatch.setattr(recording.subprocess, 'run', probe)
    path = tmp_path / 'master.webm'
    assert recording.keyframes(path) == [0., 2., 3.]
    command = probe.call_args.args[0]
    assert command == ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                       '-show_entries', 'packet=pts_time,flags', '-of', 'json', str(path)]
    assert probe.call_args.kwargs['timeout'] == 120
    assert probe.call_args.kwargs['check'] is True


@pytest.mark.parametrize('timestamp', [{}, {'pts_time': None}, {'pts_time': 'bad'},
    {'pts_time': 'NaN'}, {'pts_time': 'inf'}, {'pts_time': '-0.2'}])
def test_invalid_keyframe_timestamp_refuses(monkeypatch, tmp_path, timestamp):
    monkeypatch.setattr(recording.subprocess, 'run', Mock(return_value=SimpleNamespace(
        stdout=json.dumps({'packets': [dict(timestamp, flags='K_')]}))))
    with pytest.raises(RuntimeError, match='invalid keyframe timestamp'):
        recording.keyframes(tmp_path / 'master.webm')


@pytest.mark.parametrize('packets', [[], [dict(pts_time='0.0', flags='__')]])
def test_capture_without_keyframe_packets_refuses(monkeypatch, tmp_path, packets):
    monkeypatch.setattr(recording.subprocess, 'run', Mock(return_value=SimpleNamespace(
        stdout=json.dumps({'packets': packets}))))
    with pytest.raises(RuntimeError, match='no keyframe packets'):
        recording.keyframes(tmp_path / 'master.webm')


def test_late_decode_failure_cannot_replace_previous_recording(tmp_path):
    from tools.recording_storage import Store
    valid = tmp_path / 'valid.webm'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
        'color=c=red:s=32x24:r=5', '-frames:v', '3', '-c:v', 'libvpx-vp9',
        '-threads', '1', '-g', '1', str(valid)], check=True, timeout=15)
    assert recording.keyframes(valid) == [0., .2, .4]
    assert recording.playable(valid)
    packets = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_packets', '-show_data', '-show_entries', 'packet=pos,size,data', '-of', 'json', str(valid)],
        capture_output=True, check=True, timeout=15).stdout)['packets']
    broken = bytearray(valid.read_bytes())
    payload = bytes.fromhex(''.join(line.partition(':')[2].split('  ')[0]
                                   for line in packets[1]['data'].splitlines() if ':' in line))
    size = int(packets[1]['size'])
    assert len(payload) == size
    # WebM packet positions point to the enclosing block, before its payload.
    offset = broken.find(payload, int(packets[1]['pos']))
    assert offset >= int(packets[1]['pos'])
    broken[offset:offset + size] = b'\0' * size
    store = Store(root=tmp_path)
    with store.begin('e2e', 1) as clip:
        clip.path.write_bytes(valid.read_bytes())
        previous = clip.publish(['VM'], validate=recording.playable)
    with pytest.raises(subprocess.CalledProcessError):
        with store.begin('e2e', 1) as clip:
            clip.path.write_bytes(broken)
            # The former one-frame check accepts this exact damaged candidate.
            subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(clip.path),
                '-frames:v', '1', '-f', 'null', '-'], check=True, capture_output=True, timeout=15)
            clip.publish(['Other-VM'], validate=recording.playable)
    assert previous.read_bytes() == valid.read_bytes()
    assert list(store.path.glob('e2e-1-*.webm')) == [previous]
