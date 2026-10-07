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
from tests.support.e2e_evidence import attempt
from tests.support.e2e_recording import session


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
    from native_fixtures import fixture_actions
    current = lifecycle.PackageLifecycleJourney(context, Mock(), case.PLAN,
        operations=case.OPERATIONS, checks=case.CHECKS, actions=fixture_actions(include_refusal=False))
    transfer.provision.assert_called_once_with(context.lease, context.guestfs)
    return current


def test_continuous_case_keeps_its_complete_hour_budget(monkeypatch):
    import e2e_worker
    record = Mock()
    monkeypatch.setattr(lifecycle, 'record_installed_journey', record)
    recorder, context = Mock(), Mock()

    case.execute(recorder, context)

    record.assert_called_once()
    assert record.call_args.args == (recorder, context, case.PLAN)
    assert record.call_args.kwargs['timeout'] == 3600
    journey_type = record.call_args.kwargs['journey_type']
    assert journey_type.func is lifecycle.PackageLifecycleJourney
    assert journey_type.keywords == {'operations': case.OPERATIONS, 'checks': case.CHECKS}
    assert record.call_args.kwargs['timeout'] <= e2e_worker.MAX_TIMEOUT_SECONDS


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


@pytest.mark.parametrize('binding', [command.BINDING, command.REMOVE,
                                     command.REINSTALL, command.FRESH_INSTALL])
@pytest.mark.parametrize('fault', ['', 'missing-completion', 'missing-notice', 'trailing-product',
    'wrong-package', 'wrong-version', 'wrong-scriptlet', 'unfinished', 'duplicate',
    'unframed', 'foreign-output', 'status', 'installed-version'])
def test_fedora_reads_exact_product_scriptlet_before_dnf_footer(monkeypatch, binding, fault):
    item = boundary(monkeypatch)
    item.verified.asset_files = {'package.rpm': DIGEST}
    package = {'name': 'oh-no-parent-control', 'version': '0:1.3-0.1.dev.fc44',
               'architecture': 'x86_64', 'sha256': DIGEST}
    item.package_identities = Mock(return_value={'current': package})
    removing = binding == command.REMOVE
    item.read_identity = Mock(return_value=identity('wrong' if fault == 'installed-version'
        else None if removing else package['version']))
    scriptlet = '%postun' if removing else '%posttrans'
    label = scriptlet + ' scriptlet: oh-no-parent-control-0:1.3-0.1.dev.fc44.x86_64'
    if fault == 'wrong-package': label = label.replace('oh-no-parent-control-', 'another-package-')
    if fault == 'wrong-version': label = label.replace('1.3-', '1.2-')
    if fault == 'wrong-scriptlet': label = label.replace(scriptlet, '%pretrans')
    notice = command.REMOVAL_NOTICE if removing else command.NOTICE
    output = ([] if removing else [command.COMPLETE]) + [notice]
    if fault == 'missing-completion' and not removing: output.remove(command.COMPLETE)
    if fault == 'missing-notice': output.remove(notice)
    if fault == 'trailing-product': output.append('later product diagnostic')
    lines = ['Transaction Summary:', ' Installing: 1 package',
             '>>> Running ' + label, '>>> Finished ' + label, '>>> Scriptlet output:',
             *('>>> ' + line for line in output), '>>> ',
             'Warning: skipped OpenPGP checks for 1 package from repository: @commandline']
    if fault == 'unfinished': lines.remove('>>> Finished ' + label)
    if fault == 'duplicate': lines += lines[2:]
    if fault == 'unframed': lines = output
    if fault == 'foreign-output':
        # Another package's valid-looking messages cannot complete our callback.
        lines = lines[:5] + ['>>> unrelated product output', '>>> Running %posttrans scriptlet: other-1.x86_64',
            '>>> Finished %posttrans scriptlet: other-1.x86_64', '>>> Scriptlet output:',
            *('>>> ' + line for line in output), '>>> ']
    item.binding = binding
    item.receipt = (('\n'.join(lines) + '\n').encode(), 1 if fault == 'status' else 0)
    failing = fault and not (fault == 'missing-completion' and removing)
    if failing:
        with pytest.raises(EvidenceError): item.read_result()
    else:
        result = item.read_result()
        assert result['notice'] == notice
        assert result['completion'] == (None if removing else command.COMPLETE)
        item.read_identity.assert_called_once()


