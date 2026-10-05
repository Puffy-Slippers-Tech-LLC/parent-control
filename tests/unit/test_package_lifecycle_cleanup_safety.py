"""Continuous lifecycle ordering, public assertions and failure ownership."""

from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import package_command as command
import package_lifecycle as lifecycle
import removal_journey as case
from private_artifacts import EvidenceError
from tests.support.desktop_session import RUN_PROBE, props
from tests.support.package_command import boundary, DIGEST
from tests.support.perl import run_perl


@pytest.fixture(autouse=True)
def platform(monkeypatch):
    monkeypatch.setattr(command.session_control, 'package_format', lambda: 'deb')


def identity(version):
    return {'version': version, 'packages': {'current': DIGEST}, 'boot': 'b' * 64, 'session': '7',
            'preserved': {'accounts': {'1000': {'identity': ['fixture-parent', 1000],
                                              'groups': [1000, 27], 'language': 'en_US.UTF-8'}},
                          'files': {'hostname': 'c' * 64}, 'system_locale': ['LANG=en_US.UTF-8'],
                          'observer_locale': {'LANG': 'C.UTF-8'}}}


def journey(monkeypatch):
    transfer = Mock()
    monkeypatch.setattr(lifecycle, 'AssetTransfer', Mock(return_value=transfer))
    context = SimpleNamespace(installed_snapshot=None, verified=SimpleNamespace(upgrade_inputs=None),
                              lease=Mock(), guestfs=Mock())
    current = case.RemovalJourney(context, Mock())
    transfer.provision.assert_called_once_with(context.lease, context.guestfs)
    return current


@pytest.mark.parametrize('binding', command.LIFECYCLE)
@pytest.mark.parametrize('fault', ['', 'phase', 'version', 'status', 'notice', 'trailing', 'transport'])
def test_finite_command_refuses_wrong_phase_and_independent_failure(monkeypatch, binding, fault):
    item = boundary(monkeypatch)
    item.verified.upgrade_inputs = None
    item.package_identities = Mock(return_value={'current': {'version': '1.3'}})
    removing = binding in (command.REMOVE, command.PURGE)
    expected_before = '1.3' if removing else None
    before = identity('wrong' if fault == 'phase' else expected_before)
    after = identity('wrong' if fault == 'version' else None if removing else '1.3')
    item.read_identity = Mock(side_effect=[before, after])
    raw = (command.PURGE_COMPLETE + '\n' + command.REMOVAL_NOTICE + '\n' if binding == command.PURGE
           else command.REMOVAL_NOTICE + '\n' if removing else command.COMPLETE + '\n' + command.NOTICE + '\n')
    if fault == 'notice': raw = 'transaction completed\n'
    if fault == 'trailing': raw += 'manager summary\n'
    item.transport.call.return_value = raw.encode()
    item.transport.commands.last_returncode = 1 if fault == 'status' else 0
    if fault == 'transport': item.transport.call.side_effect = TimeoutError()
    if fault in ('phase', 'transport'):
        with pytest.raises((EvidenceError, TimeoutError)):
            item.submit(binding, DIGEST, item.identity)
        if fault == 'phase':
            item.transport.call.assert_not_called()
            assert not item.attempted
        else:
            with pytest.raises(EvidenceError, match='replay'):
                item.submit(binding, DIGEST, item.identity)
        return
    item.submit(binding, DIGEST, item.identity)
    failing = fault and not (fault == 'trailing' and binding == command.PURGE)
    if failing:
        with pytest.raises(EvidenceError): item.read_result()
    else:
        output = item.read_result()
        assert output['operation'] == binding and output['notice'] == (
            command.REMOVAL_NOTICE if removing else command.NOTICE)
        assert item.transport.call.call_count == 1


