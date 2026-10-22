"""Execution inputs use real private journals and inert, verified bundles.

Resource review: pytest-private disk roots, tiny inert ELF fixtures and one
bounded, waited Python descendant. No compiler/container/VM/display/service,
external storage, shared cache or product installation. Compatible unit overlap.
"""
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import select
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tests.support.fixture_bundles import compiler_record, environment_record, inert_elf
from tools import artifact_inputs, fixture_bundle as bundle, fixture_execution as execution
from tools import fixture_manifest, fixture_producer, test_retention as retention
from tools import test_storage as storage

SOURCE = 'tests/fixtures/onpc_test_application.c'
GUI = 'tests/fixtures/gui_application.py'
AUTOMATION = 'common/oh_no_parent_control_ui/gtk_automation.py'


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(storage, 'BASE', tmp_path / 'output/test-runs')
    producers = storage.directory('allocations') / 'fixture-producers'
    producers.mkdir(mode=0o700)
    monkeypatch.setattr(storage, 'fixture_directory', lambda: producers)
    source = tmp_path / 'checkout'
    files = {SOURCE: b'int fixture;\n', GUI: b'# GUI\n', AUTOMATION: b'# runtime\n',
             'rpm/Containerfile': b'FROM fedora:44\n',
             'rpm/oh-no-parent-control.spec.in': b'BuildRequires: gcc\n',
             'debian/Containerfile': b'FROM ubuntu:26.04\n',
             'debian/control': b'Source: fixture\nBuild-Depends: gcc\n',
             'product.py': b'product one\n'}
    for name, data in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    monkeypatch.setattr(artifact_inputs, 'NATIVE_RUNTIME_SOURCES', (SOURCE, GUI, AUTOMATION))
    monkeypatch.setattr(bundle, 'environment_inputs', lambda root, target: environment_record(target))
    calls = []

    def target_build(source, workspace, target, environment):
        calls.append(target)
        compiled = workspace / 'compiled'
        compiled.mkdir()
        return compiled, compiler_record(target)

    def assemble(source, compiled, staging, inputs, environment):
        payloads = {}
        for name, declaration in fixture_manifest.declarations().items():
            value = declaration['source']
            if isinstance(value, bytes):
                payloads[name] = value
            elif value in ('onpc-test-gui.py', 'gtk_automation.py'):
                payloads[name] = (source / (GUI if value == 'onpc-test-gui.py'
                                          else AUTOMATION)).read_bytes()
            else:
                payloads[name] = inert_elf(value)
        fixture_manifest.write(staging, inputs, payloads)

    monkeypatch.setattr(bundle, 'target_build', target_build)
    monkeypatch.setattr(bundle, 'assemble', assemble)
    store = retention.Store(storage.directory('state') / 'retention-fixture-test')
    return source, store, calls, fixture_producer.Store()


def prepare(rig, target='ubuntu'):
    return execution.prepare(target=target, root=rig[0])


@pytest.mark.parametrize('target', ['ubuntu', 'fedora'])
def test_matching_input_reuses_only_same_active_run(rig, target):
    source, store, calls, producer = rig
    with store.session():
        selected = prepare(rig, target)
        token = os.environ[retention.VARIABLE]
        again = prepare(rig, target)
        assert again == selected and calls == [target]
        assert os.environ[retention.VARIABLE] == token
        assert producer.snapshot() is None
        assert execution.verify(selected)['build_identity'] == selected.build_identity
        assert execution.Selection.from_record(json.loads(json.dumps(selected.record()))) == selected
        with pytest.raises(FrozenInstanceError):
            selected.key = '0' * 64
    with store.session():
        newer = prepare(rig, target)
        assert newer.path != selected.path and selected.path.is_dir()
        assert calls == [target, target]


def test_product_edits_do_not_invalidate_fixture_but_fixture_edits_freeze_selection(rig):
    source, store, calls, _ = rig
    with store.session():
        selected = prepare(rig)
        original = execution.verify(selected)
        (source / 'product.py').write_bytes(b'product two\n')
        assert prepare(rig) == selected
        (source / SOURCE).write_bytes(b'int changed_fixture;\n')
        assert execution.verify(selected) == original
        changed = prepare(rig)
        assert changed.key != selected.key and changed.path != selected.path
        assert calls == ['ubuntu', 'ubuntu']


