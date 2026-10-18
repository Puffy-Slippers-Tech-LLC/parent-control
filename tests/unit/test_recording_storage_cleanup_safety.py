"""Private fixture files only: latest-recording ownership and crash boundaries."""
import json
import os
from pathlib import Path
import socket

import pytest

from tools import recording_storage as storage
from tools import test_storage
from tools import recording_control


@pytest.fixture
def store(tmp_path):
    return storage.Store(root=tmp_path)


def write(recording, data=b'playable fixture'):
    recording.path.write_bytes(data)


def publish(store, category='e2e', case_id=150, names=('onpc-Alpha', 'onpc-Beta'), data=b'playable fixture'):
    with store.begin(category, case_id) as recording:
        write(recording, data)
        return recording.publish(names, validate=lambda path: path.read_bytes().startswith(b'playable'))


def manifest(store, key='e2e-150'):
    return json.loads((store.path / ('.' + key + '.json')).read_text())


def test_shared_kind_and_latest_per_case_survive_vm_set_change(store, tmp_path):
    assert store.path == test_storage.directory('recordings', root=tmp_path)
    assert store.path == tmp_path / 'output/test-runs/recordings'
    previous = publish(store)
    assert previous.name == 'e2e-150-Alpha-Beta.webm'
    other_case = publish(store, case_id=151)
    other_category = publish(store, category='ui')
    unknown = store.path / 'e2e-150-unregistered.webm'
    unknown.write_bytes(b'keep unknown')
    latest = publish(store, names=('onpc-Beta',), data=b'playable latest')
    assert latest.name == 'e2e-150-Beta.webm'
    assert latest.read_bytes() == b'playable latest'
    assert latest.stat().st_mode & 0o777 == 0o600
    assert not previous.exists()
    assert other_case.is_file() and other_category.is_file()
    assert unknown.read_bytes() == b'keep unknown'
    state = manifest(store)
    assert state['provenance']['vm_names'] == ['onpc-Beta']
    assert state['staging'] is state['pending'] is None


def test_privileged_caller_lookup_is_read_only_and_checks_owner(store, tmp_path, monkeypatch):
    owner = store.path.stat().st_uid
    # The maintained unit launcher runs as the ordinary checkout owner.
    assert owner > 0
    before = {path.name: path.stat().st_ino for path in store.path.iterdir()}
    monkeypatch.setattr(test_storage.os, 'geteuid', lambda: 0)
    assert test_storage.recordings_directory(root=tmp_path, caller_uid=owner, create=False) == store.path
    assert {path.name: path.stat().st_ino for path in store.path.iterdir()} == before
    with pytest.raises(ValueError, match='ownership'):
        test_storage.recordings_directory(root=tmp_path, caller_uid=owner + 1, create=False)
    missing = tmp_path / 'missing-checkout'
    with pytest.raises(FileNotFoundError):
        test_storage.recordings_directory(root=missing, caller_uid=owner, create=False)
    assert not missing.exists()


@pytest.mark.parametrize('effective, caller, create', [(1000, 1000, False), (0, 0, False),
                                                      (0, True, False), (0, 1000, True)])
def test_caller_lookup_refuses_writes_invalid_uid_or_nonroot(tmp_path, monkeypatch, effective, caller, create):
    monkeypatch.setattr(test_storage.os, 'geteuid', lambda: effective)
    with pytest.raises(ValueError, match='caller lookup requires'):
        test_storage.recordings_directory(root=tmp_path, caller_uid=caller, create=create)
    assert not (tmp_path / 'output').exists()


def test_same_filename_atomic_replace_and_no_time_or_size_rotation(store):
    previous = publish(store)
    previous_identity = previous.stat().st_ino
    os.utime(previous, (1, 1))
    with store.begin('e2e', 150) as recording:
        write(recording, b'playable replacement' * 1024)
        assert previous.read_bytes() == b'playable fixture'
        latest = recording.publish(('onpc-Alpha', 'onpc-Beta'), validate=lambda _: True)
    assert previous == latest and latest.stat().st_ino != previous_identity
    assert latest.read_bytes() == b'playable replacement' * 1024


