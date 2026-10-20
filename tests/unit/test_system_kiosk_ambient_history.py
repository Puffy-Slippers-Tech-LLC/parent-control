"""Private files and observer doubles; no live account, mount, UI or VM owner."""

import copy
import os
import stat
from types import SimpleNamespace

import pytest

import system_kiosk_ambient_history as history


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setattr(history, 'PARENT', tmp_path)
    monkeypatch.setattr(history.guest, 'guard', lambda: dict(
        run='unit', package_sha256='a' * 64, selected_inputs_sha256='b' * 64))
    records = {}
    monkeypatch.setattr(history.checkpoints, 'private', lambda: tmp_path)

    def publish(name, value):
        assert name not in records
        records[name] = copy.deepcopy(value)
        (tmp_path / name).write_text('{}')
    monkeypatch.setattr(history.checkpoints, 'publish', publish)
    monkeypatch.setattr(history.checkpoints, 'read_private', lambda path: copy.deepcopy(records[path.name]))
    identity = history.confinement.sibling_identity
    monkeypatch.setattr(history.confinement, 'sibling_identity',
                        lambda target: identity(target)[:3] + [0, 0])

    def create(name, kind=None, *, replacement=False):
        path = history.path(name)
        assert not os.path.lexists(path)
        kind = kind or history.KINDS[name]
        if kind == 'link':
            path.symlink_to(history.path('vanished' if replacement else 'file').name)
        elif kind == 'directory':
            path.mkdir()
            path.chmod(0o755)
            if name not in ('empty', 'added'):
                (path / 'canary').write_text(('replacement-' if replacement else 'original-') + name + '\n')
                (path / 'canary').chmod(0o444)
        else:
            path.write_text(('replacement-' if replacement else 'original-') + name + '\n')
            path.chmod(0o644)
        return history.snapshot(path)
    monkeypatch.setattr(history, 'create', create)
    for name in history.KINDS:
        if name != 'added':
            create(name)
    original = history.host_state()
    history.save('prepared', state=original)
    history.save('source', original=original)
    history.save('observed-initial', host=original)
    return records


def finish_step(step):
    history.change(step)
    history.save('observed-' + step, host=history.host_state())


def test_empty_addition_removal_and_cross_kind_replacement_restore_original_inodes(rig):
    original = history.host_state()
    finish_step('empty-added')
    assert history.snapshot(history.path('added'))['children'] == {}
    finish_step('empty-removed')
    assert history.host_state() == original
    finish_step('replaced')
    replaced = history.host_state()
    assert 'children' in replaced['file'] and 'sha256' in replaced['directory']
    assert replaced['link']['link'] != original['link']['link']
    assert all(replaced[name]['identity'][:2] != original[name]['identity'][:2]
               for name in ('file', 'directory', 'link'))
    finish_step('replacement-restored')
    assert history.host_state() == original


def test_mode_mutation_changes_same_pins_and_restores_exact_mode(rig):
    # Supply the immediate predecessor without replaying unrelated steps.
    original = history.host_state()
    history.save('observed-replacement-restored', host=original)
    finish_step('writable')
    for name in ('file', 'directory'):
        actual = history.snapshot(history.path(name))['identity']
        assert actual[:2] == original[name]['identity'][:2]
        assert actual[2] & 0o022 == 0o022
    finish_step('mode-restored')
    assert history.host_state() == original


def test_actual_host_unlink_survives_as_independently_open_original_inode(rig):
    original = history.host_state()
    history.save('observed-owner-restored', host=original)
    with history.path('vanished').open('rb') as pinned:
        before = os.fstat(pinned.fileno())
        finish_step('unlinked')
        assert not history.path('vanished').exists() and not history.path('empty').exists()
        assert os.fstat(pinned.fileno()).st_nlink == 0 and pinned.read() == b'original-vanished\n'
        finish_step('unlinked-restored')
        assert history.path('vanished').stat().st_ino != before.st_ino
    assert history.snapshot(history.path('vanished'))['sha256'] == original['vanished']['sha256']


@pytest.mark.parametrize('change', ['replace', 'bytes', 'unknown-child', 'foreign-checkpoint'])
def test_mutation_refuses_changed_host_or_attempt_before_input(rig, change):
    if change == 'replace':
        history.path('file').rename(history.path('file-saved'))
        history.path('file').write_text('original')
    elif change == 'bytes':
        history.path('file').write_text('foreign')
    elif change == 'unknown-child':
        (history.path('directory') / 'foreign').write_text('foreign')
    else:
        rig['retained-ambient-observed-initial.json']['binding']['package_sha256'] = 'c' * 64
    with pytest.raises(history.guest.GuestError):
        history.change('empty-added')
    assert not history.path('added').exists()


