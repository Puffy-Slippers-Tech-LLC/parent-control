"""Real-file, unprivileged qualification of finite evidence preservation."""

import hashlib
import io
import os
from pathlib import Path
import stat
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from types import SimpleNamespace
import zipfile

import pytest

import evidence_bundle as bundle


@pytest.mark.parametrize('targets', [[], ['guest-one'], ['guest-two', 'guest-one'],
                                    ['guest-two', 'unused', 'guest-one']])
@pytest.mark.parametrize('first_export', [False, True])
def test_catalogue_includes_only_selected_targets_host_and_guest_journals(
        tmp_path, monkeypatch, targets, first_export):
    import vm_config

    state = tmp_path / 'state'
    state.mkdir()
    for name in ('retention-host', 'retention-batch', 'retention', 'standalone-reports',
                 'retention-guest-one', 'retention-guest-two', 'retention-unregistered'):
        (state / name).mkdir()
    uid, gid = os.geteuid(), os.getegid()
    (state / f'recovery-diagnostics-{uid}').mkdir()
    (state / f'recovery-diagnostics-{uid + 1}').mkdir()
    for target in ('guest-one', 'guest-two', 'unregistered'):
        (state / f'retention-{uid}-{target}').mkdir()
        (state / f'recovery-diagnostics-{uid}-{target}').mkdir()
    # Exercise the privileged catalogue without changing this test process's
    # identity or accessing any real journals, VM, or registry entries.
    monkeypatch.setattr(bundle, 'os', SimpleNamespace(**(vars(os) | {'geteuid': lambda: 0})))
    monkeypatch.setattr(bundle, 'identity', lambda *_: nullcontext())
    def directory(kind, **_):
        if first_export and kind == 'exports':
            raise FileNotFoundError('no exports yet')
        return tmp_path / kind

    monkeypatch.setattr(bundle.storage, 'directory', directory)
    monkeypatch.setattr(vm_config, 'registry', lambda: dict.fromkeys(['guest-one', 'guest-two', 'unused']))
    selection = bundle.Selection(tmp_path, uid, gid, targets, [], [])
    journals = selection.catalogue()
    fixed = {'retention-host', 'retention-batch', 'retention', 'standalone-reports'}
    populated = [target for target in targets if target != 'unused']
    assert {(path.name, owner, group) for path, owner, group in journals} == {
        *((name, uid, gid) for name in fixed),
        *((f'retention-{target}', uid, gid) for target in populated),
        *((f'retention-{uid}-{target}', 0, 0) for target in populated),
        *((f'recovery-diagnostics-{uid}-{target}', 0, 0) for target in populated),
        (f'recovery-diagnostics-{uid}', 0, 0),
    }
    assert len(journals) == len(fixed) + 3 * len(populated) + 1
    with pytest.raises(ValueError, match='registered canonical targets'):
        bundle.Selection(tmp_path, uid, gid, ['unregistered'], [], []).catalogue()


@pytest.mark.parametrize('journal', ['retention-{uid}-guest',
                                    'recovery-diagnostics-{uid}-guest',
                                    'recovery-diagnostics-{uid}'])
def test_inaccessible_selected_target_journal_remains_a_refusal(tmp_path, monkeypatch, journal):
    from contextlib import nullcontext
    import vm_config

    monkeypatch.setattr(bundle, 'os', SimpleNamespace(**(vars(os) | {'geteuid': lambda: 0})))
    monkeypatch.setattr(bundle, 'identity', lambda *_: nullcontext())
    monkeypatch.setattr(bundle.storage, 'directory', lambda *_args, **_kwargs: tmp_path)
    monkeypatch.setattr(vm_config, 'registry', lambda: {'guest': None})
    target = tmp_path / journal.format(uid=os.geteuid())
    original = Path.lstat
    original_stat = Path.stat
    def lstat(path, *args, **kwargs):
        if path == target:
            raise PermissionError('target journal inaccessible')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', lstat)
    def stat_path(path, *args, **kwargs):
        if path == target:
            raise PermissionError('target journal inaccessible')
        return original_stat(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', stat_path)
    with pytest.raises(PermissionError, match='target journal inaccessible'):
        bundle.Selection(tmp_path, os.geteuid(), os.getegid(), ['guest'], [], []).catalogue()


@pytest.mark.parametrize('missing_error', [FileNotFoundError, PermissionError])
@pytest.mark.parametrize('export_error', [FileNotFoundError, PermissionError])
@pytest.mark.parametrize('targets', [[], ['unused']])
def test_host_only_catalogue_without_privileged_storage(
        tmp_path, monkeypatch, missing_error, export_error, targets):
    import vm_config

    state = tmp_path / 'state'
    state.mkdir()
    (state / 'retention-host').mkdir()
    uid, gid = os.geteuid(), os.getegid()
    monkeypatch.setattr(bundle, 'os', SimpleNamespace(**(vars(os) | {'geteuid': lambda: 0})))
    monkeypatch.setattr(bundle, 'identity', lambda *_: nullcontext())
    monkeypatch.setattr(vm_config, 'registry', lambda: {'unused': None})
    reads = []

    def directory(kind, **_):
        reads.append(kind)
        if len(reads) == 1:
            raise missing_error('privileged state unavailable')
        if kind == 'exports':
            raise export_error('exports unavailable')
        return state

    monkeypatch.setattr(bundle.storage, 'directory', directory)
    selection = bundle.Selection(tmp_path, uid, gid, targets, [], [])
    if PermissionError in (missing_error, export_error):
        with pytest.raises(PermissionError):
            selection.catalogue()
    else:
        assert selection.catalogue() == [(state / 'retention-host', uid, gid)]


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    storage, retention = bundle.storage, bundle.retention
    monkeypatch.delenv(retention.VARIABLE, raising=False)
    checkout = tmp_path / 'checkout'
    checkout.mkdir(mode=0o700)
    monkeypatch.setattr(storage, 'ROOT', checkout)
    monkeypatch.setattr(storage, 'BASE', checkout / 'output/test-runs')
    sources = retention.Store(storage.directory('state') / 'retention-host')
    exports = retention.Store(storage.directory('exports') / 'retention')
    uid, gid = os.geteuid(), os.getegid()

    def catalogue(self, **_):
        journals = [sources.path]
        if exports.path.exists():
            journals.append(exports.path)
        return [(path, uid, gid) for path in journals]

    monkeypatch.setattr(bundle.Selection, 'catalogue', catalogue)

    def allocate(contents):
        with sources.session():
            root = Path(retention.allocate(tempfile.mkdtemp, prefix='onpc-bundle-fixture-'))
            for name, data in contents.items():
                path = root / name
                path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                path.write_bytes(data)
                path.chmod(0o600)
        return root

    def select(paths=(), previous=()):
        return bundle.Selection(checkout, uid, gid, [],
                                [str(path) for path in paths], [str(path) for path in previous])

    def publish(paths=(), previous=()):
        with select(paths, previous) as selection:
            return bundle.export(selection, expected=selection.plan()['selection_sha256'])

    def inspect(path, **options):
        result = bundle.inspect(checkout, uid, gid, str(path), **options)
        return result['manifest'] if options.get('member') is None else result

    return SimpleNamespace(checkout=checkout, sources=sources, exports=exports,
                           allocate=allocate, select=select, publish=publish, inspect=inspect)


def test_bundle_reads_overlap_without_rejecting_another_reader(evidence, monkeypatch):
    source = evidence.allocate({'report.md': b'passed\n', 'cleanup.json': b'{"complete":true}'})
    output = evidence.publish([source])['path']
    inspect_record = bundle.inspect_record
    nested = []

    def overlapping_read(record, uid, **options):
        # The outer inspection already holds the journal locks. Reenter through
        # the public reader with independent descriptors before it releases them.
        monkeypatch.setattr(bundle, 'inspect_record', inspect_record)
        nested.append(evidence.inspect(output, member=str(source / 'cleanup.json')))
        return inspect_record(record, uid, **options)

    monkeypatch.setattr(bundle, 'inspect_record', overlapping_read)
    assert evidence.inspect(output, member=str(source / 'report.md')) == b'passed\n'
    assert nested == [b'{"complete":true}']


def test_multiple_allocations_preserve_exact_bytes_manifest_and_sources(evidence):
    first = evidence.allocate({'results.json': b'{"passed":true}\n',
                               'nested/junit.xml': b'<testsuite/>\x00\xff'})
    second = evidence.allocate({'cleanup.log': b'cleanup complete\n'})
    paths = [first / 'results.json', first / 'nested/junit.xml', second / 'cleanup.log']
    before = {str(path): (path.read_bytes(), bundle.fingerprint(path.stat())) for path in paths}
    with evidence.select([first, second]) as selection:
        plan = selection.plan()
        assert plan['files'] == 3
        assert plan['logical_bytes'] == sum(len(value[0]) for value in before.values())
        assert len(plan['manifest']['source_budgets']) == 1
        result = bundle.export(selection, expected=plan['selection_sha256'])
    output = Path(result['path'])
    assert hashlib.sha256(output.read_bytes()).hexdigest() == result['sha256']
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert stat.S_IMODE(output.parent.stat().st_mode) == 0o700
    assert output.stat().st_uid == os.geteuid()
    manifest = evidence.inspect(output)
    assert manifest == plan['manifest']
    assert {entry['path'] for entry in manifest['files']} == set(before)
    for entry in manifest['files']:
        data, identity = before[entry['path']]
        assert entry['bytes'] == len(data)
        assert entry['sha256'] == hashlib.sha256(data).hexdigest()
        assert entry['identity'] == identity
        assert entry['allocation']['path'] in (str(first), str(second))
        assert evidence.inspect(output, member=entry['path']) == data
        assert evidence.inspect(output, member=entry['path'], offset=1, count=3) == data[1:4]
        source = Path(entry['path'])
        assert (source.read_bytes(), bundle.fingerprint(source.stat())) == before[str(source)]


def test_repeated_export_reuses_verified_copy_without_allocating_or_evicting(evidence, monkeypatch):
    root = evidence.allocate({'result.json': b'exact proof', 'other.json': b'other report'})
    source = root / 'result.json'
    original = (source.read_bytes(), bundle.fingerprint(source.stat()))
    first = evidence.publish([source])
    other = evidence.publish([root / 'other.json'])
    journal = (evidence.exports.path / 'current.json').read_bytes()
    monkeypatch.setattr(bundle.retention.Publication, 'allocate',
                        lambda *_args, **_options: pytest.fail('identical export allocated'))
    verify = bundle.verify_stream
    verifications = []
    def counted(stream):
        verifications.append(stream)
        return verify(stream)
    monkeypatch.setattr(bundle, 'verify_stream', counted)
    for _ in range(5):
        assert evidence.publish([source]) == first
    assert len(verifications) == 10  # At most the two retained candidate bundles per request.
    assert (evidence.exports.path / 'current.json').read_bytes() == journal
    assert Path(other['path']).exists()
    assert (source.read_bytes(), bundle.fingerprint(source.stat())) == original


def test_concurrent_identical_exports_commit_one_private_copy(evidence, monkeypatch):
    root = evidence.allocate({'result.json': b'concurrent proof'})
    ready = threading.Barrier(2)
    allocate = bundle.retention.Publication.allocate
    allocations = []
    def counted(transaction, *args, **options):
        path = allocate(transaction, *args, **options)
        allocations.append(path)
        return path
    monkeypatch.setattr(bundle.retention.Publication, 'allocate', counted)
    def publish():
        with evidence.select([root]) as selection:
            ready.wait(timeout=10)
            return bundle.export(selection, expected=selection.selection_sha256)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(), range(2)))
    assert results[0] == results[1]
    assert len(allocations) == 1
    output = Path(results[0]['path'])
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert stat.S_IMODE(output.parent.stat().st_mode) == 0o700
    assert output.stat().st_uid == output.parent.stat().st_uid == os.geteuid()
    assert evidence.inspect(output, member=str(root / 'result.json')) == b'concurrent proof'
    with evidence.exports.inspection() as state:
        assert state['history'] == [] and len(state['paths']) == 1


