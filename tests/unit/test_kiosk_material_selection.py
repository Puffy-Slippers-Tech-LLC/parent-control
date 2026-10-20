"""Required material and retained selection using only pytest-private descriptors."""
import copy
import errno
import hashlib
import json
import os
from types import SimpleNamespace

import pytest

from tests.support.kiosk_material import private_store, named_fixture
from tests.support.kiosk_material_selection import material_scene, selected_scene


def add_ambient(scene, kind):
    path = '/usr/ambient'
    target = scene.retained / path.lstrip('/')
    if kind == 'directory':
        target.mkdir(mode=0o755)
        (target / 'original-child').write_bytes(b'original-manager-child')
    elif kind == 'link':
        target.symlink_to('original-target')
    else:
        target.write_bytes(b'original-manager-token')
        target.chmod(0o644)
    scene.layout.append(dict(path=path, kind=kind,
                             **({'link': 'original-target'} if kind == 'link' else {})))
    scene.pin(path, kind)
    return path, target


@pytest.mark.parametrize('kind', ['file', 'directory', 'link'])
@pytest.mark.parametrize('transition', ['add', 'remove', 'rename', 'mode', 'owner',
                                       'kind', 'disappear-reappear'])
def test_ambient_host_transitions_keep_original_sources(material_scene, monkeypatch, kind, transition):
    scene = material_scene
    path, original = add_ambient(scene, kind)
    snapshot, select = selected_scene(scene, monkeypatch)
    baseline = select()
    before_layout = copy.deepcopy(scene.layout)
    before = scene.helper.file_identity(scene.helper.os.fstat(scene.pins[path]['fd']))
    host = scene.fixture.host / path.lstrip('/')
    def create_host(replacement=False):
        if kind == 'directory':
            host.mkdir(mode=0o755)
            if replacement:
                (host / 'new-content').write_bytes(b'NEW-HOST-DIRECTORY-TOKEN')
        elif kind == 'link':
            host.symlink_to('NEW-HOST-LINK-TOKEN' if replacement else 'host-before')
        else:
            host.write_bytes(b'NEW-HOST-FILE-TOKEN' if replacement else b'host-before')
            host.chmod(0o644)

    def remove_host():
        host.rmdir() if kind == 'directory' else host.unlink()

    if transition != 'add':
        create_host()
    if transition == 'remove':
        remove_host()
    elif transition == 'rename':
        host.rename(host.with_name('renamed-host'))
    elif transition == 'mode':
        if kind == 'link':
            scene.fixture.overrides[str(host)] = {'st_mode': os.lstat(host).st_mode | 0o022}
        else:
            host.chmod(0o777)
    elif transition == 'owner':
        scene.fixture.overrides[str(host)] = {'st_uid': 1234}
    elif transition == 'kind':
        remove_host()
        if kind == 'directory':
            host.write_bytes(b'NEW-HOST-KIND-TOKEN')
        else:
            host.mkdir(mode=0o755)
    else:
        if transition == 'disappear-reappear':
            remove_host()
        create_host(replacement=True)
    # Selection can inspect only the caller's pins after independent current
    # material verification. Any source-path fallback is a regression.
    monkeypatch.setattr(scene.helper, 'runtime_open',
                        lambda *args, **kwargs: pytest.fail('selection reopened a host source'))
    actual_open = scene.helper.os.open

    def no_host_open(source, *args, **kwargs):
        name = os.fsdecode(source)
        assert not (name == '/usr' or name.startswith('/usr/') or
                    name.startswith(str(scene.fixture.host))), 'selection opened current host content'
        return actual_open(source, *args, **kwargs)

    monkeypatch.setattr(scene.helper.os, 'open', no_host_open)
    result = select()
    assert result == baseline
    assert result['sources'][path]['assertion'] == before
    assert result['sources'][path]['index'] == sorted(scene.pins).index(path)
    assert scene.layout == before_layout
    assert original.lstat().st_ino == before[1]
    if kind == 'file':
        assert original.read_bytes() == b'original-manager-token'
    elif kind == 'directory':
        assert (original / 'original-child').read_bytes() == b'original-manager-child'
    else:
        assert os.readlink(original) == 'original-target'
    assert snapshot['digest'] == result['material']


