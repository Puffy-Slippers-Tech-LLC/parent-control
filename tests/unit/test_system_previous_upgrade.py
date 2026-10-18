"""Fail-closed policy history checks without installing packages or using a VM."""

import json
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_previous_upgrade as upgrade


@pytest.mark.parametrize('entry', ['prepare', 'verify_updated', 'verify_reboot'])
def test_attempt_guard_precedes_every_history_operation(monkeypatch, entry):
    monkeypatch.setattr(upgrade.guest, 'guard', Mock(side_effect=upgrade.guest.GuestError('guard')))
    load = Mock()
    wait = Mock()
    monkeypatch.setattr(upgrade, 'load_state', load)
    monkeypatch.setattr(upgrade.guest, 'wait_for_boot', wait)
    with pytest.raises(upgrade.guest.GuestError, match='guard'):
        getattr(upgrade, entry)(Mock())
    load.assert_not_called()
    wait.assert_not_called()


@pytest.mark.parametrize('observed,now', [([100, 43201], 200), ([101, 43200], 200),
                                         ([100, 43200], 43300), ([100, 43200], 99)])
def test_grant_refuses_replenishment_shifted_issuance_expiry_and_future(observed, now):
    with pytest.raises(upgrade.guest.GuestError, match='grant-expired-or-replaced'):
        upgrade.verify_grant([100, 43200], observed, now)


def test_fixed_grant_decreases_across_midnight_and_downtime():
    grant = [86300, 43200]
    assert upgrade.verify_grant(grant, grant, 86401) == 43099
    assert upgrade.verify_grant(grant, grant, 90000) == 39500


@pytest.fixture
def checkpoint(tmp_path, monkeypatch):
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    monkeypatch.setattr(upgrade.guest, 'PAYLOAD', tmp_path)
    # Unit fixtures belong to the unprivileged launcher; emulate root metadata.
    original_lstat = upgrade.Path.lstat
    original_fstat = upgrade.os.fstat

    def root_info(info):
        fields = list(info)
        fields[4] = fields[5] = 0
        return os.stat_result(fields)

    monkeypatch.setattr(upgrade.Path, 'lstat', lambda path: root_info(original_lstat(path)))
    monkeypatch.setattr(upgrade.os, 'fstat', lambda fd: root_info(original_fstat(fd)))
    marker = dict(run='a' * 32, package_sha256='b' * 64,
                  baseline_sha256='c' * 64, selected_inputs_sha256='d' * 64)
    return marker, {'schema': 1, 'binding': upgrade.binding(marker)}


def test_checkpoint_is_private_durable_and_bound_to_exact_attempt(checkpoint):
    marker, state = checkpoint
    upgrade.save_state(state)
    assert upgrade.load_state(marker) == state
    assert upgrade.state_path().stat().st_mode & 0o777 == 0o600
    marker['selected_inputs_sha256'] = 'e' * 64
    with pytest.raises(upgrade.guest.GuestError, match='checkpoint-attempt'):
        upgrade.load_state(marker)


def test_checkpoint_never_overwrites_or_follows_existing_file(checkpoint, tmp_path):
    marker, state = checkpoint
    target = tmp_path / 'foreign'
    target.write_text('foreign')
    upgrade.state_path().symlink_to(target)
    with pytest.raises(OSError):
        upgrade.save_state(state)
    with pytest.raises(OSError):
        upgrade.load_state(marker)
    assert target.read_text() == 'foreign'


@pytest.mark.parametrize('fault', ['mode', 'hardlink', 'size', 'schema'])
def test_checkpoint_refuses_unsafe_or_foreign_record(checkpoint, tmp_path, fault):
    marker, state = checkpoint
    upgrade.save_state(state)
    path = upgrade.state_path()
    if fault == 'mode':
        path.chmod(0o644)
    elif fault == 'hardlink':
        os.link(path, tmp_path / 'alias')
    elif fault == 'size':
        path.write_text(' ' * 65537)
    else:
        state['schema'] = 2
        path.write_text(json.dumps(state))
    with pytest.raises(upgrade.guest.GuestError, match='checkpoint-'):
        upgrade.load_state(marker)