def test_changed_source_recaptures_without_mutating_existing_copy(evidence):
    root = evidence.allocate({'result.json': b'first proof'})
    source = root / 'result.json'
    first = evidence.publish([source])
    source.write_bytes(b'changed proof')
    changed = (source.read_bytes(), bundle.fingerprint(source.stat()))
    second = evidence.publish([source])
    assert first['path'] != second['path']
    assert evidence.inspect(first['path'], member=str(source)) == b'first proof'
    assert evidence.inspect(second['path'], member=str(source)) == b'changed proof'
    assert evidence.publish([source]) == second
    assert (source.read_bytes(), bundle.fingerprint(source.stat())) == changed


@pytest.mark.parametrize('defect', ['missing', 'replaced', 'corrupt', 'receipt', 'public-mode'])
def test_stale_reuse_refuses_without_allocating_or_mutating_journal(evidence, monkeypatch, defect):
    root = evidence.allocate({'result.json': b'exact proof'})
    first = evidence.publish([root])
    output = Path(first['path'])
    journal = (evidence.exports.path / 'current.json').read_bytes()
    if defect == 'missing':
        output.unlink()
    elif defect == 'replaced':
        contents = output.read_bytes()
        output.unlink()
        output.write_bytes(contents)
        output.chmod(0o600)
    elif defect == 'corrupt':
        output.write_bytes(b'corrupt')
    elif defect == 'receipt':
        (output.parent / 'receipt.json').write_bytes(b'{}')
    else:
        output.chmod(0o644)
    monkeypatch.setattr(bundle.retention.Publication, 'allocate',
                        lambda *_args, **_options: pytest.fail('stale copy allocated'))
    with pytest.raises((ValueError, OSError)):
        evidence.publish([root])
    assert (evidence.exports.path / 'current.json').read_bytes() == journal
    assert (root / 'result.json').read_bytes() == b'exact proof'


def test_identical_reuse_does_not_require_staging_capacity(evidence, monkeypatch):
    root = evidence.allocate({'result.json': b'exact proof'})
    first = evidence.publish([root])
    with evidence.exports.inspection() as state:
        usage = bundle.retention.publication_usage(state['paths'])
    monkeypatch.setattr(bundle.retention, 'MAX_RETAINED_BYTES', usage + 4096)
    assert evidence.publish([root]) == first


def test_cumulative_bundle_survives_source_and_export_rotation(evidence):
    expected, roots, outputs = {}, [], []
    previous = []
    for index in range(6):
        data = f'raw proof {index}\n'.encode()
        root = evidence.allocate({'result.json': data})
        roots.append(root)
        expected[str(root / 'result.json')] = data
        result = evidence.publish([root], previous)
        outputs.append(Path(result['path']))
        previous = [outputs[-1]]
        manifest = evidence.inspect(outputs[-1])
        assert {entry['path'] for entry in manifest['files']} == set(expected)
        for entry in manifest['files']:
            assert evidence.inspect(outputs[-1], member=entry['path']) == expected[entry['path']]
    assert [path.exists() for path in roots] == [False] * 3 + [True] * 3
    assert [path.exists() for path in outputs] == [False] * 3 + [True] * 3
    with evidence.exports.inspection() as state:
        assert len(state['history']) == 2
    assert bundle.retention.RUNS_TO_KEEP == 3
    assert bundle.retention.MAX_RETAINED_BYTES == 4 * 1024 ** 3


