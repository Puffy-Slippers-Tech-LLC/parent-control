"""Private request/policy/transport doubles and waited Perl; no live resources.

No host accounts, VM, bus, display or shared filesystem mutation. Existing
recorder fixtures allocate private retained/scratch paths and own teardown.
Compatible in unit and cleanup inventories.
"""
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import accessible_ui as public
import e2e_worker
import installed_journey
import language_composition as shared
import language_persistence as case
import session_control
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import WORKER
from tests.support.e2e_evidence import attempt
from tests.support.e2e_recording import session
from tests.support.perl import run_perl
from ui_observations import OPERATION_LABELS, UiObservations


def policy(child='riley', language='en', elapsed=0):
    chinese = language == 'zh-Hans'
    identity = 'fixture-child' if child == 'riley' else 'existing-fixture-child'
    row = 'parent-app-' + 'a' * 16
    value = dict(child=identity, account_name=public.CHILD if child == 'riley' else public.EXISTING_CHILD,
        limit_enabled=True, allowance_minutes=60, chooser_absent=True,
        management='限制屏幕时间' if chinese else 'Screen time limit',
        management_labels=list(case.LABELS[language]), rows=[[row, 'allowed', 'precise']],
        app_names=[[row, 'Fixture application']],
        balances=dict(child=identity, expanded=True, observed_monotonic_ns=(100 + elapsed) * 10**9))
    for key, seconds in (('daily', 3600 - elapsed), ('one_time', 0), ('total', 3600 - elapsed)):
        value['balances'][key] = dict(seconds=seconds, precision_seconds=1, text='public duration')
    return value


def expected_form(stage='direct-form'):
    return deepcopy(case.CHECKS[stage].keywords['expected'])


@pytest.mark.parametrize('operation,account_name', [
    *((operation, public.CHILD_ACCOUNTS[public.CHILD] if binding[0] else 'oh-no-parent-control')
      for operation, binding in public.LANGUAGE_HISTORY_REQUESTS.items()),
    *((operation, 'oh-no-parent-control') for operation, (binding, _) in public.TEXT_OPERATIONS.items()
      if binding == 'jordan-kiosk-fraction'),
])
def test_history_observer_enters_owning_account_before_any_ui(monkeypatch, operation, account_name):
    monkeypatch.setattr(public.sys, 'argv', ['observer', operation, '1.1'])
    monkeypatch.setattr(public.os, 'geteuid', lambda: 0)
    account = SimpleNamespace(pw_name=account_name, pw_uid=1234)
    lookup = Mock(return_value=account)
    monkeypatch.setattr(public.pwd, 'getpwnam', lookup)
    environment = public.observation_environment
    desktop = Mock(return_value={'desktop': 'child-session'})
    monkeypatch.setattr(public, 'session_environment', desktop)

    def stop_before_privilege_change(selected, selected_operation):
        assert selected is account and selected_operation == operation
        if account_name == 'oh-no-parent-control':
            assert environment(selected, operation) == {
                'XDG_RUNTIME_DIR': '/run/user/1234',
                'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1234/bus'}
            desktop.assert_not_called()
        else:
            assert environment(selected, operation) == {'desktop': 'child-session'}
            desktop.assert_called_once_with(account)
        raise LookupError('stop before privilege change')

    monkeypatch.setattr(public, 'observation_environment', stop_before_privilege_change)
    with pytest.raises(LookupError, match='stop before privilege change'):
        public.main()
    lookup.assert_called_once_with(account_name)


def test_complete_operation_and_worker_bundle_registration():
    assert len(case.SCREENS) == sum(map(len, (case.SETUP, case.PARENT, case.STATION, case.OVERLAY, case.FINAL)))
    for stage, tag in case.SCREENS.items():
        if tag.startswith('ui:'):
            assert tag[3:] in public.OPERATIONS and tag[3:] in OPERATION_LABELS
        else:
            assert tag[7:] in session_control.BINDINGS
    bundle = e2e_worker.distribution_inputs()
    assert b'language_persistence' in bundle['tests/smoke.pm']
    assert b'sub run' in bundle['lib/onpc_language_persistence.pm']
    assert case.PLAN.stage_actions == {'offline-enter': 'language-offline', 'offline-restore': 'language-online'}
    # Every public preservation endpoint is checked, including nondefault UID
    # and independent Parent / request / overlay meanings.
    assert set(case.FORM_STAGES) <= set(case.CHECKS)
    for stages, prefix in ((case.PARENT, 'parent-'), (case.FINAL, 'final-')):
        for stage, tag in stages.items():
            if stage.endswith('-selected'):
                assert tag in public.PARENT_LANGUAGE_SELECTIONS or tag[3:] in public.PARENT_LANGUAGE_SELECTIONS