def test_fedora_purge_reads_packaged_command_final_notice(monkeypatch):
    item = boundary(monkeypatch)
    item.verified.asset_files = {'package.rpm': DIGEST}
    item.binding = command.PURGE
    item.read_identity = Mock(return_value=identity(None))
    item.receipt = (('DNF transaction progress\n' + command.PURGE_COMPLETE + '\n' +
                     command.REMOVAL_NOTICE + '\n').encode(), 0)
    assert item.read_result()['completion'] == command.PURGE_COMPLETE
    item.read_identity.assert_called_once()


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


@pytest.mark.parametrize('binding', [command.REMOVE, command.PURGE])
@pytest.mark.parametrize('removed_account', ['oh-no-parent-control', 'onpc-kiosk'])
def test_removal_exempts_only_the_package_owned_account(monkeypatch, binding, removed_account):
    current = journey(monkeypatch)
    before, after = identity('1.3'), identity(None)
    before['preserved']['accounts']['1006'] = {
        'identity': [removed_account, 1006], 'groups': [1006], 'language': ''}
    current.commands[binding] = Mock(
        read_result=Mock(return_value={'operation': binding, 'outcome': 'passed'}),
        read_identity=Mock(side_effect=[after, deepcopy(after)]),
        package_identities=Mock(return_value={'current': {'version': '1.3'}}))
    current.entries[binding] = before
    stage = next(result for _, operation, result in case.OPERATIONS if operation == binding)
    if removed_account == 'oh-no-parent-control':
        current.check_settings(stage, {})
        assert binding in current.results
    else:
        with pytest.raises(EvidenceError, match='personal-state-changed'):
            current.check_settings(stage, {})
        assert binding not in current.results


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


@pytest.mark.parametrize('fault', ['', 'retained-five', 'reapplied-four'])
def test_continuous_history_retains_four_minutes_before_reapplying_five(monkeypatch, fault):
    current = journey(monkeypatch)
    policy = {'settings': {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['4 minutes']},
              'rows': [[case.MATCH_APP, 'permanent', 'precise']],
              'balances': {'daily': 240, 'one_time': 0, 'total': 240}}
    current.check_settings('initial-policy', {'ui': {'language_policy': deepcopy(policy)}})
    if fault == 'retained-five':
        policy['settings']['allowance'] = ['5 minutes']
        with pytest.raises(EvidenceError):
            current.check_settings('retained-policy', {'ui': {'language_policy': policy}})
        return
    current.check_settings('retained-policy', {'ui': {'language_policy': deepcopy(policy)}})
    policy['settings']['allowance'] = ['4 minutes' if fault == 'reapplied-four' else '5 minutes']
    if fault:
        with pytest.raises(EvidenceError):
            current.check_settings('reapply-policy', {'ui': {'language_policy': policy}})
    else:
        current.check_settings('reapply-policy', {'ui': {'language_policy': policy}})
    stages = list(case.PLAN.screen_tags)
    assert (stages.index('initial-allowance-saved') < stages.index('retained-policy')
            < stages.index('reapply-allowance-saved') < stages.index('reapply-policy'))


@pytest.mark.parametrize('fault', ['', 'overlay-approver', 'overlay-choices', 'remove-result', 'retained-accounts', 'retained-policy', 'blocked-after-reinstall',
                                  'purge-result', 'fresh-request', 'fresh-returned'])
