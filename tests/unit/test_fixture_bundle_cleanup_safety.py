"""Frozen bundle construction with real private producer allocation/cleanup.

Resource review: pytest-private disk files only, under an injected shared-storage
root. Target builds return tiny inert ELF records. Two bounded, waited Python
children cover lease forwarding and fresh frozen assembly. No compiler,
container, VM, display, service, shared cache or shared fixture store is used.
"""
import errno
import os
from pathlib import Path
import struct
import shutil
import subprocess
import sys

import pytest

from tools import artifact_inputs, fixture_bundle as bundle, fixture_manifest
from tools import fixture_producer, test_storage as storage


GUI = 'tests/fixtures/gui_application.py'
AUTOMATION = 'common/oh_no_parent_control_ui/gtk_automation.py'
SOURCE = 'tests/fixtures/onpc_test_application.c'
CLOSURE = (SOURCE, GUI, AUTOMATION)
ENVIRONMENT_FILES = {
    'rpm/Containerfile': b'FROM fedora:44\n',
    'rpm/oh-no-parent-control.spec.in': (
        b'Name: product\nVersion: @VERSION@\nBuildRequires: gcc\nRequires: old-runtime\n'),
    'debian/Containerfile': b'FROM ubuntu:26.04\n',
    'debian/control': (b'Source: product\nBuild-Depends: gcc\n\n'
                       b'Package: product\nDepends: old-runtime\n'),
}


@pytest.fixture
def source_root(tmp_path, monkeypatch):
    root = tmp_path / 'checkout'
    for name, data in {**ENVIRONMENT_FILES, SOURCE: b'int fixture;\n',
                       GUI: b'# fixture GUI\n', AUTOMATION: b'# automation\n',
                       'product.py': b'product version one\n'}.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (root / SOURCE).chmod(0o640)
    monkeypatch.setattr(artifact_inputs, 'NATIVE_RUNTIME_SOURCES', CLOSURE)
    monkeypatch.setattr(bundle, 'assemble', fake_assemble)
    return root


