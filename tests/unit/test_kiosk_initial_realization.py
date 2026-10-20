"""Initial intent/copy preparation, without mounts or admission publication."""
import copy
import hashlib
from pathlib import Path

import pytest

from tests.support.kiosk_material import private_store, material_host


def test_all_required_consumers_have_independent_skeleton_parents(material_host):
    scene, helper = material_host, material_host.helper
    current = scene.measure()
    layout = helper.initial_directory_layout(current)
    nodes = {node['path']: node for node in layout}
    files = current['native'] + current['preserved'] + current['payload'] + [
        item for item in current['runtime'] if item['kind'] == 'file']
    for item in files:
        assert nodes[item['path']]['kind'] == 'file'
        for parent in Path(item['path']).parents:
            if parent not in (Path('/'), Path('/usr')):
                assert nodes[str(parent)]['kind'] == 'tree'
    mask = '/usr/share/confinement/user-units/masked.service'
    assert nodes[mask] == dict(path=mask, kind='link', link='/dev/null')
    assert '/dev/null' not in nodes
    assert not any(node['kind'] == 'directory' and any(
        Path(node['path']) in Path(item['path']).parents for item in files) for node in layout)


def test_bytecode_cache_is_checked_but_never_bound_into_initial_view(material_host):
    scene, helper = material_host, material_host.helper
    directory = scene.physical('/usr/lib/oh-no-parent-control/kiosk/__pycache__')
    directory.mkdir(mode=0o755)
    bytecode = directory / 'main.cpython-313.pyc'
    bytecode.write_bytes(b'validated-unconsumed-cache')
    bytecode.chmod(0o644)
    current = scene.measure()
    layout = helper.initial_directory_layout(current)
    assert not any('__pycache__' in node['path'] for node in layout)
    (directory / 'foreign.py').write_bytes(b'unknown-code')
    with pytest.raises(ValueError, match='runtime-membership'):
        scene.measure()


def test_initial_plan_retains_exact_copy_indices_and_original_native_sources(material_host):
    scene, helper = material_host, material_host.helper
    current = scene.measure()
    with helper.InitialPreparation(scene.fixture.store, current) as attempt:
        plan = attempt.plan()
        assert plan['material'] == current['digest']
        assert 'native_copies_pending' not in plan
        assert plan['native']['records'] == current['native']
        assert plan['native']['copies'] == attempt.native_copies
        assert not {'view', 'invocation', 'ready'} & plan.keys()
        copy_root = scene.fixture.store / attempt.publication.name
        assert [source['source_index'] for source in plan['sources'].values()] == list(
            range(len(plan['sources'])))
        for path, source in plan['sources'].items():
            if source['source_class'] in ('runtime', 'payload'):
                record = attempt.receipt['records'][source['index']]
                target = copy_root / source['name']
                original = scene.physical(path)
                assert record['path'] == path
                assert hashlib.sha256(target.read_bytes()).hexdigest() == record['sha256']
                assert target.stat().st_ino != original.stat().st_ino
                assert list(helper.file_identity(helper.os.stat(target))) == source['copy_identity']
                assert source['assertion'] == list(current['assertions'].get(
                    path, current['runtime_assertions'].get(path)))
            elif source['source_class'] == 'native':
                record = current['native'][source['index']]
                member = plan['native']['copies'][source['index']]
                assert 'copy_pending' not in source
                assert source['name'] == member['name'] == 'native-' + str(source['index'])
                assert source['path'] == record.get('source', path)
                assert source['assertion'] == list(current['assertions'][source['path']])
                target = copy_root / source['name']
                assert target.read_bytes() == scene.physical(source['path']).read_bytes()
                assert hashlib.sha256(target.read_bytes()).hexdigest() == record['sha256']
                assert target.stat().st_ino != scene.physical(source['path']).stat().st_ino
                assert target.stat().st_nlink == 1
                assert list(helper.file_identity(helper.os.stat(target))) == source['copy_identity']
                assert target.stat().st_mode & 0o7777 == record['mode']
                assert source['source_index'] != source['index']
        payload = str(helper.PAYLOAD / 'config.json')
        assert plan['sources'][payload]['source_class'] == 'payload'
        assert plan['sources']['/usr/lib/helper']['source_class'] == 'vendor'
        assert not (copy_root / 'ready').exists()
    assert not list(scene.fixture.store.iterdir())


