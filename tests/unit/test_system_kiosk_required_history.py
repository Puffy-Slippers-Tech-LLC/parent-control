"""Required retained histories use real private inodes and bounded API doubles."""

import base64
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_kiosk_required_history as history


@pytest.fixture
def files(tmp_path, monkeypatch):
    path = tmp_path / 'required'
    original = b'\x7fELF-private-native-content'
    path.write_bytes(original)
    path.chmod(0o755)
    fd = os.open(path, os.O_RDONLY)
    try:
        metadata, _ = history.snapshot(fd)
    finally:
        os.close(fd)
    intent = dict(path=str(path), metadata=metadata, data=base64.b64encode(original).decode(),
                  sha256=history.sha(original), backend='apparmor', original={}, pam={}, ordinary={},
                  boot='b' * 32)
    records = {}

    def saved(branch, phase):
        return intent if phase == 'intent' else records[(branch, phase)]

    def save(branch, phase, **values):
        assert (branch, phase) not in records
        records[branch, phase] = values

    monkeypatch.setattr(history, 'saved', saved)
    monkeypatch.setattr(history, 'save', save)
    monkeypatch.setattr(history, 'boundary', Mock(return_value=object()))
    monkeypatch.setattr(history.native, 'private', lambda: tmp_path)
    return SimpleNamespace(path=path, original=original, intent=intent, records=records)


def enable_privilege(files):
    files.path.chmod(0o4755)
    files.intent['backend'] = 'selinux'
    files.intent['metadata']['st_mode'] = files.path.stat().st_mode


@pytest.mark.parametrize('branch', history.BRANCHES)
def test_each_mutation_changes_required_input_and_restores_exact_original_inode(files, branch):
    if branch == 'privilege':
        enable_privilege(files)
    before = files.path.stat()
    history.mutate(branch)
    changed = files.path.read_bytes()
    if branch == 'privilege':
        assert changed == files.original
        assert files.path.stat().st_mode & 0o6000 == 0
    else:
        assert changed != files.original
        assert changed.startswith(files.original)
    history.restore(branch)
    after = files.path.stat()
    assert files.path.read_bytes() == files.original
    assert (after.st_dev, after.st_ino, after.st_mode, after.st_uid, after.st_gid,
            after.st_mtime_ns) == (before.st_dev, before.st_ino, before.st_mode, before.st_uid,
                                   before.st_gid, before.st_mtime_ns)
    assert (branch, 'restored') in files.records


@pytest.mark.parametrize('partial', [b'', b'\n', history.SUFFIX[:12], history.SUFFIX])
def test_interrupted_append_recovers_from_durable_intent_without_mutated_checkpoint(files, partial):
    with files.path.open('ab') as stream:
        stream.write(partial)
    history.restore('native')
    assert files.path.read_bytes() == files.original
    assert ('native', 'mutated') not in files.records
    assert ('native', 'restored') in files.records


@pytest.mark.parametrize('mutation', ['replace', 'prefix', 'extra', 'mode', 'hardlink', 'xattr'])
def test_cleanup_refuses_foreign_state_and_preserves_it(files, mutation):
    if mutation == 'replace':
        files.path.rename(files.path.with_name('displaced'))
        files.path.write_bytes(files.original)
    elif mutation == 'prefix':
        files.path.write_bytes(b'foreign-prefix')
    elif mutation == 'extra':
        files.path.write_bytes(files.original + b'foreign-suffix')
    elif mutation == 'mode':
        files.path.chmod(0o777)
    elif mutation == 'hardlink':
        os.link(files.path, files.path.with_name('foreign-link'))
    else:
        os.setxattr(files.path, 'user.foreign', b'unknown')
    before = files.path.read_bytes(), files.path.stat().st_mode
    with pytest.raises(history.guest.GuestError, match='required-history:'):
        history.restore('native')
    assert (files.path.read_bytes(), files.path.stat().st_mode) == before
    assert ('native', 'restored') not in files.records


def test_mutation_refuses_uncheckpointed_prior_drift(files):
    files.path.write_bytes(files.original + history.SUFFIX)
    with pytest.raises(history.guest.GuestError, match='unattributable-file'):
        history.mutate('native')
    assert not files.records


def test_native_candidate_is_actual_selected_required_inventory():
    inventory = Mock(return_value=[dict(path='/usr/bin/xdg-dbus-proxy', role='service')])
    assert history.selected_path('native', {'inventory': inventory}, {}) == Path('/usr/bin/xdg-dbus-proxy')
    for rows in ([], [dict(path='/usr/bin/xdg-dbus-proxy', role='blocked')]):
        inventory.return_value = rows
        with pytest.raises(history.guest.GuestError, match='native-not-selected'):
            history.selected_path('native', {'inventory': inventory}, {})