@pytest.mark.parametrize('failure', ['exception', 'invalid', 'empty'])
def test_failed_encoder_or_playability_check_preserves_previous(store, failure):
    previous = publish(store)
    before = previous.read_bytes()
    with pytest.raises((RuntimeError, ValueError)):
        with store.begin('e2e', 150) as recording:
            if failure == 'exception':
                write(recording, b'incomplete')
                raise RuntimeError('encoder failed')
            if failure != 'empty':
                write(recording, b'not playable')
            recording.publish(['onpc-Beta'], validate=lambda _: failure == 'empty')
    assert previous.read_bytes() == before
    assert not any(path.name.startswith('.e2e-150-') and path.suffix == '.webm'
                   for path in store.path.iterdir())


def test_same_case_lock_refuses_but_other_case_can_record(store):
    with store.begin('e2e', 150) as first:
        with pytest.raises(ValueError, match='another recorder'):
            store.begin('e2e', 150)
        with store.begin('e2e', 151) as second:
            write(first)
            write(second)
            second.publish(['onpc-Beta'], validate=lambda _: True)
        first.publish(['onpc-Alpha'], validate=lambda _: True)


def test_forwarded_encoder_descriptor_preserves_case_until_descendant_closes(store):
    recording = store.begin('e2e', 150)
    write(recording)
    stage = recording.path
    inherited = os.dup(recording.descriptors()[0])
    recording.close(abort=False)
    try:
        with pytest.raises(ValueError, match='another recorder'):
            store.begin('e2e', 150)
        assert stage.read_bytes() == b'playable fixture'
    finally:
        os.close(inherited)
    with store.begin('e2e', 150):
        assert not stage.exists()


def test_idle_abandoned_stage_is_reclaimed_without_touching_previous_or_unknown(store):
    previous = publish(store)
    abandoned = store.begin('e2e', 150)
    write(abandoned, b'incomplete')
    stage = abandoned.path
    abandoned.close(abort=False)
    unknown = store.path / '.e2e-150-unknown.webm'
    unknown.write_bytes(b'unknown')
    with store.begin('e2e', 150):
        assert not stage.exists()
        assert previous.is_file() and unknown.read_bytes() == b'unknown'


@pytest.mark.parametrize('boundary', ['intent', 'rename', 'current', 'delete', 'finished'])
@pytest.mark.parametrize('same_name', [False, True])
def test_publication_recovers_every_durable_boundary(store, monkeypatch, boundary, same_name):
    previous = publish(store)
    recording = store.begin('e2e', 150)
    write(recording, b'playable newest')
    names = ['onpc-Alpha', 'onpc-Beta'] if same_name else ['onpc-Beta']
    if same_name and boundary == 'delete':
        recording.close()
        return
    original_save, original_rename, original_remove = recording._save, recording._publish_rename, recording._remove
    saves = 0
    with monkeypatch.context() as fault:
        def save():
            nonlocal saves
            original_save()
            saves += 1
            if (boundary, saves) in [('intent', 1), ('current', 2), ('finished', 3)]:
                raise KeyboardInterrupt

        def rename(source, dest, **kwargs):
            original_rename(source, dest, **kwargs)
            if boundary == 'rename':
                raise KeyboardInterrupt

        def remove(record):
            original_remove(record)
            if boundary == 'delete':
                raise KeyboardInterrupt

        fault.setattr(recording, '_save', save)
        fault.setattr(recording, '_publish_rename', rename)
        fault.setattr(recording, '_remove', remove)
        with pytest.raises(KeyboardInterrupt):
            recording.publish(names, validate=lambda _: True)
    recording.close(abort=False)
    with store.begin('e2e', 150):
        latest = store.path / ('e2e-150-' + '-'.join(n.removeprefix('onpc-') for n in names) + '.webm')
        assert latest.read_bytes() == b'playable newest'
        assert previous == latest or not previous.exists()
        state = manifest(store)
        assert state['current']['name'] == latest.name
        assert state['pending'] is None


@pytest.mark.parametrize('fault', ['symlink', 'hardlink', 'mode', 'replacement'])
def test_stage_refusal_preserves_previous_and_replaced_entry(store, fault):
    previous = publish(store)
    recording = store.begin('e2e', 150)
    write(recording)
    path = recording.path
    if fault == 'symlink':
        path.unlink()
        path.symlink_to(previous)
    elif fault == 'hardlink':
        os.link(path, store.path / 'unowned-hardlink')
    elif fault == 'mode':
        path.chmod(0o644)
    else:
        path.rename(path.with_suffix('.held'))
        path.write_bytes(b'replaced')
        path.chmod(0o600)
    with pytest.raises((ValueError, OSError)):
        recording.publish(['onpc-Beta'], validate=lambda _: True)
    with pytest.raises((ValueError, OSError)):
        recording.close()
    assert previous.read_bytes() == b'playable fixture'
    assert path.exists()