def test_actual_continuous_worker_consumes_all_unique_stages_and_stops_on_failure(fault):
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_lifecycle;')
    source = source.replace('onpc_desktop_session::run', 'onpc_lifecycle::run_removal')
    source = source.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]]; }")
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
    titles = [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown']
    assert titles == [case.PLAN.prefix + '-' + stage for stage in stages]
    if not fault:
        assert result['events'].count(['secret']) == 1 + len(case.PLAN.challenges) + 1
        assert [event for event in result['events'] if event[0] != 'title'][-1] == ['power', 'off']
        assert [event[1] for event in result['events']
                if event[0] == 'text' and event[1] in ('4', '5')] == []
        assert all(stage in stages for stage in (
            'initial-allowance-text-selected', 'initial-allowance-text-read',
            'reapply-allowance-text-selected', 'reapply-allowance-text-read'))
    assert not any(event[0] in ('pointer', 'click') for event in result['events'])


def test_continuous_case_selects_overlay_local_approver_before_shared_choice_comparison():
    stages = list(case.PLAN.screen_tags)
    assert case.PLAN.screen_tags['overlay-approver'] == 'ui:overlay-flow-approver-select'
    assert stages.index('overlay-launch') + 1 == stages.index('overlay-approver')
    assert stages.index('overlay-approver') + 1 == stages.index('overlay-choices')
    assert case.SAVED_CHOICES == dict(child='fixture-child', approver='fixture-parent',
        duration_seconds=75, allow_soft=True, custom_text='1.25')


@pytest.mark.parametrize('fault', ['', 'missing-baseline', 'policy', 'rows', 'grant', 'choices', 'replay'])
def test_shared_checks_accept_renamed_endpoints_and_freeze_independent_values(monkeypatch, fault):
    from journey_checks import policy_projection, request_choices
    current = journey(monkeypatch)
    settings = {'child': 'independent-child', 'limit_enabled': True, 'allowance': ['9 minutes']}
    choices = {'child': 'independent-child', 'approver': 'independent-parent',
               'duration_seconds': 90, 'custom_text': '1.5', 'allow_soft': False}
    current.checks = {
        'source-policy': policy_projection(settings, row=('independent-app', 'permanent'), capture='independent-policy'),
        'source-request': request_choices(choices, capture='independent-request'),
        'later-policy': policy_projection(settings, row=('independent-app', 'permanent'),
                                         same='independent-policy', grant='zero'),
        'later-request': request_choices(choices, same='independent-request'),
    }
    policy = {'settings': deepcopy(settings), 'rows': [['independent-app', 'permanent', 'precise']],
              'balances': {'daily': 540, 'one_time': 0, 'total': 540}}
    request = {'ui': {'valid_choice': {'request': {**choices, 'surface': 'child-overlay'}}}}
    if fault != 'missing-baseline':
        current.check_settings('source-policy', {'ui': {'language_policy': policy}})
        current.check_settings('source-request', request)
        policy['settings']['allowance'] = ['changed after capture']
        request['ui']['valid_choice']['request']['approver'] = 'changed after capture'
    later = {'settings': deepcopy(settings), 'rows': [['independent-app', 'permanent', 'precise']],
             'balances': {'daily': 501, 'one_time': 0, 'total': 501}}
    request = {'ui': {'valid_choice': {'request': {**choices, 'surface': 'kiosk'}}}}
    if fault == 'policy': later['settings']['limit_enabled'] = False
    if fault == 'rows': later['rows'][0][1] = 'allowed'
    if fault == 'grant': later['balances']['one_time'] = 90
    if fault == 'choices': request['ui']['valid_choice']['request']['duration_seconds'] = 1800
    if fault == 'replay':
        current.check_settings('later-policy', {'ui': {'language_policy': later}})
    if fault:
        with pytest.raises(EvidenceError):
            current.check_settings('later-request' if fault == 'choices' else 'later-policy',
                request if fault == 'choices' else {'ui': {'language_policy': later}})
    else:
        current.check_settings('later-policy', {'ui': {'language_policy': later}})
        current.check_settings('later-request', request)


@pytest.mark.parametrize('fault', ['', 'renamed-child-picker-opened', 'renamed-child-choice-highlighted',
                                  'renamed-parent-selected', 'independent-text-focus', 'independent-text-read',
                                  'independent-saved', 'invalid-prefix', 'invalid-value'])
def test_shared_management_and_allowance_accept_independent_prefixes_and_stop_input(fault):
    source = RUN_PROBE[:RUN_PROBE.index('require onpc_desktop_session;')] + r'''
require onpc_journey;
require onpc_parent;
require onpc_allowance_boundaries;
my $journey = onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {
    push @events, ['stage', $_[0]];
    die 'fixed refusal' if $_[0] eq $action;
    return {observed => $_[0], ui_focused => 1};
});
my $ok = eval {
    onpc_parent::named_management($journey, $action eq 'invalid-prefix' ? '../unsafe' : 'renamed', 'child');
    onpc_allowance_boundaries::custom_value($journey, 'independent', $action eq 'invalid-value' ? 99999 : 5);
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''
    result = json.loads(run_perl(source, fault).stdout)
    expected = [['stage', 'renamed-parent-command'], ['stage', 'renamed-parent-window'],
                ['stage', 'renamed-child-picker-opened'], ['stage', 'renamed-child-choice-highlighted'],
                ['stage', 'renamed-parent-selected'], ['stage', 'independent-open'],
                ['stage', 'independent-text-focus'], ['stage', 'independent-text-selected'],
                ['stage', 'independent-text-read'], ['stage', 'independent-saved']]
    assert bool(result['ok']) == (not fault), result
    if fault == 'invalid-prefix': expected = []
    elif fault == 'invalid-value': expected = expected[:5]
    elif fault: expected = expected[:expected.index(['stage', fault]) + 1]
    assert result['events'] == expected


def test_shared_scope_preserves_input_callback_and_independent_consumption():
    source = RUN_PROBE[:RUN_PROBE.index('require onpc_desktop_session;')] + r'''
require onpc_journey;
my $journey = onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {
    push @events, ['stage', $_[0]];
    die 'scope:transport' unless @_ == 3 && !defined($_[1]) && ref($_[2]) eq 'CODE';
    $_[2]->();
    return {observed => $_[0]};
});
my $section = $journey->scope('renamed');
my $reply = $section->seen('input', sub { push @events, ['single-input']; });
$section->consume_observation('input', $reply);
my $replay = eval { $section->consume_observation('input', $reply); 1; };
print encode_json({prefix => $section->{prefix}, replay => $replay ? 1 : 0, events => \@events});
'''
    result = json.loads(run_perl(source, '').stdout)
    assert result == {'prefix': 'independent-renamed', 'replay': 0,
                      'events': [['stage', 'renamed-input'], ['single-input']]}


@pytest.mark.parametrize('role', ['parent', 'child'])
@pytest.mark.parametrize('fault', ['', 'role', 'prefix', 'focused', 'recipient', 'rechecked', 'desktop'])
def test_shared_named_login_binds_role_and_fresh_challenge_before_secret(role, fault):
    from journey_blocks import fresh_desktop, prefixed_stages
    stages = list(prefixed_stages('independent', fresh_desktop(role)))
    first, second = stages[2:4]
    fail_at = {'focused': stages[1], 'recipient': first, 'rechecked': second, 'desktop': stages[-1]}.get(fault, '')
    source = RUN_PROBE[:RUN_PROBE.index('require onpc_desktop_session;')] + r'''