@pytest.fixture
def private_store(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    root = tmp_path / 'output/test-runs/host/fixtures'
    root.mkdir(mode=0o700, parents=True)
    monkeypatch.setattr(storage, 'fixture_directory', lambda: root)
    return fixture_producer.Store()


def inert_elf(identity):
    """Bounded ELF64 ABI record for verification, never executed by these tests."""
    data = bytearray(768)
    base = 0x400000
    loader = b'/lib64/ld-linux-x86-64.so.2\0'
    strings = b'\0libc.so.6\0GLIBC_2.2.5\0'
    struct.pack_into('<16sHHIQQQIHHHHHH', data, 0,
                     b'\x7fELF\x02\x01\x01' + bytes(9), 2, 62, 1,
                     base + 700, 64, 0, 0, 64, 56, 3, 0, 0, 0)
    for index, segment in enumerate((
            (1, 5, 0, base, base, len(data), len(data), 1),
            (3, 4, 256, base + 256, base + 256, len(loader), len(loader), 1),
            (2, 4, 320, base + 320, base + 320, 96, 96, 1))):
        struct.pack_into('<IIQQQQQQ', data, 64 + index * 56, *segment)
    data[256:256 + len(loader)] = loader
    for index, entry in enumerate(((5, base + 512), (10, len(strings)),
                                   (1, 1), (0x6fffffff, 1),
                                   (0x6ffffffe, base + 600), (0, 0))):
        struct.pack_into('<qQ', data, 320 + index * 16, *entry)
    data[512:512 + len(strings)] = strings
    struct.pack_into('<HHIII', data, 600, 1, 1, 1, 16, 0)
    struct.pack_into('<IHHII', data, 616, 0, 0, 2, 11, 0)
    data[700:700 + len(identity)] = identity.encode()
    return bytes(data)


def fake_target(source, workspace, target, environment):
    from tests.support.fixture_bundles import compiler_record
    assert bundle.source_snapshot(source)[1][SOURCE] == b'int fixture;\n'
    assert Path(environment['TMPDIR']).is_dir()
    compiled = workspace / 'compiled'
    compiled.mkdir()
    for declaration in fixture_manifest.declarations().values():
        key = declaration['source']
        if isinstance(key, str) and key not in ('onpc-test-gui.py', 'gtk_automation.py'):
            (compiled / key).write_bytes(inert_elf(key))
    return compiled, compiler_record(target)


def fake_assemble(source, compiled, staging, inputs, environment):
    payloads = {}
    for member, declaration in fixture_manifest.declarations().items():
        key = declaration['source']
        if isinstance(key, bytes):
            payloads[member] = key
        elif key in ('onpc-test-gui.py', 'gtk_automation.py'):
            payloads[member] = (source / (GUI if key == 'onpc-test-gui.py' else AUTOMATION)).read_bytes()
        else:
            payloads[member] = (compiled / key).read_bytes()
    fixture_manifest.write(staging, inputs, payloads)


def output_with_unrelated(tmp_path, private_store):
    output = tmp_path / 'requested-output'
    output.mkdir()
    unrelated = private_store.path / 'unrelated-output'
    unrelated.mkdir(mode=0o700)
    witness = unrelated / 'complete.json'
    witness.write_bytes(b'previous unrelated output\n')
    witness.chmod(0o600)
    return output, witness, (witness.stat(), witness.read_bytes())


def assert_cleanup(private_store, witness, before):
    assert private_store.snapshot() is None
    assert not list(private_store.path.glob('producer-*'))
    info, data = before
    assert witness.read_bytes() == data
    assert (witness.stat().st_ino, witness.stat().st_mode) == (info.st_ino, info.st_mode)


@pytest.mark.parametrize('target', ['ubuntu', 'fedora'])
def test_freeze_copies_exact_closure_and_modes(source_root, tmp_path, target):
    destination = tmp_path / 'frozen'
    destination.mkdir()
    records, environment = bundle.freeze(source_root, destination, target)
    assert set(records) == set(CLOSURE)
    assert bundle.source_snapshot(destination) == bundle.source_snapshot(source_root)
    assert environment == bundle.environment_inputs(destination, target)
    assert {str(path.relative_to(destination)) for path in destination.rglob('*')
            if path.is_file()} == set(CLOSURE) | set(ENVIRONMENT_FILES)
    assert not (destination / 'product.py').exists()
    assert (destination / SOURCE).stat().st_ino != (source_root / SOURCE).stat().st_ino


@pytest.mark.parametrize('changed', [SOURCE, 'debian/control'])
def test_freeze_refuses_source_or_environment_change_during_copy(
        source_root, tmp_path, monkeypatch, changed):
    destination = tmp_path / 'frozen'
    destination.mkdir()
    copy = bundle.shutil.copyfile

    def mutate(source, target):
        result = copy(source, target)
        if source == source_root / 'debian/control':
            path = source_root / changed
            path.write_bytes(path.read_bytes().replace(b'gcc', b'clang') + b'changed\n')
        return result

    monkeypatch.setattr(bundle.shutil, 'copyfile', mutate)
    with pytest.raises(ValueError, match='changed while freezing'):
        bundle.freeze(source_root, destination, 'ubuntu')


@pytest.mark.parametrize('link', ['symbolic', 'hard'])
def test_source_snapshot_refuses_links(source_root, tmp_path, link):
    source = source_root / SOURCE
    outside = tmp_path / 'outside'
    outside.write_bytes(source.read_bytes())
    source.unlink()
    if link == 'symbolic':
        source.symlink_to(outside)
    else:
        os.link(outside, source)
    with pytest.raises(ValueError, match='link|invalid fixture source'):
        bundle.source_snapshot(source_root)
    assert outside.read_bytes() == b'int fixture;\n'


def test_source_snapshot_refuses_concurrent_edit(source_root, monkeypatch):
    fstat = bundle.os.fstat
    calls = 0

    def edit_during_read(descriptor):
        nonlocal calls
        calls += 1
        if calls == 2:
            (source_root / SOURCE).write_bytes(b'concurrent edit\n')
        return fstat(descriptor)

    monkeypatch.setattr(bundle.os, 'fstat', edit_during_read)
    with pytest.raises(ValueError, match='changed during capture'):
        bundle.source_snapshot(source_root)


@pytest.mark.parametrize('target', ['ubuntu', 'fedora'])
def test_fixture_product_and_dependency_inputs_invalidate_independently(source_root, target):
    source = bundle.source_snapshot(source_root)[0]
    environment = bundle.environment_inputs(source_root, target)
    (source_root / 'product.py').write_bytes(b'product version two\n')
    # Product runtime dependencies/version metadata do not affect fixture builds.
    for name in ('debian/control', 'rpm/oh-no-parent-control.spec.in'):
        path = source_root / name
        path.write_bytes(path.read_bytes().replace(b'old-runtime', b'new-runtime')
                         .replace(b'@VERSION@', b'99.0'))
    assert bundle.source_snapshot(source_root)[0] == source
    assert bundle.environment_inputs(source_root, target) == environment
    (source_root / SOURCE).write_bytes(b'fixture change\n')
    assert bundle.source_snapshot(source_root)[0] != source
    assert bundle.environment_inputs(source_root, target) == environment
    changed_source = bundle.source_snapshot(source_root)[0]
    name = 'debian/control' if target == 'ubuntu' else 'rpm/oh-no-parent-control.spec.in'
    path = source_root / name
    path.write_bytes(path.read_bytes().replace(b'gcc', b'clang'))
    assert bundle.environment_inputs(source_root, target) != environment
    assert bundle.source_snapshot(source_root)[0] == changed_source


@pytest.mark.parametrize('failure', ['build', 'interrupt', 'disk-full'])
def test_build_failures_clean_exact_owned_allocations(
        source_root, private_store, tmp_path, monkeypatch, failure):
    output, witness, before = output_with_unrelated(tmp_path, private_store)
    expected = {'build': subprocess.CalledProcessError,
                'interrupt': KeyboardInterrupt, 'disk-full': OSError}[failure]

    def failed_target(source, workspace, target, environment):
        assert {item['name'] for item in private_store.snapshot()['slot']['allocations']} == {
            'sources', 'build', 'scratch'}
        (workspace / 'partial').write_bytes(b'partial build output')
        if failure == 'build':
            raise subprocess.CalledProcessError(1, ['mock-target'], stderr='target failed')
        if failure == 'disk-full':
            raise OSError(errno.ENOSPC, 'injected disk exhaustion')
        raise KeyboardInterrupt

    monkeypatch.setattr(bundle, 'target_build', failed_target)
    with pytest.raises(expected) as caught:
        bundle.build(output, target='ubuntu', root=source_root)
    if failure == 'disk-full':
        assert caught.value.errno == errno.ENOSPC
    assert not list(output.iterdir())
    assert_cleanup(private_store, witness, before)


@pytest.mark.parametrize('changed_root', ['original', 'frozen'])
def test_source_mutation_after_target_build_refuses_publication(
        source_root, private_store, tmp_path, monkeypatch, changed_root):
    output, witness, before = output_with_unrelated(tmp_path, private_store)

    def mutate_after_build(source, workspace, target, environment):
        result = fake_target(source, workspace, target, environment)
        root = source_root if changed_root == 'original' else source
        (root / SOURCE).write_bytes(b'changed after build\n')
        return result

    monkeypatch.setattr(bundle, 'target_build', mutate_after_build)
    with pytest.raises(ValueError, match='changed during build'):
        bundle.build(output, target='ubuntu', root=source_root)
    assert not list(output.iterdir())
    assert_cleanup(private_store, witness, before)


@pytest.mark.parametrize('target', ['ubuntu', 'fedora'])
def test_success_publishes_only_verified_complete_bundle_atomically(
        source_root, private_store, tmp_path, monkeypatch, target):
    output, witness, before = output_with_unrelated(tmp_path, private_store)
    monkeypatch.setattr(bundle, 'target_build', fake_target)
    rename = bundle.os.rename
    publications = []

    def verified_rename(source, destination, *args, **kwargs):
        if Path(destination) == output / 'native-runtime':
            assert not list(output.iterdir())
            manifest = fixture_manifest.verify(source, target=target)
            assert set(manifest['members']) == set(fixture_manifest.declarations())
            assert private_store.snapshot()['slot']['state'] == 'verifying'
            publications.append((source, destination))
        return rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(bundle.os, 'rename', verified_rename)
    final = bundle.build(output, target=target, root=source_root)
    assert final == output / 'native-runtime'
    assert len(publications) == 1
    assert set(final.iterdir()) == {final / name for name in (
        'fixture-manifest.json', 'payload.tar', 'complete.json')}
    manifest = fixture_manifest.verify(final, target=target)
    assert manifest['inputs']['source'] == bundle.source_snapshot(source_root)[0]
    assert manifest['inputs']['target'] == bundle.TARGETS[target]
    assert list(output.iterdir()) == [final]
    assert_cleanup(private_store, witness, before)


def test_target_runner_forwards_actual_producer_lease(private_store):
    from tools import fixture_target_build as target
    with private_store.producer(transaction_id='a' * 32,
            compatibility_key='test-runtime', build_key='test-build'):
        token = target._LEASE_FDS.set(storage.scratch_descriptors())
        try:
            result = target._run([sys.executable, '-B', '-c',
                'import os; print("\\n".join(os.readlink("/proc/self/fd/"+fd) '
                'for fd in os.listdir("/proc/self/fd") '
                'if os.path.exists("/proc/self/fd/"+fd)))'])
            assert str(private_store.path / 'producer.lock').encode() in result.stdout
        finally:
            target._LEASE_FDS.reset(token)
    assert private_store.snapshot() is None


def test_assembly_executes_frozen_declarations_in_fresh_context(tmp_path, monkeypatch):
    from tests.support.fixture_bundles import compiler_record, environment_record
    source, compiled, output = [tmp_path / name for name in ('frozen', 'compiled', 'bundle')]
    for directory in (source, compiled, output):
        directory.mkdir(mode=0o700)
    for name in artifact_inputs.NATIVE_RUNTIME_SOURCES:
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle.ROOT / name, destination)
    declaration_source = source / 'tests/fixtures/native_assets.py'
    declaration_source.write_bytes(declaration_source.read_bytes().replace(
        b'ONPC Allowed Fixture', b'ONPC Frozen Fixture'))
    recorded = {'source': bundle.source_snapshot(source)[0],
                'toolchain': {'environment': environment_record('ubuntu'),
                              'compiler': compiler_record('ubuntu')},
                'target': bundle.TARGETS['ubuntu'],
                'dependencies': fixture_manifest.DEPENDENCIES}
    for member, declaration in fixture_manifest.declarations().items():
        key = declaration['source']
        if isinstance(key, str) and declaration['mode'] == 0o755:
            (compiled / key).write_bytes(inert_elf(key))
    def reject_live_declarations():
        raise AssertionError('assembly used already-loaded declarations')
    with monkeypatch.context() as local:
        local.setattr(fixture_manifest, 'declarations', reject_live_declarations)
        bundle.assemble(source, compiled, output, recorded,
                        {'PATH': os.defpath, 'LANG': 'C', 'PYTHONDONTWRITEBYTECODE': '1'})
    assert b'ONPC Frozen Fixture' in (output / 'payload.tar').read_bytes()
    assert b'ONPC Allowed Fixture' not in (output / 'payload.tar').read_bytes()
    assert (output / 'complete.json').is_file()
    # The independent live verifier supplies an additional refusal guard when
    # its declaration version differs from the frozen construction inputs.
    with pytest.raises(ValueError, match='fixture:literal-bytes'):
        fixture_manifest.verify(output)