@pytest.mark.parametrize('suffix', ['', '-guest-one'])
def test_recovery_diagnostic_samples_survive_rotation(evidence, suffix):
    evidence.sources.path = evidence.sources.path.with_name(
        f'recovery-diagnostics-{os.geteuid()}{suffix}')
    previous, expected, roots = [], {}, []
    for index in range(4):
        # Diagnostics retain original nonpassing verdicts and the complete
        # command/input/cleanup/native-availability closure, not a summary.
        files = {'observed.json': f'[{index}]\n'.encode(),
                 'result.json': b'{"outcome":"diagnostic","complete":false}',
                 'commands.json': b'[{"argv":["fixed-probe"],"exit_status":1}]',
                 'input.json': f'{{"attempt":{index}}}'.encode(),
                 'cleanup.json': b'{"state":"pending","vm_preserved":true}',
                 'native-status.json': b'{"available":false}'}
        root = evidence.allocate(files)
        roots.append(root)
        expected.update({str(root / name): data for name, data in files.items()})
        result = evidence.publish([root], previous)
        previous = [Path(result['path'])]
    assert not roots[0].exists()
    assert len(evidence.inspect(previous[0])['files']) == len(expected)
    for path, data in expected.items():
        assert evidence.inspect(previous[0], member=path) == data


def test_failed_publication_preserves_all_exports_and_allows_retry(evidence, monkeypatch):
    root = evidence.allocate({'result.json': b'original proof',
                              **{f'old-{index}.json': str(index).encode() for index in range(3)}})
    outputs = [Path(evidence.publish([root / f'old-{index}.json'])['path']) for index in range(3)]
    journal = (evidence.exports.path / 'current.json').read_bytes()
    write = bundle.Selection.write

    def interrupted(self, path):
        write(self, path)
        raise OSError('fixture publication failure')

    with monkeypatch.context() as patch:
        patch.setattr(bundle.Selection, 'write', interrupted)
        with pytest.raises(OSError, match='fixture publication failure'):
            evidence.publish([root])
    assert (evidence.exports.path / 'current.json').read_bytes() == journal
    assert all(path.is_file() for path in outputs)
    assert not (evidence.exports.path / bundle.retention.PUBLICATION).exists()
    assert (root / 'result.json').read_bytes() == b'original proof'
    latest = Path(evidence.publish([root])['path'])
    assert latest.is_file() and not outputs[0].exists()
    assert all(path.is_file() for path in outputs[1:])


def test_group_failure_after_first_member_never_publishes_partial_bundle(evidence, monkeypatch):
    root = evidence.allocate({'first.json': b'first proof', 'second.json': b'second proof'})
    previous = evidence.publish([root / 'first.json'])
    journal = (evidence.exports.path / 'current.json').read_bytes()
    stream_bytes = bundle.stream_bytes
    copied = []
    def interrupted(source, size, output=None):
        if output is not None:
            copied.append(size)
            if len(copied) == 2:
                raise OSError('fixture second-member interruption')
        return stream_bytes(source, size, output)
    with monkeypatch.context() as patch:
        patch.setattr(bundle, 'stream_bytes', interrupted)
        with pytest.raises(OSError, match='second-member interruption'):
            evidence.publish([root])
    assert len(copied) == 2
    assert (evidence.exports.path / 'current.json').read_bytes() == journal
    assert Path(previous['path']).exists()
    assert not (evidence.exports.path / bundle.retention.PUBLICATION).exists()
    result = evidence.publish([root])
    assert evidence.inspect(result['path'], member=str(root / 'first.json')) == b'first proof'
    assert evidence.inspect(result['path'], member=str(root / 'second.json')) == b'second proof'
    assert {path.name: path.read_bytes() for path in root.iterdir()} == {
        'first.json': b'first proof', 'second.json': b'second proof'}


@pytest.mark.parametrize('sync_failure', [False, True])
def test_bulk_archive_writes_are_paced_and_sync_failure_preserves_prior_proof(
        evidence, monkeypatch, sync_failure):
    previous_source = evidence.allocate({'previous.json': b'previous proof'})
    previous = evidence.publish([previous_source])
    payload = b'bounded evidence copy\n' * 10000
    source = evidence.allocate({'result.log': payload})
    before = (evidence.exports.path / 'current.json').read_bytes()
    batch, rate = 32768, 131072
    clock, waits, sizes = [0.0], [], []
    real_sync = os.fsync

    def sleep(delay):
        assert delay > 0
        waits.append(delay)
        clock[0] += delay

    def sync(fd):
        size = os.fstat(fd).st_size
        if size > batch // 2:
            sizes.append(size)
            if sync_failure:
                raise OSError('injected archive batch sync failure')
            if len(sizes) == 1:
                # Slow flushes retain a bounded recovery interval rather than
                # multiplying disk contention into minutes of launcher delay.
                clock[0] += 10
        real_sync(fd)

    with monkeypatch.context() as local:
        local.setattr(bundle, 'ARCHIVE_SYNC_BYTES', batch)
        local.setattr(bundle, 'ARCHIVE_BYTES_PER_SECOND', rate)
        local.setattr(bundle, 'time', SimpleNamespace(monotonic=lambda: clock[0], sleep=sleep))
        local.setattr(bundle, 'os', SimpleNamespace(**(vars(os) | {'fsync': sync})))
        if sync_failure:
            with pytest.raises(OSError, match='archive batch sync failure'):
                evidence.publish([source])
        else:
            result = evidence.publish([source])
    assert sizes
    assert all(0 <= after - before <= batch for before, after in zip([0, *sizes], sizes))
    if sync_failure:
        assert (evidence.exports.path / 'current.json').read_bytes() == before
        assert not (evidence.exports.path / bundle.retention.PUBLICATION).exists()
    else:
        assert waits[0] == pytest.approx(1)
        assert len(waits) >= len(payload) // batch
        assert waits[1:] == pytest.approx([batch / rate] * (len(waits) - 1))
        assert evidence.inspect(result['path'], member=str(source / 'result.log'), count=len(payload)) == payload
    assert Path(previous['path']).exists()
    assert (source / 'result.log').read_bytes() == payload


@pytest.mark.parametrize('fault', ['mode', 'symlink', 'hardlink', 'fifo', 'parent-link',
                                  'allocation-replacement', 'mount', 'owner'])
def test_unsafe_sources_are_refused_without_changing_journal(evidence, monkeypatch, fault):
    root = evidence.allocate({'nested/result.json': b'proof'})
    source = root / 'nested/result.json'
    journal = (evidence.sources.path / 'current.json').read_bytes()
    if fault == 'mode':
        source.chmod(0o666)
    elif fault in ('symlink', 'hardlink', 'fifo'):
        original = source.with_name('original')
        source.rename(original)
        if fault == 'symlink':
            source.symlink_to(original)
        elif fault == 'hardlink':
            os.link(original, source)
        else:
            os.mkfifo(source)
    elif fault == 'parent-link':
        source.parent.rename(root / 'original')
        source.parent.symlink_to(root / 'original')
    elif fault == 'allocation-replacement':
        root.rename(root.with_name(root.name + '-original'))
        root.mkdir(mode=0o700)
    elif fault == 'mount':
        mount_id = bundle.retention.mount_id
        def mounted(fd):
            return 'fixture-mount' if Path(os.readlink(f'/proc/self/fd/{fd}')) == root else mount_id(fd)
        monkeypatch.setattr(bundle.retention, 'mount_id', mounted)
    else:
        safe = bundle.safe
        def foreign_owner(info, uid, **options):
            if stat.S_ISREG(info.st_mode):
                info = SimpleNamespace(st_mode=info.st_mode, st_uid=uid + 1,
                                       st_nlink=info.st_nlink)
            return safe(info, uid, **options)
        monkeypatch.setattr(bundle, 'safe', foreign_owner)
    with pytest.raises((ValueError, OSError)):
        with evidence.select([source]):
            pytest.fail('unsafe selected evidence accepted')
    assert (evidence.sources.path / 'current.json').read_bytes() == journal
    assert not evidence.exports.path.exists()


@pytest.mark.parametrize('change', ['replace', 'mutate', 'grow'])
def test_inventory_to_copy_mutation_is_refused(evidence, change):
    root = evidence.allocate({'result.json': b'original'})
    source = root / 'result.json'
    with evidence.select([source]) as selection:
        if change == 'replace':
            source.rename(root / 'original')
            source.write_bytes(b'original')
            source.chmod(0o600)
        else:
            source.write_bytes(b'changed!' if change == 'mutate' else b'original plus')
        with pytest.raises(ValueError, match='changed'):
            bundle.export(selection, expected=selection.selection_sha256)
    assert source.exists()
    assert not (evidence.exports.path / bundle.retention.PUBLICATION).exists()


