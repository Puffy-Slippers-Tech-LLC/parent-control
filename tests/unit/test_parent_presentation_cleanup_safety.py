"""Private recorder/decoder files and waited Perl; no live VM, bus or display.

Compatible in unit and cleanup inventories: pytest-owned storage, process-local
values and bounded owned subprocesses, with no shared path or external service.
"""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import accessible_ui as public
import e2e_worker
import language_composition as shared
import parent_presentation as case
from private_artifacts import EvidenceError
from tests.support.e2e_kiosk import WORKER
from tests.support.perl import run_perl
from ui_observations import UiObservations, OPERATION_LABELS


def policy(selected='en', elapsed=0):
    row = 'parent-app-' + 'a' * 16
    value = dict(child='fixture-child', account_name='Riley (Child)', limit_enabled=True,
        allowance_minutes=60, chooser_absent=True, management=case.TEXT[selected][3],
        management_labels=list(case.LABELS[selected]), rows=[[row, 'allowed', 'precise']],
        app_names=[[row, 'יישום לדוגמה' if selected == 'he' else 'Fixture application']],
        balances=dict(child='fixture-child', expanded=True,
            observed_monotonic_ns=(100 + elapsed) * 10**9))
    for key, seconds in (('daily', 3600), ('one_time', 0), ('total', 3600)):
        value['balances'][key] = public.duration_projection(
            ('1ש׳' if seconds else '0דק׳') if selected == 'he' else ('1h' if seconds else '0m'),
            language=selected)
    return value


def test_complete_bindings_and_actual_distribution():
    assert all(tag[3:] in public.OPERATIONS and tag[3:] in OPERATION_LABELS
               for tag in case.SCREENS.values())
    bundle = e2e_worker.distribution_inputs()
    assert b'parent_presentation' in bundle['tests/smoke.pm']
    assert b'sub run' in bundle['lib/onpc_parent_presentation.pm']
    assert all(stage in case.CHECKS for stage in case.POLICY_LANGUAGES)
    assert case.CHECKS['policy-captured'].keywords['capture'] == 'original-policy'
    assert case.CHECKS['draft-captured'].keywords['capture'] == 'original-draft'


@pytest.mark.parametrize('fault', ['', *case.SCREENS])
def test_real_worker_order_titles_and_terminal_refusal(monkeypatch, fault):
    if fault: monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', fault)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_parent_presentation')
    worker = worker.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]] }")
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
        last = max(index for index, event in enumerate(result['events']) if event[0] == 'stage')
        assert not any(event[0] in ('key', 'secret', 'text') for event in result['events'][last + 1:])


@pytest.mark.parametrize('fault', ['', 'changed', 'missing', 'replay', 'storage'])
@pytest.mark.parametrize('stage', [
    'hebrew-feedback-open',
    # The reopen stage reads the retained draft; keep the existing case selector.
    pytest.param('english-return-feedback-open', id='english-return-feedback-read'),
    'hebrew-final',
])
def test_real_decoder_and_recorder_compare_before_reply(tmp_path, stage, fault):
    journey = shared.language_journey(checks=case.CHECKS)(SimpleNamespace(directory=tmp_path), Mock(), case.PLAN)
    original_policy = policy()
    journey.check_settings('policy-captured', {'ui': {'language_state': original_policy}})
    journey.check_settings('hebrew-state', {'ui': {'language_state': policy('he', 5)}})
    draft = deepcopy(case.DRAFT)
    journey.check_settings('draft-captured', {'ui': {'feedback': draft}})
    original_policy['app_names'][0][1] = 'changed caller-owned input'
    draft['attachments'].append('changed caller-owned input')
    assert journey.public_captures['original-policy'][0]['app_names'][0][1] == 'Fixture application'
    assert journey.public_captures['original-draft'] == case.DRAFT
    operation = case.SCREENS[stage][3:]
    payload = dict(operation=operation, outcome='passed', interface='ApplicationUI+external-provider')
    if stage == 'hebrew-final':
        payload['language_state'] = policy('he', 10)
        if fault == 'changed': payload['language_state']['rows'][0][1] = 'permanent'
    else:
        checks = case.CHECKS[stage].keywords['checks']
        payload.update(dialog_presentation=deepcopy(checks[0].keywords['expected']), feedback=deepcopy(case.DRAFT))
        if fault == 'changed': payload['feedback']['draft'] = 'synthetic-first'
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(payload, ensure_ascii=False).encode()))
    observer = UiObservations(transport)
    if stage != 'hebrew-final' and fault == 'changed':
        with pytest.raises(EvidenceError): observer.observe(operation)
        transport.call.assert_called_once()
        return
    decoded = observer.observe(operation)
    journey.boot = 'a' * 64
    journey.steps = [{'stage': item} for item in case.PLAN.stages[:case.PLAN.stages.index(stage)]]
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value=decoded))
    if fault == 'missing': journey.public_captures.clear()
    if fault == 'replay': journey.checked_stages.add(stage)
    if fault == 'storage': journey.progress.side_effect = OSError('storage failed')
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).is_file()


