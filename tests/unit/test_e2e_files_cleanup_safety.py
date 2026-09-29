"""Private tmp_path files, mocked transport and bounded isolated Python; no VM."""
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


@pytest.fixture(autouse=True)
def exported_format_validation_on_development_host(monkeypatch):
    # The host has no installed product. Load the same maintained format parser
    # from source; the isolated VM command uses its fixed installed common path.
    from tests.support.paths import ROOT
    monkeypatch.syspath_prepend(str(ROOT / 'common'))


def diagnostic_bytes(*, maximum=False):
    from common.oh_no_parent_control_ui.diagnostic_report import build_report
    from common.oh_no_parent_control_ui.diagnostic_events import event
    from tests.support.system_info import sample_info
    record = {**event('diagnostic.rejected'), 'component': 'broker', 'level': 'INFO',
              'sequence': 1, 'segment': 1, 'elapsed_ms': 100}
    logs = ({f'{component}/2026-09-{day:02}.log': []
             for component in ('broker', 'child', 'kiosk', 'parent') for day in (10, 11, 12)}
            if maximum else {'broker/2026-09-12.log': [record]})
    return build_report(logs, system_info=sample_info())


def saved_diagnostics(home, content, *, mode=0o700):
    root = home / 'Downloads'
    root.mkdir(mode=mode)
    (root / 'unrelated.txt').write_bytes(b'preserve existing download')
    staged = guest.operate(home, 'stage', None, 'save')
    target = root / guest.SAVE_NAME
    target.write_bytes(content)
    target.chmod(0o600)
    return guest.operate(home, 'saved', staged, 'save')


@pytest.mark.parametrize('mode', [0o700, 0o755])
def test_diagnostic_export_exact_maximum_inventory_decoder_and_original_owner(home, mode):
    receipt = saved_diagnostics(home, diagnostic_bytes(maximum=True), mode=mode)
    calls = []
    def call(argv, **kwargs):
        calls.append(argv[7])
        result = guest.operate(home, argv[7], json.loads(argv[8]), argv[9])
        return (json.dumps(result, sort_keys=True) + '\n').encode()
    transport = SimpleNamespace(config={'run': 'owned'}, call=call)
    owner = controller.SyntheticFiles(transport, 'save')
    owner.attempt, owner.previous = 'owned', receipt
    owner.attempted.add('saved')
    actual = controller.read_declared_zip(transport, receipt, attempt='owned',
                                         artifact='diagnostic-export', owner=owner)
    assert len(actual['members']) == 17 and actual['checks'] == {
        'inventory': True, 'headers': True, 'system': True, 'contents': True, 'records': 0}
    assert len((json.dumps(actual, sort_keys=True) + '\n').encode()) <= 4096
    assert owner.previous == receipt and calls == ['open-zip']
    with pytest.raises(EvidenceError, match='save-owner'):
        controller.read_declared_zip(transport, receipt, attempt='owned',
                                     artifact='diagnostic-export', owner=owner)
    assert owner.call('cleanup') == {'absent': True}
    root = home / 'Downloads'
    assert sorted(p.name for p in root.iterdir()) == ['unrelated.txt']
    assert root.stat().st_mode & 0o777 == mode
    assert (root / 'unrelated.txt').read_bytes() == b'preserve existing download'


@pytest.mark.parametrize('fault', ['attempt', 'user', 'artifact', 'owner', 'receipt', 'failed', 'transport'])
def test_diagnostic_controller_refuses_wrong_entry_without_transport(home, fault):
    from copy import deepcopy
    receipt = saved_diagnostics(home, diagnostic_bytes())
    transport = SimpleNamespace(config={'run': 'owned'}, call=Mock())
    owner = controller.SyntheticFiles(transport, 'save')
    owner.attempt, owner.previous = 'owned', deepcopy(receipt)
    owner.attempted.add('saved')
    options = dict(attempt='owned', artifact='diagnostic-export', owner=owner)
    if fault == 'attempt': options['attempt'] = 'other'
    if fault == 'user': options['user'] = 'onpc-child-alex'
    if fault == 'artifact': options['artifact'] = '../diagnostic-export'
    if fault == 'owner': options['owner'] = None
    if fault == 'receipt': receipt['files'][guest.SAVE_NAME]['identity'][1] += 1
    if fault == 'failed': owner.failed = True
    if fault == 'transport': owner.transport = Mock()
    with pytest.raises(EvidenceError):
        controller.read_declared_zip(transport, receipt, **options)
    transport.call.assert_not_called()