@pytest.mark.parametrize('binding', lifecycle.HISTORY)
@pytest.mark.parametrize('fault', ['', 'personal-account', 'files', 'boot', 'session', 'unstable', 'version'])
def test_receipt_requires_personal_preservation_and_same_activation_boundary(monkeypatch, binding, fault):
    current = journey(monkeypatch)
    before = identity('1.3' if binding in (command.REMOVE, command.PURGE) else None)
    after = identity(None if binding in (command.REMOVE, command.PURGE) else '1.3')
    if fault == 'personal-account': after['preserved']['accounts']['1000']['groups'] = []
    if fault == 'files': after['preserved']['files'] = {}
    if fault == 'boot': after['boot'] = 'd' * 64
    if fault == 'session': after['session'] = '8'
    if fault == 'version': after['version'] = 'wrong'
    other = deepcopy(after)
    if fault == 'unstable': other['session'] = '8'
    receipt = Mock(read_result=Mock(return_value={'operation': binding, 'outcome': 'passed'}),
                   read_identity=Mock(side_effect=[after, other]),
                   package_identities=Mock(return_value={'current': {'version': '1.3'}}))
    current.commands[binding] = receipt
    current.entries[binding] = before
    stage = next(result for _, operation, result in case.OPERATIONS if operation == binding)
    observed = {}
    if fault:
        with pytest.raises(EvidenceError): current.check_settings(stage, observed)
        assert binding not in current.results
    else:
        current.check_settings(stage, observed)
        assert observed['package']['independent_readback'] and binding in current.results


@pytest.mark.parametrize('fault', ['daily', 'enabled', 'rows', 'grant', 'choices'])
def test_retained_and_fresh_assertions_use_independent_customer_expectations(monkeypatch, fault):
    current = journey(monkeypatch)
    policy = {'settings': {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['4 minutes']},
              'rows': [[case.MATCH_APP, 'permanent', 'precise']],
              'balances': {'daily': 900, 'one_time': 0, 'total': 900}}
    current.check_settings('initial-policy', {'ui': {'language_policy': deepcopy(policy)}})
    if fault == 'daily': policy['settings']['allowance'] = ['0 minutes']
    if fault == 'enabled': policy['settings']['limit_enabled'] = False
    if fault == 'rows': policy['rows'] = [[case.MATCH_APP, 'allowed', 'precise']]
    if fault == 'grant': policy['balances']['one_time'] = 75
    if fault == 'choices':
        observed = {'ui': {'valid_choice': {'request': {'child': 'fixture-child',
            'approver': 'fixture-parent', 'duration_seconds': 1800, 'custom_text': None, 'allow_soft': False}}}}
        stage = 'retained-request'
    else:
        observed, stage = {'ui': {'language_policy': policy}}, 'retained-policy'
    with pytest.raises(EvidenceError): current.check_settings(stage, observed)


@pytest.mark.parametrize('fault', ['', 'remove-result', 'retained-policy', 'blocked-after-reinstall',
                                  'purge-result', 'fresh-request', 'fresh-returned'])
def test_actual_continuous_worker_consumes_all_unique_stages_and_stops_on_failure(fault):
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_package_removal;')
    source = source.replace('onpc_desktop_session::run', 'onpc_package_removal::run')
    declarations = json.dumps(list(case.PLAN.invocations))
    challenges = json.dumps({name: list(binding) for name, binding in case.PLAN.challenges.items()})
    source = source.replace('}, $action);', '}, decode_json(q{' + declarations + '}), decode_json(q{' + challenges + '}));')
    replies = {stage: {'id': name, 'role': role, 'surface': 'gdm', 'check': check}
               for name, (role, first, second) in case.PLAN.challenges.items()
               for stage, check in ((first, 'qualified'), (second, 'rechecked'))}
    source = source.replace("push @events, ['stage', $_[0]];", """
        push @events, ['stage', $_[0]];
        die 'fixed refusal' if $_[0] eq $action;
        my $bindings = decode_json(q{REPLIES});
        return {observed => $_[0], challenge => $bindings->{$_[0]}} if exists $bindings->{$_[0]};
        return {observed => $_[0], ui_focused => 1} if $_[0] =~ /(?:greeter|list|opened)$/;
        return {observed => $_[0], station_destination => 'default-request-form'} if $_[0] =~ /station-branch$/;
    """.replace('REPLIES', json.dumps(replies)))
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault), result
    expected = list(case.PLAN.screen_tags)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    if not fault:
        assert result['events'].count(['secret']) == 1 + len(case.PLAN.challenges) + 1
        assert result['events'][-1] == ['power', 'off']
    assert not any(event[0] in ('pointer', 'click') for event in result['events'])


