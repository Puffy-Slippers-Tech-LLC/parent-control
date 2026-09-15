"""Bounded repetition and refusal of foreign, active or recovery-owned storage."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import json
import os
from pathlib import Path
import runpy
import shutil
import stat
import tempfile
from types import SimpleNamespace
import uuid

import pytest

from tools import test_retention as retention


def allocated(parent, name):
    path = parent / name
    path.mkdir(mode=0o700)
    (path / 'test.log').write_bytes(b'evidence' * 128)
    retention.retain(path)
    return path


def advance_to_expiry(store):
    for _ in range(2):
        with store.session():
            pass


@pytest.fixture
def repetition_tree():
    # Only the bounded repetition workload uses /tmp (tmpfs on the host).
    # Keep real filesystem calls; disk-backed sync/error checks use tmp_path.
    with tempfile.TemporaryDirectory(prefix='onpc-retention-stress-', dir='/tmp') as root:
        yield Path(root)


@pytest.mark.parametrize('outcome', ['pass', 'failure', 'interrupt'])
def test_one_hundred_runs_have_constant_retained_size(repetition_tree, outcome):
    store = retention.Store(repetition_tree / 'state')
    foreign = repetition_tree / 'onpc-unregistered'
    foreign.mkdir()
    (foreign / 'keep').write_text('not owned by this runner')
    sizes = []
    previous = []
    for number in range(100):
        try:
            with store.session():
                if len(previous) == 3:
                    assert all(not path.exists() for path in previous.pop(0))
                assert all(path.exists() for group in previous for path in group)
                previous.append([allocated(repetition_tree, f'run-{number}-{kind}')
                                 for kind in ('report', 'build-a', 'build-b', 'ui', 'vm')])
                # Producers may independently discard passing render output.
                disposable = allocated(repetition_tree, f'render-{number}')
                # Fail before another iteration if a regression grows this
                # shared-filesystem footprint. Includes journals and sentinels.
                entries = list(repetition_tree.rglob('*'))
                assert len(entries) < 64
                assert sum(p.stat().st_size for p in entries if p.is_file()) < 256 * 1024
                shutil.rmtree(disposable)
                if outcome == 'failure':
                    raise ValueError('assertion failed')
                if outcome == 'interrupt':
                    raise KeyboardInterrupt
        except (ValueError, KeyboardInterrupt):
            if outcome == 'pass':
                raise
        sizes.append(sum(p.stat().st_size for group in previous for path in group for p in path.iterdir()))
        assert len(list(repetition_tree.glob('run-*'))) == 5 * min(number + 1, 3)
        assert (foreign / 'keep').read_text() == 'not owned by this runner'
    assert len(set(sizes[2:])) == 1
    state = json.loads((store.path / 'current.json').read_text())
    assert len(state['paths']) == 6
    assert len(state['history']) == 2
    assert all(len(entry['paths']) == 6 for entry in state['history'])


def test_same_run_keeps_all_vm_categories_until_fourth_run(tmp_path):
    store = retention.Store(tmp_path / 'state')
    run = uuid.uuid4().hex
    for index in range(4):
        with store.session(run=run):
            allocated(tmp_path, f'category-{index}')
            assert len(list(tmp_path.glob('category-*'))) == index + 1
    advance_to_expiry(store)
    assert len(list(tmp_path.glob('category-*'))) == 4
    with store.session():
        assert not list(tmp_path.glob('category-*'))


def test_active_owner_is_not_rotated(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'active')
        with pytest.raises(ValueError, match='another owner'):
            with retention.Store(store.path).session():
                pytest.fail('competing owner admitted')
        assert path.exists()


def test_parallel_writers_do_not_lose_allocations(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        with ThreadPoolExecutor(max_workers=4) as pool:
            paths = list(pool.map(lambda number: allocated(tmp_path, f'worker-{number}'), range(30)))
    advance_to_expiry(store)
    with store.session():
        assert all(not path.exists() for path in paths)


@pytest.mark.parametrize('kind', ['symlink', 'directory'])
def test_replaced_allocation_is_preserved_and_refused(tmp_path, kind):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'owned')
    path.rename(tmp_path / 'original')
    if kind == 'symlink':
        path.symlink_to(tmp_path / 'original', target_is_directory=True)
    else:
        path.mkdir(mode=0o700)
        (path / 'keep').write_text('replacement')
    with pytest.raises((ValueError, OSError)):
        with store.session():
            pytest.fail('replaced allocation accepted')
    assert (tmp_path / 'original/test.log').exists()
    assert path.exists()


def test_nested_symlink_never_deletes_its_target(tmp_path):
    store = retention.Store(tmp_path / 'state')
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'keep').write_text('foreign')
    with store.session():
        path = allocated(tmp_path, 'owned')
        (path / 'link').symlink_to(outside, target_is_directory=True)
        os.link(outside / 'keep', path / 'hardlink')
    advance_to_expiry(store)
    with store.session():
        assert not path.exists()
        assert (outside / 'keep').read_text() == 'foreign'


def test_unfinished_journal_stops_repetition_before_allocating(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'recovery')
    journal = store.path / 'current.json'
    state = json.loads(journal.read_text())
    state['finished'] = False
    journal.write_text(json.dumps(state))
    for _ in range(5):
        with pytest.raises(ValueError, match='previous owner did not finish'):
            with store.session():
                pytest.fail('unfinished owner bypassed')
        assert path.exists()
    assert len(list(tmp_path.iterdir())) == 2


def test_recovery_pins_entire_unfinished_journal_outside_rotation(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        older = allocated(tmp_path, 'older')
    with store.session():
        interrupted = allocated(tmp_path, 'interrupted')
    journal = store.path / 'current.json'
    state = json.loads(journal.read_text())
    state['finished'] = False
    journal.write_text(json.dumps(state))
    for _ in range(5):
        with store.session(recover=lambda candidate: candidate == state):
            pass
    archived = store.path / f'interrupted-{state["run"]}.json'
    assert json.loads(archived.read_text()) == state
    assert older.exists() and interrupted.exists()


def test_recovery_callback_cannot_override_cleanup_failure(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'unsafe')
        retention.preserve_for_recovery()
    with pytest.raises(ValueError, match='previous owner did not finish'):
        with store.session(recover=lambda _: pytest.fail('cleanup marker bypassed')):
            pass
    assert path.exists()
    assert not list(store.path.glob('interrupted-*.json'))


def test_failed_recovery_guard_never_rotates_or_marks_finished(tmp_path):
    store = retention.Store(tmp_path / 'state')
    def refuse():
        raise ValueError('recovery unfinished')
    with store.session():
        path = allocated(tmp_path, 'old')
    with pytest.raises(ValueError, match='recovery unfinished'):
        with store.session(guard=refuse):
            pytest.fail('recovery guard bypassed')
    assert path.exists()
    calls = []
    def fail_on_exit():
        calls.append(1)
        if len(calls) == 2:
            refuse()
    with pytest.raises(ValueError, match='recovery unfinished'):
        with store.session(guard=fail_on_exit):
            allocated(tmp_path, 'new')
    assert not json.loads((store.path / 'current.json').read_text())['finished']


def test_fixture_cleanup_failure_pins_evidence_after_controller_exit(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'unsafe-fixture')
        retention.preserve_for_recovery()
    with pytest.raises(ValueError, match='previous owner did not finish'):
        with store.session():
            pytest.fail('unproven fixture cleanup bypassed')
    assert path.exists()


def test_allocation_registers_before_unmasking_interrupts(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    calls = []
    original = retention.retain
    def registered(path, **options):
        calls.append('register')
        return original(path, **options)
    def mask(action, signals):
        calls.append('block' if action == retention.signal.SIG_BLOCK else 'restore')
        return set()
    monkeypatch.setattr(retention, 'retain', registered)
    monkeypatch.setattr(retention.signal, 'pthread_sigmask', mask)
    with store.session():
        result = retention.allocate(tempfile.mkdtemp, prefix='allocation-', dir=tmp_path)
        assert calls == ['block', 'register', 'restore']
    advance_to_expiry(store)
    with store.session():
        assert not Path(result).exists()


def test_registration_failure_removes_only_the_new_empty_allocation(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    def broken(path, **options):
        raise OSError('journal unavailable')
    with store.session():
        monkeypatch.setattr(retention, 'retain', broken)
        with pytest.raises(OSError, match='journal unavailable'):
            retention.allocate(tempfile.mkdtemp, prefix='allocation-', dir=tmp_path)
        assert not list(tmp_path.glob('allocation-*'))


@pytest.mark.parametrize('fault', [None, 'file-sync', 'replace', 'directory-sync'])
def test_registration_syncs_before_return_and_preserves_evidence_on_io_failure(tmp_path, monkeypatch,
                                                                             fault):
    # Use the launcher's ordinary disk-backed tmp_path for the durability
    # protocol. All operations remain real except the one injected I/O failure.
    store = retention.Store(tmp_path / 'state')
    calls, created = [], []
    real_sync, real_replace = os.fsync, os.replace

    def factory(**options):
        path = tempfile.mkdtemp(**options)
        created.append(path)
        return path

    def sync(fd):
        stage = 'directory-sync' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file-sync'
        calls.append(stage)
        if stage == 'file-sync':
            # The bytes must already have left Python's buffer before fsync.
            pending = json.loads((store.path / 'current.tmp').read_text())
            assert {record['path'] for record in pending['paths']} == {str(existing), created[0]}
        if fault == stage:
            raise OSError('injected ' + stage)
        real_sync(fd)

    def replace(*args, **options):
        calls.append('replace')
        if fault == 'replace':
            raise OSError('injected replace')
        real_replace(*args, **options)

    with store.session():
        existing = allocated(tmp_path, 'existing-evidence')
        original = json.loads((store.path / 'current.json').read_text())
        with monkeypatch.context() as patch:
            patch.setattr(os, 'fsync', sync)
            patch.setattr(os, 'replace', replace)
            expectation = pytest.raises(OSError, match='injected ' + fault) if fault else nullcontext()
            with expectation:
                result = retention.allocate(factory, prefix='allocation-', dir=tmp_path)
                calls.append('returned')
        order = ['file-sync', 'replace', 'directory-sync', 'returned']
        assert calls == (order[:order.index(fault) + 1] if fault else order)
        assert len(created) == 1
        assert Path(created[0]).exists() is (fault is None)
        if fault is None:
            assert result == created[0]
        saved = json.loads((store.path / 'current.json').read_text())
        assert saved['paths'][0] == original['paths'][0]
        assert (existing / 'test.log').read_bytes() == b'evidence' * 128
        if fault in ('file-sync', 'replace'):
            assert saved == original
        else:
            # Directory-sync failure can expose the replaced journal; it must
            # still raise, remove only the fresh empty tree and retain evidence.
            assert {record['path'] for record in saved['paths']} == {str(existing), created[0]}


def test_sbuild_traversable_scratch_is_registered_and_rotated(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = Path(retention.allocate(tempfile.mkdtemp, dir=tmp_path, mode=0o711))
        assert path.stat().st_mode & 0o777 == 0o711
        (path / 'early-failure').mkdir()
    advance_to_expiry(store)
    with store.session():
        assert not path.exists()


def test_inaccessible_sbuild_scratch_stops_growth(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        evidence = allocated(tmp_path, 'build-evidence')
        path = Path(retention.allocate(tempfile.mkdtemp, dir=tmp_path, mode=0o711))
        child = path / 'unproven-chroot-cleanup'
        child.mkdir(mode=0)
    try:
        for _ in range(3):
            with pytest.raises(PermissionError):
                with store.session():
                    pytest.fail('unproven chroot cleanup admitted another run')
            assert child.exists()
            assert (evidence / 'test.log').exists()
    finally:
        child.chmod(0o700)


def test_journal_hardlink_is_rejected_before_truncation(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        pass
    outside = tmp_path / 'keep'
    outside.write_text('original data')
    outside.chmod(0o600)
    os.link(outside, store.path / 'current.tmp')
    with pytest.raises(ValueError, match='unsafe ownership'):
        with store.session():
            pytest.fail('hardlinked journal accepted')
    assert outside.read_text() == 'original data'


def test_symlink_storage_parent_does_not_create_external_directories(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (tmp_path / 'link').symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        with retention.Store(tmp_path / 'link/new').session():
            pytest.fail('symlink storage accepted')
    assert not list(outside.iterdir())


def test_mount_boundary_is_refused(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'owned')
    original = os.stat
    def changed(name, *args, **kwargs):
        value = original(name, *args, **kwargs)
        if name == 'test.log':
            return SimpleNamespace(st_dev=value.st_dev + 1)
        return value
    monkeypatch.setattr(retention.os, 'stat', changed)
    with pytest.raises(ValueError, match='mounted storage'):
        with store.session():
            pytest.fail('mount accepted')
    assert (path / 'test.log').exists()


@pytest.mark.parametrize('nested', [False, True])
def test_same_device_bind_mount_is_refused(tmp_path, monkeypatch, nested):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'owned')
        mounted = path / 'mounted' if nested else path
        mounted.mkdir(exist_ok=True)
        (mounted / 'keep').write_text('mounted data')
    original = retention.mount_id
    def changed(fd):
        return 'foreign-mount' if Path(os.readlink(f'/proc/self/fd/{fd}')) == mounted else original(fd)
    monkeypatch.setattr(retention, 'mount_id', changed)
    with pytest.raises(ValueError, match='mounted storage'):
        with store.session():
            pytest.fail('bind mount accepted')
    assert (mounted / 'keep').read_text() == 'mounted data'


def test_root_replacement_during_deletion_never_erases_replacement(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'owned')
    advance_to_expiry(store)
    clear = retention.clear_tree
    def replaced(fd, device):
        path.rename(tmp_path / 'original')
        path.mkdir(mode=0o700)
        (path / 'keep').write_text('replacement')
        clear(fd, device)
    monkeypatch.setattr(retention, 'clear_tree', replaced)
    with pytest.raises(ValueError, match='changed during cleanup'):
        with store.session():
            pytest.fail('replacement accepted')
    assert (path / 'keep').read_text() == 'replacement'


def test_dispatcher_groups_privileged_categories_by_aggregate(tmp_path, monkeypatch):
    import test_retention as dispatcher_retention
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    run = dispatcher['run']
    run.__globals__['retention_guard'] = lambda root: None
    run.__globals__['selection'] = lambda root, argv: ['selected-controller']
    caller = SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid(),
                             pw_name='fixture', pw_dir=str(tmp_path))
    monkeypatch.setattr(dispatcher['os'], 'getgrouplist', lambda *args: [])
    store = dispatcher_retention.Store(tmp_path / 'root-state')
    monkeypatch.setattr(dispatcher_retention, 'Store', lambda path: store)
    owned = []
    def execute(command, **kwargs):
        if command == ['selected-controller']:
            assert kwargs['env'][retention.VARIABLE] == os.environ[retention.VARIABLE]
            owned.append(allocated(tmp_path, f'vm-{len(owned)}'))
        return 0
    control = SimpleNamespace(run=execute, installed=lambda **kw: nullcontext(control))
    monkeypatch.setattr(dispatcher['runpy'], 'run_path', lambda path: {
        'Control': lambda: control, 'safety_command': lambda root: ['safety']})
    first = uuid.uuid4().hex
    for category in ('system', 'e2e'):
        assert run(root, [f'--retention-run={first}', '--unattended', category], caller) == 0
    assert all(path.exists() for path in owned)
    for _ in range(2):
        assert run(root, [f'--retention-run={uuid.uuid4().hex}', '--unattended', 'system'], caller) == 0
        assert all(path.exists() for path in owned)
    assert run(root, [f'--retention-run={uuid.uuid4().hex}', '--unattended', 'system'], caller) == 0
    assert not any(path.exists() for path in owned[:2])
    assert all(path.exists() for path in owned[2:])


def test_original_single_run_journal_upgrades_without_losing_evidence(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session():
        path = allocated(tmp_path, 'original')
    journal = store.path / 'current.json'
    state = json.loads(journal.read_text())
    del state['history']
    journal.write_text(json.dumps(state))
    advance_to_expiry(store)
    assert path.exists()
    with store.session():
        assert not path.exists()


@pytest.mark.parametrize('fault', [None, 'identity', 'mode', 'unfinished', 'foreign'])
def test_legacy_system_export_is_preserved_only_after_identity_audit(tmp_path, fault):
    store = retention.Store(tmp_path / 'state')
    with tempfile.TemporaryDirectory(prefix='onpc-system-', dir='/tmp') as name:
        path = Path(name)
        with store.session() as old_run:
            retention.retain(path)
            (path / 'result.log').write_text('retained evidence')
            if fault == 'foreign':
                foreign = allocated(tmp_path, 'foreign')
        journal = store.path / 'current.json'
        old = json.loads(journal.read_text())
        path.chmod(0o755)
        if fault == 'identity':
            old['paths'][0]['inode'] += 1
        elif fault == 'mode':
            path.chmod(0o777)
        elif fault == 'unfinished':
            old['finished'] = False
        elif fault == 'foreign':
            foreign.chmod(0o755)
        journal.write_text(json.dumps(old))
        if fault:
            with pytest.raises(ValueError):
                with store.session(preserve_completed=retention.legacy_system_evidence):
                    pytest.fail('unsafe legacy journal accepted')
            assert json.loads(journal.read_text()) == old
        else:
            with store.session(preserve_completed=retention.legacy_system_evidence):
                assert json.loads(journal.read_text())['history'] == []
            assert json.loads((store.path / f'preserved-{old_run}.json').read_text()) == old
            for _ in range(4):
                with store.session(preserve_completed=retention.legacy_system_evidence):
                    pass
        assert (path / 'result.log').read_text() == 'retained evidence'


def test_older_vm_token_cannot_resume_after_a_newer_run(tmp_path):
    store = retention.Store(tmp_path / 'state')
    with store.session() as run:
        path = allocated(tmp_path, 'old-vm')
    with store.session():
        current = allocated(tmp_path, 'current-vm')
    with pytest.raises(ValueError, match='older run cannot resume'):
        with store.session(run=run):
            pytest.fail('older run resumed')
    assert path.exists() and current.exists()


def test_shell_review_copies_rotate_with_their_aggregate(tmp_path):
    namespace = runpy.run_path(str(Path(__file__).resolve().parents[2] /
                                  'tests/ui/test_child_shell_lifecycle.py'))
    preserve = namespace['_preserve_attempt_artifacts']
    preserve.__globals__['ARTIFACTS'] = tmp_path / 'review'
    source = tmp_path / 'shell-runtime'
    source.mkdir()
    log = source / 'lifecycle-events.log'
    store = retention.Store(tmp_path / 'state')
    copies = []
    for index in range(4):
        log.write_text(f'run {index}')
        with store.session():
            # The real producer allocates a unique runtime for each attempt.
            current = tmp_path / f'onpc-child-lifecycle-{index}'
            shutil.copytree(source, current)
            copies.append(preserve(current, 'lifecycle'))
        assert all(path.exists() for path in copies[-3:])
    assert not copies[0].exists()
    assert [(path / log.name).read_text() for path in copies[1:]] == ['run 1', 'run 2', 'run 3']


@pytest.mark.parametrize('phase', ['complete', 'running', 'cleanup-requested'])
def test_privileged_guard_reads_the_shared_recovery_journal(tmp_path, monkeypatch, phase):
    import prepare_host as baseline
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    monkeypatch.setattr(baseline, 'BASELINES', tmp_path)
    for name, content in (('.lock', ''), ('phase.json', '{"phase":"finalized"}'),
                          ('system-run.json', json.dumps({'phase': phase}))):
        path = tmp_path / name
        path.write_text(content)
        path.chmod(0o600)
    if phase == 'complete':
        dispatcher['retention_guard'](root)
    else:
        with pytest.raises(ValueError, match='recovery is unfinished'):
            dispatcher['retention_guard'](root)


@pytest.mark.parametrize('value', ['../outside', '', 'a' * 31, 'g' * 32])
def test_privileged_run_token_cannot_supply_paths(value):
    dispatcher = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
    with pytest.raises(ValueError, match='invalid-retention-run'):
        dispatcher['run'](Path('/missing'), ['--retention-run=' + value, '--unattended'], None)