@pytest.mark.parametrize('fault', ['missing', 'symlink', 'replaced', 'hardlink', 'changed',
                                  'directory', 'unknown', 'owner'])
def test_diagnostic_reader_identity_refuses_and_preserves_output(home, monkeypatch, fault):
    receipt = saved_diagnostics(home, diagnostic_bytes())
    root, target = home / 'Downloads', home / 'Downloads' / guest.SAVE_NAME
    if fault == 'missing': target.unlink()
    if fault == 'symlink':
        target.rename(home / 'preserved')
        target.symlink_to(home / 'preserved')
    if fault == 'replaced':
        target.rename(home / 'preserved')
        target.write_bytes(diagnostic_bytes())
        target.chmod(0o600)
    if fault == 'hardlink': os.link(target, home / 'preserved')
    if fault == 'changed': target.write_bytes(b'changed')
    if fault == 'directory':
        root.rename(home / 'preserved')
        root.symlink_to(home / 'preserved', target_is_directory=True)
    if fault == 'unknown': (root / 'unknown').write_bytes(b'keep')
    if fault == 'owner':
        uid = os.getuid()
        monkeypatch.setattr(guest.os, 'getuid', lambda: uid + 1)
    before = target.read_bytes() if target.exists() else None
    with pytest.raises((ValueError, OSError)):
        guest.operate(home, 'open-zip', {'receipt': receipt, 'artifact': 'diagnostic-export'}, 'save')
    with pytest.raises((ValueError, OSError)):
        guest.operate(home, 'cleanup', receipt, 'save')
    assert (target.read_bytes() if target.exists() else None) == before


@pytest.mark.parametrize('fault', ['system-null', 'summary', 'inventory', 'header', 'count',
    'content', 'folder', 'date', 'duplicate', 'unsafe', 'archive-limit', 'member-limit',
    'expanded-limit', 'count-limit', 'deadline', 'crc'])
def test_diagnostic_archive_refuses_bad_contents_and_bounds(monkeypatch, fault):
    import io
    import zipfile
    source = diagnostic_bytes()
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    info = json.loads(entries['system-info.json'])
    log = 'broker/2026-09-12.log'
    if fault == 'system-null': info['system'] = None
    if fault == 'summary': info['private'] = 'private@example.test'
    if fault == 'inventory': info['logs'] = {}
    if fault == 'header': entries[log] = b'Wrong heading\n'
    if fault == 'count': info['logs'][log] = 2
    if fault == 'content':
        entries[log] += b'[INFO] segment=1 +0ms #1 op=0 event=private fields={} | private\n'
        info['logs'][log] = 2
    if fault == 'folder': entries['child/'] = b'not empty'
    if fault == 'date':
        entries['parent/2026-02-30.log'] = entries.pop(log)
        info['logs'] = {'parent/2026-02-30.log': 0}
    if fault == 'unsafe': entries['../private'] = b'x'
    if fault == 'member-limit': entries[log] = b'x' * (16 * 1024 * 1024 + 1)
    if fault == 'expanded-limit':
        entries[log] = b'x' * (8 * 1024 * 1024)
        entries['child/2026-09-12.log'] = b'x' * (8 * 1024 * 1024)
    if fault == 'count-limit': entries.update({f'child/{n}.log': b'' for n in range(18)})
    entries['system-info.json'] = (json.dumps(info, indent=2, sort_keys=True) + '\n').encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries.items(): archive.writestr(name, value)
        if fault == 'duplicate':
            with pytest.warns(UserWarning): archive.writestr(log, entries[log])
    content = output.getvalue()
    if fault == 'archive-limit': content += b'x' * (2 * 1024 * 1024)
    if fault == 'deadline':
        ticks = iter([0, guest.ZIP_SECONDS + 1])
        monkeypatch.setattr(guest.time, 'monotonic', lambda: next(ticks))
    if fault == 'crc':
        # Rewrite uncompressed bytes so the central directory's CRC disagrees.
        content = guest.make_zip(list(entries.items())).replace(b'ONPC component log', b'XNPC component log')
    with pytest.raises(ValueError): guest.inspect_zip(content, diagnostic=True)