def test_cleanup_refuses_replaced_fixture_and_preserves_every_other_entry(rig):
    original = history.host_state()
    history.path('file').write_text('foreign')
    with pytest.raises(history.guest.GuestError, match='cleanup-identity'):
        history.cleanup()
    assert history.path('file').read_text() == 'foreign'
    assert history.snapshot(history.path('directory')) == original['directory']


def test_cleanup_known_lost_reply_and_idempotence(rig):
    finish_step('empty-added')
    history.cleanup()
    assert all(value is None for value in history.host_state().values())
    history.cleanup()
    history.path('file').write_text('foreign')
    with pytest.raises(history.guest.GuestError, match='cleanup-replacement'):
        history.cleanup()
    assert history.path('file').read_text() == 'foreign'


def test_private_view_rejects_reopened_replacement_and_narrowing_requires_empty_mask(rig, tmp_path):
    original = {name: history.snapshot(history.path(name)) for name in history.KINDS}
    # A real mount is outside this host test; actual identities and bytes are
    # checked with the fixture as the positive source and a copied name as negative.
    history.private_entries(history.Path('/'), original)
    history.path('file').rename(history.path('file-saved'))
    history.path('file').write_text('original')
    with pytest.raises(history.guest.GuestError, match='original-pin-changed'):
        history.private_entries(history.Path('/'), original)


def test_snapshot_accepts_unlinked_pin_but_rejects_hardlink_and_special_node(rig):
    descriptor = os.open(history.path('vanished'), os.O_RDONLY)
    try:
        history.path('vanished').unlink()
        # /proc/self/fd is a symlink; use a real fstat to prove this host control's
        # unlink rather than claim an actual mounted-source qualification.
        assert os.fstat(descriptor).st_nlink == 0
    finally:
        os.close(descriptor)
    os.link(history.path('file'), history.path('file-saved'))
    with pytest.raises(history.guest.GuestError, match='fixture-type'):
        history.snapshot(history.path('file'))


def test_checkpoint_inventory_is_finite_unique_and_includes_all_history_steps():
    names = history.checkpoint_names()
    assert len(names) == len(set(names))
    assert all('retained-ambient-observed-' + step + '.json' in names for step in history.STEPS)


def test_prepare_records_each_exclusive_creation_before_publishing_complete_state(rig, monkeypatch):
    for name, value in history.host_state().items():
        history.remove(history.path(name), value)
    for name in tuple(rig):
        (history.checkpoints.private() / name).unlink()
    rig.clear()
    original_lstat = history.Path.lstat
    def lstat(target, *args, **kwargs):
        info = original_lstat(target, *args, **kwargs)
        return SimpleNamespace(st_mode=info.st_mode, st_uid=0, st_gid=0) if target == history.PARENT else info
    monkeypatch.setattr(history.Path, 'lstat', lstat)
    monkeypatch.setattr(history.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1001))
    monkeypatch.setattr(history.confinement, 'wait_kiosk_inactive', lambda account: None)
    history.prepare()
    names = list(rig)
    assert names[0] == 'retained-ambient-prepare-intent.json'
    assert names[-1] == 'retained-ambient-prepared.json'
    for name in history.KINDS:
        if name != 'added':
            saved = rig['retained-ambient-created-' + name + '.json']
            assert saved['fixture'] == name and saved['snapshot'] == history.snapshot(history.path(name))
    history.cleanup()
    assert all(value is None for value in history.host_state().values())


@pytest.mark.parametrize('fault', ['noop', 'extra-mode', 'replacement'])
def test_metadata_mutation_requires_exact_independent_same_inode_result(rig, monkeypatch, fault):
    original = history.host_state()
    history.save('observed-replacement-restored', host=original)
    chmod = history.Path.chmod

    def broken(target, mode, *args, **kwargs):
        if target == history.path('file'):
            if fault == 'noop':
                return
            if fault == 'replacement':
                target.rename(history.path('file-saved'))
                target.write_text('original')
            if fault == 'extra-mode':
                mode |= 0o100
        return chmod(target, mode, *args, **kwargs)
    monkeypatch.setattr(history.Path, 'chmod', broken)
    with pytest.raises(history.guest.GuestError, match='metadata-change'):
        history.change('writable')
    assert 'retained-ambient-changed-writable.json' not in rig