@pytest.mark.parametrize('backend,mode', [('apparmor', 0o755), ('selinux', 0o4755)])
def test_preserved_candidate_is_fixed_verified_vendor_helper_on_both_backends(backend, mode):
    inventory = Mock(return_value=([dict(path=str(history.PRESERVED_HELPER), mode=mode)], {}))
    config = {'backend': backend}
    assert history.selected_path('privilege', {'preserved_inventory': inventory}, config) == history.PRESERVED_HELPER
    inventory.assert_called_once_with(config)


@pytest.mark.parametrize('rows', [[], [dict(path='/usr/libexec/other-helper', mode=0o4755)],
                                   [dict(path=str(history.PRESERVED_HELPER), mode=0o755)] * 2])
def test_preserved_candidate_refuses_missing_other_or_duplicate_helpers(rows):
    inventory = Mock(return_value=(rows, {}))
    with pytest.raises(history.guest.GuestError, match='privileged-helper-missing'):
        history.selected_path('privilege', {'preserved_inventory': inventory}, {})


@pytest.mark.parametrize('backend,mode,changed', [
    ('apparmor', 0o755, 0o644), ('selinux', 0o4755, 0o755), ('selinux', 0o6755, 0o755),
])
def test_vendor_mode_drift_is_effective_safe_and_recovers_original_inode(files, backend, mode, changed):
    files.path.chmod(mode)
    files.intent['backend'] = backend
    files.intent['metadata']['st_mode'] = files.path.stat().st_mode
    original_inode = files.path.stat().st_ino
    history.mutate('privilege')
    assert files.path.stat().st_mode & 0o7777 == changed
    assert changed & ~mode == 0
    assert files.path.read_bytes() == files.original
    history.restore('privilege')
    assert files.path.stat().st_mode & 0o7777 == mode
    assert files.path.stat().st_ino == original_inode


@pytest.mark.parametrize('backend,mode', [('apparmor', 0o644), ('apparmor', 0o4755),
                                       ('selinux', 0o755), ('unknown', 0o4755)])
def test_vendor_mode_mutation_refuses_an_unrecognized_original_requirement(files, backend, mode):
    files.intent['backend'] = backend
    files.intent['metadata']['st_mode'] = mode
    with pytest.raises(history.guest.GuestError, match='vendor-privilege-mode'):
        history.privilege_mode(files.intent)


def test_ubuntu_cleanup_refuses_a_mode_outside_original_or_exact_tightening(files):
    files.path.chmod(0o654)
    with pytest.raises(history.guest.GuestError, match='unattributable-file'):
        history.restore('privilege')
    assert files.path.stat().st_mode & 0o7777 == 0o654


@pytest.mark.parametrize('branch', history.BRANCHES)
def test_refusal_composes_actual_stage_and_preserves_manager_identity(files, monkeypatch, branch):
    if branch == 'privilege':
        enable_privilege(files)
    history.mutate(branch)
    observation = dict(call=dict(pid=42, exe='/usr/bin/python3.14'), markers=[])
    stale = Mock(return_value=observation)
    monkeypatch.setattr(history.native, 'stale_admission', stale)
    monkeypatch.setattr(history.guest, 'pam_service_state', lambda: {})
    monkeypatch.setattr(history, 'ordinary_controls', Mock())
    import system_kiosk_accounts
    monkeypatch.setattr(system_kiosk_accounts, 'verify_ordinary', Mock())
    commands = SimpleNamespace(last_returncode=1, run=Mock(return_value=
        b'configuration failed reason=policy-load-incomplete-reconfigure-required; preserving'),
        sequence=0)
    monkeypatch.setattr(history.guest, 'commands', commands)
    capture = Mock(return_value=observation)
    monkeypatch.setattr(history, 'capture_refusal', capture)
    history.refusal(branch)
    assert (branch, 'refusal') in files.records
    if branch == 'native':
        stale.assert_called_once()
        capture.assert_not_called()
        commands.run.assert_not_called()
    elif branch in ('config', 'policy'):
        commands.run.assert_called_once_with([history.INTEGRATION, 'verify'], check=False,
                                             merge_stderr=True, timeout=15)
        assert files.records[branch, 'refusal']['stage'] == 'measurement'
    else:
        assert files.records[branch, 'refusal']['stage'] == 'measurement'
    assert files.records[branch, 'refusal']['observation'] == observation
    assert history.boundary.call_count == 4  # before/after mutation and refusal


