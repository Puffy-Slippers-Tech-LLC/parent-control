"""Private tmp_path filesystem and process-local transport; no VM or host files."""
import json
import fcntl
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import synthetic_files as controller
import synthetic_files_guest as guest
from private_artifacts import EvidenceError
from owned_commands import CommandError


@pytest.fixture
def home(tmp_path):
    path = tmp_path / 'home'
    path.mkdir(mode=0o700)
    return path


def test_exact_copy_rename_and_independent_cleanup(home):
    before = guest.operate(home, 'stage', None)
    root = home / guest.DIRECTORY
    assert {p.name: p.read_bytes() for p in root.iterdir()} == guest.FILES
    copied = guest.operate(home, 'copy', before)
    assert (root / guest.COPY).read_bytes() == (root / 'Synthetic note.txt').read_bytes()
    renamed = guest.operate(home, 'rename', copied)
    assert not (root / guest.COPY).exists()
    assert (root / guest.RENAMED).read_bytes() == guest.FILES['Synthetic note.txt']
    assert guest.operate(home, 'read', renamed) == renamed
    assert guest.operate(home, 'cleanup', renamed) == {'absent': True}
    assert guest.operate(home, 'absent', {'absent': True}) == {'absent': True}
    assert list(home.iterdir()) == []


# Boundary profiles retain private pytest storage and process-local transports.
# Each profile is <= 5 MiB+1 on disk; no build, bus, display or shared resource.
# This module retains its compatible unit AND cleanup classifications.
@pytest.mark.parametrize('profile', sorted(guest.BOUNDARY_PROFILES))
def test_boundary_fixtures_exact_bytes_and_owned_cleanup(home, profile):
    import accessible_ui
    expected = guest.BOUNDARY_PROFILES[profile]
    assert tuple(expected.items()) == accessible_ui.BOUNDARY_FILES[profile]
    staged = guest.operate(home, 'stage', None, profile)
    root = home / (guest.DIRECTORY + '-' + profile)
    assert {path.name: path.read_bytes() for path in root.iterdir()} == expected
    assert guest.operate(home, 'read', staged, profile) == staged
    for operation in ('stage', 'copy', 'rename'):
        with pytest.raises(ValueError):
            guest.operate(home, operation, staged, profile)
    assert guest.operate(home, 'cleanup', staged, profile) == {'absent': True}
    assert guest.operate(home, 'absent', {'absent': True}, profile) == {'absent': True}


@pytest.mark.parametrize('fault', ['unknown', 'changed', 'replaced', 'symlink', 'hardlink'])
def test_boundary_fixture_cleanup_refuses_unknown_or_replaced_files(home, fault):
    staged = guest.operate(home, 'stage', None, 'maximum')
    root = home / (guest.DIRECTORY + '-maximum')
    path = root / 'Maximum.txt'
    if fault == 'unknown': (root / 'unknown').write_bytes(b'preserve')
    if fault == 'changed': path.write_bytes(b'changed')
    if fault == 'replaced':
        path.rename(home / 'preserve')
        path.write_bytes(guest.BOUNDARY_PROFILES['maximum']['Maximum.txt'])
        path.chmod(0o600)
    if fault == 'symlink':
        path.rename(home / 'preserve')
        path.symlink_to(home / 'preserve')
    if fault == 'hardlink': os.link(path, home / 'preserve')
    before = {entry.name: entry.lstat() for entry in root.iterdir()}
    with pytest.raises(ValueError):
        guest.operate(home, 'cleanup', staged, 'maximum')
    assert {entry.name: entry.lstat() for entry in root.iterdir()} == before


def test_boundary_controller_retains_profiles_receipts_and_independent_cleanup(home):
    from attachment_boundaries import stage_boundaries, cleanup_boundaries
    def call(argv, **kwargs):
        profile = argv[9] if len(argv) == 10 else 'standard'
        value = guest.operate(home, argv[7], json.loads(argv[8]), profile)
        return (json.dumps(value, sort_keys=True) + '\n').encode()
    journey = SimpleNamespace(transport=SimpleNamespace(call=call))
    stage_boundaries(journey, lambda: None)
    assert len(list(home.iterdir())) == 7
    assert cleanup_boundaries(journey, lambda: None) == {'owned_cleanup': True}
    assert not list(home.iterdir())