@pytest.mark.parametrize('fault', ['empty', 'incomplete', 'corrupt', 'extra', 'replaced', 'missing'])
def test_matching_registered_invalid_input_is_preserved_and_refused(rig, fault):
    _, store, calls, _ = rig
    # A replacement prevents normal finalization too; retain it as recovery
    # evidence instead of allowing session cleanup to hide the refusal.
    with store.session():
        selected = prepare(rig)
        allocation = Path(selected.allocation)
        if fault == 'empty':
            (selected.path / 'complete.json').unlink()
            (selected.path / 'payload.tar').unlink()
            (selected.path / 'fixture-manifest.json').unlink()
            selected.path.rmdir()
        elif fault == 'incomplete':
            (selected.path / 'complete.json').unlink()
        elif fault == 'corrupt':
            (selected.path / 'payload.tar').write_bytes(b'corrupt bytes')
        elif fault == 'extra':
            (allocation / 'unregistered-note').write_bytes(b'preserve')
        elif fault in ('replaced', 'missing'):
            allocation.rename(allocation.with_name(allocation.name + '-original'))
            if fault == 'replaced':
                allocation.mkdir(mode=0o700)
            retention.preserve_for_recovery()
        before = sorted(str(path) for path in allocation.rglob('*')) if allocation.exists() else []
        with pytest.raises((ValueError, FileNotFoundError)):
            prepare(rig)
        assert calls == ['ubuntu']
        assert (sorted(str(path) for path in allocation.rglob('*'))
                if allocation.exists() else []) == before


def test_unregistered_nonempty_input_never_adopted(rig):
    source, store, calls, _ = rig
    key = execution.input_key(bundle.source_snapshot(source)[0], environment_record('ubuntu'), 'ubuntu')
    unknown = storage.allocation_parent() / (execution._prefix('ubuntu', key) + 'unknown')
    unknown.mkdir(mode=0o700)
    witness = unknown / 'complete.json'
    witness.write_bytes(b'unknown owner\n')
    with store.session():
        selected = prepare(rig)
        assert Path(selected.allocation) != unknown
        assert witness.read_bytes() == b'unknown owner\n'
        with store.opened() as fd:
            assert str(unknown) not in {record['path'] for record in store.read(fd)['paths']}
    assert calls == ['ubuntu']


def test_copy_is_independent_verified_and_atomic_before_producer_release(rig, monkeypatch):
    _, store, _, producer = rig
    rename, observed = bundle.os.rename, []

    def publication(source, destination, *args, **kwargs):
        destination = Path(destination)
        if destination.name == 'native-runtime':
            assert Path(source).name == '.native-runtime-staging'
            output_fd = kwargs['dst_dir_fd']
            assert kwargs['src_dir_fd'] == output_fd
            output = Path(os.readlink(f'/proc/self/fd/{output_fd}'))
            assert not (output / destination).exists()
            record = producer.snapshot()
            staging = next(Path(item['path']) / 'bundle' for item in record['slot']['allocations']
                           if item['name'] == 'staging')
            assert fixture_manifest.verify(output / source) == fixture_manifest.verify(staging)
            for name in ('payload.tar', 'fixture-manifest.json', 'complete.json'):
                assert (output / source / name).stat().st_ino != (staging / name).stat().st_ino
            observed.append(output / destination)
        return rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(bundle.os, 'rename', publication)
    with store.session():
        selected = prepare(rig)
        assert observed == [selected.path]
        assert producer.snapshot() is None


