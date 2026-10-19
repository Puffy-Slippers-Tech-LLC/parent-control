"""Unwired immutable runtime copies; private files and descriptor witnesses only."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
from types import SimpleNamespace

import pytest

from tests.support.paths import ROOT


def load_helper():
    spec = importlib.util.spec_from_file_location('private_kiosk_pin_storage',
                                                ROOT / 'tools/kiosk_confinement.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


@pytest.fixture
def private_store(tmp_path, monkeypatch):
    helper = load_helper()
    host, store = tmp_path / 'host', tmp_path / 'store'
    host.mkdir(mode=0o755)
    store.mkdir(mode=0o700)
    overrides, labels = {}, {}
    raw_os = os

    def metadata(info, path):
        values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
        values.update(st_uid=0, st_gid=0)
        # The test launcher owns fixture ancestors. The product still checks
        # every real child mode, inode, timestamp, link count and membership.
        if path == tmp_path or path in tmp_path.parents:
            values['st_mode'] &= ~0o7022
        values.update(overrides.get(str(path), {}))
        return SimpleNamespace(**values)

    def fd_path(fd):
        return Path(raw_os.readlink('/proc/self/fd/' + str(fd)).removesuffix(' (deleted)'))

    def fstat(fd):
        return metadata(raw_os.fstat(fd), fd_path(fd))

    def stat_path(path, *, dir_fd=None, follow_symlinks=True):
        actual = Path(path)
        if dir_fd is not None:
            actual = fd_path(dir_fd) / actual
        return metadata(raw_os.stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks), actual)

    def label_key(fd):
        info = raw_os.fstat(fd)
        return info.st_dev, info.st_ino

    def policy_label(path, mode):
        typ = ('bin_t' if path.startswith('/usr/bin/') else
               'systemd_unit_file_t' if '/user-units/' in path else
               'usr_t' if '/share/' in path else 'lib_t')
        return 'system_u:object_r:' + typ + ':s0'

    def default_label(fd):
        path = fd_path(fd)
        if host in path.parents:
            return policy_label('/' + str(path.relative_to(host)), raw_os.fstat(fd).st_mode)
        return helper.RUNTIME_CONTEXT.decode()

    def getxattr(fd, name):
        assert name == 'security.selinux'
        return (labels.get(label_key(fd), default_label(fd)) + '\0').encode()

    def setxattr(fd, name, value):
        assert name == 'security.selinux'
        labels[label_key(fd)] = value.rstrip(b'\0').decode()

    proxy = SimpleNamespace(**{name: getattr(raw_os, name) for name in dir(raw_os)})
    proxy.fstat, proxy.stat = fstat, stat_path
    proxy.getxattr, proxy.setxattr = getxattr, setxattr
    proxy.listxattr = lambda fd: []
    monkeypatch.setattr(helper, 'os', proxy)
    monkeypatch.setattr(helper, 'runtime_policy_label', policy_label)
    actual_open = helper.runtime_open

    def source_open(path, **kwargs):
        text = str(path)
        return actual_open(host / text.lstrip('/') if text == '/usr' or text.startswith('/usr/')
                           else path, **kwargs)

    monkeypatch.setattr(helper, 'runtime_open', source_open)
    return SimpleNamespace(helper=helper, host=host, store=store, overrides=overrides,
                           labels=labels, fd_path=fd_path, label_key=label_key,
                           policy_label=policy_label, actual_open=actual_open)


def named_fixture(fixture):
    specs = {
        '/usr/bin/oh-no-parent-control': {'kind': 'file', 'role': 'script'},
        '/usr/lib/oh-no-parent-control/kiosk': {'kind': 'directory', 'role': 'module'},
        '/usr/lib/oh-no-parent-control/kiosk/main.py': {'kind': 'file', 'role': 'module'},
        '/usr/share/extension/wellbeingLogic.mjs': {'kind': 'file', 'role': 'wellbeing'},
        '/usr/share/extension/schemas/gschemas.compiled': {'kind': 'file', 'role': 'wellbeing'},
        '/usr/share/confinement/user-units': {'kind': 'directory', 'role': 'unit'},
        '/usr/share/confinement/user-units/service.conf': {'kind': 'file', 'role': 'unit'},
        '/usr/share/confinement/user-units/masked.service': {
            'kind': 'link', 'role': 'unit', 'link': '/dev/null'},
        '/usr/share/confinement/session-data': {'kind': 'directory', 'role': 'session-data'},
        '/usr/share/confinement/session-data/service': {'kind': 'file', 'role': 'session-data'},
    }
    for path, spec in sorted(specs.items()):
        target = fixture.host / path.lstrip('/')
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if spec['kind'] == 'directory':
            target.mkdir(mode=0o755, exist_ok=True)
        elif spec['kind'] == 'link':
            target.symlink_to(spec['link'])
        else:
            target.write_bytes(('original:' + path).encode())
            target.chmod(0o755 if spec['role'] == 'script' else 0o644)
    # pathlib's parents=True uses the ambient umask for intermediate parents,
    # rather than the leaf's explicit mode. Model package-installed ancestry
    # before any test deliberately mutates it, independent of a host umask002.
    for directory in fixture.host.rglob('*'):
        if directory.is_dir() and not directory.is_symlink():
            directory.chmod(0o755)
    return specs


def test_runtime_membership_matches_maintained_package_map(tmp_path):
    helper = load_helper()
    makefile = (ROOT / 'Makefile').read_text()

    def source_names(variable):
        return {name.removesuffix('.py') for line in makefile.splitlines()
                if re.match(variable + r'\s*(?::=|\+=)', line)
                for name in line.split('=', 1)[1].split() if name.endswith('.py')}

    assert set(helper.RUNTIME_KIOSK_MODULES) == source_names('KIOSK_SOURCES')
    assert set(helper.RUNTIME_COMMON_MODULES) == source_names('COMMON_SOURCES')
    assert set(helper.RUNTIME_LOCALES) == {path.stem for path in (ROOT / 'po').glob('*.po')}
    expected_release = {}
    for path in (ROOT / 'po/whats-new').glob('*/*.po'):
        expected_release.setdefault(path.parent.name, set()).add(path.stem)
    assert {release: set(languages) for release, languages in helper.RUNTIME_RELEASE_CATALOGS.items()} == expected_release
    for distribution in ('ubuntu', 'fedora'):
        specs = helper.runtime_input_specs(distribution)
        helper.runtime_specs_valid(specs)
        for name in ('feedback.css', 'rich_editor/application_ui.js', 'rich_editor/quill.js',
                     'rich_editor/quill.snow.css', 'rich_editor/quill.js.LICENSE.txt',
                     'rich_editor/LICENSE'):
            assert '/usr/lib/oh-no-parent-control/common/oh_no_parent_control_ui/' + name in specs
        for name in ('request-options.json', 'lava-heat.bin', 'kiosk-background-still.png',
                     'kiosk-background-scenery-clear.png', 'fonts/Monocraft.ttf', 'fonts/OFL.txt'):
            assert '/usr/lib/oh-no-parent-control/kiosk/oh_no_parent_control_kiosk/' + name in specs
        assert (str(helper.PAYLOAD / 'session-data') in specs) is (distribution == 'ubuntu')
        assert not any('/__pycache__' in path for path in specs)
        assert '/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/extension.js' not in specs
        policy_spec = importlib.util.spec_from_file_location('private_runtime_policy',
                                                           ROOT / 'tools/kiosk_confinement_policy.py')
        policy = importlib.util.module_from_spec(policy_spec)
        policy_spec.loader.exec_module(policy)
        generated = tmp_path / distribution
        policy.generate(generated, distribution)
        for subtree in ('user-units', 'session-data'):
            expected = {str(helper.PAYLOAD / subtree)} | {
                str(helper.PAYLOAD / path.relative_to(generated))
                for path in (generated / subtree).rglob('*')}
            if not (generated / subtree).exists():
                expected = set()
            assert {path for path in specs if path == str(helper.PAYLOAD / subtree) or
                    path.startswith(str(helper.PAYLOAD / subtree) + '/')} == expected


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
def test_independent_named_copies_survive_original_write_unlink_and_replacement(private_store, backend):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, backend)
    with helper.RuntimeCopyPublication(fixture.store, backend, specs) as attempt:
        receipt = attempt.copy(records, assertions)
        before = {}
        for item in receipt['copies']:
            record = records[item['index']]
            original = fixture.host / record['path'].lstrip('/')
            private = fixture.store / attempt.name / item['name']
            before[item['name']] = private.read_bytes()
            assert private.stat().st_ino != original.stat().st_ino
            assert private.stat().st_nlink == 1
            original.write_bytes(b'host-write')
            original.unlink()
            original.write_bytes(b'host-replacement')
            if backend == 'selinux':
                assert fixture.labels[(private.stat().st_dev, private.stat().st_ino)] == record['label']
        helper.verify_runtime_copies(attempt.fd, receipt, backend, specs)
        name = 'a' * 64
        attempt.publish(name, receipt)
        assert {path.name: path.read_bytes() for path in (fixture.store / name).iterdir()
                if path.name != 'runtime.json'} == before
        completed = fixture.store / name
    # This independently opened publication survives closure of all producer
    # descriptors and never consults any now-replaced host source path.
    fd = helper.runtime_open(completed, directory=True)
    try:
        helper.verify_runtime_copies(fd, receipt, backend, specs)
    finally:
        os.close(fd)
    assert completed.is_dir()


@pytest.mark.parametrize('fault', ['content', 'mode', 'owner', 'label', 'member', 'record', 'hardlink'])
def test_private_copy_or_receipt_mutation_refuses_without_repair(private_store, fault):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'selinux')
    attempt = helper.RuntimeCopyPublication(fixture.store, 'selinux', specs)
    try:
        receipt = attempt.copy(records, assertions)
        private = fixture.store / attempt.name / receipt['copies'][0]['name']
        if fault == 'content':
            private.write_bytes(b'changed')
        elif fault == 'mode':
            private.chmod(0o666)
        elif fault == 'owner':
            fixture.overrides[str(private)] = {'st_uid': 1234}
        elif fault == 'label':
            fixture.labels[(private.stat().st_dev, private.stat().st_ino)] = 'system_u:object_r:usr_t:s0'
        elif fault == 'member':
            (private.parent / 'unexpected.py').write_bytes(b'code')
        elif fault == 'record':
            (private.parent / 'runtime.json').write_bytes(b'{}')
        else:
            os.link(private, fixture.store / 'outside-link')
        with pytest.raises(ValueError):
            helper.verify_runtime_copies(attempt.fd, receipt, 'selinux', specs)
        assert private.exists()
    finally:
        attempt.close()


@pytest.mark.parametrize('fault', ['wrong-context', 'native-entrypoint', 'unlabeled'])
def test_source_role_labels_are_checked_against_file_context_policy(private_store, fault):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    source = fixture.host / 'usr/bin/oh-no-parent-control'
    typ = {'wrong-context': 'lib_t', 'native-entrypoint': 'onpc_kiosk_manager_exec_t',
           'unlabeled': 'unlabeled_t'}[fault]
    fixture.labels[(source.stat().st_dev, source.stat().st_ino)] = 'system_u:object_r:' + typ + ':s0'
    with pytest.raises(ValueError, match='runtime-label-changed'):
        helper.measure_runtime_inputs(specs, 'selinux')
    assert not list(fixture.store.iterdir())


@pytest.mark.parametrize('fault', ['extra-code', 'escape-link', 'special', 'writable', 'hardlink', 'ancestor'])
def test_required_runtime_membership_and_trust_refuse(private_store, fault):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    source = fixture.host / 'usr/lib/oh-no-parent-control/kiosk/main.py'
    if fault == 'extra-code':
        (source.parent / 'injected.py').write_bytes(b'code')
    elif fault == 'escape-link':
        source.unlink()
        source.symlink_to('/etc/passwd')
    elif fault == 'special':
        source.unlink()
        os.mkfifo(source)
    elif fault == 'writable':
        source.chmod(0o666)
    elif fault == 'hardlink':
        os.link(source, fixture.store / 'link')
    else:
        source.parent.chmod(0o777)
    with pytest.raises(ValueError):
        helper.measure_runtime_inputs(specs, 'apparmor')


def test_only_known_bytecode_caches_are_excluded(private_store):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    cache = fixture.host / 'usr/lib/oh-no-parent-control/kiosk/__pycache__'
    cache.mkdir(mode=0o755)
    (cache / 'main.cpython-313.pyc').write_bytes(b'cached-bytecode')
    (cache / 'main.cpython-313.pyc').chmod(0o644)
    records, _ = helper.measure_runtime_inputs(specs, 'apparmor')
    assert all('__pycache__' not in record['path'] for record in records)
    (cache / 'injected.py').write_bytes(b'code')
    with pytest.raises(ValueError, match='runtime-membership'):
        helper.measure_runtime_inputs(specs, 'apparmor')


def test_unknown_module_bytecode_is_not_a_known_build_cache(private_store):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    cache = fixture.host / 'usr/lib/oh-no-parent-control/kiosk/__pycache__'
    cache.mkdir(mode=0o755)
    (cache / 'injected.cpython-313.pyc').write_bytes(b'unknown-bytecode')
    (cache / 'injected.cpython-313.pyc').chmod(0o644)
    with pytest.raises(ValueError, match='runtime-membership'):
        helper.measure_runtime_inputs(specs, 'apparmor')


def test_same_byte_path_replacement_after_measurement_refuses(private_store):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'apparmor')
    source = fixture.host / 'usr/bin/oh-no-parent-control'
    replacement = source.with_name('replacement')
    replacement.write_bytes(source.read_bytes())
    replacement.chmod(0o755)
    replacement.replace(source)
    with helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs) as attempt:
        with pytest.raises(ValueError, match='runtime-source-changed'):
            attempt.copy(records, assertions)
    assert not list(fixture.store.iterdir())


def test_actual_copy_is_bounded_against_source_growth(private_store, monkeypatch):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'apparmor')
    original_digest = helper.runtime_read_digest
    copied = []

    def grow_at_copy(fd, size, *, target=-1):
        if target >= 0:
            with fixture.fd_path(fd).open('ab') as stream:
                stream.write(b'growth-beyond-measured-size')
            copied.append(fixture.fd_path(target))
        return original_digest(fd, size, target=target)

    monkeypatch.setattr(helper, 'runtime_read_digest', grow_at_copy)
    with helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs) as attempt:
        with pytest.raises(ValueError, match='runtime-source-changed'):
            attempt.copy(records, assertions)
        assert copied and copied[0].stat().st_size <= records[0]['size']
    assert not list(fixture.store.iterdir())


@pytest.mark.parametrize('fault', ['rows', 'bytes', 'schema', 'mode', 'version', 'mount', 'root-label'])
def test_reuse_enforces_closed_schema_labels_mount_identity_and_shared_budgets(private_store, fault, monkeypatch):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'selinux')
    with helper.RuntimeCopyPublication(fixture.store, 'selinux', specs) as attempt:
        receipt = attempt.copy(records, assertions)
        changed = copy.deepcopy(receipt)
        kwargs = {}
        if fault == 'rows':
            kwargs['used_rows'] = helper.MAX_ROWS
        elif fault == 'bytes':
            kwargs['used_bytes'] = helper.MAX_COPY_BYTES
        elif fault == 'schema':
            changed['records'][0]['unknown'] = True
        elif fault == 'mode':
            changed['records'][0]['mode'] = 0o4755
        elif fault == 'version':
            changed['format'] = 99
        elif fault == 'mount':
            changed['mount'] = '99999999'
        else:
            fixture.labels[fixture.label_key(attempt.fd)] = 'system_u:object_r:usr_t:s0'
        with pytest.raises(ValueError):
            helper.verify_runtime_copies(attempt.fd, changed, 'selinux', specs, **kwargs)


@pytest.mark.parametrize('fault', ['unknown', 'hardlink', 'foreign', 'replacement', 'mount'])
def test_identity_owned_failure_recovery_refuses_ambiguous_objects(private_store, fault, monkeypatch):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'apparmor')
    attempt = helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs)
    try:
        attempt.copy(records, assertions)
        ticket = attempt.ticket()
        scratch = fixture.store / attempt.name
        member = scratch / next(name for name in ticket['members'] if name != 'runtime.json')
        if fault == 'unknown':
            (scratch / 'unknown').write_bytes(b'unknown')
        elif fault == 'hardlink':
            os.link(member, fixture.store / 'hardlink')
        elif fault == 'foreign':
            fixture.overrides[str(member)] = {'st_uid': 1234}
        elif fault == 'replacement':
            member.unlink()
            member.write_bytes(b'foreign replacement')
        else:
            actual_mount = helper.runtime_mount_id
            monkeypatch.setattr(helper, 'runtime_mount_id', lambda fd: (
                '999999' if fixture.fd_path(fd) == member else actual_mount(fd)))
        before = {path.name for path in scratch.iterdir()}
        with pytest.raises(ValueError):
            helper.reclaim_runtime_scratch(fixture.store, ticket)
        assert {path.name for path in scratch.iterdir()} == before
    finally:
        attempt.close()


def test_failure_cleanup_removes_only_exact_incomplete_attempt(private_store):
    fixture, helper = private_store, private_store.helper
    unrelated = fixture.store / 'unrelated'
    unrelated.mkdir(mode=0o700)
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'apparmor')
    with pytest.raises(RuntimeError, match='injected-publication-cut'):
        with helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs) as attempt:
            attempt.copy(records, assertions)
            raise RuntimeError('injected-publication-cut')
    assert list(fixture.store.iterdir()) == [unrelated]


def test_constructor_label_failure_cleans_its_recorded_empty_scratch(private_store, monkeypatch):
    fixture, helper = private_store, private_store.helper
    actual_label = helper.runtime_file_label

    def fail_label(fd, backend, **kwargs):
        if kwargs.get('write'):
            raise OSError('injected-label-failure')
        return actual_label(fd, backend, **kwargs)

    monkeypatch.setattr(helper, 'runtime_file_label', fail_label)
    with pytest.raises(OSError, match='injected-label-failure'):
        helper.RuntimeCopyPublication(fixture.store, 'selinux', named_fixture(fixture))
    assert not list(fixture.store.iterdir())


def test_atomic_publication_refuses_existing_directory_and_generation_limit(private_store):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'apparmor')
    existing = fixture.store / ('a' * 64)
    existing.mkdir(mode=0o700)
    with helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs) as attempt:
        receipt = attempt.copy(records, assertions)
        with pytest.raises(OSError):
            attempt.publish(existing.name, receipt)
        assert not list(existing.iterdir())
        for name in ('b', 'c', 'd'):
            (fixture.store / (name * 64)).mkdir(mode=0o700)
        with pytest.raises(ValueError, match='generation-limit-reboot-required'):
            attempt.publish('e' * 64, receipt)
    assert {path.name for path in fixture.store.iterdir()} == {name * 64 for name in 'abcd'}


def test_supporting_publication_has_no_ready_or_admission_authority(private_store):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'apparmor')
    with helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs) as attempt:
        receipt = attempt.copy(records, assertions)
        attempt.publish('a' * 64, receipt)
        with pytest.raises(ValueError, match='runtime-completed-publication'):
            attempt.abort()
    assert not any(path.name in ('ready', 'generation', 'bindings', 'tree')
                   for path in (fixture.store / ('a' * 64)).iterdir())
    source = (ROOT / 'tools/kiosk_confinement.py').read_text().split('def prepare(role):', 1)[1]
    assert 'RuntimeCopyPublication(' not in source
    assert 'measure_runtime_inputs(' not in source


def test_producer_records_cannot_authorize_a_new_source_path(private_store, monkeypatch):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'apparmor')
    forged = copy.deepcopy(records)
    forged[0]['path'] = '/usr/bin/foreign-script'
    with helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs) as attempt:
        with monkeypatch.context() as patch:
            patch.setattr(helper, 'runtime_open', lambda *args, **kwargs: pytest.fail('foreign source opened'))
            with pytest.raises(ValueError, match='runtime-membership'):
                attempt.copy(forged, assertions)


@pytest.mark.parametrize('where', ['root', 'copy', 'manifest'])
def test_same_inode_mount_substitution_refuses_publication_and_reuse(private_store, monkeypatch, where):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'apparmor')
    with helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs) as attempt:
        receipt = attempt.copy(records, assertions)
        selected = (fixture.store / attempt.name if where == 'root' else
                    fixture.store / attempt.name / ('runtime.json' if where == 'manifest' else
                                                    receipt['copies'][0]['name']))
        actual = helper.runtime_mount_id
        with monkeypatch.context() as patch:
            patch.setattr(helper, 'runtime_mount_id', lambda fd: (
                '99999999' if fixture.fd_path(fd) == selected else actual(fd)))
            with pytest.raises(ValueError):
                helper.verify_runtime_copies(attempt.fd, receipt, 'apparmor', specs)
            with pytest.raises(ValueError):
                attempt.publish('a' * 64, receipt)
        assert not (fixture.store / ('a' * 64)).exists()


def test_interruption_after_atomic_publish_preserves_completed_supporting_copies(private_store, monkeypatch):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'apparmor')
    actual_fsync = helper.os.fsync
    with pytest.raises(OSError, match='injected-after-rename'):
        with helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs) as attempt:
            receipt = attempt.copy(records, assertions)

            def fsync(fd):
                if fd == attempt.parent:
                    raise OSError('injected-after-rename')
                actual_fsync(fd)

            monkeypatch.setattr(helper.os, 'fsync', fsync)
            attempt.publish('a' * 64, receipt)
    completed = fixture.store / ('a' * 64)
    assert completed.is_dir()
    assert not (completed / 'ready').exists()
    fd = helper.runtime_open(completed, directory=True)
    try:
        helper.verify_runtime_copies(fd, receipt, 'apparmor', specs)
    finally:
        os.close(fd)


def test_primary_failure_and_recovery_refusal_remain_separate(private_store):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'apparmor')
    with pytest.raises(RuntimeError, match='primary-bind-failure') as failure:
        with helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs) as attempt:
            attempt.copy(records, assertions)
            (fixture.store / attempt.name / 'foreign').write_bytes(b'unknown')
            raise RuntimeError('primary-bind-failure')
    assert failure.value.runtime_scratch_ticket['name'] == attempt.name
    assert failure.value.__notes__ == ['runtime-scratch-cleanup-failed: ValueError']
    assert attempt.fd == attempt.parent == -1
    assert (fixture.store / attempt.name / 'foreign').read_bytes() == b'unknown'


def test_constructor_open_failure_recovers_only_its_recorded_scratch(private_store, monkeypatch):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    actual_open, failed = helper.os.open, []

    def open_file(path, flags, *args, **kwargs):
        if isinstance(path, str) and path.startswith('.runtime-') and not failed:
            failed.append(path)
            raise OSError('injected-scratch-open-failure')
        return actual_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(helper.os, 'open', open_file)
    with pytest.raises(OSError, match='injected-scratch-open-failure'):
        helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs)
    assert failed and not list(fixture.store.iterdir())


@pytest.mark.parametrize('mutation', ['ambient-sibling', 'ancestor-replacement', 'ancestor-mode'])
def test_source_walk_ignores_only_ancestor_sibling_metadata(private_store, monkeypatch, mutation):
    fixture, helper = private_store, private_store.helper
    named_fixture(fixture)
    directory = fixture.host / 'usr/bin'
    original_stat, changed = helper.os.stat, []

    def stat_path(path, *, dir_fd=None, follow_symlinks=True):
        info = original_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)
        selected = Path(path) if dir_fd is None else fixture.fd_path(dir_fd) / path
        if selected == directory and not changed:
            changed.append(True)
            if mutation == 'ambient-sibling':
                (directory / 'unrelated-sibling').write_bytes(b'ambient')
                (directory / 'unrelated-sibling').chmod(0o644)
            elif mutation == 'ancestor-replacement':
                directory.rename(directory.with_name('old-bin'))
                directory.mkdir(mode=0o755)
            else:
                directory.chmod(0o777)
        return info

    monkeypatch.setattr(helper.os, 'stat', stat_path)
    if mutation == 'ambient-sibling':
        fd = helper.runtime_open('/usr/bin/oh-no-parent-control')
        try:
            assert os.read(fd, 4096) == b'original:/usr/bin/oh-no-parent-control'
        finally:
            os.close(fd)
    else:
        with pytest.raises(ValueError, match='runtime-source-changed'):
            helper.runtime_open('/usr/bin/oh-no-parent-control')
    assert changed


def test_new_file_identity_read_failure_closes_fd_and_preserves_unknown_scratch(private_store, monkeypatch):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    actual_open, actual_fstat, captured, failed = helper.os.open, helper.os.fstat, [], []

    def open_file(path, flags, *args, **kwargs):
        fd = actual_open(path, flags, *args, **kwargs)
        if path == '0' and flags & os.O_CREAT:
            captured.append(fd)
        return fd

    def fail_fstat(fd):
        if fd in captured and not failed:
            failed.append(True)
            raise OSError('injected-new-file-identity-failure')
        return actual_fstat(fd)

    monkeypatch.setattr(helper.os, 'open', open_file)
    monkeypatch.setattr(helper.os, 'fstat', fail_fstat)
    with pytest.raises(OSError, match='injected-new-file-identity-failure') as failure:
        with helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs) as attempt:
            attempt._new_file('0')
    assert len(captured) == 1
    with pytest.raises(OSError):
        os.fstat(captured[0])
    assert failure.value.runtime_scratch_ticket['members'] == {}
    assert failure.value.__notes__ == ['runtime-scratch-cleanup-failed: ValueError']
    assert (fixture.store / attempt.name / '0').is_file()
    assert attempt.fd == attempt.parent == -1