def test_unselected_sibling_updates_do_not_invalidate_selected_proof(evidence, monkeypatch):
    root = evidence.allocate({'proof/result.json': b'exact proof', 'chat.json': b'old chat'})
    source = root / 'proof'
    write = bundle.Selection.write

    def update_siblings(selection, destination):
        # Atomic launcher control writes change the allocation's timestamps,
        # size and link count without changing the selected proof subtree.
        temporary = root / 'chat-new.json'
        temporary.write_bytes(b'new chat')
        temporary.replace(root / 'chat.json')
        (root / 'another-capsule').mkdir(mode=0o700)
        return write(selection, destination)

    with evidence.select([source]) as selection:
        expected = selection.plan()['selection_sha256']
        monkeypatch.setattr(bundle.Selection, 'write', update_siblings)
        exported = bundle.export(selection, expected=expected)
    manifest = evidence.inspect(exported['path'])
    assert {entry['path'] for entry in manifest['files']} == {str(source / 'result.json')}
    assert evidence.inspect(exported['path'], member=str(source / 'result.json')) == b'exact proof'
    assert (root / 'chat.json').read_bytes() == b'new chat'


@pytest.mark.parametrize('change', ['add', 'remove', 'replace-parent', 'parent-mode'])
def test_selected_tree_and_traversal_identity_changes_still_refuse(evidence, change):
    root = evidence.allocate({'ancestor/proof/result.json': b'exact proof',
                              'ancestor/proof/extra.json': b'extra proof'})
    parent = root / 'ancestor'
    source = parent / 'proof'
    with evidence.select([source]) as selection:
        if change == 'add':
            (source / 'new.json').write_bytes(b'new proof')
        elif change == 'remove':
            (source / 'extra.json').unlink()
        elif change == 'replace-parent':
            parent.rename(root / 'previous')
            parent.mkdir(mode=0o700)
            (root / 'previous/proof').rename(source)
        else:
            parent.chmod(0o500)
        try:
            with pytest.raises(ValueError, match='directory changed'):
                bundle.export(selection, expected=selection.selection_sha256)
        finally:
            if change == 'parent-mode':
                parent.chmod(0o700)
    assert not (evidence.exports.path / bundle.retention.PUBLICATION).exists()


@pytest.mark.parametrize('phase', ['inventory', 'copy'])
def test_mutation_during_streaming_is_refused(evidence, monkeypatch, phase):
    root = evidence.allocate({'result.json': b'original'})
    source = root / 'result.json'
    stream_bytes = bundle.stream_bytes

    def mutate(stream, size, output=None):
        result = stream_bytes(stream, size, output)
        if (phase == 'inventory' and output is None) or (phase == 'copy' and output is not None):
            source.write_bytes(b'changed!')
        return result

    if phase == 'inventory':
        monkeypatch.setattr(bundle, 'stream_bytes', mutate)
        with pytest.raises(ValueError, match='changed'):
            with evidence.select([source]):
                pytest.fail('source mutation during inventory accepted')
    else:
        with evidence.select([source]) as selection:
            monkeypatch.setattr(bundle, 'stream_bytes', mutate)
            with pytest.raises(ValueError, match='changed'):
                bundle.export(selection, expected=selection.selection_sha256)
    assert source.read_bytes() == b'changed!'


@pytest.mark.parametrize('name', ['snapshot.json', '.ssh/key', 'ssh-key', 'id_ed25519',
                                 'credentials.json', 'private.pem', 'private.key'])
def test_credentials_paths_are_refused(evidence, name):
    root = evidence.allocate({name: b'secret'})
    with pytest.raises(ValueError, match='credentials'):
        with evidence.select([root]):
            pytest.fail('credential path accepted')


@pytest.mark.parametrize('kind', [b'OPENSSH', b'RSA', b'EC', b'ENCRYPTED', b''])
@pytest.mark.parametrize('ending', [b'\nsecret', b'\r\nsecret', b''])
@pytest.mark.parametrize('split', [10, 34, 35, 36])
def test_private_key_contents_are_refused_across_read_boundary(evidence, kind, ending, split):
    header = b'-----BEGIN ' + (kind + b' ' if kind else b'') + b'PRIVATE KEY-----'
    root = evidence.allocate({'ordinary.log': b'x' * (65536 - split) + header + ending})
    with pytest.raises(ValueError, match='private key'):
        with evidence.select([root]):
            pytest.fail('private key content accepted')


@pytest.mark.parametrize('split', [10, 34, 35, 36])
def test_quoted_key_test_source_is_preserved_exactly(evidence, split):
    header = b'-----BEGIN OPENSSH ' + b'PRIVATE KEY-----'
    data = (b'x' * (65536 - split) + header + b"\\nsecret'})\n"
            + b"pattern = rb'" + header + b"'\n")
    root = evidence.allocate({'agent-commands.log': data})
    result = evidence.publish([root])
    assert evidence.inspect(result['path'], member=str(root / 'agent-commands.log'),
                            count=len(data)) == data
    assert (root / 'agent-commands.log').read_bytes() == data


@pytest.mark.parametrize('ending', [b'\\n', b'\\r\\n'])
@pytest.mark.parametrize('split', [10, 40, 70])
def test_serialized_private_key_contents_are_refused_across_read_boundary(evidence, ending, split):
    data = (b'x' * (65536 - split) + b'-----BEGIN OPENSSH ' + b'PRIVATE KEY-----'
            + ending + b'b3BlbnNzaC1rZXktdjE=' + ending)
    root = evidence.allocate({'ordinary.json': data})
    with pytest.raises(ValueError, match='private key'):
        with evidence.select([root]):
            pytest.fail('serialized private key content accepted')


@pytest.mark.parametrize('kind', ['empty', 'duplicate', 'relative', 'dotdot', 'unrecorded', 'many'])
def test_malformed_source_selections_are_refused(evidence, kind):
    root = evidence.allocate({'result.json': b'proof'})
    source = str(root / 'result.json')
    paths = {'empty': [], 'duplicate': [source, source], 'relative': ['relative/file'],
             'dotdot': [str(root) + '/../result.json'], 'unrecorded': [str(root.parent / 'unknown')],
             'many': [source + str(index) for index in range(257)]}[kind]
    with pytest.raises(ValueError):
        with evidence.select(paths):
            pytest.fail('malformed selection accepted')


def test_file_count_limit_and_stale_plan_are_refused(evidence, monkeypatch):
    root = evidence.allocate({'result.json': b'proof', 'cleanup.json': b'complete'})
    with evidence.select([root]) as selection:
        with pytest.raises(ValueError, match='selection changed'):
            bundle.export(selection, expected='0' * 64)
    monkeypatch.setattr(bundle, 'MAX_FILES', 1)
    with pytest.raises(ValueError, match='file count'):
        with evidence.select([root]):
            pytest.fail('excessive file count accepted')


def test_bundle_over_one_gib_is_planned_and_verified_with_retention_still_enforced(
        evidence, tmp_path, monkeypatch):
    root = evidence.allocate({'history.zip': b''})
    source = root / 'history.zip'
    size = 1024 ** 3 + 1
    with source.open('r+b') as stream:
        stream.truncate(size)

    class SparseWriter:
        """Keep this real ZIP's zero payload sparse instead of writing a GiB."""
        def __init__(self, stream):
            self.stream = stream

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def write(self, data):
            if data and not data.strip(b'\0'):
                self.stream.seek(len(data), os.SEEK_CUR)
                return len(data)
            return self.stream.write(data)

    archive_path = tmp_path / 'large-evidence.zip'
    with evidence.select([source]) as selection:
        plan = selection.plan()
        assert plan['logical_bytes'] == size
        assert plan['projected_bytes'] > size
        with archive_path.open('w+b') as stream:
            with zipfile.ZipFile(SparseWriter(stream), 'w', compression=zipfile.ZIP_STORED) as archive:
                with source.open('rb') as original, archive.open('files/00000000', 'w', force_zip64=True) as output:
                    assert bundle.stream_bytes(original, size, output) == plan['manifest']['files'][0]['sha256']
                data = bundle.encoded(plan['manifest'])
                archive.writestr('manifest.json', data)
                archive.writestr('manifest.sha256', bundle.digest(data))
            assert stream.tell() > size
            verified, manifest = bundle.verify_stream(stream)
            verified.close()
            assert manifest == plan['manifest']
        # Removing the bundle ceiling must not bypass publication's existing
        # simultaneous-space admission or allocate a partial export on refusal.
        monkeypatch.setattr(bundle.retention, 'MAX_RETAINED_BYTES', 4096)
        with pytest.raises(bundle.retention.CapacityExceeded):
            bundle.export(selection, expected=plan['selection_sha256'])
    assert source.stat().st_size == size
    assert not list(evidence.exports.path.parent.glob('onpc-evidence-bundle-*'))


