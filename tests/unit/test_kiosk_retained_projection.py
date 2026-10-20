"""Bounded descriptor projection from a caller-owned, already verified clone.

Only pytest-private files/descriptors and process-local doubles are used here.
The actual recursive clone and its authority belong to the native witnesses.
"""
import errno
import os

import pytest

from tests.support.kiosk_material_selection import material_scene, selected_scene
from tests.support.kiosk_material import private_store


def projection(scene, extra=0):
    entries = {path: dict(kind='tree' if path == '/usr' else next(
        node['kind'] for node in scene.layout if node['path'] == path),
        identity=pin['identity']) for path, pin in scene.pins.items()}
    for index in range(extra):
        path = '/usr/ambient-' + str(index)
        target = scene.retained / path.lstrip('/')
        target.write_bytes(b'original-retained-source')
        target.chmod(0o644)
        info = target.stat()
        entries[path] = dict(kind='file', identity=(info.st_dev, info.st_ino))
        scene.layout.append(dict(path=path, kind='file'))
    for node in scene.layout:
        if node['path'] not in entries and node['kind'] != 'empty-directory':
            info = (scene.retained / node['path'].lstrip('/')).lstat()
            entries[node['path']] = dict(kind=node['kind'], identity=(info.st_dev, info.st_ino))
    return scene.helper.RetainedSourceProjection(scene.pins['/usr']['fd'], entries)


def test_streaming_selection_keeps_constant_descriptor_use_and_original_bytes(material_scene, monkeypatch):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    before = len(os.listdir('/proc/self/fd'))
    with projection(scene, extra=512) as pins:
        raw_open = scene.helper.os.open
        peaks = []

        def observe(path, *args, **kwargs):
            # No absolute source can be the host pathname. The only absolute
            # reopen names a checked, still-open descriptor to allow hashing.
            assert not os.fspath(path).startswith('/') or os.fspath(path).startswith('/proc/self/fd/')
            result = raw_open(path, *args, **kwargs)
            peaks.append(len(os.listdir('/proc/self/fd')))
            return result

        monkeypatch.setattr(scene.helper.os, 'open', observe)
        selected = scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, pins)
        assert selected['layout'] == sorted(scene.layout, key=lambda node: node['path'])
        assert set(selected['sources']) == set(pins)
        assert max(peaks) <= before + 4
        assert [source['index'] for _, source in sorted(selected['sources'].items())] == list(range(len(pins)))
        source = pins['/usr/ambient-511']['fd']
        assert os.read(source, 100) == b'original-retained-source'
        assert not os.get_inheritable(source)
        assert not os.get_inheritable(pins.root)
    assert len(os.listdir('/proc/self/fd')) == before
    # The caller's clone root remains owned by its native caller.
    assert os.fstat(scene.pins['/usr']['fd']).st_ino == scene.pins['/usr']['identity'][1]


@pytest.mark.parametrize('change', ['root', 'file', 'ancestor', 'alias'])
def test_projection_refuses_foreign_identity_before_reading_replacement(material_scene, monkeypatch, change):
    scene = material_scene
    before = len(os.listdir('/proc/self/fd'))
    pins = projection(scene)
    try:
        if change == 'root':
            entries = {path: dict(entry) for path, entry in pins.entries.items()}
            entries['/usr']['identity'] = (0, 1)
            with pytest.raises(ValueError, match='retained-source-identity'):
                scene.helper.RetainedSourceProjection(scene.pins['/usr']['fd'], entries)
            return
        target = scene.retained / 'usr/bin/native'
        if change == 'file':
            target.rename(target.with_name('old-native'))
            target.write_bytes(b'FOREIGN-HOST-TOKEN')
        else:
            parent = target.parent
            parent.rename(parent.with_name('old-bin'))
            if change == 'ancestor':
                parent.mkdir(mode=0o755)
                # Even the same endpoint inode cannot bless a replaced parent.
                os.link(parent.with_name('old-bin') / 'native', target)
            else:
                parent.symlink_to('old-bin', target_is_directory=True)
        raw_open = scene.helper.os.open

        def no_read(path, flags, *args, **kwargs):
            assert flags & os.O_PATH, 'foreign source was reopened for reading'
            return raw_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(scene.helper.os, 'open', no_read)
        with pytest.raises(ValueError, match='retained-source-identity'):
            pins['/usr/bin/native']
    finally:
        pins.close()
        assert len(os.listdir('/proc/self/fd')) == before


@pytest.mark.parametrize('required', [False, True])
@pytest.mark.parametrize('error', [errno.EACCES, errno.EPERM, errno.EIO, errno.ESTALE])
def test_local_open_failure_narrows_only_ambient_projection(material_scene, monkeypatch, required, error):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    before = len(os.listdir('/proc/self/fd'))
    with projection(scene, extra=1) as pins:
        path = '/usr/bin/native' if required else '/usr/ambient-0'
        leaf = path.rsplit('/', 1)[1]
        raw_open = scene.helper.os.open

        def unavailable(name, *args, **kwargs):
            if name == leaf:
                raise OSError(error, 'injected private-source failure')
            return raw_open(name, *args, **kwargs)

        monkeypatch.setattr(scene.helper.os, 'open', unavailable)
        if required:
            with pytest.raises(OSError) as caught:
                scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, pins)
            assert caught.value.errno == error
        else:
            original = list(scene.layout)
            selected = scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, pins)
            assert path not in selected['sources']
            assert all(node['path'] != path for node in selected['layout'])
            assert scene.layout == original
    assert len(os.listdir('/proc/self/fd')) == before