@pytest.fixture
def preserved(monkeypatch):
    state = {'accounts': {'child': 1001, 'other': 1002},
             'identities': {'child': {'identity': 1}, 'other': {'identity': 2}},
             'other': 'digest', 'policy': {'policy': 1},
             'native': {'limits': [1, 2220, [100, 43200]], 'filter': ['hard']},
             'remaining': 43100}
    monkeypatch.setattr(upgrade, 'identity', lambda uid: {'identity': uid - 1000})
    monkeypatch.setattr(upgrade, 'account_digest', lambda uid: 'digest')
    monkeypatch.setattr(upgrade, 'saved_preferences', lambda uid: {'policy': 1})
    monkeypatch.setattr(upgrade, 'native_state', lambda uid: state['native'])
    monkeypatch.setattr(upgrade.time, 'time', lambda: 300)
    return state


@pytest.mark.parametrize('fault', ['identity', 'other', 'saved', 'native', 'expiry'])
def test_preservation_rejects_each_independent_loss(preserved, monkeypatch, fault):
    if fault == 'identity':
        monkeypatch.setattr(upgrade, 'identity', lambda uid: {})
    elif fault == 'other':
        monkeypatch.setattr(upgrade, 'account_digest', lambda uid: 'changed')
    elif fault == 'saved':
        monkeypatch.setattr(upgrade, 'saved_preferences', lambda uid: {})
    elif fault == 'native':
        monkeypatch.setattr(upgrade, 'native_state', lambda uid: {})
    else:
        monkeypatch.setattr(upgrade.time, 'time', lambda: 50000)
    with pytest.raises(upgrade.guest.GuestError, match='previous-upgrade:'):
        upgrade.verify_preserved(preserved)


def test_update_gate_is_diagnostics_only_and_preserves_rules(preserved, monkeypatch):
    preserved.update(boot='old-boot', old_version='1.3')
    monkeypatch.setattr(upgrade.guest, 'guard', lambda: {})
    monkeypatch.setattr(upgrade, 'load_state', lambda marker: preserved)
    monkeypatch.setattr(upgrade, 'boot', lambda: 'old-boot')
    monkeypatch.setattr(upgrade.guest, 'reboot_requested', lambda: True)
    monkeypatch.setattr(upgrade.guest, 'verify_package_files', Mock())
    monkeypatch.setattr(upgrade.guest, 'package_path', lambda: 'candidate')
    monkeypatch.setattr(upgrade.guest, 'package_identity', lambda *args, **kwargs: '1.4')
    monkeypatch.setattr(upgrade.guest, 'execution_rule_state', lambda: 'rules')
    gate = Mock()
    retirement = Mock(return_value='pre-reboot-removal-refused')
    monkeypatch.setattr(upgrade.guest, 'verify_reboot_gate', gate)
    monkeypatch.setattr(upgrade.guest, 'verify_upgrade_admission_receipt', retirement)
    public = Mock(side_effect=AssertionError('policy API before reboot'))
    monkeypatch.setattr(upgrade, 'call', public)
    record = Mock()
    upgrade.verify_updated(record)
    gate.assert_called_once_with()
    retirement.assert_called_once_with('old-boot')
    public.assert_not_called()
    record.assert_any_call('onpc.previous-upgrade.admission', 'pre-reboot-removal-refused')


@pytest.mark.parametrize('stage', ['previous', 'rebooted'])
def test_enforcement_witness_requires_hard_denial_soft_allowance_and_uid_isolation(monkeypatch, stage):
    launch = Mock()
    monkeypatch.setattr(upgrade, 'observe_launch', launch)
    rules = Mock()
    monkeypatch.setattr(upgrade, 'record_rules', rules)
    record = Mock()
    upgrade.witness_enforcement({'child': 1001, 'other': 1002}, record, stage)
    assert [(args.args, args.kwargs) for args in rules.call_args_list] == [
        ((f'previous-upgrade-{stage}', 1001, True, record), {'variant': 'trusted-hard'}),
        ((f'previous-upgrade-{stage}', 1001, False, record), {'variant': 'trusted-soft'})]
    assert [(args.args, args.kwargs) for args in launch.call_args_list] == [
        ((1001, False), {'variant': 'trusted-hard'}), ((1002, True), {'variant': 'trusted-hard'}),
        ((1001, True), {'variant': 'trusted-soft'}), ((1002, True), {'variant': 'trusted-soft'})]