def archive_bytes(manifest, payload=b'proof', *, extra=None, checksum=None):
    output = io.BytesIO()
    data = bundle.encoded(manifest)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('files/00000000', payload)
        archive.writestr('manifest.json', data)
        archive.writestr('manifest.sha256', checksum or bundle.digest(data))
        if extra:
            archive.writestr(extra, b'undeclared')
    return output.getvalue()


@pytest.mark.parametrize('fault', ['traversal', 'extra', 'member-name', 'digest', 'checksum',
                                  'size', 'duplicate-path', 'private-path', 'oversized-manifest',
                                  'directory-digest', 'directory-ancestor', 'directory-duplicate',
                                  'directory-empty'])
def test_malformed_archives_are_refused_without_extraction(evidence, monkeypatch, fault):
    root = evidence.allocate({'result.json': b'proof'})
    with evidence.select([root]) as selection:
        manifest = selection.manifest
    entry = manifest['files'][0]
    extra, checksum = None, None
    if fault == 'traversal':
        extra = '../../escaped'
    elif fault == 'extra':
        extra = 'unexpected'
    elif fault == 'member-name':
        entry['member'] = '../result.json'
    elif fault == 'digest':
        entry['sha256'] = '0' * 64
    elif fault == 'checksum':
        checksum = '0' * 64
    elif fault == 'size':
        entry['bytes'] += 1
    elif fault == 'duplicate-path':
        manifest['files'].append(dict(entry, member='files/00000001'))
    elif fault == 'private-path':
        entry['path'] = str(root / 'snapshot.json')
    elif fault == 'directory-digest':
        manifest['directories'][0]['sha256'] = '0' * 64
    elif fault == 'directory-ancestor':
        manifest['directories'][0]['path'] = str(root.parent)
    elif fault == 'directory-duplicate':
        manifest['directories'].append(manifest['directories'][0])
    elif fault == 'directory-empty':
        manifest['directories'] = []
    else:
        monkeypatch.setattr(bundle, 'MAX_MANIFEST', 1)
    with pytest.raises((ValueError, KeyError)):
        bundle.verify_stream(io.BytesIO(archive_bytes(manifest, extra=extra, checksum=checksum)))
    assert not (evidence.checkout / 'escaped').exists()
    assert (root / 'result.json').read_bytes() == b'proof'


def test_inspection_verifies_whole_bundle_before_returning_member(evidence):
    root = evidence.allocate({'result.json': b'proof'})
    output = Path(evidence.publish([root])['path'])
    manifest = evidence.inspect(output)
    manifest['files'][0]['sha256'] = '0' * 64
    output.write_bytes(archive_bytes(manifest))
    with pytest.raises(ValueError, match='checksum'):
        evidence.inspect(output, member=manifest['files'][0]['path'], count=1)
    with pytest.raises(ValueError):
        evidence.inspect(root / 'result.json')


def test_verified_record_reuses_one_open_archive_for_bounded_reads(evidence, monkeypatch):
    root = evidence.allocate({'first.json': b'first proof', 'second.json': b'second proof'})
    output = Path(evidence.publish([root])['path'])
    verify = bundle.verify_stream
    calls = []

    def counted(stream):
        calls.append(stream)
        return verify(stream)

    monkeypatch.setattr(bundle, 'verify_stream', counted)
    with evidence.exports.inspection() as state:
        record = next(item for item in state['paths'] if item['path'] == str(output.parent))
        with bundle.verified_record(record, os.geteuid(), checkout=evidence.checkout) as (verified, read):
            assert verified['files'] == 2
            assert read(str(root / 'first.json')) == b'first proof'
            assert read(str(root / 'second.json'), offset=7, count=5) == b'proof'
            assert read(str(root / 'first.json'), offset=100) == b''
            for options in ({'offset': -1}, {'offset': True}, {'count': -1}, {'count': bundle.MAX_READ + 1}):
                with pytest.raises(ValueError, match='inspection byte range'):
                    read(str(root / 'first.json'), **options)
            with pytest.raises(ValueError, match='not in the manifest'):
                read(str(root / 'unselected.json'))
        assert len(calls) == 1
        with pytest.raises(ValueError):
            read(str(root / 'first.json'))
        with bundle.verified_record(record, os.geteuid(), checkout=evidence.checkout) as (_, reread):
            assert reread(str(root / 'first.json')) == b'first proof'
        assert len(calls) == 2  # Trust never survives the pinned scope.


def test_verified_reader_excludes_publication_until_scope_released(evidence):
    root = evidence.allocate({'result.json': b'exact proof'})
    output = Path(evidence.publish([root])['path'])
    with evidence.exports.inspection() as state:
        record = next(item for item in state['paths'] if item['path'] == str(output.parent))
        with bundle.verified_record(record, os.geteuid(), checkout=evidence.checkout) as (_, read):
            with pytest.raises(ValueError, match='another owner is active'):
                with evidence.exports.publication(projected_bytes=0):
                    pytest.fail('writer entered a pinned read scope')
            assert read(str(root / 'result.json')) == b'exact proof'
    with evidence.exports.publication(projected_bytes=0):
        pass


@pytest.mark.parametrize('change', ['between-reads', 'scope-exit', 'receipt', 'receipt-between-reads',
                                  'replacement'])
def test_verified_record_refuses_mutation_during_read_scope(evidence, change):
    root = evidence.allocate({'result.json': b'exact proof'})
    output = Path(evidence.publish([root])['path'])
    with evidence.exports.inspection() as state:
        record = next(item for item in state['paths'] if item['path'] == str(output.parent))
        with pytest.raises(ValueError, match='changed during inspection'):
            with bundle.verified_record(record, os.geteuid(), checkout=evidence.checkout) as (_, read):
                assert read(str(root / 'result.json')) == b'exact proof'
                if change in ('receipt', 'receipt-between-reads'):
                    receipt = output.parent / 'receipt.json'
                    receipt.write_bytes(receipt.read_bytes() + b' ')
                elif change == 'replacement':
                    data = output.read_bytes()
                    output.unlink()
                    output.write_bytes(data)
                    output.chmod(0o600)
                else:
                    with output.open('ab') as stream:
                        stream.write(b'changed')
                if change in ('between-reads', 'receipt-between-reads'):
                    read(str(root / 'result.json'))
                    pytest.fail('changed archive returned a member')


@pytest.mark.parametrize('options', [{'offset': -1}, {'count': -1}, {'count': 16 * 1024 ** 2 + 1},
                                   {'offset': True}, {'member': '../../escape'},
                                   {'member': 'files/00000000'}])
def test_inspection_refuses_unsafe_ranges_and_unselected_paths(evidence, options):
    root = evidence.allocate({'result.json': b'proof'})
    output = Path(evidence.publish([root])['path'])
    with pytest.raises(ValueError):
        evidence.inspect(output, **options)
    assert evidence.inspect(output, member=str(root / 'result.json'), offset=100) == b''