@pytest.mark.parametrize('fault', ['', *case.SCREENS])
def test_real_worker_sequence_titles_and_terminal_refusal(monkeypatch, fault):
    if fault:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', fault)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_language_persistence')
    worker = worker.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]] }")
    worker = worker.replace("$stage eq 'station-branch'", "$stage =~ /station-branch$/")
    worker = worker.replace("destination => 'default-request-form'",
        "destination => $stage =~ /^(initial|renewed)-/ ? 'initial-request-window' : 'default-request-form'")
    worker = worker.replace('sub type_password', "sub type_string { push @main::events, ['text'] }\nsub type_password")
    worker = worker.replace('picker-opened)', 'picker-opened|ready)')
    proofs = {stage: (identity, role, check)
        for identity, (role, first, second) in case.PLAN.challenges.items()
        for stage, check in ((first, 'qualified'), (second, 'rechecked'))}
    perl_proofs = '{' + ', '.join(json.dumps(key) + ' => ' + json.dumps(list(value))
                                for key, value in proofs.items()) + '}'
    worker = worker.replace('return {observed => $stage};', '''
        my $proofs = ''' + perl_proofs + ''';
        if (exists $proofs->{$stage}) {
            my ($id, $role, $check) = @{$proofs->{$stage}};
            return {observed => $stage, challenge => {id => $id, role => $role,
                surface => 'gdm', check => $check}};
        }
        return {observed => $stage};''')
    challenges = '{' + ', '.join(json.dumps(key) + ' => ' + json.dumps(list(value))
                                for key, value in case.PLAN.challenges.items()) + '}'
    worker = worker.replace('    });', '    }, ' + json.dumps(list(case.PLAN.invocations)) + ', ' + challenges + ');')
    result = json.loads(run_perl(worker).stdout)
    stages = list(case.SCREENS)
    expected = stages if not fault else stages[:stages.index(fault) + 1]
    assert bool(result['ok']) == (not fault), (result['error'], result['events'][-8:])
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown'] == [
        case.PLAN.prefix + '-' + stage for stage in expected]
    assert (['power', 'off'] in result['events']) == (not fault)
    if fault:
        # A failed rendezvous emits no further input, including secrets.
        last = max(index for index, event in enumerate(result['events']) if event[0] == 'stage')
        assert not any(event[0] in ('key', 'secret', 'text') for event in result['events'][last + 1:])


@pytest.mark.parametrize('stage,fault', [('riley-before', ''), ('jordan-before', ''),
    ('riley-online-final', ''), ('riley-online-final', 'policy'), ('riley-online-final', 'grant'),
    ('riley-online-final', 'elapsed'), ('direct-form', ''), ('direct-form', 'text'),
    ('direct-form', 'request'), ('direct-form', 'storage'), ('direct-form', 'replay')])
def test_real_recorder_step_checks_before_durable_reply(tmp_path, stage, fault):
    journey = shared.language_journey(checks=case.CHECKS)(SimpleNamespace(directory=tmp_path), Mock(), case.PLAN,
                                                      actions=shared.offline_language_actions())
    journey.boot = 'a' * 64
    journey.steps = [{'stage': s} for s in case.PLAN.stages[:case.PLAN.stages.index(stage)]]
    key = 'language_form' if stage == 'direct-form' else 'language_state'
    value = expected_form() if key == 'language_form' else policy(
        'jordan' if stage == 'jordan-before' else 'riley', 'zh-Hans' if 'final' in stage else 'en',
        elapsed=2500 if fault == 'elapsed' else 50 if 'final' in stage else 0)
    if 'final' in stage:
        case.CHECKS['riley-before'](journey, {'ui': {'language_state': policy()}})
    if fault == 'policy': value['rows'][0][1] = 'permanent'
    if fault == 'grant': value['balances']['one_time']['seconds'] = 1
    if fault == 'text': value['labels']['kiosk-request-submit'] = 'wrong'
    if fault == 'request': value['request']['approver'] = 'fixture-parent'
    if fault == 'storage': journey.progress.side_effect = OSError('storage failed')
    if fault == 'replay': journey.checked_stages.add(stage)
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={key: value}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).is_file()
        if stage.endswith('-before'):
            value['rows'][0][1] = 'permanent'
            assert journey.public_captures['jordan' if stage == 'jordan-before' else 'riley'][0]['rows'][0][1] == 'allowed'


@pytest.mark.parametrize('stage', ['direct-form', 'jordan-german', 'riley-casey'])
@pytest.mark.parametrize('fault', ['', 'child', 'surface', 'duration', 'soft', 'extra', 'text',
                                   'late-diagnostic', 'missing-reply', 'replayed-reply'])