@pytest.fixture
def preparation(tmp_path, monkeypatch):
    (tmp_path / 'results').mkdir()
    (tmp_path / 'results/previous-install.json').write_text(json.dumps({
        'boot': 'before', 'previous_package_sha256': 'a' * 64}))
    monkeypatch.setattr(upgrade.guest, 'PAYLOAD', tmp_path)
    marker = dict(run='a' * 32, package_sha256='b' * 64,
                  baseline_sha256='c' * 64, selected_inputs_sha256='d' * 64)
    monkeypatch.setattr(upgrade.guest, 'guard', lambda: marker)
    monkeypatch.setattr(upgrade.guest, 'wait_for_boot', Mock())
    monkeypatch.setattr(upgrade, 'boot', lambda: 'after')
    monkeypatch.setattr(upgrade.guest, 'reboot_cleared', lambda: True)
    monkeypatch.setattr(upgrade.guest, 'sha', lambda path: 'a' * 64)
    monkeypatch.setattr(upgrade.guest, 'KIOSK_CONFINEMENT_STATE', tmp_path / 'absent')
    monkeypatch.setattr(upgrade.guest, 'verify_package_files', Mock())
    monkeypatch.setattr(upgrade.guest, 'package_identity',
                        lambda path, **kw: 'old' if path.name.startswith('previous-') else 'new')
    accounts = {'child': 1001, 'other': 1002, 'parent': 1003}
    provision = Mock(side_effect=lambda variant: accounts.copy())
    monkeypatch.setattr(upgrade, 'provision_native', provision)
    monkeypatch.setattr(upgrade, 'account_digest', lambda uid: 'unchanged')
    monkeypatch.setattr(upgrade, 'identity', lambda uid: {'account': [uid, '/bin/bash']})
    monkeypatch.setattr(upgrade, 'native_state', lambda uid: {
        'limits': [2, 2220, [100, 45420]], 'filter': ['hard'], 'extensions': []})
    monkeypatch.setattr(upgrade.time, 'time', lambda: 200)
    monkeypatch.setattr(upgrade.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1004))
    read_text = upgrade.Path.read_text
    monkeypatch.setattr(upgrade.Path, 'read_text', lambda path, *a, **kw:
                        '{"kiosk_uid": 1005}' if str(path) == '/etc/oh-no-parent-control/config.json'
                        else read_text(path, *a, **kw))
    preferences = {'apps': {}, 'parent_control_enabled': False, 'daily_time_limit_minutes': 0,
                   'request': {'last_selected_duration': 'default', 'last_custom_minutes': 0,
                               'allow_soft_blocked_apps': False, 'last_selected_approver_uid': 0,
                               'kiosk_muted': True, 'child_muted': True}}

    def call(uid, method, signature='()', args=()):
        if method == 'GetPreferences':
            return [json.dumps(preferences)]
        if method == 'SetParentControl':
            preferences.update(parent_control_enabled=args[1], daily_time_limit_minutes=args[2])
        elif method == 'SetPreferences':
            preferences.update(json.loads(args[1]))
        elif method == 'UpdateRequestPreferences':
            preferences['request'].update(zip((
                'last_selected_duration', 'last_custom_minutes', 'allow_soft_blocked_apps',
                'last_selected_approver_uid'), args[1:]))
        else:
            raise AssertionError(method)
        return []

    monkeypatch.setattr(upgrade, 'call', call)
    events = Mock()
    monkeypatch.setattr(upgrade, 'record_rules', events.rules)
    monkeypatch.setattr(upgrade, 'observe_launch', events.launch)
    password = Mock()
    monkeypatch.setattr(upgrade, 'FixturePassword', lambda: password)
    caller = Mock()
    caller.receive.return_value = {'result': [True, 'approved']}
    caller.__enter__ = Mock(return_value=caller)
    caller.__exit__ = Mock(return_value=False)
    agent = Mock()
    agent.__enter__ = Mock(return_value=agent)
    agent.__exit__ = Mock(return_value=False)
    agent.authenticate.side_effect = lambda credential: events.authenticate(credential)
    monkeypatch.setattr(upgrade, 'PersistentCaller', lambda uid: caller)
    monkeypatch.setattr(upgrade, 'TextAgent', lambda target: agent)
    checkpoint = Mock()
    monkeypatch.setattr(upgrade, 'save_state', checkpoint)
    return SimpleNamespace(preferences=preferences, provision=provision, events=events,
                           password=password, caller=caller, agent=agent, checkpoint=checkpoint)