@pytest.mark.parametrize('kind', ['file', 'directory', 'link'])
def test_unsafe_retained_ambient_is_narrowed_without_mutating_manager(material_scene, monkeypatch, kind):
    scene = material_scene
    path, original = add_ambient(scene, kind)
    _, select = selected_scene(scene, monkeypatch)
    original_layout = copy.deepcopy(scene.layout)
    if kind == 'link':
        scene.fixture.overrides[str(original)] = {'st_uid': 1234}
    else:
        original.chmod(0o777)
    result = select()
    assert path not in result['sources']
    assert [entry for entry in result['layout'] if entry['path'] == path] == (
        [dict(path=path, kind='empty-directory')] if kind == 'directory' else [])
    assert scene.layout == original_layout
    assert original.is_symlink() if kind == 'link' else original.exists()
    if kind == 'directory':
        assert (original / 'original-child').read_bytes() == b'original-manager-child'
    # The returned invocation decision does not widen when trust returns.
    if kind == 'link':
        scene.fixture.overrides.clear()
    else:
        original.chmod(0o755)
    assert path not in result['sources']


def test_original_mask_and_absence_never_acquire_host_sources(material_scene, monkeypatch):
    scene = material_scene
    scene.layout.append(dict(path='/usr/masked', kind='empty-directory'))
    (scene.fixture.host / 'usr/masked').mkdir(mode=0o755)
    (scene.fixture.host / 'usr/new-file').write_bytes(b'new-host-source')
    _, select = selected_scene(scene, monkeypatch)
    result = select()
    assert dict(path='/usr/masked', kind='empty-directory') in result['layout']
    assert '/usr/masked' not in result['sources']
    assert '/usr/new-file' not in result['sources']
    assert all(entry['path'] != '/usr/new-file' for entry in result['layout'])


def test_ambient_omission_preserves_original_source_indices(material_scene, monkeypatch):
    scene = material_scene
    path, original = add_ambient(scene, 'file')
    _, select = selected_scene(scene, monkeypatch)
    baseline = select()
    original.chmod(0o666)
    narrowed = select()
    assert path not in narrowed['sources']
    for name, source in narrowed['sources'].items():
        assert source['index'] == baseline['sources'][name]['index']


@pytest.mark.parametrize('fault', ['mode', 'owner', 'provenance', 'missing'])
def test_required_retained_ancestor_cannot_become_ambient(material_scene, monkeypatch, fault):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    path = '/usr/bin'
    target = scene.retained / 'usr/bin'
    if fault == 'mode':
        target.chmod(0o777)
    elif fault == 'owner':
        scene.fixture.overrides[str(target)] = {'st_uid': 1234}
    elif fault == 'provenance':
        scene.pins[path]['identity'] = (0, 0)
    else:
        del scene.pins[path]
    before = copy.deepcopy(scene.layout)
    with pytest.raises(ValueError):
        scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
    assert scene.layout == before
    assert (target / 'native').read_bytes() == scene.required['/usr/bin/native']


def test_current_material_verification_failure_precedes_selection(material_scene, monkeypatch):
    scene = material_scene
    snapshot = scene.measure()

    def changed(value):
        assert value is snapshot
        raise ValueError('current-required-input-changed')

    monkeypatch.setattr(scene.helper, 'verify_required_material', changed)
    with pytest.raises(ValueError, match='current-required-input-changed'):
        scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)