def test_public_refusal_requires_new_actual_causes_and_no_graphical_session(files, monkeypatch):
    history.mutate('config')
    window = dict(boot='b' * 32, realtime_us=10000000, monotonic_us=10)
    files.records['config', 'refusal'] = dict(public_window=window, observation=dict(call=dict(pid=41)))
    rows = required_journal('config')
    run = Mock(side_effect=['\n'.join(json.dumps(row) for row in rows), ''])
    monkeypatch.setattr(history.guest, 'run', run)
    monkeypatch.setattr(history.native, 'refusal_window', lambda:
                        dict(window, realtime_us=10000010, monotonic_us=20))
    monkeypatch.setattr(history, 'ordinary_controls', Mock())
    history.public_refusal('config')
    receipt = files.records['config', 'public-refusal']
    assert receipt['graphical_session'] == 'absent'
    assert {row['kind'] for row in receipt['markers']} == {'cause', 'native'}
    assert run.call_args_list[0].args[0] == ['journalctl', '-b', '--since=@10',
                                            '--no-pager', '-o', 'json']


@pytest.mark.parametrize('message,timestamp', [
    ('foreign reason=command-failed', '10000002'),
    ('onpc.kiosk confinement reason=command-failed', '9999999'),
    ('onpc.kiosk confinement reason=unexpected-preserved-executable', '10000002'),
])
def test_public_refusal_does_not_reuse_internal_old_or_unrelated_causes(files, monkeypatch,
                                                                    message, timestamp):
    history.mutate('config')
    window = dict(boot='b' * 32, realtime_us=10000000, monotonic_us=10)
    files.records['config', 'refusal'] = dict(public_window=window, observation=dict(call=dict(pid=41)))
    rows = [dict(MESSAGE=message, __REALTIME_TIMESTAMP=timestamp),
            dict(MESSAGE='onpc.pam kiosk execution-boundary outcome=denied stage=prepare',
                 __REALTIME_TIMESTAMP='10000003')]
    monkeypatch.setattr(history.guest, 'run', Mock(return_value='\n'.join(
        json.dumps(row) for row in rows)))
    monkeypatch.setattr(history.native.time, 'monotonic', Mock(side_effect=[0, 100]))
    with pytest.raises(history.guest.GuestError, match='stale-manager-reason'):
        history.public_refusal('config')
    assert ('config', 'public-refusal') not in files.records


def required_journal(branch):
    stage, reason = history.refusal_cause(branch)
    source = dict(_UID='0', _PID='42', _EXE='/usr/libexec/gdm-session-worker',
                  _COMM='gdm-session-wor', _TRANSPORT='syslog', _BOOT_ID='b' * 32)
    prefix = 'pam_oh_no_parent_control(gdm-password:session): '
    return [dict(source, MESSAGE=prefix + 'onpc.pam kiosk native-view outcome=denied role=gate '
                 f'stage={stage} reason={reason} errno=-1',
                 _SOURCE_REALTIME_TIMESTAMP='10000001',
                 __REALTIME_TIMESTAMP='10000001', __MONOTONIC_TIMESTAMP='11'),
            dict(source, MESSAGE=prefix + 'onpc.pam kiosk execution-boundary outcome=denied '
                 f'stage={stage}', _SOURCE_REALTIME_TIMESTAMP='10000002',
                 __REALTIME_TIMESTAMP='10000002', __MONOTONIC_TIMESTAMP='12')]


@pytest.mark.parametrize('branch', history.BRANCHES)
@pytest.mark.parametrize('fault', [None, 'earlier-stage', 'generic-reason', 'other-role',
                                  'old-source', 'delayed-old-source', 'foreign-source', 'different-call'])