require onpc_journey;
require onpc_gdm;
my $replies = decode_json(q{REPLIES});
my $journey = onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {
    push @events, ['stage', $_[0]];
    die 'fixed refusal' if $_[0] eq q{FAIL};
    return $replies->{$_[0]};
});
$journey->declare_invocations(decode_json(q{STAGES}));
$journey->declare_challenges(decode_json(q{CHALLENGES}));
my $ok = eval { onpc_gdm::named_login($journey, q{PREFIX}, q{ROLE}); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''
    replies = {stage: {'observed': stage, 'ui_focused': True} for stage in stages}
    for stage, check in ((first, 'qualified'), (second, 'rechecked')):
        replies[stage] = {'observed': stage, 'challenge': {
            'id': 'independent', 'role': role, 'surface': 'gdm', 'check': check}}
    source = (source.replace('REPLIES', json.dumps(replies)).replace('FAIL', fail_at)
        .replace('STAGES', json.dumps(stages)).replace('CHALLENGES', json.dumps({'independent': [role, first, second]}))
        .replace('PREFIX', '../unsafe' if fault == 'prefix' else 'independent')
        .replace('ROLE', ('child' if role == 'parent' else 'parent') if fault == 'role' else role))
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault), result
    observed = [event[1] for event in result['events'] if event[0] == 'stage']
    assert observed == ([] if fault in ('prefix', 'role') else
                        stages[:stages.index(fail_at) + 1] if fail_at else stages)
    assert result['events'].count(['secret']) == (1 if fault in ('', 'desktop') else 0)