def test_diagnostic_content_and_uncertain_decoder_latch(home):
    receipt = saved_diagnostics(home, diagnostic_bytes())
    actual = guest.operate(home, 'open-zip', {
        'receipt': receipt, 'artifact': 'diagnostic-export'}, 'save')
    assert actual['checks']['records'] == 1
    assert actual['members']['broker/2026-09-12.log']['size'] > 300
    for raw in (b'{"matched": true}\n', b'x' * 4097):
        transport = SimpleNamespace(config={'run': 'owned'}, call=Mock(return_value=raw))
        owner = controller.SyntheticFiles(transport, 'save')
        owner.attempt, owner.previous = 'owned', receipt
        owner.attempted.add('saved')
        with pytest.raises(EvidenceError):
            controller.read_declared_zip(transport, receipt, attempt='owned',
                                         artifact='diagnostic-export', owner=owner)
        assert owner.failed
        with pytest.raises(EvidenceError, match='save-owner'):
            controller.read_declared_zip(transport, receipt, attempt='owned',
                                         artifact='diagnostic-export', owner=owner)
        transport.call.assert_called_once()


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


# Save uses private tmp_path files, transport doubles and a bounded Python child; the
# existing compatible unit and cleanup classifications remain appropriate.
def test_save_worker_loads_shared_destination_in_isolated_guest(home):
    import subprocess
    import sys
    from download_destination import download_directory
    transport = Mock()
    transport.call.return_value = b'{"absent": true}\n'
    controller.SyntheticFiles(transport, 'save')._command('absent', {'absent': True})
    program = transport.call.call_args.kwargs['input']
    subprocess.run([sys.executable, '-I', '-c',
                    "import sys; namespace={'__name__':'worker'}; "
                    "exec(compile(sys.stdin.read(), 'worker.py', 'exec'), namespace); "
                    "assert str(namespace['download_directory']('/home/bound-user')) "
                    "== '/home/bound-user/Downloads'"],
                   input=program, check=True, capture_output=True, timeout=20)
    assert download_directory(home) == home / 'Downloads'


def test_save_destinations_capture_real_output_and_cancel_absence(home):
    staged = guest.operate(home, 'stage', None, 'save')
    root = home / guest.SAVE_DIRECTORY
    assert not os.access(root / 'Unwritable', os.W_OK)
    path = root / guest.SAVE_NAME
    path.write_bytes(b'product-output-stand-in')
    path.chmod(0o600)
    saved = guest.operate(home, 'saved', staged, 'save')
    assert saved['files'][guest.SAVE_NAME]['size'] == len(b'product-output-stand-in')
    assert guest.operate(home, 'read', saved, 'save') == saved
    assert guest.operate(home, 'cleanup', saved, 'save') == {'absent': True}
    assert guest.operate(home, 'absent', {'absent': True}, 'save') == {'absent': True}


@pytest.mark.parametrize('fault', ['missing', 'symlink', 'hardlink', 'public', 'empty',
    'oversize', 'unknown', 'cancelled', 'replaced-directory', 'writable-denied'])