def test_branch_observer_requires_its_own_actual_native_cause(files, monkeypatch, branch, fault):
    rows = required_journal(branch)
    if fault == 'earlier-stage':
        rows[0]['MESSAGE'] = rows[0]['MESSAGE'].replace(
            'stage=' + history.refusal_cause(branch)[0], 'stage=authority')
    elif fault == 'generic-reason':
        rows[0]['MESSAGE'] = rows[0]['MESSAGE'].replace(history.refusal_cause(branch)[1], 'command-failed')
    elif fault == 'other-role':
        rows[0]['MESSAGE'] = rows[0]['MESSAGE'].replace('role=gate', 'role=manager')
    elif fault == 'old-source':
        rows[0]['__REALTIME_TIMESTAMP'] = '10000000'
    elif fault == 'delayed-old-source':
        rows[0]['_SOURCE_REALTIME_TIMESTAMP'] = '10000000'
    elif fault == 'foreign-source':
        rows[0]['_EXE'] = '/tmp/gdm-session-worker'
    elif fault == 'different-call':
        rows[1]['_PID'] = '43'
    window = dict(boot='b' * 32, realtime_us=10000000, monotonic_us=10)
    monkeypatch.setattr(history.native, 'refusal_window', lambda:
                        dict(window, realtime_us=10000010, monotonic_us=20))
    monkeypatch.setattr(history.native.time, 'monotonic', Mock(side_effect=[0, 100]))
    monkeypatch.setattr(history.guest, 'run', Mock(return_value='\n'.join(json.dumps(row) for row in rows)))
    monkeypatch.setattr(history.confinement, 'first_exec', lambda *args, **kwargs:
        (125, b'{"pam":14,"pid":42,"exe":"/usr/libexec/gdm-session-worker"}'))
    # Internal first_exec starts before these finite source timestamps.
    monkeypatch.setattr(history.native, 'refusal_window', Mock(side_effect=[window,
                        dict(window, realtime_us=10000010, monotonic_us=20)]))
    if fault:
        with pytest.raises(history.guest.GuestError, match='stale-manager-reason'):
            history.capture_refusal(object(), branch)
    else:
        result = history.capture_refusal(object(), branch)
        assert {row['kind'] for row in result['markers']} == {'cause', 'native'}
        assert result['call']['pid'] == 42


def test_actual_stale_manager_failure_is_not_replaced_by_an_earlier_refusal(files, monkeypatch):
    history.mutate('native')
    monkeypatch.setattr(history.native, 'stale_admission', Mock(side_effect=
        history.guest.GuestError('native-update:stale-manager-reason')))
    monkeypatch.setattr(history.guest, 'commands', SimpleNamespace(sequence=0))
    with pytest.raises(history.guest.GuestError, match='stale-manager-reason'):
        history.refusal('native')
    assert ('native', 'refusal') not in files.records


@pytest.mark.parametrize('action,branch', [('prepare', '../native'), ('unknown', None), ('cleanup', 'native')])
def test_command_rejects_unbounded_actions_before_mutation(monkeypatch, action, branch):
    monkeypatch.setattr(history, 'binding', Mock())
    mutate = Mock()
    monkeypatch.setattr(history, 'mutate', mutate)
    with pytest.raises(history.guest.GuestError, match='required-history:'):
        history.command(action, branch)
    mutate.assert_not_called()


def test_identity_guard_precedes_every_command(monkeypatch):
    monkeypatch.setattr(history, 'binding', Mock(side_effect=history.guest.GuestError('identity')))
    mutate = Mock()
    monkeypatch.setattr(history, 'mutate', mutate)
    with pytest.raises(history.guest.GuestError, match='identity'):
        history.command('mutate', 'native')
    mutate.assert_not_called()


def test_boundary_binds_original_unit_invocation_and_retained_view(monkeypatch):
    account = SimpleNamespace(pw_uid=41000)
    monkeypatch.setattr(history.pwd, 'getpwnam', Mock(return_value=account))
    observed = dict(pid=42, identity=['start', 1, ['41000'] * 4], namespace='mnt:[7]',
                    label='enforce', generation='retained-material-and-view')
    probe = Mock(return_value=observed)
    monkeypatch.setattr(history.confinement, 'manager_boundary', probe)
    unit = Mock(return_value={'InvocationID': 'owned'})
    monkeypatch.setattr(history.scope, 'manager', unit)
    intent = dict(backend='apparmor', original=dict(boundary=observed,
                                                  unit={'InvocationID': 'owned'}))
    assert history.boundary(intent) is account
    probe.assert_called_once_with(account, 'user@41000.service', 'apparmor', retained_view=True)
    unit.return_value = {'InvocationID': 'replacement'}
    with pytest.raises(history.guest.GuestError, match='manager-replaced'):
        history.boundary(intent)


def test_checkpoint_inventory_is_finite_complete_and_unique():
    names = history.checkpoint_names()
    assert len(names) == len(set(names)) == 24
    assert 'required-history-native-public-refusal.json' in names
    assert 'required-history-privilege-complete.json' in names


@pytest.mark.parametrize('phase', ['pam', 'public'])
def test_refusal_diagnostics_use_the_existing_redacted_text_export_route(files, phase):
    path = history.diagnostic_path('config', phase)
    assert path == files.path.parent / 'required-history-output' / ('config-' + phase + '.txt')
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    path.write_text('first failure')
    with pytest.raises(FileExistsError):
        history.diagnostic_path('config', phase)
    assert path.read_text() == 'first failure'