def test_projection_links_remain_links_and_never_follow_absolute_targets(material_scene):
    scene = material_scene
    target = scene.retained / 'usr/mask'
    target.symlink_to('/dev/null')
    info = target.lstat()
    scene.layout.append(dict(path='/usr/mask', kind='link', link='/dev/null'))
    with projection(scene) as pins:
        borrowed = pins['/usr/mask']['fd']
        assert os.readlink('', dir_fd=borrowed) == '/dev/null'
        assert os.fstat(borrowed).st_ino == info.st_ino
        with pytest.raises(OSError):
            os.read(borrowed, 1)


def test_selection_retains_original_slots_across_masks_absences_and_late_loss(material_scene, monkeypatch):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    # These original V rows have no source descriptors. Their slots still
    # precede every bin/source slot, and must survive a fresh I selection.
    scene.layout.extend([dict(path='/usr/aaa-mask', kind='empty-directory'),
                         dict(path='/usr/aab-absent', kind='absent')])
    lost = scene.retained / 'usr/aac-late-loss'
    lost.write_bytes(b'original-manager-dentry')
    lost.chmod(0o644)
    scene.layout.append(dict(path='/usr/aac-late-loss', kind='file'))
    scene.pin('/usr/aac-late-loss', 'file')
    slots = {path: 7 + 3 * index for index, path in enumerate(
        sorted(['/usr', *(node['path'] for node in scene.layout)]))}
    entries = {path: dict(kind='tree' if path == '/usr' else next(
        node['kind'] for node in scene.layout if node['path'] == path),
        identity=pin['identity']) for path, pin in scene.pins.items()}
    with scene.helper.RetainedSourceProjection(scene.pins['/usr']['fd'], entries) as pins:
        selected = scene.helper.select_retained_material(
            snapshot, snapshot['record'], scene.layout, pins, source_slots=slots)
        raw_open = scene.helper.os.open

        def unavailable(name, *args, **kwargs):
            if name == 'aac-late-loss':
                raise OSError(errno.EACCES, 'private ambient open refusal')
            return raw_open(name, *args, **kwargs)

        monkeypatch.setattr(scene.helper.os, 'open', unavailable)
        narrower = scene.helper.select_retained_material(
            snapshot, snapshot['record'], scene.layout, pins, source_slots=slots)
    assert selected['source_slots'] == slots
    assert selected['source_slots'] is not slots
    assert {path: item['index'] for path, item in selected['sources'].items()} == {
        path: slots[path] for path in scene.pins}
    assert dict(path='/usr/aaa-mask', kind='empty-directory') in selected['layout']
    assert all(node['path'] != '/usr/aab-absent' for node in selected['layout'])
    assert dict(path='/usr/aab-absent', kind='absent') in scene.layout
    assert narrower['source_slots'] == slots
    assert '/usr/aac-late-loss' not in narrower['sources']
    assert all(node['path'] != '/usr/aac-late-loss' for node in narrower['layout'])
    assert narrower['sources']['/usr/bin/native']['index'] == slots['/usr/bin/native']
    assert lost.read_bytes() == b'original-manager-dentry'


def test_default_plan_slots_count_original_masks(material_scene, monkeypatch):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    scene.layout.append(dict(path='/usr/aaa-mask', kind='empty-directory'))
    selected = scene.helper.select_retained_material(snapshot, snapshot['record'], scene.layout, scene.pins)
    complete = sorted(['/usr', *(node['path'] for node in scene.layout)])
    assert selected['sources']['/usr/bin/native']['index'] == complete.index('/usr/bin/native')
    assert selected['source_slots']['/usr/aaa-mask'] == 1


@pytest.mark.parametrize('fault', ['missing', 'extra', 'duplicate', 'reversed', 'boolean', 'negative'])
def test_selection_refuses_ambiguous_original_slots_before_source_access(material_scene, monkeypatch, fault):
    scene = material_scene
    snapshot, _ = selected_scene(scene, monkeypatch)
    paths = sorted(['/usr', *(node['path'] for node in scene.layout)])
    slots = dict(zip(paths, range(len(paths))))
    if fault == 'missing':
        del slots[paths[-1]]
    elif fault == 'extra':
        slots['/usr/foreign'] = len(paths)
    elif fault == 'duplicate':
        slots[paths[-1]] = slots[paths[-2]]
    elif fault == 'reversed':
        slots[paths[-1]], slots[paths[-2]] = slots[paths[-2]], slots[paths[-1]]
    else:
        slots[paths[-1]] = True if fault == 'boolean' else -1
    with pytest.raises(ValueError, match='retained-source-identity'):
        scene.helper.select_retained_material(
            snapshot, snapshot['record'], scene.layout, scene.pins, source_slots=slots)


@pytest.mark.parametrize('change', ['relative', 'outside', 'dotdot', 'unknown', 'identity', 'parent', 'root-kind'])
def test_projection_rejects_ambiguous_schema_without_opening_sources(material_scene, change):
    scene = material_scene
    with projection(scene) as pins:
        entries = {path: dict(entry) for path, entry in pins.entries.items()}
        if change in ('relative', 'outside', 'dotdot'):
            name = {'relative': 'usr/foreign', 'outside': '/etc/foreign', 'dotdot': '/usr/../foreign'}[change]
            entries[name] = dict(kind='file', identity=(1, 1))
        elif change == 'unknown':
            entries['/usr']['fd'] = 99
        elif change == 'identity':
            entries['/usr']['identity'] = [True, 1]
        elif change == 'parent':
            del entries['/usr/bin']
        else:
            entries['/usr']['kind'] = 'directory'
        before = len(os.listdir('/proc/self/fd'))
        with pytest.raises(ValueError):
            scene.helper.RetainedSourceProjection(scene.pins['/usr']['fd'], entries)
        assert len(os.listdir('/proc/self/fd')) == before