def test_duplicate_archive_member_names_are_refused(evidence):
    root = evidence.allocate({'result.json': b'proof'})
    with evidence.select([root]) as selection:
        manifest = selection.manifest
    data = archive_bytes(manifest)
    output = io.BytesIO(data)
    with pytest.warns(UserWarning, match='Duplicate name'):
        with zipfile.ZipFile(output, 'a') as archive:
            archive.writestr('files/00000000', b'proof')
    with pytest.raises(ValueError, match='ambiguous'):
        bundle.verify_stream(io.BytesIO(output.getvalue()))


def test_nested_identity_switch_restores_authority_before_groups(monkeypatch):
    current = {'uid': 0, 'gid': 0}
    events = []
    monkeypatch.setattr(os, 'geteuid', lambda: current['uid'])
    monkeypatch.setattr(os, 'getegid', lambda: current['gid'])
    def uid(value):
        current['uid'] = value
        events.append(('uid', value))
    def gid(value):
        assert current['uid'] == 0
        current['gid'] = value
        events.append(('gid', value))
    monkeypatch.setattr(os, 'seteuid', uid)
    monkeypatch.setattr(os, 'setegid', gid)
    with pytest.raises(RuntimeError):
        with bundle.identity(1000, 1000):
            assert current == {'uid': 1000, 'gid': 1000}
            with bundle.identity(0, 0):
                assert current == {'uid': 0, 'gid': 0}
            assert current == {'uid': 1000, 'gid': 1000}
            raise RuntimeError('fixture')
    assert current == {'uid': 0, 'gid': 0}
    assert events[:2] == [('gid', 1000), ('uid', 1000)]


@pytest.mark.parametrize('foreign', [False, True])
def test_private_group_metadata_is_preserved_and_foreign_group_refused(evidence, monkeypatch, foreign):
    root = evidence.allocate({'progress.json': b'{"passed":true}'})
    source = root / 'progress.json'
    source.chmod(0o664)
    uid = os.getuid()
    monkeypatch.setattr(bundle.grp, 'getgrgid', lambda gid: SimpleNamespace(
        gr_mem=['unrelated-account'] if foreign else [bundle.pwd.getpwuid(uid).pw_name]))
    monkeypatch.setattr(bundle.pwd, 'getpwall', lambda: [])
    if foreign:
        with pytest.raises(ValueError, match='unsafe writable group'):
            evidence.publish([root])
    else:
        output = evidence.publish([root])
        assert evidence.inspect(output['path'], member=str(source)) == source.read_bytes()


@pytest.mark.parametrize('substitute', ['missing', 'same-bytes', 'extra-file'])
def test_destination_substitution_cannot_commit_or_rotate(evidence, monkeypatch, substitute):
    root = evidence.allocate({'result.json': b'proof',
                              **{f'old-{index}.json': str(index).encode() for index in range(3)}})
    previous = [Path(evidence.publish([root / f'old-{index}.json'])['path']) for index in range(3)]
    before = (evidence.exports.path / 'current.json').read_bytes()
    write = bundle.Selection.write
    def changed(self, destination):
        write(self, destination)
        path = Path(os.readlink(f'/proc/self/fd/{destination.fileno()}'))
        if substitute == 'extra-file':
            (path.parent / 'unpublished').write_bytes(b'extra')
        else:
            data = path.read_bytes()
            path.unlink()
            if substitute == 'same-bytes':
                path.write_bytes(data)
                path.chmod(0o600)
    monkeypatch.setattr(bundle.Selection, 'write', changed)
    with pytest.raises((ValueError, OSError)):
        evidence.publish([root])
    assert (evidence.exports.path / 'current.json').read_bytes() == before
    assert all(path.exists() for path in previous)
    assert not (evidence.exports.path / bundle.retention.PUBLICATION).exists()
    monkeypatch.setattr(bundle.Selection, 'write', write)
    retried = Path(evidence.publish([root])['path'])
    assert retried.exists() and not previous[0].exists()


def test_deferred_corruption_preserves_old_exports_until_verified(evidence):
    root = evidence.allocate({'result.json': b'proof',
                              **{f'old-{index}.json': str(index).encode() for index in range(3)}})
    previous = [Path(evidence.publish([root / f'old-{index}.json'])['path']) for index in range(3)]
    with evidence.select([root]) as selection:
        result = bundle.export(selection, expected=selection.selection_sha256, defer_cleanup=True)
    output = Path(result['path'])
    data = output.read_bytes()
    output.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='checksum'):
        bundle.finish(evidence.checkout, os.getuid(), os.getgid())
    assert all(path.exists() for path in previous)
    # Corruption remains a refusal even if bytes are restored: the recorded file
    # identity changed. A new reviewed preservation must precede retirement.
    output.write_bytes(data)
    with pytest.raises(ValueError, match='checksum'):
        bundle.finish(evidence.checkout, os.getuid(), os.getgid())
    assert all(path.exists() for path in previous)


def test_archive_directory_is_bounded_before_zip_parser(evidence, monkeypatch):
    root = evidence.allocate({'result.json': b'proof'})
    with evidence.select([root]) as selection:
        data = bytearray(archive_bytes(selection.manifest))
    # EOCD claims more members than the permitted finite selection.
    data[-12:-10] = (bundle.MAX_FILES + 3).to_bytes(2, 'little')
    monkeypatch.setattr(bundle.zipfile, 'ZipFile', lambda *args, **kw: pytest.fail('unbounded parser reached'))
    with pytest.raises(ValueError, match='archive directory'):
        bundle.verify_stream(io.BytesIO(data))


def test_manifest_duplicate_json_keys_are_refused():
    with pytest.raises(ValueError, match='ambiguous JSON'):
        bundle.decoded(b'{"schema":1,"schema":2}')


def test_recorded_foreign_checkout_allocation_is_refused(evidence):
    outside = evidence.checkout.parent / 'unrelated-private-data'
    outside.mkdir(mode=0o700)
    (outside / 'result.json').write_bytes(b'foreign data')
    with evidence.sources.session():
        bundle.retention.retain(outside)
    with pytest.raises(ValueError, match='trusted checkout storage'):
        with evidence.select([outside]):
            pytest.fail('recorded foreign allocation accepted')


@pytest.mark.parametrize('defect', ['none', 'unselected', 'outside', 'credential', 'parent-link', 'leaf-link', 'live-replacement'])
def test_plan_references_reuse_only_verified_exact_archived_members(evidence, defect):
    root = evidence.allocate({'result.json': b'exact proof'})
    source = root / 'result.json'
    archive = evidence.publish([root])['path']
    for _ in range(3):
        evidence.allocate({'later.json': b'later'})
    assert not source.exists()
    namespace = 'a' * 64
    bundle.plan_parent(evidence.checkout, namespace, create=True)
    reference = source
    if defect == 'unselected':
        reference = root / 'unselected.json'
    elif defect == 'outside':
        reference = evidence.checkout.parent / 'outside.json'
    elif defect == 'credential':
        reference = root / 'credentials.json'
    elif defect == 'parent-link':
        root.symlink_to(evidence.checkout.parent)
    elif defect == 'leaf-link':
        root.mkdir(mode=0o700)
        source.symlink_to(evidence.checkout / 'absent.json')
    elif defect == 'live-replacement':
        root.mkdir(mode=0o700)
        source.write_bytes(b'replacement')
    selection = bundle.Selection(evidence.checkout, os.geteuid(), os.getegid(), [], [], [],
                                 plan_namespace=namespace, references=[str(reference), archive])
    if defect in ('none', 'leaf-link', 'live-replacement'):
        # The selected archive owns this proof. Never open a later object at
        # its original pathname, including a replacement link.
        with selection:
            assert selection.files[str(source)][0]['sha256'] == bundle.digest(b'exact proof')
            assert selection.files[str(source)][1][0] == 'bundle'
    else:
        expected = (bundle.EvidenceUnavailable if defect == 'unselected' else
                    OSError if defect == 'parent-link' else ValueError)
        with pytest.raises(expected) as failure:
            with selection:
                pytest.fail('unsafe or unproven reference accepted')
        if defect != 'unselected':
            assert not isinstance(failure.value, bundle.EvidenceUnavailable)


@pytest.mark.parametrize('defect', ['none', 'legacy-files-only', 'partial-file-selection',
                                  'sibling-prefix', 'reappeared', 'wrong-target'])