def test_raw_retained_manager_metadata_observes_same_inode_changes(rig):
    pins = {name: history.snapshot(history.path(name)) for name in history.KINDS}
    original = history.host_state()
    history.save('observed-replacement-restored', host=original)
    finish_step('writable')
    changed = history.host_state()
    history.manager_metadata(history.Path('/'), pins, changed)
    with pytest.raises(history.guest.GuestError, match='manager-metadata'):
        history.manager_metadata(history.Path('/'), pins, original)
    finish_step('mode-restored')
    history.manager_metadata(history.Path('/'), pins, original)


def test_observe_rejects_self_recorded_metadata_without_expected_mutation(rig):
    original = history.host_state()
    history.save('intent-writable', before=original)
    history.save('changed-writable', state=original)
    # Refuses before account lookup, manager observation or any live command.
    with pytest.raises(history.guest.GuestError, match='metadata-change'):
        history.observe('writable')


@pytest.mark.parametrize('cut', ['saved-file', 'replacement-file', 'saved-directory',
                               'replacement-directory', 'saved-link', 'replacement-link'])
def test_cleanup_recovers_partial_recorded_replacements(rig, monkeypatch, cut):
    finish_step('empty-added')
    finish_step('empty-removed')
    save = history.save

    def interrupt(name, **values):
        save(name, **values)
        if name == cut:
            raise RuntimeError('owned cut')
    monkeypatch.setattr(history, 'save', interrupt)
    with pytest.raises(RuntimeError, match='owned cut'):
        history.change('replaced')
    monkeypatch.setattr(history, 'save', save)
    history.cleanup()
    assert all(value is None for value in history.host_state().values())


def test_cleanup_recovers_rename_before_saved_checkpoint(rig, monkeypatch):
    finish_step('empty-added')
    finish_step('empty-removed')
    save = history.save

    def interrupt(name, **values):
        if name == 'saved-file':
            raise RuntimeError('owned cut')
        save(name, **values)
    monkeypatch.setattr(history, 'save', interrupt)
    with pytest.raises(RuntimeError):
        history.change('replaced')
    monkeypatch.setattr(history, 'save', save)
    history.cleanup()
    assert all(value is None for value in history.host_state().values())


@pytest.mark.parametrize('cut', ['removed', 'restored', 'directory-child'])
def test_cleanup_recovers_partial_replacement_restoration(rig, monkeypatch, cut):
    finish_step('empty-added')
    finish_step('empty-removed')
    finish_step('replaced')
    before = history.host_state()
    history.save('intent-replacement-restored', before=before)
    if cut == 'directory-child':
        (history.path('file') / 'canary').unlink()
    else:
        history.remove(history.path('file'), before['file'])
        if cut == 'restored':
            history.path('file-saved').rename(history.path('file'))
    history.cleanup()
    assert all(value is None for value in history.host_state().values())


@pytest.mark.parametrize('step', ['writable', 'mode-restored'])
def test_cleanup_recovers_partial_exact_mode_change(rig, monkeypatch, step):
    history.save('observed-replacement-restored', host=history.host_state())
    if step == 'mode-restored':
        finish_step('writable')
    chmod = history.Path.chmod

    def interrupt(target, mode, *args, **kwargs):
        chmod(target, mode, *args, **kwargs)
        if target == history.path('file'):
            raise RuntimeError('owned cut')
    monkeypatch.setattr(history.Path, 'chmod', interrupt)
    with pytest.raises(RuntimeError):
        history.change(step)
    monkeypatch.setattr(history.Path, 'chmod', chmod)
    history.cleanup()
    assert all(value is None for value in history.host_state().values())


@pytest.fixture
def owners(rig, monkeypatch):
    # Private metadata double: no chown of host files and no real account lookup.
    values = {}
    snapshot = history.snapshot

    def observed(target, **kwargs):
        value = snapshot(target, **kwargs)
        if value is not None and target in values:
            value['identity'][3:5] = values[target]
        return value
    monkeypatch.setattr(history, 'snapshot', observed)
    monkeypatch.setattr(history.pwd, 'getpwnam', lambda name: SimpleNamespace(
        pw_uid=os.getuid() + 1000, pw_gid=os.getgid() + 1000))

    def chown(target, uid, gid, **kwargs):
        assert kwargs == {'follow_symlinks': False}
        values[target] = [uid, gid]
    monkeypatch.setattr(history.os, 'chown', chown)
    return values, chown