@pytest.mark.parametrize('when', ['target-replace', 'target-symlink', 'copy-replace'])
def test_publication_never_writes_replaced_output_allocation(rig, tmp_path, monkeypatch, when):
    _, store, calls, producer = rig
    original_target, original_copy = bundle.target_build, bundle.shutil.copyfileobj
    external = tmp_path / 'external'
    external.mkdir(mode=0o700)
    external_witness = external / 'preserve'
    external_witness.write_bytes(b'external original bytes\n')
    displaced = []
    replacement = []

    def replace_allocation():
        with store.opened() as fd:
            record = store.read(fd)['paths'][0]
        allocation = Path(record['path'])
        original = allocation.with_name(allocation.name + '-displaced')
        retention.preserve_for_recovery()
        allocation.rename(original)
        displaced.append(original)
        if when == 'target-symlink':
            allocation.symlink_to(external, target_is_directory=True)
        else:
            allocation.mkdir(mode=0o700)
            (allocation / 'preserve').write_bytes(b'replacement original bytes\n')
        replacement.append(allocation)

    def target(*args, **kwargs):
        result = original_target(*args, **kwargs)
        if when.startswith('target-'):
            replace_allocation()
        return result

    def copy(*args, **kwargs):
        if not displaced:
            replace_allocation()
        return original_copy(*args, **kwargs)

    monkeypatch.setattr(bundle, 'target_build', target)
    if when == 'copy-replace':
        monkeypatch.setattr(bundle.shutil, 'copyfileobj', copy)
    with store.session():
        with pytest.raises(ValueError, match='replaced'):
            prepare(rig)
        assert calls == ['ubuntu'] and producer.snapshot() is None
        assert len(displaced) == len(replacement) == 1
        assert external_witness.read_bytes() == b'external original bytes\n'
        assert list(external.iterdir()) == [external_witness]
        assert not (displaced[0] / 'native-runtime').exists()
        if when == 'copy-replace':
            assert (displaced[0] / '.native-runtime-staging').is_dir()
        else:
            assert not list(displaced[0].iterdir())
        if when == 'target-symlink':
            assert replacement[0].is_symlink()
        else:
            assert sorted(path.name for path in replacement[0].iterdir()) == ['preserve']
            assert (replacement[0] / 'preserve').read_bytes() == b'replacement original bytes\n'
        with store.opened() as fd:
            state = store.read(fd)
            assert state['paths'][0]['inode'] == displaced[0].stat().st_ino
            assert 'recovery-required' in os.listdir(fd)


@pytest.mark.parametrize('when', ['copy', 'rename', 'owner-loss'])
def test_interruption_preserves_registered_unpublished_input_and_refuses_retry(rig, monkeypatch, when):
    _, store, calls, producer = rig
    original_copy, original_rename = bundle.shutil.copyfileobj, bundle.os.rename

    def copy(source, destination, *args, **kwargs):
        if when == 'copy':
            destination.write(b'partial')
            raise OSError('interrupted fixture copy')
        return original_copy(source, destination, *args, **kwargs)

    def rename(source, destination, *args, **kwargs):
        if Path(destination).name == 'native-runtime':
            raise OSError('interrupted fixture rename')
        return original_rename(source, destination, *args, **kwargs)

    owner = retention.owner_descriptor
    probes = []

    def owner_loss():
        probes.append(True)
        if when == 'owner-loss' and producer.snapshot() is not None:
            raise ValueError('fixture execution: owner lost')
        return owner()

    monkeypatch.setattr(bundle.shutil, 'copyfileobj', copy)
    if when == 'rename':
        monkeypatch.setattr(bundle.os, 'rename', rename)
    monkeypatch.setattr(retention, 'owner_descriptor', owner_loss)
    with store.session():
        with pytest.raises((ValueError, OSError), match='interrupted|owner lost'):
            prepare(rig)
        assert producer.snapshot() is None
        with store.opened() as fd:
            paths = store.read(fd)['paths']
        assert len(paths) == 1
        allocation = Path(paths[0]['path'])
        assert not (allocation / 'native-runtime').exists()
        with pytest.raises(ValueError, match='incomplete'):
            prepare(rig)
        assert calls == ['ubuntu']


def test_competing_preparation_is_excluded_without_allocating(rig):
    _, store, calls, _ = rig
    with store.session(), store.opened() as fd, store.locked(fd, 'fixture-input.lock'):
        with pytest.raises(ValueError, match='another owner is active'):
            prepare(rig)
        assert store.read(fd)['paths'] == [] and calls == []