def test_archived_directory_requires_complete_selected_tree(evidence, monkeypatch, defect):
    catalogue = bundle.Selection.catalogue
    def journals(selection, **options):
        entries = catalogue(selection, **options)
        if selection.plan_namespace is not None:
            journal = selection.publication_parent() / 'retention'
            if journal.exists():
                entries.append((journal, os.geteuid(), os.getegid()))
        return entries
    monkeypatch.setattr(bundle.Selection, 'catalogue', journals)
    root = evidence.allocate({'result.json': b'exact proof', 'nested/cleanup.json': b'cleaned'})
    paths = [root / 'result.json'] if defect == 'partial-file-selection' else [root]
    if defect == 'legacy-files-only':
        with evidence.select(paths) as selection:
            selection.manifest.pop('directories', None)
            selection.selection_sha256 = bundle.digest(bundle.encoded(selection.manifest))
            archive = bundle.export(selection, expected=selection.selection_sha256)['path']
    else:
        archive = evidence.publish(paths)['path']
    for _ in range(3):
        evidence.allocate({'later.json': b'later'})
    assert not root.exists()
    namespace = 'a' * 64
    bundle.plan_parent(evidence.checkout, namespace, create=True)
    reference = root.with_name(root.name[:-1]) if defect == 'sibling-prefix' else root
    if defect == 'reappeared':
        root.mkdir(mode=0o700)
    elif defect == 'wrong-target':
        original_context = bundle.Selection.reference_context
        def context(selection, path):
            if path == root / 'nested/cleanup.json':
                raise bundle.logical.EvidenceContextError('archived reference target does not match selection')
            return original_context(selection, path)
        monkeypatch.setattr(bundle.Selection, 'reference_context', context)
    selection = bundle.Selection(evidence.checkout, os.geteuid(), os.getegid(), [], [], [archive],
                                 plan_namespace=namespace, references=[str(reference)])
    if defect in ('none', 'reappeared'):
        with selection:
            assert set(selection.files) == {str(root / 'result.json'), str(root / 'nested/cleanup.json')}
            if defect == 'none':
                # The unused original may reappear while archived proof is pinned.
                root.mkdir(mode=0o700)
                selection.plan()
            renewed = bundle.export(selection, expected=selection.selection_sha256)['path']
        with bundle.Selection(evidence.checkout, os.geteuid(), os.getegid(), [], [], [renewed],
                              plan_namespace=namespace, references=[str(root)]) as carried:
            assert carried.directory_selections == selection.directory_selections
    else:
        expected = (ValueError if defect == 'wrong-target' else bundle.EvidenceUnavailable)
        with pytest.raises(expected):
            with selection:
                pytest.fail('unproven directory accepted')


@pytest.mark.parametrize('removed', ['some', 'all'])
def test_archived_directory_survives_original_changes_but_explicit_sources_are_checked(evidence, removed):
    root = evidence.allocate({'result.json': b'exact proof', 'cleanup.json': b'cleaned'})
    archive = evidence.publish([root])['path']
    (root / 'result.json').unlink()
    if removed == 'all':
        (root / 'cleanup.json').unlink()
    namespace = 'a' * 64
    bundle.plan_parent(evidence.checkout, namespace, create=True)
    with bundle.Selection(evidence.checkout, os.geteuid(), os.getegid(), [], [], [archive],
                          plan_namespace=namespace, references=[str(root)]) as selection:
        assert selection.files[str(root / 'result.json')][1][0] == 'bundle'
        renewed = bundle.export(selection, expected=selection.selection_sha256)['path']
    assert evidence.inspect(renewed, member=str(root / 'result.json')) == b'exact proof'
    with pytest.raises(ValueError, match='selected directory|conflicting evidence'):
        with bundle.Selection(evidence.checkout, os.geteuid(), os.getegid(), [], [str(root)], [archive],
                              plan_namespace=namespace):
            pytest.fail('changed explicit live directory accepted')
    assert evidence.inspect(archive, member=str(root / 'result.json')) == b'exact proof'


def test_reference_fallback_requires_plan_and_explicit_sources_keep_live_revalidation(evidence):
    root = evidence.allocate({'result.json': b'exact proof'})
    source = root / 'result.json'
    archive = evidence.publish([root])['path']
    with pytest.raises(ValueError, match='validated plan'):
        with bundle.Selection(evidence.checkout, os.geteuid(), os.getegid(), [], [], [],
                              references=[str(source), archive]):
            pytest.fail('unscoped fallback accepted')
    namespace = 'a' * 64
    bundle.plan_parent(evidence.checkout, namespace, create=True)
    with bundle.Selection(evidence.checkout, os.geteuid(), os.getegid(), [], [str(source)], [],
                          plan_namespace=namespace, references=[archive]) as selection:
        assert selection.files[str(source)][1][0] == 'source'
        source.write_bytes(b'changed after inventory')
        with pytest.raises(ValueError, match='identity changed'):
            bundle.export(selection, expected=selection.selection_sha256)


def test_cumulative_directory_cannot_adopt_file_valued_ancestor(evidence):
    root = evidence.allocate({'nested/result.json': b'exact proof'})
    directory = root / 'nested'
    first = evidence.publish([directory])['path']
    (directory / 'result.json').unlink()
    directory.rmdir()
    directory.write_bytes(b'later file at the old directory path')
    second = evidence.publish([directory])['path']
    with pytest.raises(ValueError, match='conflicting file and directory evidence'):
        with evidence.select(previous=[first, second]):
            pytest.fail('contradictory directory and file captures accepted')
    assert evidence.inspect(first, member=str(directory / 'result.json')) == b'exact proof'
    assert evidence.inspect(second, member=str(directory)) == directory.read_bytes()


@pytest.mark.parametrize('operation', ['plan', 'export'])
def test_inherited_receipt_change_invalidates_selected_archive(evidence, operation):
    root = evidence.allocate({'result.json': b'proof'})
    archive = Path(evidence.publish([root])['path'])
    with evidence.select(previous=[archive]) as selection:
        receipt = archive.parent / 'receipt.json'
        # An in-place receipt write leaves its containing directory unchanged.
        before = archive.parent.stat().st_mtime_ns
        receipt.write_bytes(b'{}')
        assert archive.parent.stat().st_mtime_ns == before
        with pytest.raises(ValueError, match='inherited receipt identity changed'):
            if operation == 'plan':
                selection.plan()
            else:
                bundle.export(selection, expected=selection.selection_sha256)


@pytest.mark.parametrize('kind', ['source', 'bundle'])
def test_missing_mandatory_inputs_never_become_renewable_references(evidence, kind):
    root = evidence.allocate({'result.json': b'proof'})
    path = root / 'result.json' if kind == 'source' else Path(evidence.publish([root])['path'])
    path.unlink()
    namespace = 'a' * 64
    bundle.plan_parent(evidence.checkout, namespace, create=True)
    with pytest.raises(FileNotFoundError) as failure:
        with bundle.Selection(evidence.checkout, os.geteuid(), os.getegid(), [],
                              [str(path)] if kind == 'source' else [],
                              [str(path)] if kind == 'bundle' else [], plan_namespace=namespace):
            pytest.fail('missing mandatory input accepted')
    assert not isinstance(failure.value, bundle.EvidenceUnavailable)


def test_public_recovery_removes_only_recorded_incomplete_stage(evidence, monkeypatch):
    root = evidence.allocate({'result.json': b'proof'})
    previous = [Path(evidence.publish([root])['path']) for _ in range(3)]
    original = (evidence.exports.path / 'current.json').read_bytes()
    remove = bundle.retention.remove
    def interrupted(record, *, validate_only=False):
        if not validate_only:
            raise KeyboardInterrupt('fixture interruption')
        return remove(record, validate_only=validate_only)
    with monkeypatch.context() as patch:
        patch.setattr(bundle.retention, 'remove', interrupted)
        with pytest.raises(KeyboardInterrupt):
            with evidence.exports.publication(projected_bytes=65536) as transaction:
                stage = transaction.allocate(tempfile.mkdtemp, prefix='onpc-evidence-bundle-',
                                             dir=evidence.exports.path.parent)
                (stage / 'incomplete').write_bytes(b'partial')
    bundle.recover(evidence.checkout, os.getuid(), os.getgid())
    assert not stage.exists()
    assert (evidence.exports.path / 'current.json').read_bytes() == original
    assert all(path.exists() for path in previous)