def test_owner_changes_require_exact_same_inode_and_restore_recorded_owner(rig, owners):
    original = history.host_state()
    pins = {name: history.snapshot(history.path(name)) for name in history.KINDS}
    history.save('observed-mode-restored', host=original)
    finish_step('foreign-owned')
    changed = history.host_state()
    for name in ('file', 'directory'):
        assert changed[name]['identity'][:3] == original[name]['identity'][:3]
        assert changed[name]['identity'][3:5] == [os.getuid() + 1000, os.getgid() + 1000]
    history.manager_metadata(history.Path('/'), pins, changed)
    with pytest.raises(history.guest.GuestError, match='manager-metadata'):
        history.manager_metadata(history.Path('/'), pins, original)
    finish_step('owner-restored')
    assert history.host_state() == original


@pytest.mark.parametrize('step', ['foreign-owned', 'owner-restored'])
def test_cleanup_recovers_partial_exact_owner_change(rig, owners, monkeypatch, step):
    history.save('observed-mode-restored', host=history.host_state())
    if step == 'owner-restored':
        finish_step('foreign-owned')
    _, chown = owners

    def interrupt(target, uid, gid, **kwargs):
        chown(target, uid, gid, **kwargs)
        if target == history.path('file'):
            raise RuntimeError('owned cut')
    monkeypatch.setattr(history.os, 'chown', interrupt)
    with pytest.raises(RuntimeError):
        history.change(step)
    history.cleanup()
    assert all(value is None for value in history.host_state().values())


@pytest.mark.parametrize('fault', ['noop', 'other-owner', 'other-group'])
def test_owner_mutation_refuses_unintended_metadata(rig, owners, monkeypatch, fault):
    history.save('observed-mode-restored', host=history.host_state())
    _, chown = owners

    def broken(target, uid, gid, **kwargs):
        if fault == 'noop':
            return
        chown(target, uid + (fault == 'other-owner'), gid + (fault == 'other-group'), **kwargs)
    monkeypatch.setattr(history.os, 'chown', broken)
    with pytest.raises(history.guest.GuestError, match='metadata-change'):
        history.change('foreign-owned')


def test_partial_owner_recovery_preserves_unattributable_foreign_owner(rig, owners):
    values, _ = owners
    original = history.host_state()
    history.save('intent-foreign-owned', before=original, owner=[os.getuid() + 1000, os.getgid() + 1000])
    values[history.path('file')] = [os.getuid() + 2000, os.getgid() + 1000]
    before = history.host_state()
    with pytest.raises(history.guest.GuestError, match='cleanup-identity'):
        history.cleanup()
    assert history.host_state() == before


@pytest.mark.parametrize('foreign', ['unrecorded-replacement', 'changed-saved', 'extra-mode'])
def test_partial_recovery_refuses_unknown_state_before_deleting_anything(rig, foreign):
    original = history.host_state()
    if foreign == 'extra-mode':
        history.save('intent-writable', before=original)
        history.path('file').chmod(0o777)
    else:
        history.save('intent-replaced', before=original)
        history.path('file').rename(history.path('file-saved'))
        if foreign == 'changed-saved':
            history.path('file-saved').write_text('foreign')
        else:
            history.path('file').mkdir()
    before = history.host_state()
    with pytest.raises(history.guest.GuestError, match='cleanup-identity'):
        history.cleanup()
    assert history.host_state() == before


def test_resumed_cleanup_preflights_unknown_entries_before_any_removal(rig):
    original = history.host_state()
    history.save('cleanup-intent', state=original)
    history.save('removing-file', snapshot=original['file'])
    history.path('file').write_text('foreign')
    before = history.host_state()
    with pytest.raises(history.guest.GuestError, match='cleanup-identity'):
        history.cleanup()
    assert history.host_state() == before


def test_resumed_cleanup_recovers_partial_recorded_directory_removal(rig):
    original = history.host_state()
    history.save('cleanup-intent', state=original)
    history.save('removing-directory', snapshot=original['directory'])
    (history.path('directory') / 'canary').unlink()
    history.cleanup()
    assert all(value is None for value in history.host_state().values())