def test_initial_native_substitution_keeps_separate_origin_and_destination(material_host):
    scene, helper = material_host, material_host.helper
    scene.config['executables'][0]['source'] = '/usr/lib/library.so'
    current = scene.measure()
    with helper.InitialPreparation(scene.fixture.store, current) as attempt:
        source = attempt.plan()['sources']['/usr/bin/native']
        assert source['path'] == '/usr/lib/library.so'
        assert source['record']['path'] == '/usr/bin/native'
        assert source['assertion'] == list(current['assertions']['/usr/lib/library.so'])
        target = scene.fixture.store / attempt.publication.name / source['name']
        assert target.read_bytes() == scene.physical('/usr/lib/library.so').read_bytes()
        assert target.stat().st_ino != scene.physical('/usr/lib/library.so').stat().st_ino


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('fault', ['bytes', 'hash', 'mode', 'replacement', 'receipt-index', 'role',
                                  'hardlink', 'capability', 'label'])
def test_initial_native_copy_refuses_independent_tampering(material_host, monkeypatch, backend, fault):
    scene, helper = material_host, material_host.helper
    scene.config['backend'] = backend
    if backend == 'selinux':
        # material_host starts with AppArmor's absent vendor label. Declare
        # this fixture's ordinary SELinux helper label before attestation;
        # preserved_inventory must still compare it against the inode label.
        scene.config['preserved_executables'][0]['label'] = 'system_u:object_r:lib_t:s0'
        scene.inputs()
        policy = scene.payload / 'onpc-kiosk.cil'
        policy.write_bytes((scene.payload / 'onpc-kiosk.apparmor').read_bytes())
        policy.chmod(0o644)
    current = scene.measure()
    with helper.InitialPreparation(scene.fixture.store, current) as attempt:
        member = attempt.native_copies[0]
        record = attempt.snapshot['native'][0]
        target = scene.fixture.store / attempt.publication.name / member['name']
        key = target.stat().st_dev, target.stat().st_ino
        if backend == 'selinux':
            assert scene.fixture.labels[key] == record['label']
            assert ':onpc_kiosk_' + record['role'].replace('-', '_') + '_exec_t:' in record['label']
            # Supporting copies keep their ordinary labels, never native roles.
            assert all(':onpc_kiosk_' not in item['label'] for item in attempt.records
                       if item['kind'] == 'file')
        if fault == 'bytes':
            target.write_bytes(b'foreign-native-bytes')
        elif fault == 'hash':
            before = target.stat()
            data = target.read_bytes()
            target.write_bytes(bytes([data[0] ^ 1]) + data[1:])
            # Freeze the transaction assertion only: the digest still reads
            # actual private bytes and must independently detect this change.
            scene.fixture.overrides[str(target)] = dict(
                st_mtime_ns=before.st_mtime_ns, st_ctime_ns=before.st_ctime_ns)
        elif fault == 'mode':
            target.chmod(0o666)
        elif fault == 'replacement':
            original = target.with_name('displaced-native')
            target.rename(original)
            target.write_bytes(original.read_bytes())
            target.chmod(record['mode'])
        elif fault == 'receipt-index':
            member['index'] = len(attempt.native_copies)
        elif fault == 'role':
            record['role'] = 'session' if record['role'] != 'session' else 'service'
        elif fault == 'hardlink':
            extra = target.with_name('extra-hardlink')
            helper.os.link(target, extra)
        elif fault == 'capability':
            original_list = helper.os.listxattr
            monkeypatch.setattr(helper.os, 'listxattr', lambda fd:
                ['security.capability'] if scene.fixture.fd_path(fd) == target else original_list(fd))
        elif backend == 'selinux':
            scene.fixture.labels[key] = 'system_u:object_r:onpc_kiosk_session_exec_t:s0'
        else:
            record['label'] = 'system_u:object_r:onpc_kiosk_session_exec_t:s0'
        try:
            with pytest.raises(ValueError):
                attempt.verify()
        finally:
            if fault == 'mode':
                target.chmod(0o755)
            elif fault == 'replacement':
                target.unlink()
                original.rename(target)
            elif fault == 'hardlink':
                extra.unlink()
    assert not list(scene.fixture.store.iterdir())