def test_save_capture_refuses_unsafe_output_without_cleanup(home, fault):
    staged = guest.operate(home, 'stage', None, 'save')
    root = home / guest.SAVE_DIRECTORY
    path = root / guest.SAVE_NAME
    path.write_bytes(b'output')
    path.chmod(0o600)
    if fault == 'missing':
        path.unlink()
    elif fault == 'symlink':
        path.unlink()
        path.symlink_to(home / 'unrelated')
    elif fault == 'hardlink':
        os.link(path, home / 'unrelated')
    elif fault == 'public':
        path.chmod(0o644)
    elif fault == 'empty':
        path.write_bytes(b'')
    elif fault == 'oversize':
        with path.open('wb') as stream:
            stream.truncate(guest.SAVE_LIMIT + 1)
    elif fault in ('unknown', 'cancelled'):
        (root / ('Cancelled diagnostics.zip' if fault == 'cancelled' else 'unknown')).touch()
    elif fault == 'replaced-directory':
        staged['directory'][1] += 1
    else:
        (root / 'Unwritable').chmod(0o700)
    with pytest.raises((ValueError, OSError)):
        guest.operate(home, 'saved', staged, 'save')
    assert root.exists()


@pytest.mark.parametrize('fault', ['changed', 'replaced', 'unknown', 'cancelled'])
def test_save_cleanup_preserves_changed_or_unknown_objects(home, fault):
    staged = guest.operate(home, 'stage', None, 'save')
    root = home / guest.SAVE_DIRECTORY
    path = root / guest.SAVE_NAME
    path.write_bytes(b'output')
    path.chmod(0o600)
    saved = guest.operate(home, 'saved', staged, 'save')
    if fault == 'changed':
        path.write_bytes(b'change')
    elif fault == 'replaced':
        path.rename(home / 'original')
        path.write_bytes(b'output')
        path.chmod(0o600)
    else:
        (root / ('Cancelled diagnostics.zip' if fault == 'cancelled' else 'unknown')).touch()
    with pytest.raises(ValueError):
        guest.operate(home, 'cleanup', saved, 'save')
    assert path.exists()


def test_save_preserves_existing_downloads_and_unrelated_files(home):
    root = home / 'Downloads'
    root.mkdir(mode=0o755)
    unrelated = root / 'existing.txt'
    unrelated.write_bytes(b'keep existing download')
    before = guest.identity(unrelated.lstat())
    staged = guest.operate(home, 'stage', None, 'save')
    path = root / guest.SAVE_NAME
    path.write_bytes(b'output')
    path.chmod(0o600)
    saved = guest.operate(home, 'saved', staged, 'save')
    assert guest.operate(home, 'cleanup', saved, 'save') == {'absent': True}
    assert guest.operate(home, 'absent', {'absent': True}, 'save') == {'absent': True}
    assert list(root.iterdir()) == [unrelated]
    assert guest.identity(unrelated.lstat()) == before
    assert unrelated.read_bytes() == b'keep existing download'


@pytest.mark.parametrize('name', [guest.SAVE_NAME, guest.SAVE_CANCEL_NAME, 'Unwritable'])
def test_save_refuses_preexisting_destination_objects(home, name):
    root = home / 'Downloads'
    root.mkdir(mode=0o755)
    existing = root / name
    existing.write_bytes(b'preserve')
    with pytest.raises(ValueError):
        guest.operate(home, 'stage', None, 'save')
    assert list(root.iterdir()) == [existing]
    assert existing.read_bytes() == b'preserve'


def test_save_qualification_owns_actions_and_failed_transport_latches(tmp_path):
    from parent_setup_qualification import SaveChooserQualification
    from save_chooser import PLAN
    journey = SaveChooserQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan is PLAN
    assert set(journey.actions) == {'save-prepare', 'save-read', 'save-preserved', 'save-cleanup'}
    transport = Mock()
    transport.call.side_effect = TimeoutError
    files = controller.SyntheticFiles(transport, 'save')
    with pytest.raises(TimeoutError):
        files.call('stage')
    with pytest.raises(EvidenceError, match='replay'):
        files.call('stage')
    transport.call.assert_called_once()