def test_container_build_uses_documented_image_id_caller_home_and_descendant_leases(
        private_store, monkeypatch):
    import json
    from tools import rpm_builder
    from tests.support.fixture_bundles import compiler_record
    monkeypatch.setattr(rpm_builder, 'require_image', lambda source: 'reviewed-image')
    read_text = bundle.Path.read_text
    monkeypatch.setattr(bundle.Path, 'read_text', lambda path, *args, **kwargs:
        'ID=ubuntu\nVERSION_ID=26.04\n' if str(path) == '/etc/os-release'
        else read_text(path, *args, **kwargs))
    commands = []
    with private_store.producer(transaction_id='b' * 32,
            compatibility_key='test-target', build_key='test-build') as producer:
        source = producer.allocate('sources')
        workspace = producer.allocate('build')
        environment = producer.environment({'HOME': str(workspace), 'PATH': os.defpath})
        leases = storage.scratch_descriptors()
        def run(command, *, environment):
            commands.append(command)
            assert environment['HOME'] == str(Path.home())
            if command[:3] == ['podman', 'image', 'inspect']:
                return subprocess.CompletedProcess(command, 0, 'a' * 64 + '\n', '')
            assert command[:4] == [sys.executable, '-I', '-S', '-B']
            assert command[4] == str(source / 'tools/fixture_container.py')
            assert 'a' * 64 in command
            assert [command[index + 1] for index, value in enumerate(command)
                    if value == '--lease-fd'] == list(map(str, leases))
            compiled = workspace / 'compiled'
            compiler = compiler_record('fedora')
            compiler.pop('image_identity')
            compiler['abi'] = {}
            for identity in ('mechanical', 'A', 'H', 'S', 'N', 'trusted-hard',
                             'trusted-soft', 'trusted-activity'):
                data = inert_elf(identity)
                (compiled / identity).write_bytes(data)
                compiler['abi'][identity] = fixture_manifest.verify_elf(data)
            (compiled / 'toolchain.json').write_text(json.dumps(compiler))
            return subprocess.CompletedProcess(command, 0, '', '')
        monkeypatch.setattr(bundle, '_run', run)
        compiled, compiler = bundle.target_build(source, workspace, 'fedora', environment)
        assert compiler['image_identity'] == 'sha256:' + 'a' * 64
        assert 'abi' not in compiler
        assert len(commands) == 2
    assert private_store.snapshot() is None