def test_unknown_destination_is_not_overwritten_and_old_recording_survives(store):
    previous = publish(store)
    unknown = store.path / 'e2e-150-Beta.webm'
    unknown.write_bytes(b'unknown')
    with pytest.raises(ValueError, match='unowned destination'):
        with store.begin('e2e', 150) as recording:
            write(recording)
            recording.publish(['onpc-Beta'], validate=lambda _: True)
    assert previous.read_bytes() == b'playable fixture'
    assert unknown.read_bytes() == b'unknown'


def test_destination_appearing_after_preflight_is_never_overwritten(store, monkeypatch):
    previous = publish(store)
    recording = store.begin('e2e', 150)
    write(recording)
    rename = recording._publish_rename
    target = store.path / 'e2e-150-Beta.webm'
    def racing_rename(source, destination, **kwargs):
        target.write_bytes(b'unknown late arrival')
        return rename(source, destination, **kwargs)
    monkeypatch.setattr(recording, '_publish_rename', racing_rename)
    with pytest.raises(FileExistsError):
        recording.publish(['onpc-Beta'], validate=lambda _: True)
    recording.close(abort=False)
    assert target.read_bytes() == b'unknown late arrival'
    assert previous.read_bytes() == b'playable fixture'


@pytest.mark.parametrize('fault', ['bytes', 'replacement', 'symlink', 'hardlink'])
def test_superseded_recording_changed_identity_or_bytes_blocks_cleanup(store, fault):
    previous = publish(store)
    recording = store.begin('e2e', 150)
    write(recording, b'playable newest')
    if fault == 'bytes':
        previous.write_bytes(b'changed bytes')
    elif fault == 'replacement':
        previous.rename(previous.with_suffix('.held'))
        previous.write_bytes(b'unknown replacement')
        previous.chmod(0o600)
    elif fault == 'symlink':
        previous.rename(previous.with_suffix('.held'))
        previous.symlink_to(previous.with_suffix('.held'))
    else:
        os.link(previous, store.path / 'unowned-link')
    with pytest.raises((ValueError, OSError)):
        recording.publish(['onpc-Beta'], validate=lambda _: True)
    recording.close(abort=False)
    assert previous.exists()
    assert not (store.path / 'e2e-150-Beta.webm').exists()


def test_changed_candidate_after_intent_is_preserved_and_previous_retained(store, monkeypatch):
    previous = publish(store)
    recording = store.begin('e2e', 150)
    write(recording)
    save = recording._save
    def interrupted_save():
        save()
        raise KeyboardInterrupt
    with monkeypatch.context() as fault:
        fault.setattr(recording, '_save', interrupted_save)
        with pytest.raises(KeyboardInterrupt):
            recording.publish(['onpc-Beta'], validate=lambda _: True)
    stage = recording.path
    recording.close(abort=False)
    stage.write_bytes(b'changed after verification')
    with pytest.raises(ValueError, match='bytes changed'):
        store.begin('e2e', 150)
    assert stage.exists() and previous.is_file()


@pytest.mark.parametrize('entry', ['manifest', 'lock', 'root'])
def test_replaced_management_entries_refuse_mutation(store, entry):
    previous = publish(store)
    recording = store.begin('e2e', 150)
    write(recording)
    path = (store.path if entry == 'root' else
            store.path / ('.e2e-150.json' if entry == 'manifest' else '.e2e-150.lock'))
    held = path.with_name(path.name + '-held')
    path.rename(held)
    if entry == 'root':
        path.mkdir(mode=0o700)
    else:
        path.write_text('unknown')
        path.chmod(0o600)
    with pytest.raises((ValueError, OSError)):
        recording.publish(['onpc-Beta'], validate=lambda _: True)
    recording.close(abort=False)
    assert (held / previous.name).exists() if entry == 'root' else previous.exists()


@pytest.mark.parametrize('category, case_id', [('../e2e', 150), ('e2e', '150'), ('e2e', True), ('e2e', 0)])
def test_invalid_case_identity_refuses_without_creating_entries(store, category, case_id):
    with pytest.raises(ValueError):
        store.begin(category, case_id)
    assert not list(store.path.iterdir())