def test_declared_text_read_and_disposable_refusal_probes(home):
    receipt = guest.operate(home, 'stage', None)
    expected = guest.operate(home, 'open-text',
                             {'receipt': receipt, 'artifact': guest.TEXT_ARTIFACT})
    assert expected == {'artifact': guest.TEXT_ARTIFACT, 'matched': True,
                        'size': len(guest.FILES[guest.TEXT_NAME]),
                        'sha256': receipt['files'][guest.TEXT_NAME]['sha256']}
    for artifact in ('../synthetic-note', '/synthetic-note', 'unrelated'):
        with pytest.raises(ValueError):
            guest.operate(home, 'open-text', {'receipt': receipt, 'artifact': artifact})
    assert guest.operate(home, 'probe-text', receipt) == {
        'refused': ['missing', 'symlink', 'replaced', 'empty', 'different', 'oversized'],
        'owned_cleanup': True}
    assert guest.operate(home, 'read', receipt) == receipt
    assert guest.operate(home, 'cleanup', receipt) == {'absent': True}
    assert list(home.iterdir()) == []


def test_declared_text_reader_binds_attempt_and_user_without_transport(home):
    receipt = guest.operate(home, 'stage', None)
    calls = []

    def call(argv, **kwargs):
        calls.append(argv)
        value = guest.operate(home, argv[-2], json.loads(argv[-1]))
        return (json.dumps(value, sort_keys=True) + '\n').encode()

    transport = SimpleNamespace(config={'run': 'owned-attempt'}, call=call)
    expected = controller.read_declared_text(transport, receipt, attempt='owned-attempt')
    assert expected['matched'] is True
    assert calls[0][2] == 'onpc-parent-jamie'
    for options in ({'attempt': 'wrong-attempt'},
                    {'attempt': 'owned-attempt', 'user': 'onpc-child-alex'},
                    {'attempt': 'owned-attempt', 'artifact': '../synthetic-note'}):
        with pytest.raises(EvidenceError):
            controller.read_declared_text(transport, receipt, **options)
    assert len(calls) == 1
    assert guest.operate(home, 'cleanup', receipt) == {'absent': True}


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


@pytest.mark.parametrize('operation', ['copy', 'rename', 'cleanup', 'change-source'])
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
        assert kwargs['input'].endswith(Path(guest.__file__).read_bytes())
        namespace = {'__name__': 'worker'}
        exec(compile(kwargs['input'], 'worker.py', 'exec'), namespace)
        assert namespace['download_directory'](home) == home / 'Downloads'
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


def test_document_open_entry_and_prerequisites(monkeypatch):
    import check_e2e_document_open
    import check_graphical_smoke
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_document_open, 'smoke', run)
    assert check_e2e_document_open.main() == 0
    assert run.call_args.kwargs['document_open'] is True
    assert run.call_args.kwargs['fresh_desktop'] == 'parent'
    with pytest.raises(CommandError, match='document-open-prerequisites'):
        check_graphical_smoke.main(document_open=True)


def test_document_open_qualification_registers_exact_worker_action(tmp_path):
    from parent_setup_qualification import DocumentOpenQualification
    context = SimpleNamespace(directory=tmp_path)
    journey = DocumentOpenQualification.journey(context, Mock())
    assert journey.plan.worker_mode == 'fresh_parent_desktop'
    assert journey.plan.stage_actions == {'desktop': 'document-open'}
    assert journey.actions == {'document-open': controller.qualify_text}


def test_document_open_qualification_uses_shared_reader_and_cleans_both_entries(home):
    operations = []

    def call(argv, **kwargs):
        operation = argv[-2]
        operations.append(operation)
        try:
            value = guest.operate(home, operation, json.loads(argv[-1]))
        except (ValueError, OSError):
            value = {'refused': True}
        return (json.dumps(value, sort_keys=True) + '\n').encode()

    transport = SimpleNamespace(config={'run': 'owned-attempt'}, call=call)
    result = controller.qualify_text(SimpleNamespace(transport=transport), lambda: None)
    assert result['independent_entries'] == 2
    assert result['fault_matrix_refused'] and result['owned_cleanup']
    assert operations.count('open-text') == 10
    assert operations.count('probe-text') == 2
    assert operations.count('cleanup') == 2
    assert not list(home.iterdir())