def test_supporting_only_publication_refuses_unchecked_native_members(material_host):
    scene, helper = material_host, material_host.helper
    with helper.InitialPreparation(scene.fixture.store, scene.measure()) as attempt:
        attempt.verify()
        with pytest.raises(ValueError, match='runtime-membership'):
            attempt.publication.publish('a' * 64, attempt.receipt)
        assert not attempt.publication.published
        ticket = attempt.ticket()
        assert {member['name'] for member in attempt.native_copies} <= ticket['members'].keys()
    assert not list(scene.fixture.store.iterdir())


def test_detach_transfers_only_exact_incomplete_copy_ticket(material_host):
    scene, helper = material_host, material_host.helper
    with helper.InitialPreparation(scene.fixture.store, scene.measure()) as attempt:
        ticket = attempt.ticket()
        assert attempt.detach() == ticket
        assert attempt.publication is None
        with pytest.raises(ValueError, match='runtime-publication-replaced'):
            attempt.detach()
    scratch = scene.fixture.store / ticket['name']
    assert scratch.is_dir()
    assert not (scratch / 'ready').exists()
    helper.reclaim_runtime_scratch(scene.fixture.store, ticket)
    assert not list(scene.fixture.store.iterdir())


def test_failed_transfer_verification_keeps_python_cleanup_ownership(material_host):
    scene, helper = material_host, material_host.helper
    with helper.InitialPreparation(scene.fixture.store, scene.measure()) as attempt:
        target = scene.fixture.store / attempt.publication.name / attempt.native_copies[0]['name']
        target.write_bytes(b'changed before native transfer')
        with pytest.raises(ValueError, match='runtime-copy-identity|runtime-copy-changed'):
            attempt.detach()
        assert attempt.publication is not None
    assert not list(scene.fixture.store.iterdir())


def test_failed_native_copy_removes_only_owned_scratch(material_host, monkeypatch):
    scene, helper = material_host, material_host.helper
    current = scene.measure()
    original = helper.runtime_read_digest

    def fail_native_write(fd, size, *, target=-1):
        if target >= 0 and scene.fixture.fd_path(target).name.startswith('native-'):
            raise OSError('injected-native-write-failure')
        return original(fd, size, target=target)

    monkeypatch.setattr(helper, 'runtime_read_digest', fail_native_write)
    with pytest.raises(OSError, match='injected-native-write-failure'):
        helper.InitialPreparation(scene.fixture.store, current)
    assert not list(scene.fixture.store.iterdir())


@pytest.mark.parametrize('fault', ['bytes', 'mode', 'replacement', 'receipt-index'])
def test_initial_supporting_copy_refuses_independent_tampering(material_host, fault):
    scene, helper = material_host, material_host.helper
    current = scene.measure()
    with helper.InitialPreparation(scene.fixture.store, current) as attempt:
        member = attempt.receipt['copies'][0]
        target = scene.fixture.store / attempt.publication.name / member['name']
        if fault == 'bytes':
            target.write_bytes(b'foreign-bytes')
        elif fault == 'mode':
            target.chmod(0o666)
        elif fault == 'receipt-index':
            member['index'] = len(attempt.records)
        else:
            # Preserve the owned inode for exact cleanup after observing refusal.
            original = target.with_name('displaced')
            target.rename(original)
            target.write_bytes(original.read_bytes())
            target.chmod(0o644)
        try:
            with pytest.raises(ValueError):
                attempt.verify()
        finally:
            if fault == 'mode':
                target.chmod(0o644)
            elif fault == 'replacement':
                target.unlink()
                original.rename(target)
    assert not list(scene.fixture.store.iterdir())


def test_source_replacement_refuses_even_though_owned_copy_keeps_bytes(material_host):
    scene, helper = material_host, material_host.helper
    current = scene.measure()
    with helper.InitialPreparation(scene.fixture.store, current) as attempt:
        path = '/usr/bin/oh-no-parent-control'
        source = attempt.sources[path]
        target = scene.fixture.store / attempt.publication.name / source['name']
        copied = target.read_bytes()
        host = scene.physical(path)
        replacement = host.with_name('replacement')
        replacement.write_bytes(host.read_bytes())
        replacement.chmod(0o755)
        replacement.replace(host)
        assert target.read_bytes() == copied
        with pytest.raises(ValueError, match='changed'):
            attempt.verify()