@pytest.mark.parametrize('operation', ['../copy', '/copy', 'unknown', 'rename', 'stage'])
def test_wrong_operation_changes_nothing(home, operation):
    before = guest.operate(home, 'stage', None)
    with pytest.raises(ValueError):
        guest.operate(home, operation, before)
    assert guest.snapshot(home / guest.DIRECTORY) == before


@pytest.mark.parametrize('operation', ['copy', 'rename', 'cleanup'])
@pytest.mark.parametrize('fault', ['unknown', 'symlink', 'hardlink', 'content', 'owner', 'directory', 'replaced'])
def test_unsafe_fixture_refuses_before_any_mutation(home, monkeypatch, operation, fault):
    before = guest.operate(home, 'stage', None)
    root = home / guest.DIRECTORY
    target = root / 'Synthetic note.txt'
    if fault == 'unknown':
        (root / 'unregistered').write_text('preserve')
    elif fault == 'symlink':
        target.unlink()
        target.symlink_to(home / 'outside')
    elif fault == 'hardlink':
        os.link(target, home / 'outside')
    elif fault == 'content':
        target.write_bytes(b'changed')
    elif fault == 'owner':
        real = guest.os.getuid()
        monkeypatch.setattr(guest.os, 'getuid', lambda: real + 1)
    elif fault == 'directory':
        root.rename(home / 'preserved')
        root.symlink_to(home / 'preserved', target_is_directory=True)
    elif fault == 'replaced':
        target.rename(home / 'preserved')
        target.write_bytes(guest.FILES[target.name])
        target.chmod(0o600)
    names = sorted(os.listdir(root))
    identities = {name: (root / name).lstat() for name in names}
    with pytest.raises(ValueError):
        guest.operate(home, operation, before)
    assert sorted(os.listdir(root)) == names
    assert {name: (root / name).lstat() for name in names} == identities


def test_duplicate_destination_does_not_change_files(home):
    staged = guest.operate(home, 'stage', None)
    copied = guest.operate(home, 'copy', staged)
    with pytest.raises(ValueError):
        guest.operate(home, 'copy', copied)
    assert guest.snapshot(home / guest.DIRECTORY) == copied


def test_concurrent_command_refuses_before_mutation(home):
    before = guest.operate(home, 'stage', None)
    fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            guest.operate(home, 'copy', before)
        assert guest.snapshot(home / guest.DIRECTORY) == before
    finally:
        os.close(fd)


def test_wrong_file_owner_preserved(home, monkeypatch):
    before = guest.operate(home, 'stage', None)
    original = Path.lstat

    def wrong_owner(path):
        value = original(path)
        if path.name == 'Synthetic note.txt':
            fields = list(value)
            fields[4] += 1
            return os.stat_result(fields)
        return value

    with monkeypatch.context() as local:
        local.setattr(Path, 'lstat', wrong_owner)
        with pytest.raises(ValueError):
            guest.operate(home, 'cleanup', before)
    assert guest.snapshot(home / guest.DIRECTORY) == before


def test_stale_receipt_cannot_delete_replaced_directory(home):
    staged = guest.operate(home, 'stage', None)
    root = home / guest.DIRECTORY
    root.rename(home / 'preserved')
    replacement = guest.operate(home, 'stage', None)
    with pytest.raises(ValueError):
        guest.operate(home, 'cleanup', staged)
    assert guest.snapshot(root) == replacement


def test_uncertain_transport_refuses_replay():
    vm = SimpleNamespace(call=Mock(side_effect=TimeoutError))
    files = controller.SyntheticFiles(vm)
    with pytest.raises(TimeoutError):
        files.call('stage')
    with pytest.raises(EvidenceError, match='files:replay'):
        files.call('stage')
    with pytest.raises(EvidenceError, match='files:replay'):
        files.call('cleanup')
    assert vm.call.call_count == 1


def test_qualification_uses_argument_arrays_and_reads_independently(home):
    calls = []

    def call(argv, **kwargs):
        calls.append(argv[-2])
        assert argv[:7] == ['/usr/sbin/runuser', '--user', 'onpc-parent-jamie', '--',
                            '/usr/bin/python3', '-I', '-']
        assert kwargs['input'] == Path(guest.__file__).read_bytes()
        assert kwargs['timeout'] == 30
        try:
            value = guest.operate(home, argv[-2], json.loads(argv[-1]))
        except ValueError:
            value = {'refused': True}
        return (json.dumps(value, sort_keys=True) + '\n').encode()

    result = controller.qualify(SimpleNamespace(transport=SimpleNamespace(call=call)), lambda: None)
    assert result['owned_cleanup'] and result['exact_content_readback']
    assert result['independent_entries'] == 2
    assert calls[:4] == ['stage', 'read', 'read', 'read']
    assert calls[-2:] == ['cleanup', 'absent']
    assert not list(home.iterdir())