# ZIP additions retain private tmp_path storage, in-memory bounded archives and
# process-local doubles: compatible in both unit and cleanup schedulers.
def test_archive_qualification_shared_reader_and_cleanup(home):
    operations = []

    def call(argv, **kwargs):
        assert kwargs['timeout'] == 30
        operations.append(argv[7])
        try:
            value = guest.operate(home, argv[7], json.loads(argv[8]), argv[9])
        except (ValueError, OSError):
            value = {'refused': True}
        return (json.dumps(value, sort_keys=True) + '\n').encode()

    transport = SimpleNamespace(config={'run': 'owned-attempt'}, call=call)
    result = controller.qualify_zip(SimpleNamespace(transport=transport), lambda: None)
    assert result['independent_entries'] == 2 and result['exact_entries_and_contents']
    assert result['fault_matrix_refused'] and result['owned_cleanup']
    assert operations.count('open-zip') == 8
    assert operations.count('probe-zip') == operations.count('cleanup') == 2
    assert not list(home.iterdir())


def test_archive_entry_plan_and_prerequisites(tmp_path, monkeypatch):
    import check_e2e_open_a_customer_document_or_archive as entry
    import check_graphical_smoke
    from parent_setup_qualification import ArchiveOpenQualification
    run = Mock(return_value=0)
    monkeypatch.setattr(entry, 'smoke', run)
    assert entry.main() == 0
    assert run.call_args.kwargs['archive_open'] is True
    with pytest.raises(CommandError, match='archive-open-prerequisites'):
        check_graphical_smoke.main(archive_open=True)
    journey = ArchiveOpenQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan.worker_mode == 'fresh_parent_desktop'
    assert journey.plan.stage_actions == {'desktop': 'archive-open'}
    assert journey.actions == {'archive-open': controller.qualify_zip}


@pytest.mark.parametrize('fault', ['replaced', 'owner', 'hardlink', 'directory'])
def test_archive_reader_and_cleanup_preserve_wrong_identity(home, monkeypatch, fault):
    receipt = guest.operate(home, 'stage', None, 'zip')
    root = home / (guest.DIRECTORY + '-zip')
    target = root / guest.ZIP_NAME
    if fault == 'replaced':
        target.rename(home / 'preserved')
        target.write_bytes(guest.ZIP_FILES[guest.ZIP_NAME])
        target.chmod(0o600)
    if fault == 'owner':
        original = guest.os.getuid()
        monkeypatch.setattr(guest.os, 'getuid', lambda: original + 1)
    if fault == 'hardlink': os.link(target, home / 'preserved')
    if fault == 'directory':
        root.rename(home / 'preserved')
        root.symlink_to(home / 'preserved', target_is_directory=True)
    before = target.read_bytes()
    with pytest.raises((ValueError, OSError)):
        guest.operate(home, 'open-zip', {'receipt': receipt, 'artifact': guest.ZIP_ARTIFACT}, 'zip')
    with pytest.raises((ValueError, OSError)):
        guest.operate(home, 'cleanup', receipt, 'zip')
    assert target.read_bytes() == before


@pytest.mark.parametrize('name', ['../note.txt', '/note.txt', 'a//b', 'a/./b',
                                 'a\\b', 'C:note.txt', 'a\x01b'])
def test_zip_unsafe_member_names(name):
    with pytest.raises(ValueError):
        guest.inspect_zip(guest.make_zip([(name, b'x')]))


def test_zip_independent_compressed_archive_and_deadline(monkeypatch):
    import io
    import zipfile
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('metadata.json', '{"kind":"synthetic","version":1}\n')
        archive.writestr('note.txt', 'Independent synthetic archive note\n')
        archive.writestr('empty/', '')
    assert set(guest.inspect_zip(output.getvalue())['members']) == {
        'metadata.json', 'note.txt', 'empty/'}
    ticks = iter([0, guest.ZIP_SECONDS + 1])
    monkeypatch.setattr(guest.time, 'monotonic', lambda: next(ticks))
    with pytest.raises(ValueError):
        guest.inspect_zip(output.getvalue())


