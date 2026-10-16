"""Real-file, unprivileged qualification of finite evidence preservation."""

import hashlib
import io
import os
from pathlib import Path
import stat
import tempfile
from contextlib import nullcontext
from types import SimpleNamespace
import zipfile

import pytest

import evidence_bundle as bundle


@pytest.mark.parametrize('targets', [[], ['guest-one'], ['guest-two', 'guest-one']])
def test_catalogue_includes_only_selected_targets_host_and_guest_journals(
        tmp_path, monkeypatch, targets):
    import vm_config

    state = tmp_path / 'state'
    state.mkdir()
    for name in ('retention-host', 'retention-batch', 'retention', 'standalone-reports',
                 'retention-guest-one', 'retention-guest-two', 'retention-unregistered'):
        (state / name).mkdir()
    uid, gid = os.geteuid(), os.getegid()
    # Exercise the privileged catalogue without changing this test process's
    # identity or accessing any real journals, VM, or registry entries.
    monkeypatch.setattr(bundle, 'os', SimpleNamespace(**(vars(os) | {'geteuid': lambda: 0})))
    monkeypatch.setattr(bundle, 'identity', lambda *_: nullcontext())
    monkeypatch.setattr(bundle.storage, 'directory', lambda kind, **_: tmp_path / kind)
    monkeypatch.setattr(vm_config, 'registry', lambda: {'guest-one': None, 'guest-two': None})
    selection = bundle.Selection(tmp_path, uid, gid, targets, [], [])
    journals = selection.catalogue()
    fixed = {'retention-host', 'retention-batch', 'retention', 'standalone-reports'}
    assert {(path.name, owner, group) for path, owner, group in journals} == {
        *((name, uid, gid) for name in fixed),
        *((f'retention-{target}', uid, gid) for target in targets),
        *((f'retention-{uid}-{target}', 0, 0) for target in targets),
    }
    assert len(journals) == len(fixed) + 2 * len(targets)
    with pytest.raises(ValueError, match='registered canonical targets'):
        bundle.Selection(tmp_path, uid, gid, ['unregistered'], [], []).catalogue()


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    storage, retention = bundle.storage, bundle.retention
    monkeypatch.delenv(retention.VARIABLE, raising=False)
    checkout = tmp_path / 'checkout'
    checkout.mkdir(mode=0o700)
    monkeypatch.setattr(storage, 'ROOT', checkout)
    monkeypatch.setattr(storage, 'BASE', checkout / 'output/test-runs')
    sources = retention.Store(storage.directory('state') / 'retention-fixture')
    exports = retention.Store(storage.directory('exports') / 'retention')
    uid, gid = os.geteuid(), os.getegid()

    def catalogue(self):
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


def test_failed_publication_preserves_all_exports_and_allows_retry(evidence, monkeypatch):
    root = evidence.allocate({'result.json': b'original proof'})
    outputs = [Path(evidence.publish([root])['path']) for _ in range(3)]
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


def test_private_key_contents_are_refused_across_read_boundary(evidence):
    root = evidence.allocate({'ordinary.log': b'x' * (65536 - 10)
                              + b'-----BEGIN OPENSSH PRIVATE KEY-----\nsecret'})
    with pytest.raises(ValueError, match='private key'):
        with evidence.select([root]):
            pytest.fail('private key content accepted')


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


def test_oversized_source_and_stale_plan_are_refused(evidence, monkeypatch):
    root = evidence.allocate({'result.json': b'proof'})
    with evidence.select([root]) as selection:
        with pytest.raises(ValueError, match='selection changed'):
            bundle.export(selection, expected='0' * 64)
    monkeypatch.setattr(bundle, 'MAX_BYTES', 4)
    with pytest.raises(ValueError, match='limit'):
        with evidence.select([root]):
            pytest.fail('oversized source accepted')


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
                                  'size', 'duplicate-path', 'private-path', 'oversized-manifest'])
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


@pytest.mark.parametrize('options', [{'offset': -1}, {'count': -1}, {'count': 16 * 1024 ** 2 + 1},
                                   {'offset': True}, {'member': '../../escape'},
                                   {'member': 'files/00000000'}])
def test_inspection_refuses_unsafe_ranges_and_unselected_paths(evidence, options):
    root = evidence.allocate({'result.json': b'proof'})
    output = Path(evidence.publish([root])['path'])
    with pytest.raises(ValueError):
        evidence.inspect(output, **options)
    assert evidence.inspect(output, member=str(root / 'result.json'), offset=100) == b''


def test_archive_size_and_duplicate_member_names_are_refused(evidence, monkeypatch):
    root = evidence.allocate({'result.json': b'proof'})
    with evidence.select([root]) as selection:
        manifest = selection.manifest
    data = archive_bytes(manifest)
    with monkeypatch.context() as patch:
        patch.setattr(bundle, 'MAX_BYTES', len(data) - 1)
        with pytest.raises(ValueError, match='archive exceeds'):
            bundle.verify_stream(io.BytesIO(data))
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
    root = evidence.allocate({'result.json': b'proof'})
    previous = [Path(evidence.publish([root])['path']) for _ in range(3)]
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
    root = evidence.allocate({'result.json': b'proof'})
    previous = [Path(evidence.publish([root])['path']) for _ in range(3)]
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