def test_shared_public_capture_supports_renamed_endpoints_and_refuses_mutation(tmp_path):
    journey = shared.language_journey(checks={})(SimpleNamespace(directory=tmp_path), Mock(), case.PLAN)
    expected = {'nested': ['synthetic']}
    capture = shared.public_language_value('feedback', expected, capture='independent-origin')
    compare = shared.public_language_value('feedback', expected, same='independent-origin')
    capture(journey, {'ui': {'feedback': deepcopy(expected)}})
    with pytest.raises(EvidenceError, match='capture-replay'): capture(journey, {'ui': {'feedback': expected}})
    compare(journey, {'ui': {'feedback': expected}})
    expected['nested'].append('changed')
    with pytest.raises(EvidenceError): compare(journey, {'ui': {'feedback': expected}})
    assert journey.public_captures['independent-origin'] == {'nested': ['synthetic']}
    journey.public_captures.clear()
    with pytest.raises(EvidenceError, match='missing-public-capture'):
        compare(journey, {'ui': {'feedback': {'nested': ['synthetic']}}})


@pytest.mark.parametrize('stage', ['hebrew-final', 'english-return-state', 'english-return-final'])
@pytest.mark.parametrize('fault', ['', 'name', 'policy', 'account', 'grant', 'elapsed', 'missing-names'])
def test_language_names_and_original_policy_remain_exact_before_reply(tmp_path, stage, fault):
    journey = shared.language_journey(checks=case.CHECKS)(
        SimpleNamespace(directory=tmp_path), Mock(), case.PLAN)
    english = policy()
    hebrew = policy('he', 10)
    journey.check_settings('policy-captured', {'ui': {'language_state': english}})
    journey.check_settings('hebrew-state', {'ui': {'language_state': hebrew}})
    english['app_names'][0][1] = 'mutated English input'
    hebrew['app_names'][0][1] = 'mutated Hebrew input'
    assert journey.public_captures['original-policy'][0]['app_names'][0][1] == 'Fixture application'
    assert journey.public_captures['hebrew-app-names'][0][1] == 'יישום לדוגמה'
    value = policy('he' if stage == 'hebrew-final' else 'en', 20)
    if fault == 'name': value['app_names'][0][1] = 'different application'
    if fault == 'policy': value['rows'][0][1] = 'permanent'
    if fault == 'account': value['account_name'] = 'different account'
    if fault == 'grant': value['balances']['one_time']['seconds'] = 1
    if fault == 'elapsed': value['balances']['observed_monotonic_ns'] += 601 * 10**9
    if fault == 'missing-names':
        journey.public_captures.pop('hebrew-app-names' if stage == 'hebrew-final' else 'original-policy')
    journey.boot = 'a' * 64
    journey.steps = [{'stage': item} for item in case.PLAN.stages[:case.PLAN.stages.index(stage)]]
    journey.ui = SimpleNamespace(boot_proof=journey.boot,
        observe=Mock(return_value={'language_state': value}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).is_file()