def test_qualification_entry_and_prerequisites(monkeypatch):
    import check_e2e_files
    import check_graphical_smoke
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_files, 'smoke', run)
    assert check_e2e_files.main() == 0
    assert run.call_args.kwargs['synthetic_files'] is True
    assert run.call_args.kwargs['fresh_desktop'] == 'parent'
    with pytest.raises(CommandError, match='synthetic-files-prerequisites'):
        check_graphical_smoke.main(synthetic_files=True)


def test_chooser_fixture_lifetime_retains_same_controller_and_owned_receipt(monkeypatch):
    # Same reviewed private doubles as FILE05; no additional host resources.
    import file_chooser
    fixture = Mock()
    factory = Mock(return_value=fixture)
    monkeypatch.setattr(file_chooser, 'SyntheticFiles', factory)
    journey = SimpleNamespace(transport=Mock())
    guard = Mock()
    file_chooser.stage_files(journey, guard)
    file_chooser.cleanup_files(journey, guard)
    factory.assert_called_once_with(journey.transport)
    assert [call.args for call in fixture.call.call_args_list] == [('stage',), ('cleanup',)]
    assert guard.call_count == 2


@pytest.mark.parametrize('items', [0, 1, 2, 3])
def test_chooser_qualification_uses_registered_actions_and_installed_snapshot(tmp_path, items):
    from parent_setup_qualification import FileChooserQualification
    from file_chooser import PLAN
    if items == 1:
        from parent_setup_qualification import AttachmentItemsQualification as FileChooserQualification
        from attachment_items import PLAN
    if items == 2:
        from parent_setup_qualification import AttachmentPreviewQualification as FileChooserQualification
        from attachment_preview import PLAN
    if items == 3:
        from parent_setup_qualification import AttachmentBoundariesQualification as FileChooserQualification
        from attachment_boundaries import PLAN
    context = SimpleNamespace(directory=tmp_path)
    journey = FileChooserQualification.journey(context, Mock())
    assert journey.plan is PLAN
    assert set(journey.actions) == ({'attachment-fixtures', 'attachment-cleanup'} if items == 3
                                    else {'chooser-fixtures', 'chooser-cleanup'})
    assert context.installed_snapshot.startswith('onpc-v')


@pytest.mark.parametrize('failure', [False, True])
def test_fixture_stage_records_before_reply_and_latches_failure(tmp_path, monkeypatch, failure):
    from parent_setup_qualification import SyntheticFilesQualification
    import installed_journey
    context = SimpleNamespace(directory=tmp_path)
    progress = Mock()
    journey = SyntheticFilesQualification.journey(context, progress)
    assert journey.plan.worker_mode == 'fresh_parent_desktop'
    assert journey.plan.stage_actions == {'desktop': 'synthetic-files'}
    journey.steps = [{'stage': name} for name in journey.plan.stages[:-1]]
    journey.ui = SimpleNamespace(boot_guard='', boot_proof='a' * 64,
                                 observe=Mock(return_value={}))
    journey.transport = Mock()
    monkeypatch.setattr(installed_journey.session_control, 'observe', Mock(return_value={}))
    action = Mock(side_effect=ValueError('refused') if failure else None,
                  return_value={'owned_cleanup': True})
    journey.actions['synthetic-files'] = action
    (tmp_path / 'desktop.request.json').write_text(json.dumps({'stage': 'desktop', 'screenshot': None}))
    if failure:
        with pytest.raises(ValueError, match='refused'):
            journey.step(Mock())
        with pytest.raises(EvidenceError, match='previous-failure'):
            journey.step(Mock())
        assert not (tmp_path / 'desktop.reply.json').exists()
        progress.assert_not_called()
    else:
        progress.side_effect = lambda *_: pytest.fail('reply preceded evidence') if (
            tmp_path / 'desktop.reply.json').exists() else None
        journey.step(Mock())
        assert journey.steps[-1]['fixture'] == {'owned_cleanup': True}
        assert (tmp_path / 'desktop.reply.json').exists()
    action.assert_called_once()