@pytest.mark.parametrize('kind', ['file', 'directory', 'link'])
@pytest.mark.parametrize('transition', ['disappear', 'mode', 'owner', 'replace', 'sibling-metadata'])
def test_late_ambient_changes_keep_frozen_intent_for_native_narrowing(material_host, kind, transition):
    scene, helper = material_host, material_host.helper
    path = '/usr/bin/unrelated'
    host = scene.physical(path)
    if kind == 'directory':
        host.mkdir(mode=0o755)
    elif kind == 'link':
        host.symlink_to('unconsumed-target')
    else:
        host.write_bytes(b'original-ambient-inode')
        host.chmod(0o644)
    current = scene.measure()
    with helper.InitialPreparation(scene.fixture.store, current) as attempt:
        original = attempt.plan()
        source = original['sources'][path]
        assert source['source_class'] == 'ambient'
        assert source['required'] is False
        if transition == 'disappear':
            host.rmdir() if kind == 'directory' else host.unlink()
        elif transition == 'mode':
            scene.fixture.overrides[str(host)] = {'st_mode': host.lstat().st_mode | 0o022}
        elif transition == 'owner':
            scene.fixture.overrides[str(host)] = {'st_uid': 1234}
        elif transition == 'replace':
            # Retain the original inode so allocation cannot reuse its number.
            host.rename(host.with_name('displaced-ambient'))
            host.write_bytes(b'new-host-source-must-not-enter-plan')
            host.chmod(0o644)
            assert host.stat().st_ino != source['assertion'][1]
        else:
            sibling = host / 'new-child' if kind == 'directory' else host.with_name('new-sibling')
            sibling.write_bytes(b'ambient-metadata-change')
            sibling.chmod(0o644)
        # Native must still observe/bind the original indexed source or narrow
        # actual V. Revalidating intent neither imports replacements nor claims
        # that any source was acquired, mounted or actually omitted.
        fresh = attempt.plan()
        assert fresh == original
        assert fresh['sources'][path]['assertion'] == source['assertion']
        assert not {'view', 'invocation', 'ready'} & fresh.keys()


@pytest.mark.parametrize('transition', ['disappear', 'mode', 'owner', 'replace'])
def test_required_equivalent_of_ambient_change_still_refuses(material_host, transition):
    scene, helper = material_host, material_host.helper
    current = scene.measure()
    host = scene.physical('/usr/bin/native')
    with helper.InitialPreparation(scene.fixture.store, current) as attempt:
        if transition == 'disappear':
            host.unlink()
        elif transition == 'mode':
            host.chmod(0o777)
        elif transition == 'owner':
            scene.fixture.overrides[str(host)] = {'st_uid': 1234}
        else:
            replacement = host.with_name('required-replacement')
            replacement.write_bytes(host.read_bytes())
            replacement.chmod(0o755)
            replacement.replace(host)
        with pytest.raises((ValueError, OSError)):
            attempt.plan()


@pytest.mark.parametrize('transition', ['disappear', 'unsafe', 'replace'])
def test_ambient_change_after_inventory_never_reopens_a_new_source(material_host, monkeypatch, transition):
    scene, helper = material_host, material_host.helper
    path = '/usr/bin/ambient-race'
    host = scene.physical(path)
    host.write_bytes(b'original-before-layout')
    host.chmod(0o644)
    current = scene.measure()
    identity = list(helper.file_identity(host.lstat()))
    layout = helper.initial_directory_layout

    def change_after_capture(snapshot, **kwargs):
        result = layout(snapshot, **kwargs)
        if transition == 'disappear':
            host.unlink()
        elif transition == 'unsafe':
            host.chmod(0o777)
        else:
            host.rename(host.with_name('original-ambient-race'))
            host.write_bytes(b'new-after-layout')
            host.chmod(0o644)
        return result

    monkeypatch.setattr(helper, 'initial_directory_layout', change_after_capture)
    with helper.InitialPreparation(scene.fixture.store, current) as attempt:
        source = attempt.plan()['sources'][path]
        assert source['assertion'] == identity
        assert source['source_class'] == 'ambient'


def test_masked_ambient_directory_is_not_revived_by_later_trust_restore(material_host):
    scene, helper = material_host, material_host.helper
    path = '/usr/bin/masked-ambient'
    host = scene.physical(path)
    host.mkdir(mode=0o777)
    host.chmod(0o777)
    current = scene.measure()
    with helper.InitialPreparation(scene.fixture.store, current) as attempt:
        original = attempt.plan()
        assert original['sources'][path]['kind'] == 'empty-directory'
        assert original['sources'][path]['source_class'] == 'ambient'
        assert 'assertion' not in original['sources'][path]
        host.chmod(0o755)
        assert attempt.plan() == original