def test_same_byte_current_reinstall_keeps_original_required_pin(material_scene, monkeypatch):
    scene = material_scene
    snapshot, select = selected_scene(scene, monkeypatch)
    baseline = select()
    source = scene.fixture.host / 'usr/lib/helper'
    replacement = source.with_name('replacement')
    replacement.write_bytes(source.read_bytes())
    replacement.chmod(0o755)
    replacement.replace(source)
    assert source.stat().st_ino != scene.pins['/usr/lib/helper']['identity'][1]
    assert select() == baseline
    assert snapshot['digest'] == baseline['material']


@pytest.mark.parametrize('fault', ['content', 'mode', 'owner', 'provenance', 'missing-pin',
                                  'missing-layout', 'masked-required', 'duplicate-layout'])
@pytest.mark.parametrize('path', ['/usr/bin/native', '/usr/bin/script', '/usr/lib/helper'],
                         ids=['native', 'runtime', 'preserved'])
def test_required_retained_drift_refuses_without_publication(material_scene, monkeypatch, fault, path):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    target = scene.retained / path.lstrip('/')
    if fault == 'content':
        target.write_bytes(b'changed-required-native')
    elif fault == 'mode':
        target.chmod(0o777)
    elif fault == 'owner':
        scene.fixture.overrides[str(target)] = {'st_uid': 1234}
    elif fault == 'provenance':
        scene.pins[path]['identity'] = (0, 0)
    elif fault == 'missing-pin':
        del scene.pins[path]
    elif fault == 'missing-layout':
        scene.layout[:] = [entry for entry in scene.layout if entry['path'] != path]
    elif fault == 'masked-required':
        next(entry for entry in scene.layout if entry['path'] == path)['kind'] = 'empty-directory'
    else:
        scene.layout.append(dict(path=path, kind='file'))
    before = copy.deepcopy(scene.layout)
    with pytest.raises((ValueError, OSError)):
        scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
    assert scene.layout == before
    assert not (scene.fixture.store / 'ready').exists()
    assert not (scene.fixture.store / 'bindings').exists()


def test_required_material_mismatch_cannot_select_existing_view(material_scene, monkeypatch):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    changed = copy.deepcopy(snapshot['record'])
    changed['unexpected-material-field'] = True
    with pytest.raises(ValueError):
        scene.helper.select_retained_material(snapshot, changed, scene.layout, scene.pins)


def test_unlinked_helper_renews_all_eight_assertions_without_changing_pin(material_scene, monkeypatch):
    scene = material_scene
    _, select = selected_scene(scene, monkeypatch)
    path = '/usr/lib/helper'
    fd = scene.pins[path]['fd']
    before = scene.helper.file_identity(scene.helper.os.fstat(fd))
    (scene.retained / path.lstrip('/')).unlink()
    fresh = scene.helper.file_identity(scene.helper.os.fstat(fd))
    assert os.fstat(fd).st_nlink == 0
    assert fresh[:2] == before[:2]
    assert fresh[4] != before[4]
    result = select()
    assert result['sources'][path]['assertion'] == fresh
    assert len(result['sources'][path]['assertion']) == 8
    assert os.pread(fd, 4096, 0) == scene.required[path]


def test_retained_helper_positive_hardlink_refuses(material_scene, monkeypatch):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    helper_path = scene.retained / 'usr/lib/helper'
    os.link(helper_path, scene.fixture.store / 'extra-helper-link')
    with pytest.raises(ValueError):
        scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
    assert helper_path.read_bytes() == scene.required['/usr/lib/helper']