def test_zip_controller_rejects_false_content_evidence(home):
    receipt = guest.operate(home, 'stage', None, 'zip')
    transport = SimpleNamespace(config={'run': 'owned-attempt'},
                                call=Mock(return_value=b'{"matched": true}\n'))
    with pytest.raises(EvidenceError, match='zip:comparison'):
        controller.read_declared_zip(transport, receipt, attempt='owned-attempt')
    assert guest.operate(home, 'cleanup', receipt, 'zip') == {'absent': True}


def test_zip_corrupt_crc_refuses():
    content = guest.ZIP_FILES[guest.ZIP_NAME]
    damaged = content.replace(b'Independent synthetic archive note',
                              b'Xndependent synthetic archive note')
    assert damaged != content
    with pytest.raises(ValueError):
        guest.inspect_zip(damaged)


def test_chooser_fixture_lifetime_retains_same_controller_and_owned_receipt(monkeypatch):
    # Same reviewed private doubles as FILE05; no additional host resources.
    import file_chooser
    fixture = Mock()
    fixture.profile = 'standard'
    fixture.call.side_effect = [{'files': 'owned-receipt'}, {'absent': True}]
    factory = Mock(return_value=fixture)
    monkeypatch.setattr(controller, 'SyntheticFiles', factory)
    journey = SimpleNamespace(transport=Mock())
    guard = Mock()
    file_chooser.stage_files(journey, guard)
    file_chooser.cleanup_files(journey, guard)
    factory.assert_called_once_with(journey.transport, 'standard')
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
@pytest.mark.parametrize('archive', [False, True, 'source', 'save', 'export'])
def test_fixture_stage_records_before_reply_and_latches_failure(tmp_path, monkeypatch, failure, archive):
    from parent_setup_qualification import (SyntheticFilesQualification, ArchiveOpenQualification,
                                            SourceChangeQualification)
    import installed_journey
    context = SimpleNamespace(directory=tmp_path)
    progress = Mock()
    qualification = ArchiveOpenQualification if archive else SyntheticFilesQualification
    action_name = 'archive-open' if archive else 'synthetic-files'
    if archive == 'source':
        qualification, action_name = SourceChangeQualification, 'source-change'
    if archive == 'save':
        from parent_setup_qualification import SaveChooserQualification
        qualification, action_name = SaveChooserQualification, 'save-prepare'
    if archive == 'export':
        from parent_setup_qualification import DiagnosticExportQualification
        qualification, action_name = DiagnosticExportQualification, 'diagnostic-inspect'
    journey = qualification.journey(context, progress)
    stage = ('first-refused' if archive == 'save' else
             'first-inspect' if archive == 'export' else 'desktop')
    assert journey.plan.stage_actions[stage] == action_name
    stages = list(journey.plan.stages)
    journey.steps = [{'stage': name} for name in stages[:stages.index(stage)]]
    journey.ui = SimpleNamespace(boot_guard='', boot_proof='a' * 64,
                                 observe=Mock(return_value={}))
    journey.transport = Mock()
    monkeypatch.setattr(installed_journey.session_control, 'observe', Mock(return_value={}))
    action = Mock(side_effect=ValueError('refused') if failure else None,
                  return_value={'owned_cleanup': True})
    journey.actions[action_name] = action
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if failure:
        with pytest.raises(ValueError, match='refused'):
            journey.step(Mock())
        with pytest.raises(EvidenceError, match='previous-failure'):
            journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        progress.assert_not_called()
    else:
        progress.side_effect = lambda *_: pytest.fail('reply preceded evidence') if (
            tmp_path / (stage + '.reply.json')).exists() else None
        journey.step(Mock())
        assert journey.steps[-1]['fixture'] == {'owned_cleanup': True}
        assert (tmp_path / (stage + '.reply.json')).exists()
    action.assert_called_once()