@pytest.mark.parametrize('names', [[], ['../outside'], ['onpc-'], ['onpc-A', 'A'], ['A', 'A']])
def test_invalid_vm_labels_never_replace_previous(store, names):
    previous = publish(store)
    with store.begin('e2e', 150) as recording:
        write(recording)
        with pytest.raises(ValueError):
            recording.publish(names, validate=lambda _: True)
    assert previous.is_file()


@pytest.fixture
def controller_runtime():
    # A private AF_UNIX socket uses the shared short-path exception, with no
    # server thread, subprocess, guest, display or external service.
    with test_storage.runtime_directory(prefix='onpc-record-control-') as runtime:
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
            path = runtime / 'control'
            peer.bind(str(path))
            yield dict(socket=str(path), nonce='a' * 48)


def test_control_publication_live_reader_and_inactive_close(tmp_path, controller_runtime):
    assert recording_control.endpoint(tmp_path) is None
    publication = recording_control.Publication(tmp_path)
    assert recording_control.endpoint(tmp_path) is None
    publication.publish(controller_runtime)
    assert recording_control.endpoint(tmp_path) == controller_runtime
    state = json.loads((publication.directory / 'control.json').read_text())
    assert state['owner']['pid'] == os.getpid() and state['owner']['start_ticks'] > 0
    assert len(state['run_id']) == 32 and state['active'] is True
    publication.close()
    assert publication.descriptors() == ()
    assert recording_control.endpoint(tmp_path) is None
    state = json.loads((publication.directory / 'control.json').read_text())
    assert state['active'] is False and state['endpoint'] is state['runtime'] is None


def test_control_inherited_lease_excludes_successor_until_child_exits(tmp_path):
    publication = recording_control.Publication(tmp_path)
    inherited = os.dup(publication.descriptors()[0])
    publication.close()
    try:
        with pytest.raises(ValueError, match='another controller'):
            recording_control.Publication(tmp_path)
    finally:
        os.close(inherited)
    recording_control.Publication(tmp_path).close()


def test_stale_control_reader_refuses_and_exclusive_successor_recovers(tmp_path, controller_runtime, monkeypatch):
    publication = recording_control.Publication(tmp_path)
    publication.publish(controller_runtime)
    old_state = json.loads((publication.directory / 'control.json').read_text())
    # Model abrupt controller exit: leave the durable active receipt intact.
    publication._release()
    original_process = recording_control._process
    monkeypatch.setattr(recording_control, '_alive', lambda _: False)
    with pytest.raises(ValueError, match='stale active owner'):
        recording_control.endpoint(tmp_path)
    next_publication = recording_control.Publication(tmp_path)
    state = json.loads((next_publication.directory / 'control.json').read_text())
    assert state['run_id'] != old_state['run_id'] and state['active'] is False
    assert recording_control.endpoint(tmp_path) is None
    assert recording_control._process(os.getpid()) == original_process(os.getpid())
    next_publication.close()


def test_active_live_owner_without_lease_is_not_adopted(tmp_path, controller_runtime):
    publication = recording_control.Publication(tmp_path)
    publication.publish(controller_runtime)
    publication._release()
    with pytest.raises(ValueError, match='lease is absent'):
        recording_control.endpoint(tmp_path)
    with pytest.raises(ValueError, match='live owner'):
        recording_control.Publication(tmp_path)


@pytest.mark.parametrize('kind', ['incomplete', 'symlink', 'hardlink', 'mode', 'replacement'])
def test_control_unknown_or_replaced_journal_is_preserved(tmp_path, controller_runtime, kind):
    publication = recording_control.Publication(tmp_path)
    publication.publish(controller_runtime)
    manifest_path = publication.directory / 'control.json'
    if kind == 'incomplete':
        manifest_path.write_text('{"active": true}')
    elif kind == 'symlink':
        manifest_path.rename(manifest_path.with_suffix('.held'))
        manifest_path.symlink_to(manifest_path.with_suffix('.held'))
    elif kind == 'hardlink':
        os.link(manifest_path, publication.directory / 'unknown-link')
    elif kind == 'mode':
        manifest_path.chmod(0o644)
    else:
        data = manifest_path.read_bytes()
        manifest_path.rename(manifest_path.with_suffix('.held'))
        manifest_path.write_bytes(data)
        manifest_path.chmod(0o600)
    with pytest.raises((OSError, ValueError)):
        publication.close()
    assert manifest_path.exists()
    with pytest.raises((OSError, ValueError)):
        recording_control.Publication(tmp_path)
    assert manifest_path.exists()