def selinux_projection(scene, monkeypatch):
    snapshot, _ = selected_scene(scene, monkeypatch)
    snapshot['config']['backend'] = snapshot['record']['backend'] = 'selinux'
    snapshot['record']['config'] = hashlib.sha256(
        json.dumps(snapshot['config'], sort_keys=True).encode()).hexdigest()
    labels = {'/usr/bin/native': 'system_u:object_r:onpc_kiosk_service_exec_t:s0',
              '/usr/bin/script': 'system_u:object_r:bin_t:s0',
              '/usr/lib/helper': 'system_u:object_r:policykit_auth_exec_t:s0'}
    for item in snapshot['native'] + snapshot['runtime'] + snapshot['preserved']:
        item['label'] = labels[item['path']]
        fd = scene.pins[item['path']]['fd']
        scene.fixture.labels[scene.fixture.label_key(fd)] = item['label']
    snapshot['digest'] = scene.helper.material_digest(snapshot['record'])
    return snapshot


def test_selinux_selection_preserves_distinct_native_runtime_and_helper_labels(material_scene, monkeypatch):
    scene = material_scene
    snapshot = selinux_projection(scene, monkeypatch)
    monkeypatch.setattr(scene.helper, 'runtime_open',
                        lambda *args, **kwargs: pytest.fail('SELinux selection reopened a host source'))
    result = scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
    assert result['material'] == snapshot['digest']
    assert set(scene.required) <= result['sources'].keys()
    for path in scene.required:
        fd = scene.pins[path]['fd']
        assert result['sources'][path]['assertion'] == scene.helper.file_identity(scene.helper.os.fstat(fd))
        assert os.pread(fd, 4096, 0) == scene.required[path]


@pytest.mark.parametrize('path', ['/usr/bin/native', '/usr/bin/script', '/usr/lib/helper'],
                         ids=['native', 'runtime', 'preserved'])
def test_selinux_required_source_label_mismatch_refuses(material_scene, monkeypatch, path):
    scene = material_scene
    snapshot = selinux_projection(scene, monkeypatch)
    key = scene.fixture.label_key(scene.pins[path]['fd'])
    scene.fixture.labels[key] = 'system_u:object_r:unlabeled_t:s0'
    with pytest.raises(ValueError, match='retained-required-source'):
        scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
    assert scene.fixture.labels[key] == 'system_u:object_r:unlabeled_t:s0'


@pytest.mark.parametrize('path', ['/usr/bin/native', '/usr/bin/script', '/usr/lib/helper'],
                         ids=['native', 'runtime', 'preserved'])
@pytest.mark.parametrize('fault', ['capability', 'gid', 'hardlink'])
def test_required_source_privilege_metadata_refuses(material_scene, monkeypatch, path, fault):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    target, fd = scene.retained / path.lstrip('/'), scene.pins[path]['fd']
    if fault == 'capability':
        original = scene.helper.os.listxattr
        monkeypatch.setattr(scene.helper.os, 'listxattr', lambda candidate:
                            ['security.capability'] if candidate == fd else original(candidate))
    elif fault == 'gid':
        scene.fixture.overrides[str(target)] = {'st_gid': 1234}
    else:
        os.link(target, scene.fixture.store / 'positive-hardlink')
    with pytest.raises(ValueError, match='retained-required-source'):
        scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
    assert target.read_bytes() == scene.required[path]


@pytest.mark.parametrize('kind', ['file', 'directory', 'link'])
@pytest.mark.parametrize('required', [False, True], ids=['ambient', 'required'])
@pytest.mark.parametrize('error', [errno.EACCES, errno.EPERM, errno.EIO, errno.ESTALE],
                         ids=['EACCES', 'EPERM', 'EIO', 'ESTALE'])