@pytest.mark.parametrize('suffix,schema', [('.deb', 3), ('.rpm', 4)])
def test_preparation_saves_qualified_choices_and_denies_soft_before_approval(
        preparation, monkeypatch, tmp_path, suffix, schema):
    state = preparation
    monkeypatch.setattr(upgrade.guest, 'package_path', lambda: tmp_path / ('package' + suffix))
    state.preferences['version'] = schema
    record = Mock()
    upgrade.prepare(record)
    assert [item.args for item in state.provision.call_args_list] == [
        ('trusted-hard',), ('trusted-soft',)]
    saved = state.checkpoint.call_args.args[0]
    expected = {}
    for variant, app_state in (('trusted-hard', 'permanent'), ('trusted-soft', 'conditional')):
        target, _, desktop = upgrade.native_paths(variant)
        expected[desktop] = {'state': app_state, 'targets': [str(target)], 'patterns': [],
                             'user_saved_match_rule': False}
    assert saved['policy']['apps'] == expected
    assert saved['native']['limits'] == [2, 2220, [100, 45420]]
    assert [(item[0], item.args, item.kwargs) for item in state.events.mock_calls] == [
        ('rules', ('previous-upgrade-strict', 1001, True, record), {'variant': 'trusted-soft'}),
        ('launch', (1001, False), {'variant': 'trusted-soft'}),
        ('authenticate', (state.password,), {}),
        ('rules', ('previous-upgrade-previous', 1001, True, record), {'variant': 'trusted-hard'}),
        ('launch', (1001, False), {'variant': 'trusted-hard'}),
        ('launch', (1002, True), {'variant': 'trusted-hard'}),
        ('rules', ('previous-upgrade-previous', 1001, False, record), {'variant': 'trusted-soft'}),
        ('launch', (1001, True), {'variant': 'trusted-soft'}),
        ('launch', (1002, True), {'variant': 'trusted-soft'})]
    state.password.install.assert_called_once_with(1003)
    state.agent.prompt.assert_called_once_with(1003, 1004)
    state.caller.send.assert_called_once_with({
        'kind': 'call', 'method': 'RequestOwnAccess', 'signature': '(uub)',
        'args': (1003, 43200, True)})
    state.agent.__exit__.assert_called_once()
    state.caller.__exit__.assert_called_once()


@pytest.mark.parametrize('fault', ['identities', 'strict-soft'])
def test_preparation_refuses_mismatched_fixtures_or_missing_strict_denial(
        preparation, monkeypatch, tmp_path, fault):
    state = preparation
    monkeypatch.setattr(upgrade.guest, 'package_path', lambda: tmp_path / 'package.rpm')
    state.preferences['version'] = 4
    if fault == 'identities':
        state.provision.side_effect = [{'child': 1001, 'other': 1002, 'parent': 1003}, {}]
    else:
        state.events.launch.side_effect = upgrade.guest.GuestError('enforcement:expected-denial')
    with pytest.raises(upgrade.guest.GuestError, match=(
            'fixture-identities' if fault == 'identities' else 'expected-denial')):
        upgrade.prepare(Mock())
    state.password.install.assert_not_called()
    state.agent.authenticate.assert_not_called()
    state.checkpoint.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'same-boot', 'marker', 'replenished-status'])