@pytest.mark.parametrize('entry', ['lock', 'root'])
def test_control_changed_lock_or_root_preserves_entries(tmp_path, controller_runtime, entry):
    publication = recording_control.Publication(tmp_path)
    publication.publish(controller_runtime)
    path = publication.directory if entry == 'root' else publication.directory / '.controller.lock'
    held = path.with_name(path.name + '-held')
    path.rename(held)
    if entry == 'root':
        path.mkdir(mode=0o700)
    else:
        path.write_text('unknown')
        path.chmod(0o600)
    with pytest.raises((OSError, ValueError)):
        publication.close()
    assert held.exists() and path.exists()


@pytest.mark.parametrize('fault', ['socket-symlink', 'socket-replacement', 'directory-mode', 'directory-symlink'])
def test_control_reader_rejects_changed_runtime(tmp_path, controller_runtime, fault):
    publication = recording_control.Publication(tmp_path)
    publication.publish(controller_runtime)
    path = Path(controller_runtime['socket'])
    extra = None
    held = None
    if fault == 'socket-symlink':
        path.rename(path.with_name('held'))
        path.symlink_to(path.with_name('held'))
    elif fault == 'socket-replacement':
        path.rename(path.with_name('held'))
        extra = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        extra.bind(str(path))
    elif fault == 'directory-mode':
        path.parent.chmod(0o755)
    else:
        held = path.parent.with_name(path.parent.name + '-held')
        path.parent.rename(held)
        path.parent.symlink_to(held, target_is_directory=True)
    try:
        with pytest.raises((OSError, ValueError)):
            recording_control.endpoint(tmp_path)
    finally:
        publication.close()
        if extra is not None:
            extra.close()
        if fault == 'socket-symlink':
            path.unlink()
            path.with_name('held').rename(path)
        elif fault == 'directory-mode':
            path.parent.chmod(0o700)
        elif held is not None:
            path.parent.unlink()
            held.rename(path.parent)


def test_control_root_reader_uses_only_authenticated_positive_caller(tmp_path, controller_runtime, monkeypatch):
    publication = recording_control.Publication(tmp_path)
    publication.publish(controller_runtime)
    uid = os.getuid()
    with monkeypatch.context() as privileged:
        privileged.setattr(recording_control.os, 'geteuid', lambda: 0)
        privileged.setenv('PKEXEC_UID', str(uid))
        assert recording_control.endpoint(tmp_path) == controller_runtime
        privileged.setenv('PKEXEC_UID', '0')
        with pytest.raises(ValueError, match='authenticated caller'):
            recording_control.endpoint(tmp_path)
    publication.close()


@pytest.mark.parametrize('endpoint', [dict(socket='/tmp/unowned/control', nonce='a' * 48),
                                     dict(socket='/tmp/onpc-record-control-fake/control', nonce='short'),
                                     dict(socket='/tmp/onpc-record-control-fake/../control', nonce='a' * 48)])
def test_control_rejects_unmanaged_socket_paths(tmp_path, endpoint):
    publication = recording_control.Publication(tmp_path)
    try:
        with pytest.raises(ValueError):
            publication.publish(endpoint)
        assert recording_control.endpoint(tmp_path) is None
    finally:
        publication.close()


@pytest.mark.parametrize('operation', ['publish', 'close'])
def test_control_atomic_receipt_interruption_recovers_inactive_or_stale(tmp_path, controller_runtime, monkeypatch, operation):
    publication = recording_control.Publication(tmp_path)
    if operation == 'close':
        publication.publish(controller_runtime)
    replace = os.replace
    with monkeypatch.context() as fault:
        def interrupted(source, destination, **kwargs):
            replace(source, destination, **kwargs)
            if destination == 'control.json':
                raise KeyboardInterrupt
        fault.setattr(recording_control.os, 'replace', interrupted)
        with pytest.raises(KeyboardInterrupt):
            if operation == 'publish':
                publication.publish(controller_runtime)
            else:
                publication.close()
    publication._release()
    monkeypatch.setattr(recording_control, '_alive', lambda _: False)
    successor = recording_control.Publication(tmp_path)
    assert recording_control.endpoint(tmp_path) is None
    successor.close()