def test_source_local_metadata_errors_only_narrow_ambient_view(
        material_scene, monkeypatch, kind, required, error):
    scene = material_scene
    path, original = add_ambient(scene, kind)
    snapshot, _ = selected_scene(scene, monkeypatch)
    if required:
        snapshot['proofs'].append([kind, path, 'original-target' if kind == 'link' else '-'])
        if kind == 'directory':
            next(node for node in scene.layout if node['path'] == path)['kind'] = 'tree'
        snapshot['digest'] = scene.helper.material_digest(snapshot['record'])
    fd = scene.pins[path]['fd']
    fstat = scene.helper.os.fstat
    reached = []

    def unavailable(candidate):
        if candidate == fd:
            reached.append(candidate)
            raise OSError(error, 'private source metadata unavailable')
        return fstat(candidate)

    monkeypatch.setattr(scene.helper.os, 'fstat', unavailable)
    before = copy.deepcopy(scene.layout)
    if required:
        with pytest.raises((ValueError, OSError)):
            scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
    else:
        result = scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
        assert path not in result['sources']
        assert [node for node in result['layout'] if node['path'] == path] == (
            [dict(path=path, kind='empty-directory')] if kind == 'directory' else [])
    assert scene.layout == before
    assert reached == [fd]
    assert original.is_symlink() if kind == 'link' else original.exists()


@pytest.mark.parametrize('required', [False, True], ids=['ambient', 'required'])
@pytest.mark.parametrize('error', [errno.EACCES, errno.EPERM, errno.EIO, errno.ESTALE],
                         ids=['EACCES', 'EPERM', 'EIO', 'ESTALE'])
def test_link_text_source_errors_only_omit_ambient_link(material_scene, monkeypatch, required, error):
    scene = material_scene
    path, original = add_ambient(scene, 'link')
    snapshot, _ = selected_scene(scene, monkeypatch)
    if required:
        snapshot['proofs'].append(['link', path, 'original-target'])
        snapshot['digest'] = scene.helper.material_digest(snapshot['record'])
    readlink, reached = scene.helper.os.readlink, []
    fd = scene.pins[path]['fd']

    def unavailable(name, *args, **kwargs):
        if name == '' and kwargs.get('dir_fd') == fd:
            reached.append(fd)
            raise OSError(error, 'private link source unavailable')
        return readlink(name, *args, **kwargs)

    monkeypatch.setattr(scene.helper.os, 'readlink', unavailable)
    if required:
        with pytest.raises(OSError) as failure:
            scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
        assert failure.value.errno == error
    else:
        result = scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
        assert path not in result['sources']
        assert all(node['path'] != path for node in result['layout'])
    assert reached == [fd]
    assert os.readlink(original) == 'original-target'


@pytest.mark.parametrize('error', [errno.EBADF, errno.EMFILE, errno.ENOMEM],
                         ids=['EBADF', 'EMFILE', 'ENOMEM'])
def test_global_or_bad_descriptor_errors_cannot_omit_ambient_source(material_scene, monkeypatch, error):
    scene = material_scene
    path, _ = add_ambient(scene, 'file')
    snapshot, _ = selected_scene(scene, monkeypatch)
    fstat, fd = scene.helper.os.fstat, scene.pins[path]['fd']

    def broken(candidate):
        if candidate == fd:
            raise OSError(error, 'private non-source failure')
        return fstat(candidate)

    monkeypatch.setattr(scene.helper.os, 'fstat', broken)
    with pytest.raises(OSError) as failure:
        scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
    assert failure.value.errno == error


@pytest.mark.parametrize('required', [False, True], ids=['ambient', 'required'])
@pytest.mark.parametrize('fault', ['wrong-kind', 'wrong-link-text', 'wrong-provenance'])
def test_substitute_descriptors_do_not_supply_original_source(
        material_scene, monkeypatch, required, fault):
    scene = material_scene
    path, original = add_ambient(scene, 'link')
    snapshot, _ = selected_scene(scene, monkeypatch)
    if required:
        snapshot['proofs'].append(['link', path, 'original-target'])
        snapshot['digest'] = scene.helper.material_digest(snapshot['record'])
    substitute = scene.retained / 'usr/substitute'
    if fault == 'wrong-kind':
        substitute.write_bytes(b'wrong source kind')
    else:
        substitute.symlink_to('wrong-target')
    scene.pin('/usr/substitute', 'file' if fault == 'wrong-kind' else 'link')
    substitute_pin = scene.pins.pop('/usr/substitute')
    if fault == 'wrong-provenance':
        substitute_pin['identity'] = scene.pins[path]['identity']
    scene.pins[path] = substitute_pin
    if required or fault == 'wrong-provenance':
        with pytest.raises(ValueError, match='retained-required-source|retained-source-identity'):
            scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
    else:
        result = scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
        assert path not in result['sources']
        assert all(node['path'] != path for node in result['layout'])
    assert os.readlink(original) == 'original-target'