def test_static_initial_plan_mutation_refuses_without_reobserving_ambient(material_host):
    scene, helper = material_host, material_host.helper
    current = scene.measure()
    with helper.InitialPreparation(scene.fixture.store, current) as attempt:
        attempt.sources['/usr']['required'] = False
        with pytest.raises(ValueError, match='material-source-changed'):
            attempt.verify()


def test_plan_copy_does_not_mutate_frozen_required_material(material_host):
    scene, helper = material_host, material_host.helper
    current = scene.measure()
    with helper.InitialPreparation(scene.fixture.store, current) as attempt:
        plan = attempt.plan()
        plan['sources'].clear()
        plan['layout'].clear()
        plan['runtime']['copies'].clear()
        plan['native']['copies'].clear()
        plan['native']['records'].clear()
        current['record']['config'] = '0' * 64
        fresh = attempt.plan()
        assert fresh['sources'] and fresh['layout'] and fresh['runtime']['copies']
        assert fresh['native']['copies'] and fresh['native']['records']
        assert fresh['material'] == attempt.snapshot['digest']


@pytest.mark.parametrize('budget', ['rows', 'native-bytes', 'runtime-bytes', 'payload-bytes'])
def test_initial_plan_shares_total_row_and_copy_byte_limits(material_host, monkeypatch, budget):
    scene, helper = material_host, material_host.helper
    current = scene.measure()
    layout = helper.initial_directory_layout(current)
    rows, copied = helper.initial_material_budget(current, layout)
    if budget == 'rows':
        monkeypatch.setattr(helper, 'MAX_ROWS', rows - 1)
    else:
        group = {'native-bytes': 'native', 'runtime-bytes': 'runtime', 'payload-bytes': 'payload'}[budget]
        altered = copy.deepcopy(current)
        item = next(item for item in altered[group] if 'size' in item)
        item['size'] += helper.MAX_COPY_BYTES - copied + 1
        current = altered
    with pytest.raises(ValueError, match='material-limit'):
        helper.initial_material_budget(current, layout)


def test_initial_plan_refuses_overlapping_native_and_runtime_classes(material_host):
    scene, helper = material_host, material_host.helper
    current = scene.measure()
    current['native'][0]['path'] = '/usr/bin/oh-no-parent-control'
    with pytest.raises(ValueError, match='retained-layout'):
        helper.initial_material_budget(current)


def test_failed_final_required_verification_removes_only_owned_scratch(material_host, monkeypatch):
    scene, helper = material_host, material_host.helper
    current = scene.measure()
    verify = helper.verify_required_material
    calls = 0

    def fail_final(snapshot):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise ValueError('material-source-changed')
        return verify(snapshot)

    monkeypatch.setattr(helper, 'verify_required_material', fail_final)
    with pytest.raises(ValueError, match='material-source-changed'):
        helper.InitialPreparation(scene.fixture.store, current)
    assert calls == 3
    assert not list(scene.fixture.store.iterdir())


def test_initial_plan_keeps_unrecorded_foreign_member_and_cleanup_ticket(material_host):
    scene, helper = material_host, material_host.helper
    current = scene.measure()
    ticket = None
    with pytest.raises(ValueError, match='runtime-recovery-membership'):
        with helper.InitialPreparation(scene.fixture.store, current) as attempt:
            ticket = attempt.ticket()
            foreign = scene.fixture.store / attempt.publication.name / 'foreign'
            foreign.write_bytes(b'foreign-owner')
            foreign.chmod(0o600)
            identity = foreign.stat().st_dev, foreign.stat().st_ino
    assert (foreign.stat().st_dev, foreign.stat().st_ino) == identity
    # This test created the exact foreign member; remove only that recorded inode
    # before exercising the retained, original scratch recovery ticket.
    foreign.unlink()
    helper.reclaim_runtime_scratch(scene.fixture.store, ticket)
    assert not list(scene.fixture.store.iterdir())


def test_initial_plan_is_not_wired_into_live_preparation(material_host):
    helper = material_host.helper
    assert 'InitialPreparation' not in helper.prepare.__code__.co_names
    assert 'initial_directory_layout' not in helper.prepare.__code__.co_names