# Source mutation adds only tiny private files and process-local doubles. Both
# unit and cleanup classifications remain compatible; no new host resources.
def test_source_change_qualification_and_lifetime(home):
    calls = []
    def call(argv, **kwargs):
        name, receipt = argv[7], json.loads(argv[8])
        profile = argv[9] if len(argv) == 10 else 'standard'
        calls.append((name, profile))
        try:
            value = guest.operate(home, name, receipt, profile)
        except (ValueError, OSError):
            value = {'refused': True}
        return (json.dumps(value, sort_keys=True) + '\n').encode()
    journey = SimpleNamespace(transport=SimpleNamespace(call=call))
    result = controller.qualify_source_change(journey, lambda: None)
    assert result['independent_entries'] == 2 and result['exact_changed_content']
    assert result['wrong_entry_refused'] and result['owned_cleanup']
    assert not list(home.iterdir())
    for profile in ('standard', 'single'):
        assert [name for name, current in calls if current == profile] == [
            'stage', 'read', 'probe-source', 'read', 'change-source', 'read',
            'change-source', 'read', 'cleanup', 'absent']


@pytest.mark.parametrize('profile', ['standard', 'single'])
def test_source_write_changes_only_original_and_requires_new_receipt(home, profile):
    original = guest.operate(home, 'stage', None, profile)
    changed = guest.operate(home, 'change-source', original, profile)
    root = home / (guest.DIRECTORY + ('' if profile == 'standard' else '-single'))
    assert (root / guest.TEXT_NAME).read_bytes() == b'ONPC changed synthetic attachment\n'
    assert changed['files'][guest.TEXT_NAME]['identity'][:5] == original['files'][guest.TEXT_NAME]['identity'][:5]
    for operation in ('cleanup', 'change-source', 'read'):
        with pytest.raises(ValueError):
            guest.operate(home, operation, original, profile)
    assert guest.operate(home, 'read', changed, profile) == changed
    assert guest.operate(home, 'cleanup', changed, profile) == {'absent': True}


def test_source_short_write_is_uncertain_and_never_replayed(home, monkeypatch):
    def call(argv, **kwargs):
        try:
            result = guest.operate(home, argv[7], json.loads(argv[8]))
        except (ValueError, OSError):
            result = {'refused': True}
        return (json.dumps(result, sort_keys=True) + '\n').encode()
    files = controller.SyntheticFiles(SimpleNamespace(call=call))
    original = files.call('stage')
    write = guest.os.write
    writes = []
    def partial(fd, data):
        writes.append(data)
        return write(fd, data[:3])
    monkeypatch.setattr(guest.os, 'write', partial)
    with pytest.raises(EvidenceError, match='guest-refusal'):
        files.call('change-source')
    for name in ('change-source', 'cleanup', 'read'):
        with pytest.raises(EvidenceError, match='replay'):
            files.call(name)
    assert writes == [guest.CHANGED_TEXT]
    assert files.previous == original


def test_source_entry_registration_and_refusal(tmp_path, monkeypatch):
    import check_e2e_edit_and_save_an_open_synthetic_document as entry
    import check_graphical_smoke
    from parent_setup_qualification import SourceChangeQualification
    run = Mock(return_value=0)
    monkeypatch.setattr(entry, 'smoke', run)
    assert entry.main() == 0
    assert run.call_args.kwargs['source_change'] is True
    with pytest.raises(CommandError, match='source-change-prerequisites'):
        check_graphical_smoke.main(source_change=True)
    journey = SourceChangeQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan.stage_actions == {'desktop': 'source-change'}
    assert journey.actions == {'source-change': controller.qualify_source_change}
    guard = Mock()
    with pytest.raises(EvidenceError, match='source-entry'):
        controller.change_attachment_source(SimpleNamespace(), guard)
    guard.assert_not_called()