@pytest.mark.parametrize('missing', range(1, 4))
def test_later_reboot_refuses_if_any_prior_transition_was_not_observed(monkeypatch, missing):
    current = journey(monkeypatch)
    stage = case.PLAN.reboot_transitions[4][0]
    current.steps = list(case.PLAN.stages[:case.PLAN.stages.index(stage)])
    current.boot = 'b' * 64
    current.reboot_observed = True
    current.additional_reboots_observed = {1, 2, 3} - {missing}
    current.transport = Mock()
    with pytest.raises(EvidenceError, match='reboot-replay'):
        current.submit_reboot(Mock())
    current.transport.request_customer_reboot.assert_not_called()


def test_plan_refuses_more_than_five_reboots():
    with pytest.raises(EvidenceError, match='reboot-plan'):
        replace(case.PLAN, additional_reboot_transitions=case.PLAN.additional_reboot_transitions * 2)


@pytest.mark.parametrize('fault', ['order', 'installed', 'old-package'])
def test_invalid_lifecycle_composition_refuses_before_transfer(monkeypatch, fault):
    transfer = Mock()
    monkeypatch.setattr(lifecycle, 'AssetTransfer', transfer)
    context = SimpleNamespace(installed_snapshot='wrong' if fault == 'installed' else None,
        verified=SimpleNamespace(upgrade_inputs={} if fault == 'old-package' else None))
    operations = tuple(reversed(case.OPERATIONS)) if fault == 'order' else case.OPERATIONS
    with pytest.raises(EvidenceError):
        lifecycle.PackageLifecycleJourney(context, Mock(), case.PLAN, operations=operations)
    transfer.assert_not_called()