def test_reboot_requires_new_boot_and_public_elapsed_grant(preserved, monkeypatch, fault):
    preserved.update(boot='old-boot', remaining=43200)
    preserved['accounts']['parent'] = 1003
    monkeypatch.setattr(upgrade.guest, 'guard', lambda: {})
    monkeypatch.setattr(upgrade, 'load_state', lambda marker: preserved)
    monkeypatch.setattr(upgrade, 'boot', lambda: 'old-boot' if fault == 'same-boot' else 'new-boot')
    monkeypatch.setattr(upgrade.guest, 'reboot_cleared', lambda: fault != 'marker')
    monkeypatch.setattr(upgrade.guest, 'installed', Mock())
    policy = {'parent_control_enabled': True, 'daily_time_limit_minutes': 37,
              'apps': {}, 'request': {'last_selected_duration': 'custom',
                  'last_custom_minutes': 23.0, 'allow_soft_blocked_apps': True,
                  'last_selected_approver_uid': 1003, 'kiosk_muted': True, 'child_muted': True}}
    preserved['policy'] = policy
    monkeypatch.setattr(upgrade, 'saved_preferences', lambda uid: policy)
    calls = []

    def public(uid, method, *args):
        calls.append(method)
        if method == 'GetPreferences':
            return [json.dumps(policy)]
        if method == 'GetTimeStatus':
            remaining = 43200 if fault == 'replenished-status' else 43000
            return [2220, remaining, 0, remaining]
        return [False]

    monkeypatch.setattr(upgrade, 'call', public)
    witness = Mock()
    monkeypatch.setattr(upgrade, 'witness_enforcement', witness)
    if fault:
        with pytest.raises(upgrade.guest.GuestError, match='previous-upgrade:'):
            upgrade.verify_reboot(Mock())
        witness.assert_not_called()
    else:
        record = Mock()
        upgrade.verify_reboot(record)
        assert calls == ['GetPreferences', 'PrepareOwnSession', 'GetTimeStatus']
        witness.assert_called_once_with(preserved['accounts'], record, 'rebooted')


def test_policy_comparison_preserves_old_choices_with_compatible_new_fields():
    policy = {'parent_control_enabled': True, 'daily_time_limit_minutes': 37,
              'apps': {}, 'request': {'last_selected_duration': 'custom',
                  'last_custom_minutes': 23.0, 'allow_soft_blocked_apps': True,
                  'last_selected_approver_uid': 1003, 'kiosk_muted': True, 'child_muted': True}}
    projected = upgrade.policy_projection(policy)
    policy['request']['last_custom_unit'] = 'minutes'
    policy['personal'] = {'new-compatible-field': []}
    assert upgrade.policy_projection(policy) == projected


def test_only_the_declared_kiosk_shell_transition_is_allowed():
    expected = {'account': ['station', 1005, 1005, '/home/station', '/bin/bash'],
                'home': ['ext4', 'uuid', None, 42, 1005, 1005, 0o40700]}
    assert upgrade.upgraded_identity('child', expected) is expected
    changed = upgrade.upgraded_identity('kiosk', expected)
    assert changed == {**expected, 'account': [*expected['account'][:-1], '/usr/sbin/nologin']}
    assert expected['account'][-1] == '/bin/bash'
    expected['account'][-1] = '/foreign/shell'
    with pytest.raises(upgrade.guest.GuestError, match='prior-kiosk-shell'):
        upgrade.upgraded_identity('kiosk', expected)


@pytest.mark.parametrize('version,language', [(3, None), (4, None), (4, 'changed'), (4, '')])
def test_saved_policy_requires_completed_schema_migration(tmp_path, monkeypatch, version, language):
    policy = {'version': version, 'personal': {} if language is None else {'language': language},
              'parent_control_enabled': True, 'daily_time_limit_minutes': 37,
              'apps': {}, 'request': {'last_selected_duration': 'custom',
                  'last_custom_minutes': 23.0, 'allow_soft_blocked_apps': True,
                  'last_selected_approver_uid': 1003, 'kiosk_muted': True, 'child_muted': True}}
    (tmp_path / '1001.json').write_text(json.dumps(policy))
    monkeypatch.setattr(upgrade, 'PREFERENCES', tmp_path)
    if version == 4 and language == '':
        assert upgrade.saved_preferences(1001) == upgrade.policy_projection(policy)
    else:
        with pytest.raises(upgrade.guest.GuestError, match='preference-migration'):
            upgrade.saved_preferences(1001)