@pytest.mark.parametrize('boundary', ['hash', 'final-sweep'])
def test_required_source_change_at_observation_boundary_refuses(material_scene, monkeypatch, boundary):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    path = '/usr/bin/native'
    target, fd = scene.retained / path.lstrip('/'), scene.pins[path]['fd']
    reached = []
    if boundary == 'hash':
        read_digest = scene.helper.runtime_read_digest

        def hash_then_change(candidate, size, **kwargs):
            result = read_digest(candidate, size, **kwargs)
            if candidate == fd:
                reached.append(boundary)
                target.chmod(0o700)
            return result

        monkeypatch.setattr(scene.helper, 'runtime_read_digest', hash_then_change)
    else:
        checks = []

        def current_verified(value):
            checks.append(value)
            if len(checks) == 2:
                reached.append(boundary)
                target.chmod(0o700)

        monkeypatch.setattr(scene.helper, 'verify_required_material', current_verified)
    with pytest.raises(ValueError, match='retained-source-changed'):
        scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
    assert reached == [boundary]
    assert target.read_bytes() == scene.required[path]


@pytest.mark.parametrize('fault', ['extra-field', 'relative-path', 'outside-usr', 'unknown-kind',
                                  'missing-parent', 'row-budget', 'combined-budget'])
def test_selection_layout_schema_and_row_bounds_refuse(material_scene, monkeypatch, fault):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    reason = 'retained-layout|protocol|unsafe-directory-entry'
    if fault == 'extra-field':
        scene.layout[0]['unknown'] = True
    elif fault in ('relative-path', 'outside-usr'):
        scene.layout[0]['path'] = 'usr/bin' if fault == 'relative-path' else '/etc/bin'
    elif fault == 'unknown-kind':
        scene.layout[0]['kind'] = 'socket'
    elif fault == 'missing-parent':
        scene.layout[:] = [node for node in scene.layout if node['path'] != '/usr/bin']
    elif fault == 'row-budget':
        monkeypatch.setattr(scene.helper, 'MAX_ROWS', len(scene.layout) - 1)
    else:
        monkeypatch.setattr(scene.helper, 'MAX_ROWS', len(scene.layout))
        reason = 'material-limit'
    with pytest.raises(ValueError, match=reason):
        scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)


@pytest.mark.parametrize('fault', ['bool-fd', 'negative-fd', 'text-fd', 'extra-field',
                                  'short-identity', 'bool-identity', 'negative-identity', 'missing-root'])
def test_pin_descriptor_shape_is_closed(material_scene, monkeypatch, fault):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    pin = scene.pins['/usr/bin/native']
    if fault.endswith('-fd'):
        pin['fd'] = {'bool-fd': True, 'negative-fd': -1, 'text-fd': '3'}[fault]
    elif fault == 'extra-field':
        pin['path'] = '/usr/bin/native'
    elif fault == 'short-identity':
        pin['identity'] = [pin['identity'][0]]
    elif fault == 'bool-identity':
        pin['identity'] = [True, pin['identity'][1]]
    elif fault == 'negative-identity':
        pin['identity'] = [-1, pin['identity'][1]]
    else:
        del scene.pins['/usr']
    with pytest.raises(ValueError, match='retained-source-identity'):
        scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)