@pytest.mark.parametrize('step', ['empty-added', 'empty-removed', 'replaced',
                                 'replacement-restored', 'unlinked', 'unlinked-restored'])
def test_mutation_requires_the_intended_result_before_saving_success(rig, owners, monkeypatch, step):
    for prior in history.STEPS[1:history.STEPS.index(step)]:
        finish_step(prior)
    if step in ('empty-added', 'unlinked-restored'):
        monkeypatch.setattr(history, 'create', lambda *args, **kwargs: None)
    elif step in ('empty-removed', 'unlinked'):
        monkeypatch.setattr(history, 'remove', lambda *args, **kwargs: None)
    elif step == 'replacement-restored':
        monkeypatch.setattr(history.Path, 'rename', lambda *args, **kwargs: None)
    else:
        create = history.create
        monkeypatch.setattr(history, 'create', lambda name, kind, **kwargs:
                            create(name, kind, replacement=False))
    with pytest.raises(history.guest.GuestError, match='mutation-change'):
        history.change(step)
    assert 'retained-ambient-changed-' + step + '.json' not in rig


@pytest.mark.parametrize('step', ['empty-added', 'empty-removed', 'replaced',
                                 'replacement-restored', 'unlinked', 'unlinked-restored'])
def test_observe_independently_rejects_an_unchanged_self_recorded_mutation(rig, owners, step):
    for prior in history.STEPS[1:history.STEPS.index(step)]:
        finish_step(prior)
    before = history.host_state()
    history.save('intent-' + step, before=before)
    history.save('changed-' + step, state=before)
    # Must refuse before looking up an account or a live manager.
    with pytest.raises(history.guest.GuestError, match='mutation-change'):
        history.observe(step)


@pytest.mark.parametrize('fault', ['bytes', 'link', 'kind', 'owner', 'extra-child'])
def test_replacement_validation_rejects_unintended_data_and_trust(rig, fault):
    before = history.host_state()
    finish_step('empty-added')
    finish_step('empty-removed')
    finish_step('replaced')
    actual = history.host_state()
    if fault == 'bytes':
        actual['directory']['sha256'] = before['file']['sha256']
    elif fault == 'link':
        actual['link']['link'] = before['link']['link']
    elif fault == 'kind':
        actual['directory']['identity'][2] = stat.S_IFDIR | 0o755
    elif fault == 'owner':
        actual['file']['identity'][3] = 1000
    else:
        actual['file']['children']['unknown'] = actual['file']['children']['canary']
    with pytest.raises(history.guest.GuestError, match='mutation-change'):
        history.mutation_state({'before': before}, 'replaced', actual)


@pytest.mark.parametrize('fault', [None, 'file-visible', 'original-directory', 'nonempty-mask'])
def test_invocation_narrowing_requires_absent_file_and_new_empty_directory(rig, fault):
    original = {name: history.snapshot(history.path(name)) for name in history.KINDS}
    history.path('file').rename(history.path('file-saved'))
    history.path('directory').rename(history.path('directory-saved'))
    history.path('directory').mkdir()
    if fault == 'file-visible':
        history.path('file-saved').rename(history.path('file'))
    elif fault == 'original-directory':
        history.path('directory').rmdir()
        history.path('directory-saved').rename(history.path('directory'))
    elif fault == 'nonempty-mask':
        (history.path('directory') / 'foreign').write_text('foreign')
    if fault:
        with pytest.raises(history.guest.GuestError, match='unexpected-entry|unsafe-directory-not-masked'):
            history.private_entries(history.Path('/'), original, narrowed=True)
    else:
        history.private_entries(history.Path('/'), original, narrowed=True)


@pytest.mark.parametrize('fault', ['bytes', 'child-inode', 'link-target', 'new-host-entry'])
def test_private_entry_observation_rejects_changed_original_content_or_new_sources(rig, fault):
    original = {name: history.snapshot(history.path(name)) for name in history.KINDS}
    if fault == 'bytes':
        history.path('file').write_text('foreign')
    elif fault == 'child-inode':
        child = history.path('directory') / 'canary'
        child.rename(history.PARENT / 'old-child')
        child.write_text('original-directory\n')
        child.chmod(0o444)
    elif fault == 'link-target':
        history.path('link').unlink()
        history.path('link').symlink_to(history.path('vanished').name)
    else:
        history.create('added')
    with pytest.raises(history.guest.GuestError, match='original-pin-changed|unexpected-entry'):
        history.private_entries(history.Path('/'), original)