def test_control_publish_signal_after_rename_can_close_without_abandoning_live_owner(
        tmp_path, controller_runtime, monkeypatch):
    publication = recording_control.Publication(tmp_path)
    replace = os.replace
    with monkeypatch.context() as fault:
        def interrupted(source, destination, **kwargs):
            replace(source, destination, **kwargs)
            raise KeyboardInterrupt
        fault.setattr(recording_control.os, 'replace', interrupted)
        with pytest.raises(KeyboardInterrupt):
            publication.publish(controller_runtime)
    publication.close()
    assert recording_control.endpoint(tmp_path) is None
    recording_control.Publication(tmp_path).close()


@pytest.fixture
def legacy_recordings(tmp_path, monkeypatch):
    legacy = test_storage._directory('recordings', root=tmp_path, create=True,
                                     owner='host', uid=os.geteuid())
    with monkeypatch.context() as old_route:
        old_route.setattr(test_storage, 'recordings_directory', lambda **_: legacy)
        store = storage.Store(root=tmp_path)
        previous = publish(store)
        recording_control.Publication(tmp_path).close()
    return legacy, previous


def test_legacy_directory_moves_intact_and_preserves_publication_identities(tmp_path, legacy_recordings):
    legacy, previous = legacy_recordings
    root_inode, video_inode = legacy.stat().st_ino, previous.stat().st_ino
    before = {path.name: path.read_bytes() for path in legacy.iterdir()}
    target = test_storage.recordings_directory(root=tmp_path)
    assert target == tmp_path / 'output/test-runs/recordings'
    assert not legacy.exists() and target.stat().st_ino == root_inode
    assert {path.name: path.read_bytes() for path in target.iterdir()} == before
    assert (target / previous.name).stat().st_ino == video_inode
    assert recording_control.endpoint(tmp_path) is None
    recording_control.Publication(tmp_path).close()
    latest = publish(storage.Store(root=tmp_path), names=('onpc-Beta',), data=b'playable after move')
    assert latest.read_bytes() == b'playable after move'
    assert not (target / previous.name).exists()


@pytest.mark.parametrize('owner', ['controller', 'case'])
def test_legacy_move_refuses_live_writer_without_creating_destination(
        tmp_path, legacy_recordings, monkeypatch, owner):
    legacy, previous = legacy_recordings
    with monkeypatch.context() as old_route:
        old_route.setattr(test_storage, 'recordings_directory', lambda **_: legacy)
        held = (recording_control.Publication(tmp_path) if owner == 'controller'
                else storage.Store(root=tmp_path).begin('e2e', 150))
    try:
        with pytest.raises(ValueError, match='recorder is active'):
            test_storage.recordings_directory(root=tmp_path)
        assert previous.is_file() and not (tmp_path / 'output/test-runs/recordings').exists()
    finally:
        held.close()


@pytest.mark.parametrize('conflict', ['destination', 'journal', 'lock'])
def test_legacy_move_preserves_conflicting_or_unknown_entries(tmp_path, legacy_recordings, conflict):
    legacy, previous = legacy_recordings
    target = tmp_path / 'output/test-runs/recordings'
    if conflict == 'destination':
        target.mkdir(mode=0o700)
        (target / 'unknown').write_bytes(b'preserve destination')
    else:
        path = legacy / ('control.json' if conflict == 'journal' else '.controller.lock')
        path.rename(path.with_name(path.name + '.held'))
        path.write_text('{}')
        path.chmod(0o600)
    with pytest.raises((OSError, ValueError)):
        test_storage.recordings_directory(root=tmp_path)
    assert legacy.is_dir() and previous.read_bytes() == b'playable fixture'
    if conflict == 'destination':
        assert (target / 'unknown').read_bytes() == b'preserve destination'


def test_root_caller_lookup_never_moves_legacy_directory(tmp_path, legacy_recordings, monkeypatch):
    legacy, previous = legacy_recordings
    uid = os.getuid()
    monkeypatch.setattr(test_storage.os, 'geteuid', lambda: 0)
    with pytest.raises(FileNotFoundError):
        test_storage.recordings_directory(root=tmp_path, caller_uid=uid, create=False)
    with pytest.raises(ValueError, match='unprivileged owner'):
        test_storage.recordings_directory(root=tmp_path)
    assert previous.is_file() and legacy.is_dir()