def logical_record(evidence, root, *, task='E02', check='exact', attempt='a' * 32,
                   inputs='1' * 64, target=''):
    """A producer draft bound to the fixture's real recorded file/owner."""
    import evidence_identity as logical
    with evidence.select([root]) as selected:
        files = selected.manifest['files']
        repository = selected.repository()
    info = evidence.sources.path.stat()
    owner = dict(repository_sha256=logical.digest(repository),
                 caller=dict(uid=os.geteuid(), gid=os.getegid()), journal=str(evidence.sources.path),
                 identity=dict(device=info.st_dev, inode=info.st_ino, mode=info.st_mode,
                               uid=info.st_uid, gid=info.st_gid))
    context = dict(repository=repository, workflow='fixture', owner=owner,
                   run=files[0]['allocation']['run'], task=task, check=check, attempt=attempt,
                   target=target, inputs_sha256=inputs, sources_sha256='2' * 64)
    return logical.finalize_record(dict(schema=logical.SCHEMA, version=1, context=context,
        status='passed', completeness='complete', dependencies=[],
        cleanup=dict(state='complete', record_members=[], scope=dict(owner=owner, resources=[])),
        members=[dict(role='result', original_path=entry['path'], source_allocation=entry['allocation'],
                      bytes=entry['bytes'], sha256=entry['sha256'], required=True) for entry in files]))


def publish_logical(evidence, records, sources=(), bundles=()):
    with bundle.Selection(evidence.checkout, os.geteuid(), os.getegid(), [],
                          list(map(str, sources)), list(map(str, bundles)),
                          logical_records=records) as selected:
        return bundle.export(selected, expected=selected.selection_sha256)


def exact_read(evidence, path, record, member=None, **options):
    return bundle.inspect(evidence.checkout, os.geteuid(), os.getegid(), str(path),
        record_id=record['record_id'], member_id=(member or record['members'][0])['member_id'],
        closure_sha256=record['closure_sha256'], **options)


def test_logical_identity_survives_physical_generations_and_rotation(evidence):
    root = evidence.allocate({'result.json': b'exact accepted proof'})
    record = logical_record(evidence, root)
    first = publish_logical(evidence, [record], [root])
    previous = first
    for _ in range(4):
        evidence.allocate({'later.json': b'unrelated'})
        previous = publish_logical(evidence, [], bundles=[previous['path']])
    assert not root.exists() and not Path(first['path']).exists()
    assert previous['schema'] == 2
    assert exact_read(evidence, previous['path'], record) == b'exact accepted proof'
    manifest = evidence.inspect(previous['path'])
    assert manifest['records'] == [record]
    assert manifest['member_map'][0]['original_provenance']['original_path'] == str(root / 'result.json')


@pytest.mark.parametrize('change', ['task', 'check', 'attempt', 'inputs', 'target'])
def test_same_bytes_and_basename_keep_distinct_logical_claims(evidence, change):
    first = evidence.allocate({'result.json': b'identical'})
    second = evidence.allocate({'result.json': b'identical'})
    record = logical_record(evidence, first)
    kwargs = {change: {'task': 'E03', 'check': 'other', 'attempt': 'b' * 32,
                       'inputs': '3' * 64, 'target': 'synthetic-target'}[change]}
    other = logical_record(evidence, second, **kwargs)
    output = publish_logical(evidence, [record, other], [first, second])
    assert record['record_id'] != other['record_id']
    assert record['members'][0]['member_id'] != other['members'][0]['member_id']
    assert exact_read(evidence, output['path'], record) == b'identical'
    assert exact_read(evidence, output['path'], other) == b'identical'
    with pytest.raises(bundle.LogicalEvidenceUnavailable):
        exact_read(evidence, output['path'], record, member=other['members'][0])


def test_wrong_existing_member_and_closure_do_not_supply_requested_result(evidence):
    root = evidence.allocate({'first.json': b'first', 'second.json': b'second'})
    record = logical_record(evidence, root)
    output = publish_logical(evidence, [record], [root])
    selected = record['members'][0]
    assert exact_read(evidence, output['path'], record, selected) == Path(selected['original_path']).read_bytes()
    with pytest.raises(ValueError, match='closure') as error:
        exact_read(evidence, output['path'], dict(record, closure_sha256='0' * 64))
    assert not isinstance(error.value, bundle.EvidenceUnavailable)
    for options in ({'record_id': record['record_id']}, {'member_id': selected['member_id']},
                    {'record_id': record['record_id'], 'member_id': selected['member_id'],
                     'closure_sha256': record['closure_sha256'], 'member': selected['original_path']}):
        with pytest.raises(ValueError):
            bundle.inspect(evidence.checkout, os.geteuid(), os.getegid(), output['path'], **options)


def test_legacy_schema_is_navigation_only_and_ambiguous_upgrades_refuse(evidence):
    root = evidence.allocate({'result.json': b'legacy proof'})
    record = logical_record(evidence, root)
    output = evidence.publish([root])
    assert 'schema' not in output
    with pytest.raises(ValueError, match='legacy navigation'):
        exact_read(evidence, output['path'], record)
    with evidence.select([root]) as selected:
        manifest = dict(selected.manifest, records=[], member_map=[])
    with pytest.raises(ValueError, match='manifest'):
        bundle.verify_stream(io.BytesIO(archive_bytes(manifest, b'legacy proof')))


def test_logical_manifest_cannot_adopt_another_checkout_or_conflicting_verdict(evidence):
    import evidence_identity as logical
    root = evidence.allocate({'result.json': b'proof'})
    record = logical_record(evidence, root)
    changed = {key: value for key, value in record.items() if key != 'closure_sha256'}
    changed['status'] = 'failed'
    changed = logical.finalize_record(changed)
    with pytest.raises(ValueError, match='conflicting logical record'):
        publish_logical(evidence, [record, changed], [root])
    foreign = logical.decoded(logical.encoded(record))
    foreign.pop('record_id')
    foreign.pop('closure_sha256')
    foreign['context']['repository']['inode'] += 1
    foreign['context']['owner']['repository_sha256'] = logical.digest(foreign['context']['repository'])
    foreign['cleanup']['scope']['owner'] = foreign['context']['owner']
    for member in foreign['members']:
        member.pop('member_id')
    foreign = logical.finalize_record(foreign)
    with pytest.raises(logical.EvidenceContextError, match='another checkout'):
        publish_logical(evidence, [foreign], [root])


def test_schema_two_never_invents_logical_origins_for_legacy_files(evidence):
    first = evidence.allocate({'result.json': b'proof'})
    record = logical_record(evidence, first)
    second = evidence.allocate({'unrelated.json': b'other'})
    with pytest.raises(ValueError, match='inventory'):
        publish_logical(evidence, [record], [first, second])


@pytest.mark.parametrize('schema', [1, 2])
@pytest.mark.parametrize('fault', ['boolean', 'tuple', 'short'])
def test_receipt_identity_requires_exact_integer_list(evidence, schema, fault):
    root = evidence.allocate({'result.json': b'proof'})
    info = (root / 'result.json').stat()
    fingerprint = bundle.fingerprint(info)
    receipt = dict(sha256='a' * 64, bytes=info.st_size, selection_sha256='b' * 64,
                   identity=list(fingerprint))
    if schema == 2:
        receipt['schema'] = 2
    if fault == 'boolean':
        receipt['identity'][5] = True  # Python equality alone aliases nlink=1.
    elif fault == 'tuple':
        receipt['identity'] = tuple(fingerprint)
    else:
        receipt['identity'].pop()
    with pytest.raises(ValueError, match='checksum'):
        bundle.verify_receipt(receipt, info, 'a' * 64)