def test_real_decoder_preserves_complete_request_shape_and_terminal_failure(stage, fault):
    value = expected_form(stage)
    if fault == 'child': value['request']['child'] = 'wrong-child'
    if fault == 'surface': value['request']['surface'] = 'wrong'
    if fault == 'duration': value['request']['duration_seconds'] = 1800
    if fault == 'soft': value['request']['allow_soft'] = False
    if fault == 'extra': value['extra'] = True
    if fault == 'text': value['texts']['kiosk-request-submit'] = 'x' * 513
    operation = case.SCREENS[stage][3:]
    payload = dict(operation=operation, outcome='passed', interface='AT-SPI', language_form=value)
    raw = json.dumps(payload, ensure_ascii=False).encode()
    diagnostic = {'event': 'kiosk-form-observation', 'phase': 'public-tree', 'status': 'reading',
        'elapsed_ms': 0, 'tree': 'unread', 'public_ids': {}, 'tree_reads': 0,
        'nodes_read': 0, 'incomplete_reads': 0, 'query_errors': 0}
    progress = (json.dumps(diagnostic, sort_keys=True) + '\n').encode()
    def deliver(*args, **kwargs):
        stream = progress + (b'' if fault == 'missing-reply' else raw + b'\n')
        if fault == 'late-diagnostic': stream += progress
        if fault == 'replayed-reply': stream += raw + b'\n'
        if kwargs.get('on_output') is not None:
            for index in range(0, len(stream), 37): kwargs['on_output'](stream[index:index + 37])
        return stream
    transport = SimpleNamespace(call=Mock(side_effect=deliver), commands=SimpleNamespace(progress=None))
    observer = UiObservations(transport)
    if fault:
        with pytest.raises(EvidenceError): observer.observe(operation)
        with pytest.raises(EvidenceError, match='previous-failure'): observer.observe(operation)
        transport.call.assert_called_once()
    else:
        assert observer.observe(operation) == payload


@pytest.mark.parametrize('stage,child,language', [
    ('offline-enter', 'jordan', 'en'), ('offline-restore', 'riley', 'zh-Hans')])
@pytest.mark.parametrize('fault', ['', 'policy', 'observation'])
def test_connectivity_boundary_checks_public_policy_before_action(
        tmp_path, monkeypatch, stage, child, language, fault):
    action = Mock(return_value={'connectivity': 'independently confirmed'})
    actions = {name: Mock() for name in case.PLAN.stage_actions.values()}
    actions[case.PLAN.stage_actions[stage]] = action
    journey = shared.language_journey(checks=case.CHECKS)(
        SimpleNamespace(directory=tmp_path), Mock(), case.PLAN,
        actions=actions)
    journey.boot = 'a' * 64
    journey.steps = [{'stage': s} for s in case.PLAN.stages[:case.PLAN.stages.index(stage)]]
    case.CHECKS[child + '-before'](journey, {'ui': {'language_state': policy(child)}})
    value = policy(child, language, elapsed=50)
    if fault == 'policy':
        value['rows'][0][1] = 'permanent'
    journey.ui = SimpleNamespace(boot_proof=journey.boot,
        observe=Mock(return_value={'language_state': value},
                     side_effect=EvidenceError('public observation refused') if fault == 'observation' else None))
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
    # Installed language histories do not transfer a FIX04 installer. The old
    # package-command context therefore cannot serve as their connectivity entry.
    package_context = Mock(side_effect=FileNotFoundError('no staged installer'))
    monkeypatch.setattr(session_control, 'observe', package_context)
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError):
            journey.step(Mock())
        action.assert_not_called()
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        action.assert_called_once()
        assert journey.steps[-1]['fixture'] == {'connectivity': 'independently confirmed'}
        assert (tmp_path / (stage + '.reply.json')).exists()
    journey.ui.observe.assert_called_once_with(
        'parent-language-' + child + '-enabled-' + language.lower())
    package_context.assert_not_called()


@pytest.mark.parametrize('operation', ['language-history-jordan-restored', 'language-history-riley-restored',
    'language-history-riley-casey-select', 'language-history-jordan-jamie-select'])