@pytest.mark.parametrize('fault', ['', 'meaning', 'durability'])
def test_lifecycle_recorder_constructs_shared_journey_and_checks_before_reply(session, tmp_path, monkeypatch, fault):
    from installed_journey import JourneyPlan
    from journey_checks import access_choice
    import session_control
    expected = session.payload['assertions'][0]
    tags = {'entry-start': 'system:parent-command-context', 'entry-one': 'system:parent-command-context',
            'entry-two': 'system:parent-command-context',
            **{stage: 'system:parent-command-context' for submitted, _, result in case.OPERATIONS
               for stage in (submitted, result)}, 'public-row': 'ui:access-row'}
    plan = JourneyPlan(prefix='independent-lifecycle', worker_mode='package_removal', screen_tags=tags,
        phases={'ready': 'setup', 'setup-detached': 'setup', **{stage: expected['step_id'] for stage in tags},
                'entry-start': 'start', 'entry-one': 'step-1', 'entry-two': 'step-2'},
        stage_actions={submitted: 'package-' + binding for submitted, binding, _ in case.OPERATIONS},
        assertions_after={'public-row': expected['assertion_id']})
    context = SimpleNamespace(directory=tmp_path / 'journey', installed_snapshot=None,
        verified=SimpleNamespace(inputs={}, upgrade_inputs=None), credentials=Mock(), lease=Mock(),
        guestfs=Mock(), commands=Mock())
    context.directory.mkdir()
    monkeypatch.setattr(lifecycle, 'AssetTransfer', Mock())
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={'outcome': 'passed'}))
    monkeypatch.setattr(lifecycle.PackageLifecycleJourney, 'validate', lambda _: [])
    recorder = session.recorder
    recorder.begin_case('E2E-001/gdm-observation')
    real_save = session.collector.save_report
    def save(name, report):
        if fault == 'durability' and report.get('event') == 'observation' and report.get('active_step') == expected['step_id']:
            raise OSError('storage failed')
        return real_save(name, report)
    monkeypatch.setattr(session.collector, 'save_report', save)
    checks = {'public-row': access_choice('independent-app', 'permanent')}
    def worker(**options):
        current = options['guarded_observe'].__self__
        assert type(current) is lifecycle.PackageLifecycleJourney and current.plan is plan
        assert current.operations == case.OPERATIONS and current.checks == checks
        current.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
        current.boot = 'a' * 64
        current.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': current.boot}))
        current.transport = Mock()
        current.ui = SimpleNamespace(boot_proof=current.boot, observe=Mock(return_value={
            'outcome': 'passed', 'access': {'app': 'independent-app',
            'choice': 'allowed' if fault == 'meaning' else 'permanent'}}))
        for stage in ('entry-start', 'entry-one', 'entry-two', 'public-row'):
            # This isolates recorder construction and check ordering; command
            # execution/order have their independent complete-worker tests above.
            if stage == 'public-row':
                current.steps = [{'stage': item} for item in plan.stages[:-1]]
            (context.directory / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
            options['guarded_observe'](Mock())
            assert (context.directory / (stage + '.reply.json')).exists()
        for assertion in session.payload['assertions'][1:]:
            ref = recorder.artifact('synthetic-' + assertion['assertion_id'],
                {'visible': 'screen', 'backend': 'backend', 'other_user': 'other-user'}[assertion['kind']],
                b'explicit synthetic result', reviewed=True)
            recorder.assertion(assertion['assertion_id'], artifact_ids=[ref])
        return dict(outcome='passed', shutdown_verified=True, worker_stopped=True, callback_closed=True)
    context.run_worker = worker
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            lifecycle.record_lifecycle_journey(recorder, context, plan, operations=case.OPERATIONS, checks=checks)
        assert not (context.directory / 'public-row.reply.json').exists()
    else:
        lifecycle.record_lifecycle_journey(recorder, context, plan, operations=case.OPERATIONS, checks=checks)
    assert recorder._active is None


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


def test_removed_and_purged_logins_require_station_absence_before_reinstall():
    for prefix, role in case.ROLES.items():
        product_free = prefix in ('removed', 'healthy-child', 'reinstall-parent', 'purged')
        operation = 'gdm-product-free-' if product_free else 'gdm-'
        assert case.PLAN.screen_tags[prefix + '-installed-greeter'] == (
            'ui:' + operation + ('child-list' if role == 'child' else 'list'))
    # A password challenge or unrelated greeter observation cannot complete
    # any lifecycle reboot, even when its stage is adjacent to the request.
    tags = dict(case.PLAN.screen_tags)
    tags['removed-installed-greeter'] = 'ui:gdm-parent-recipient'
    with pytest.raises(EvidenceError, match='reboot-plan'):
        replace(case.PLAN, screen_tags=tags)


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
        expected = ('/usr/bin/dnf', '--quiet', 'remove', '--no-autoremove', '-y',
                    'oh-no-parent-control') if binding == command.REMOVE else (
                    '/usr/bin/dnf', '--quiet', 'install', '-y',
                    '/var/lib/onpc-e2e-assets/package.rpm')
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
    # The denial adapter may query this launch's journal after stderr fails
    # qualification. That read is separate from the single launch submission.
    journal = Mock(return_value={'status': 'read', 'exec_errors': []})
    monkeypatch.setattr(accessible_ui, 'native_execution_journal_diagnostic', journal)
    ticks = iter((0, 3))
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: next(ticks))
    ui.wait = lambda predicate, *_args, **_kwargs: predicate()
    if fault:
        with pytest.raises(accessible_ui.UiError): ui.native_launch_command(blocked=True)
    else:
        ui.native_launch_command(blocked=True)
        assert '--wait' in run.call_args.args[0] and '--pipe' in run.call_args.args[0]
    assert run.call_count == 1
    assert journal.call_count == (1 if fault in ('successful-exec', 'wrong-error', 'output-bound') else 0)