def test_no_active_owner_or_wrong_selection_cannot_read(rig, monkeypatch):
    _, store, _, _ = rig
    with pytest.raises(ValueError):
        prepare(rig)
    with store.session():
        selected = prepare(rig)
        foreign = selected.record() | {'run': 'f' * 32}
        with pytest.raises(ValueError):
            execution.verify(foreign)
    with pytest.raises(ValueError):
        execution.verify(selected)


@pytest.mark.parametrize('foreign', ['directory', 'file'])
def test_read_only_verification_rejects_foreign_bundle_ownership(rig, monkeypatch, foreign):
    _, store, _, _ = rig
    with store.session():
        selected = prepare(rig)
        path = selected.path if foreign == 'directory' else selected.path / 'payload.tar'
        inode = path.stat().st_ino
        fstat = os.fstat

        def foreign_owner(descriptor):
            info = fstat(descriptor)
            if info.st_ino == inode:
                values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
                values['st_uid'] = info.st_uid + 1
                return SimpleNamespace(**values)
            return info

        with monkeypatch.context() as change:
            change.setattr(execution.os, 'fstat', foreign_owner)
            with pytest.raises(ValueError):
                execution.verify(selected)


def test_read_only_verification_rejects_extra_allocation_children(rig):
    _, store, _, _ = rig
    with store.session():
        selected = prepare(rig)
        (Path(selected.allocation) / 'extra').write_bytes(b'unexpected')
        with pytest.raises(ValueError, match='unexpected'):
            execution.verify(selected)


def test_recovery_retains_input_until_existing_owner_reconciles_then_rotation_resumes(rig):
    _, store, _, _ = rig
    with store.session():
        selected = prepare(rig)
        retention.preserve_for_recovery()
    with pytest.raises(ValueError, match='previous owner did not finish'):
        with store.session():
            pytest.fail('unfinished input owner bypassed')
    assert selected.path.exists()
    recovered = []
    assert store.reconcile(lambda: recovered.append('owned VM cleanup finished'))
    assert recovered == ['owned VM cleanup finished'] and selected.path.exists()
    for _ in range(retention.RUNS_TO_KEEP):
        with store.session():
            pass
    assert not Path(selected.allocation).exists()


def test_descendant_keeps_existing_owner_lock_after_coordinator_exit(rig):
    source, store, _, _ = rig
    child = None
    try:
        with store.session():
            selected = prepare(rig)
            script = (
                'import sys,json; sys.path.insert(0,sys.argv[1]); '
                'from pathlib import Path; '
                'from tools import artifact_inputs,fixture_execution,test_storage; '
                'artifact_inputs.NATIVE_RUNTIME_SOURCES=tuple(json.loads(sys.argv[4])); '
                'test_storage.ROOT=Path(sys.argv[2]); '
                'print("ready",flush=True); sys.stdin.readline(); '
                'print(fixture_execution.verify(json.loads(sys.argv[3]))["build_identity"],flush=True)')
            child = subprocess.Popen([sys.executable, '-I', '-S', '-B', '-c', script,
                str(execution.ROOT), str(source.parent), json.dumps(selected.record()),
                json.dumps([SOURCE, GUI, AUTOMATION])],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, pass_fds=retention.descriptors(), env=os.environ | retention.environment())
            assert select.select([child.stdout], [], [], 15)[0], 'descendant did not become ready'
            assert child.stdout.readline().strip() == 'ready'
        with pytest.raises(ValueError, match='another owner is active'):
            with store.session():
                pytest.fail('active descendant owner bypassed')
        assert selected.path.exists()
        (source / SOURCE).write_bytes(b'edited after selection\n')
        stdout, stderr = child.communicate('finish\n', timeout=15)
        assert child.returncode == 0, stderr
        assert stdout.strip() == selected.build_identity
        for _ in range(retention.RUNS_TO_KEEP):
            with store.session():
                pass
        assert not Path(selected.allocation).exists()
    finally:
        if child is not None and child.poll() is None:
            child.communicate('finish\n', timeout=15)