@pytest.mark.parametrize('minutes', [4, 5])
def test_finite_custom_daily_binding_has_matching_controller_and_keyboard_values(minutes):
    import accessible_ui
    assert accessible_ui.TEXT_VALUES['daily-' + str(minutes)] == ('parent-custom-daily-limit', str(minutes))
    assert accessible_ui.CUSTOM_ALLOWANCE_OPERATIONS['custom-' + str(minutes) + '-saved'] == (minutes, 'saved')
    assert case.PLAN.settings_checks['retained-parent-selected'].allowance == ('4 minutes',)


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('binding', command.LIFECYCLE)
@pytest.mark.parametrize('fault', ['', 'digest', 'phase', 'query', 'architecture'])
def test_guest_public_phase_rechecked_before_any_input(monkeypatch, package_format, binding, fault):
    import subprocess
    monkeypatch.setattr(command.session_control, 'package_format', lambda: package_format)
    monkeypatch.setattr(command.session_control, 'package_digest', lambda: 'wrong' if fault == 'digest' else DIGEST)
    installed = binding in (command.REMOVE, command.PURGE)
    if fault == 'phase': installed = not installed
    item = {'name': 'oh-no-parent-control', 'version': '0:1.3-1.fc44' if package_format == 'rpm' else '1.3',
            'architecture': 'x86_64' if package_format == 'rpm' else 'amd64', 'sha256': DIGEST}
    if package_format == 'rpm':
        rows = [item['name'], item['version'], 'aarch64' if fault == 'architecture' else 'x86_64']
        stdout = '\n'.join(rows) + '\n' if installed else 'package oh-no-parent-control is not installed\n'
        status = 0 if installed else 1
    else:
        stdout = ('install ok installed' if installed else 'deinstall ok config-files') + '\n' + item['version'] + '\n'
        status = 0
        if fault == 'architecture': stdout = 'malformed phase\n'
    run = Mock(return_value=SimpleNamespace(returncode=2 if fault == 'query' else status, stdout=stdout.encode()))
    monkeypatch.setattr(subprocess, 'run', run)
    failing = fault and not (fault == 'architecture' and package_format == 'rpm' and not installed)
    if failing:
        with pytest.raises(command.session_control.SessionError):
            command.guest_lifecycle_phase(binding, {'current': item})
    else:
        command.guest_lifecycle_phase(binding, {'current': item})
    if fault == 'digest': run.assert_not_called()
    elif package_format == 'rpm': assert run.call_args.kwargs['env']['LC_ALL'] == 'C'


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('binding', command.LIFECYCLE)
@pytest.mark.parametrize('refuse_phase', [False, True])
def test_guest_lifecycle_fixed_action_consumes_exclusive_marker_after_phase_guard(
        monkeypatch, tmp_path, package_format, binding, refuse_phase):
    import os
    import grp
    import pwd
    control = command.session_control
    monkeypatch.setattr(control, 'package_format', lambda: package_format)
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    monkeypatch.setattr(pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture'))
    monkeypatch.setattr(grp, 'getgrnam', lambda _: SimpleNamespace(gr_gid=27))
    monkeypatch.setattr(os, 'getgrouplist', lambda *_: [27])
    monkeypatch.setattr(control, 'sessions', lambda: {'7': props()})
    monkeypatch.setattr(control, 'package_digest', lambda: DIGEST)
    phase = Mock(side_effect=control.SessionError('package-phase') if refuse_phase else None)
    monkeypatch.setattr(command, 'guest_lifecycle_phase', phase)
    markers = {command.REMOVE: '.package-remove-used', command.PURGE: '.package-purge-used',
               command.REINSTALL: '.package-reinstall-used', command.FRESH_INSTALL: '.package-fresh-install-used'}
    marker = tmp_path / 'used'
    opening = os.open
    def consume(path, flags, mode):
        assert path == '/var/lib/onpc-e2e-assets/' + markers[binding]
        assert flags & os.O_EXCL and flags & os.O_NOFOLLOW and mode == 0o600
        return opening(marker, flags, mode)
    monkeypatch.setattr(os, 'open', consume)
    monkeypatch.setattr(os, 'environ', {})
    monkeypatch.setattr(os, 'dup2', Mock())
    execute = Mock()
    monkeypatch.setattr(os, 'execv', execute)
    if refuse_phase:
        with pytest.raises(control.SessionError, match='package-phase'):
            command.guest_submit(binding, DIGEST, {'current': {}})
        assert not marker.exists()
        execute.assert_not_called()
        return
    command.guest_submit(binding, DIGEST, {'current': {}})
    if binding == command.PURGE:
        expected = ('/usr/bin/oh-no-parent-control-purge', '--yes')
    elif package_format == 'rpm':
        expected = ('/usr/bin/dnf', '--quiet', 'remove' if binding == command.REMOVE else 'install', '-y',
                    'oh-no-parent-control' if binding == command.REMOVE else '/var/lib/onpc-e2e-assets/package.rpm')
    elif binding == command.REMOVE:
        expected = ('/usr/bin/apt-get', '-o', 'DPkg::Lock::Timeout=120', 'remove', '-y', 'oh-no-parent-control')
    else:
        expected = command.ARGV
    execute.assert_called_once_with(expected[0], expected)
    with pytest.raises(FileExistsError):
        command.guest_submit(binding, DIGEST, {'current': {}})
    assert execute.call_count == 1


@pytest.mark.parametrize('fault', ['', 'successful-exec', 'wrong-error', 'window', 'output-bound'])
def test_blocked_app_requires_real_permission_failure_and_complete_window_absence(monkeypatch, fault):
    import accessible_ui
    from tests.support.accessible_ui import Node, ui_for
    ui = ui_for(Node('fixture'))
    monkeypatch.setattr(accessible_ui, 'require_active_launch_session', Mock())
    ui.desktop_result = Mock()
    ui.handle_system_prompt = Mock()
    ui.native_app_closed = Mock(side_effect=[True, fault != 'window'])
    run = Mock(return_value=SimpleNamespace(returncode=0 if fault == 'successful-exec' else 203,
        stdout=b'x' * 65537 if fault == 'output-bound' else b'',
        stderr=b'No such file or directory' if fault == 'wrong-error' else b'Failed to execute: Permission denied'))
    monkeypatch.setattr(accessible_ui.subprocess, 'run', run)
    ticks = iter((0, 3))
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: next(ticks))
    ui.wait = lambda predicate, *_args, **_kwargs: predicate()
    if fault:
        with pytest.raises(accessible_ui.UiError): ui.native_launch_command(blocked=True)
    else:
        ui.native_launch_command(blocked=True)
        assert '--wait' in run.call_args.args[0] and '--pipe' in run.call_args.args[0]
    assert run.call_count == 1
