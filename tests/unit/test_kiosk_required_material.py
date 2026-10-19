"""Current required material, with real private files and complete trust walks."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from tests.unit.test_kiosk_pin_storage import private_store, named_fixture


@pytest.fixture
def material_host(private_store, monkeypatch):
    scene, helper = private_store, private_store.helper
    specs = named_fixture(scene)
    native = '/usr/bin/native'
    library = '/usr/lib/library.so'
    vendor = '/usr/lib/helper'
    for name in (native, library, vendor):
        path = scene.host / name.lstrip('/')
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        path.write_bytes(b'\x7fELF' + name.encode())
        path.chmod(0o755)
    payload = scene.host / str(helper.PAYLOAD).lstrip('/')
    payload.mkdir(mode=0o755, parents=True)
    for path in scene.host.rglob('*'):
        if path.is_dir() and not path.is_symlink():
            path.chmod(0o755)
    config = dict(backend='apparmor', runtime_inputs=specs,
                  executables=[dict(role='service', paths=[native]),
                               dict(role='library', paths=[library]),
                               dict(role='service', paths=['/usr/bin/optional'], optional=True)],
                  preserved_executables=[dict(path=vendor, mode=0o755, label=None)])

    def physical(path):
        path = Path(path)
        return scene.host / str(path).lstrip('/') if path == Path('/usr') or Path('/usr') in path.parents else path

    def logical(path):
        return Path('/') / path.relative_to(scene.host) if scene.host in path.parents else path

    # Only names are translated. Real trust walks, no-follow opens, full inode
    # assertions, byte hashing, membership and all failure checks stay active.
    raw_stat, raw_open, raw_readlink = helper.os.stat, helper.os.open, helper.os.readlink
    path_open, real_trusted = Path.open, helper.trusted
    path_exists, path_is_link, path_iterdir = Path.exists, Path.is_symlink, Path.iterdir
    monkeypatch.setattr(Path, 'exists', lambda path, **kw: path_exists(physical(path), **kw))
    monkeypatch.setattr(Path, 'is_symlink', lambda path: path_is_link(physical(path)))
    monkeypatch.setattr(Path, 'iterdir', lambda path: iter(logical(child) for child in path_iterdir(physical(path))))
    monkeypatch.setattr(Path, 'lstat', lambda path: raw_stat(physical(path), follow_symlinks=False))
    monkeypatch.setattr(Path, 'stat', lambda path, **kw: raw_stat(physical(path), **kw))
    monkeypatch.setattr(Path, 'open', lambda path, *a, **kw: path_open(physical(path), *a, **kw))
    monkeypatch.setattr(helper.os, 'open', lambda path, *a, **kw:
                        raw_open(physical(path) if isinstance(path, (str, Path)) and
                                 str(path).startswith('/') else path, *a, **kw))
    monkeypatch.setattr(helper.os, 'readlink', lambda path, *a, **kw:
                        raw_readlink(physical(path) if path else path, *a, **kw))
    monkeypatch.setattr(helper, 'trusted', lambda path, **kw: logical(real_trusted(physical(path), **kw)))
    monkeypatch.setattr(helper, 'runtime_input_specs', lambda distribution: copy.deepcopy(specs))
    monkeypatch.setattr(helper, 'enforcing', lambda cfg: None)  # No host MAC operations.
    policy = b'attested-private-policy'

    def inputs():
        data = json.dumps(config, sort_keys=True).encode()
        (payload / 'config.json').write_bytes(data)
        (payload / 'config.json').chmod(0o644)
        (payload / 'onpc-kiosk.apparmor').write_bytes(policy)
        (payload / 'onpc-kiosk.apparmor').chmod(0o644)
        return data, policy, ' '.join(hashlib.sha256(item).hexdigest() for item in (data, policy)) + '\n'

    def measure():
        return helper.required_material(*inputs())

    return SimpleNamespace(helper=helper, fixture=scene, specs=specs, config=config,
                           physical=physical, inputs=inputs, measure=measure, payload=payload)


def test_required_material_is_unchanged_by_ambient_parent_metadata(material_host):
    scene = material_host
    baseline = scene.measure()
    sibling = scene.physical('/usr/bin/unrelated')
    sibling.mkdir(mode=0o755)
    scene.helper.verify_required_material(baseline)
    # Do not rewrite config/policy between these two current observations.
    after = scene.helper.required_material(*scene.inputs())
    assert after['digest'] == baseline['digest']
    assert after['record'] == baseline['record']
    assert not any('unrelated' in path for path in after['assertions'])


@pytest.mark.parametrize('kind', ['file', 'directory', 'link'])
@pytest.mark.parametrize('transition', ['add', 'remove', 'rename', 'mode', 'owner', 'kind', 'reappear'])
def test_each_ambient_host_transition_keeps_real_material(material_host, kind, transition):
    scene = material_host
    target = scene.physical('/usr/bin/ambient')
    def create():
        if kind == 'directory':
            target.mkdir(mode=0o755)
        elif kind == 'link':
            target.symlink_to('unconsumed-target')
        else:
            target.write_bytes(b'unconsumed-original')
            target.chmod(0o644)
    def remove():
        target.rmdir() if kind == 'directory' else target.unlink()
    if transition != 'add':
        create()
    args = scene.inputs()
    original = scene.helper.required_material(*args)
    if transition == 'add':
        create()
    elif transition == 'remove':
        remove()
    elif transition == 'rename':
        target.rename(target.with_name('renamed-ambient'))
    elif transition == 'mode':
        scene.fixture.overrides[str(target)] = {'st_mode': target.lstat().st_mode | 0o022}
    elif transition == 'owner':
        scene.fixture.overrides[str(target)] = {'st_uid': 1234}
    elif transition == 'kind':
        remove()
        if kind == 'directory':
            target.write_bytes(b'new-host-file')
        else:
            target.mkdir(mode=0o755)
    else:
        remove()
        create()
    scene.helper.verify_required_material(original)
    assert scene.helper.required_material(*args)['record'] == original['record']


@pytest.mark.parametrize('changed', ['config', 'policy'])
def test_reattested_required_pair_reaches_material_mismatch(material_host, changed):
    scene, helper = material_host, material_host.helper
    baseline = scene.measure()
    if changed == 'config':
        scene.config['domains'] = ['changed-required-role']
    config_bytes, policy_bytes, _ = scene.inputs()
    if changed == 'policy':
        policy_bytes += b'\nconfigured-and-reattested-change'
        (scene.payload / 'onpc-kiosk.apparmor').write_bytes(policy_bytes)
    attestation = ' '.join(hashlib.sha256(data).hexdigest() for data in (config_bytes, policy_bytes)) + '\n'
    current = helper.required_material(config_bytes, policy_bytes, attestation)
    assert current['digest'] != baseline['digest']
    with pytest.raises(ValueError, match='manager-material-stale'):
        helper.select_retained_material(current, baseline['record'], [], {})


@pytest.mark.parametrize('path', ['/usr/bin/native', '/usr/lib/library.so', '/usr/lib/helper',
    '/usr/bin/oh-no-parent-control', '/usr/lib/oh-no-parent-control/kiosk/main.py',
    '/usr/share/extension/wellbeingLogic.mjs', '/usr/share/extension/schemas/gschemas.compiled',
    '/usr/share/confinement/user-units/service.conf', '/usr/share/confinement/session-data/service'])
def test_required_content_drift_changes_material_and_exact_restore_recovers(material_host, path):
    scene = material_host
    baseline = scene.measure()
    source = scene.physical(path)
    original = source.read_bytes()
    source.write_bytes(original + b'REATTESTED-REQUIRED-CHANGE')
    with pytest.raises(ValueError, match='changed'):
        scene.helper.verify_required_material(baseline)
    assert scene.measure()['digest'] != baseline['digest']
    source.write_bytes(original)
    assert scene.measure()['record'] == baseline['record']


@pytest.mark.parametrize('path', ['/usr/bin/native', '/usr/lib/helper', '/usr/bin/oh-no-parent-control'])
def test_same_byte_reinstall_only_in_a_fresh_required_transaction(material_host, path):
    scene = material_host
    baseline = scene.measure()
    source = scene.physical(path)
    replacement = source.with_name('same-byte-replacement')
    replacement.write_bytes(source.read_bytes())
    replacement.chmod(stat.S_IMODE(source.stat().st_mode))
    replacement.replace(source)
    with pytest.raises(ValueError, match='changed'):
        scene.helper.verify_required_material(baseline)
    current = scene.measure()
    assert current['record'] == baseline['record']
    assert current['assertions'][path][:2] != baseline['assertions'][path][:2]


@pytest.mark.parametrize('fault', ['attestation', 'config', 'policy', 'membership', 'optional',
                                  'role', 'substitution', 'alias', 'ancestor', 'helper-mode',
                                  'capability', 'runtime-member', 'disappear'])
def test_current_required_selection_refusals_and_material_changes(material_host, monkeypatch, fault):
    scene, helper = material_host, material_host.helper
    baseline = scene.measure()
    args = scene.inputs()
    if fault == 'attestation':
        args = (*args[:2], '0' * 64 + ' ' + '1' * 64 + '\n')
    elif fault in ('config', 'policy'):
        name = 'config.json' if fault == 'config' else 'onpc-kiosk.apparmor'
        (scene.payload / name).write_bytes(b'not-the-attested-bytes')
    elif fault == 'membership':
        scene.config['runtime_inputs'] = {}
        args = scene.inputs()
    elif fault == 'optional':
        path = scene.physical('/usr/bin/optional')
        path.write_bytes(b'\x7fELFoptional')
        path.chmod(0o755)
    elif fault == 'role':
        scene.config['executables'][0]['role'] = 'session'
        args = scene.inputs()
    elif fault == 'substitution':
        scene.config['executables'][0]['source'] = '/usr/lib/library.so'
        args = scene.inputs()
    elif fault == 'alias':
        link = scene.physical('/usr/bin/alias')
        link.symlink_to('native')
        scene.config['executables'][0]['paths'] = ['/usr/bin/alias']
        args = scene.inputs()
    elif fault == 'ancestor':
        scene.physical('/usr/bin').chmod(0o777)
    elif fault == 'helper-mode':
        scene.physical('/usr/lib/helper').chmod(0o4755)
    elif fault == 'capability':
        original = helper.os.listxattr
        monkeypatch.setattr(helper.os, 'listxattr', lambda fd:
            ['security.capability'] if scene.fixture.fd_path(fd).name == 'native' else original(fd))
    elif fault == 'runtime-member':
        scene.physical('/usr/lib/oh-no-parent-control/kiosk/foreign.py').write_bytes(b'unknown code')
    else:
        scene.physical('/usr/bin/native').unlink()
    if fault in ('optional', 'role', 'substitution', 'alias'):
        changed = helper.required_material(*args)
        assert changed['digest'] != baseline['digest']
        with pytest.raises(ValueError, match='manager-material-stale'):
            helper.select_retained_material(changed, baseline['record'], [], {})
    else:
        with pytest.raises((ValueError, OSError)):
            helper.required_material(*args)
    assert not any(path.name in ('ready', 'bindings') for path in scene.fixture.store.iterdir())


def test_required_measurement_refuses_replacement_during_hash(material_host, monkeypatch):
    scene, helper = material_host, material_host.helper
    args, original = scene.inputs(), helper.runtime_read_digest
    def replace(fd, size, **kwargs):
        digest = original(fd, size, **kwargs)
        source = scene.fixture.fd_path(fd)
        if source == scene.physical('/usr/bin/native'):
            target = source.with_name('replacement')
            target.write_bytes(source.read_bytes())
            target.chmod(0o755)
            target.replace(source)
        return digest
    monkeypatch.setattr(helper, 'runtime_read_digest', replace)
    with pytest.raises(ValueError, match='material-source-changed'):
        helper.required_material(*args)


@pytest.mark.parametrize('name', ['config.json', 'onpc-kiosk.apparmor'])
def test_attested_payload_pair_preserves_direct_file_requirement(material_host, name):
    scene = material_host
    args = scene.inputs()
    path = scene.payload / name
    path.rename(path.with_name('original-' + name))
    path.symlink_to('original-' + name)
    with pytest.raises(ValueError, match='substituted-path'):
        scene.helper.required_material(*args)


def test_original_ambient_addition_stales_legacy_digest_but_selects_original_material(material_host, monkeypatch):
    """Permanent before/after control for the retired 20261019T061016Z probe.

    This observes real private bytes/inodes, not the historical removed probe or
    installed native admission. 006 composes the indices with its native pin.
    """
    scene, helper = material_host, material_host.helper
    args = scene.inputs()
    baseline = helper.required_material(*args)
    def legacy_digest():
        manifest = dict(records=helper.inventory(scene.config),
                        preserved=helper.preserved_inventory(scene.config)[0],
                        layout=helper.directory_layout(scene.config,
                            helper.inventory(scene.config) + helper.preserved_inventory(scene.config)[0]))
        return hashlib.sha256(args[0] + args[1] + json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    legacy_before = legacy_digest()
    process, uid = os.getpid(), 4242
    original_read_text = Path.read_text
    def manager_view(path, *args, **kwargs):
        text = str(path)
        if text == f'/proc/{process}/status':
            return 'Uid:\t' + '\t'.join([str(uid)] * 4) + '\n'
        if text == f'/proc/{process}/root{helper.PAYLOAD}/generation':
            return legacy_before + '\n'
        if text == f'/proc/{process}/attr/apparmor/current':
            return 'onpc-kiosk-manager (enforce)\n'
        return original_read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', manager_view)
    monkeypatch.setattr(helper, 'subprocess', SimpleNamespace(run=lambda *args, **kwargs:
                        SimpleNamespace(stdout=str(process) + '\n')))
    # The real legacy matcher owns/closes a pidfd for this test process. Only
    # its manager observations are doubled; no system service is queried.
    helper.manager_generation(uid, legacy_before, 'apparmor')
    manager = scene.fixture.store / 'original-manager'
    manager.mkdir(mode=0o755)
    expected = {item['path']: item for item in baseline['native'] + baseline['preserved'] +
                baseline['runtime'] + baseline['payload'] if item.get('kind', 'file') == 'file'}
    layout, pins, opened = [], {}, []
    for kind, path, link in sorted(baseline['proofs'], key=lambda item: (item[1].count('/'), item[1])):
        if path != '/usr' and not path.startswith('/usr/'):
            continue
        target = manager / path.lstrip('/')
        if kind == 'directory':
            target.mkdir(mode=0o755)
        elif kind == 'link':
            target.symlink_to(link)
        else:
            target.write_bytes(scene.physical(path).read_bytes())
            target.chmod(expected[path]['mode'])
        if path != '/usr':
            layout.append(dict(path=path, kind='tree' if kind == 'directory' else kind,
                               **({'link': link} if kind == 'link' else {})))
        fd = os.open(target, os.O_CLOEXEC | os.O_NOFOLLOW |
                     (os.O_PATH if kind == 'link' else os.O_RDONLY) |
                     (os.O_DIRECTORY if kind == 'directory' else 0))
        opened.append(fd)
        pins[path] = dict(fd=fd, identity=helper.file_identity(helper.os.fstat(fd))[:2])
    try:
        selected_before = helper.select_retained_material(baseline, baseline['record'], layout, pins)
        scene.physical('/usr/share/unrelated-empty').mkdir(mode=0o755)
        legacy_after = legacy_digest()
        assert legacy_after != legacy_before
        with pytest.raises(ValueError, match='manager-generation-stale'):
            helper.manager_generation(uid, legacy_after, 'apparmor')
        current = helper.required_material(*args)
        selected_after = helper.select_retained_material(current, baseline['record'], layout, pins)
        assert current['digest'] == baseline['digest']
        assert selected_after == selected_before
        assert '/usr/share/unrelated-empty' not in selected_after['sources']
        assert not (manager / 'usr/share/unrelated-empty').exists()
        for path, source in selected_after['sources'].items():
            assert source['assertion'][:2] == pins[path]['identity']
            if path in expected:
                assert hashlib.sha256(os.pread(pins[path]['fd'], expected[path]['size'], 0)).hexdigest() == expected[path]['sha256']
    finally:
        for fd in opened:
            os.close(fd)