def test_closed_private_descriptor_refuses_without_closing_other_pins(material_scene, monkeypatch):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    fd = os.dup(scene.pins['/usr/bin/native']['fd'])
    os.close(fd)
    scene.pins['/usr/bin/native']['fd'] = fd
    with pytest.raises(OSError) as failure:
        scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
    assert failure.value.errno == errno.EBADF
    for path, pin in scene.pins.items():
        if path != '/usr/bin/native':
            assert os.fstat(pin['fd']).st_ino == pin['identity'][1]


@pytest.mark.parametrize('kind', ['file', 'directory', 'link'])
@pytest.mark.parametrize('error', [errno.EACCES, errno.EPERM, errno.EIO, errno.ESTALE])
@pytest.mark.parametrize('required', [False, True], ids=['ambient', 'required'])
def test_final_source_error_narrows_only_ambient_material(material_scene, monkeypatch, kind, error, required):
    scene = material_scene
    path, original = add_ambient(scene, kind)
    snapshot, _ = selected_scene(scene, monkeypatch)
    if required:
        # Required directories are concrete parents, never shallow ambient binds.
        if kind == 'directory':
            next(node for node in scene.layout if node['path'] == path)['kind'] = 'tree'
        snapshot['proofs'].append(['directory' if kind == 'directory' else kind, path,
                                   'original-target' if kind == 'link' else '-'])
        snapshot['digest'] = scene.helper.material_digest(snapshot['record'])
    fd = scene.pins[path]['fd']
    actual_fstat, reached = scene.helper.os.fstat, []
    def fstat(candidate):
        if candidate == fd:
            reached.append(candidate)
            if len(reached) == 3:  # Before/after observation succeeded; final sweep fails.
                raise OSError(error, 'private-final-source-observation')
        return actual_fstat(candidate)
    monkeypatch.setattr(scene.helper.os, 'fstat', fstat)
    original_layout = copy.deepcopy(scene.layout)
    if required:
        with pytest.raises(OSError) as failure:
            scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
        assert failure.value.errno == error
    else:
        result = scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
        assert path not in result['sources']
        assert [node for node in result['layout'] if node['path'] == path] == (
            [dict(path=path, kind='empty-directory')] if kind == 'directory' else [])
        for name, source in result['sources'].items():
            assert source['index'] == sorted(scene.pins).index(name)
    assert len(reached) == 3
    assert scene.layout == original_layout
    assert original.lstat().st_ino == scene.pins[path]['identity'][1]


@pytest.mark.parametrize('after_rename', [False, True], ids=['before-publication', 'after-publication'])
def test_interrupted_material_copy_never_publishes_ready(private_store, monkeypatch, after_rename):
    fixture, helper = private_store, private_store.helper
    specs = named_fixture(fixture)
    records, assertions = helper.measure_runtime_inputs(specs, 'apparmor')
    unrelated = fixture.store / 'unrelated'
    unrelated.mkdir(mode=0o700)
    actual_fsync = helper.os.fsync
    with pytest.raises(RuntimeError, match='material-publication-cut'):
        with helper.RuntimeCopyPublication(fixture.store, 'apparmor', specs) as attempt:
            receipt = attempt.copy(records, assertions)
            if not after_rename:
                raise RuntimeError('material-publication-cut')

            def fsync(fd):
                if fd == attempt.parent:
                    raise RuntimeError('material-publication-cut')
                actual_fsync(fd)

            monkeypatch.setattr(helper.os, 'fsync', fsync)
            attempt.publish('a' * 64, receipt)
    assert unrelated.is_dir()
    completed = fixture.store / ('a' * 64)
    assert completed.exists() is after_rename
    if after_rename:
        fd = helper.runtime_open(completed, directory=True)
        try:
            helper.verify_runtime_copies(fd, receipt, 'apparmor', specs)
        finally:
            os.close(fd)
        assert not any((completed / name).exists() for name in ('ready', 'bindings', 'tree'))
    else:
        assert list(fixture.store.iterdir()) == [unrelated]