@pytest.mark.parametrize('fault', ['', 'ownership'])
def test_request_alias_carries_nondefault_identity_language_and_values(operation, fault):
    ui = ui_for(Node(identity='kiosk-request-window'))
    ui.language_save_completed = Mock(side_effect=public.UiError('ownership') if fault else None)
    ui.select_kiosk_account = Mock(return_value={'result': 'declared'})
    overlay, child, language, approver, action = public.LANGUAGE_HISTORY_REQUESTS[operation]
    if fault:
        with pytest.raises(public.UiError): ui.language_history_request(operation)
        ui.select_kiosk_account.assert_not_called()
        assert ui.input_uncertain
    else:
        assert ui.language_history_request(operation) == {'request': {'result': 'declared'}}
        options = ui.select_kiosk_account.call_args.kwargs
        assert options['child'] == child and options['language'] == language
        assert options['duration_seconds'] == 75 and options['custom_text'] == '1.25'
        assert options['result_language'] == (language if action == 'approver' else 'de' if action == 'jordan' else 'he')


@pytest.mark.parametrize('fault', ['', 'online', 'offline', 'restore', 'replay'])
def test_shared_isolation_actions_use_owner_and_independent_probes(monkeypatch, fault):
    online = {'ipv6_default_route': False, 'probes': [{'reachable': True}]}
    offline = {'ipv6_default_route': False, 'probes': [{'reachable': False}]}
    probes = Mock(side_effect=[{**online, 'probes': [{'reachable': False}]} if fault == 'online' else online,
        online if fault == 'offline' else offline,
        offline if fault == 'restore' else online])
    owner = Mock()
    monkeypatch.setattr(shared, 'InternetIsolation', Mock(return_value=owner))
    recovery = Mock()
    monkeypatch.setattr(shared, 'restore', recovery)
    monkeypatch.setattr(shared, 'internet_result', probes)
    journey = SimpleNamespace(context=SimpleNamespace(lease=object()), transport=object())
    if fault in ('online', 'offline'):
        with pytest.raises(EvidenceError): shared.enter_offline(journey, Mock())
        if fault == 'online': owner.enter.assert_not_called()
    else:
        shared.enter_offline(journey, Mock())
        owner.enter.assert_called_once_with(journey.transport)
        if fault == 'replay':
            with pytest.raises(EvidenceError): shared.enter_offline(journey, Mock())
            assert probes.call_count == 2
        elif fault == 'restore':
            with pytest.raises(EvidenceError): shared.leave_offline(journey, Mock())
        else:
            shared.leave_offline(journey, Mock())
            recovery.assert_called_once_with(journey.context.lease)
            with pytest.raises(EvidenceError): shared.leave_offline(journey, Mock())


@pytest.mark.parametrize('fault', ['', 'meaning', 'durability'])
def test_actual_recorder_constructor_and_check_hook(session, tmp_path, monkeypatch, fault):
    expected = session.payload['assertions'][0]
    tags = {'entry-start': 'system:parent-command-context', 'entry-one': 'system:parent-command-context',
            'entry-two': 'system:parent-command-context', 'chooser': 'ui:parent-language-initial'}
    plan = replace(case.PLAN, screen_tags=tags, invocations=(), challenges={}, stage_actions={},
        phases={'ready': 'setup', 'setup-detached': 'setup', 'entry-start': 'start',
            'entry-one': 'step-1', 'entry-two': 'step-2', 'chooser': expected['step_id']},
        assertions_after={'chooser': expected['assertion_id']})
    chooser = {**case.CHOOSERS['en'], 'initial': True}
    checks = {'chooser': shared.public_language_value('language', chooser)}
    context = SimpleNamespace(directory=tmp_path / 'journey', product_free=True, asset_transfer=Mock(),
        verified=SimpleNamespace(inputs={}), credentials=Mock(), lease=Mock(), guestfs=Mock(), commands=Mock())
    context.directory.mkdir()
    recorder = session.recorder
    recorder.begin_case('E2E-001/gdm-observation')
    real_save = session.collector.save_report
    def save(name, report):
        if fault == 'durability' and report.get('event') == 'observation' and report.get('active_step') == expected['step_id']:
            raise OSError('storage failed')
        return real_save(name, report)
    monkeypatch.setattr(session.collector, 'save_report', save)
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={'outcome': 'passed'}))
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert type(journey) is shared.PublicLanguageJourney and journey.plan is plan
        journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
        journey.boot = 'a' * 64
        journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
        value = deepcopy(chooser)
        if fault == 'meaning': value['heading'] = 'incorrect'
        journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={'language': value}))
        journey.transport = Mock()
        for stage in tags:
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
    monkeypatch.setattr(shared.PublicLanguageJourney, 'validate', lambda _: [])
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            installed_journey.record_installed_journey(recorder, context, plan,
                actions={}, journey_type=shared.language_journey(checks=checks))
        assert not (context.directory / 'chooser.reply.json').exists()
    else:
        installed_journey.record_installed_journey(recorder, context, plan,
            actions={}, journey_type=shared.language_journey(checks=checks))
