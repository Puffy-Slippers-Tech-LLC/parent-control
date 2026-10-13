"""Private saved-value/recorder doubles; no VM, settings or shared resources."""
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import kiosk_reminders as reminders
from private_artifacts import EvidenceError
from ui_observations import RequestObservation, UiObservations
from tests.support.e2e_evidence import attempt
from tests.support.e2e_recording import session


CUSTOM = {'id': 'reminder-customer-choice', 'value': 90, 'unit': 'second',
          'text': 'Save <work> & games!'}


def value(records=None):
    return {'records': deepcopy(reminders.DEFAULTS if records is None else records),
            'language': 'en', 'show_in_fullscreen': True, 'fullscreen_enabled': True,
            'source': 'a' * 64}


def prepared(tmp_path):
    journey = reminders.KioskReminderJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.check_settings('overlay-defaults', {'ui': {'reminders': value()}})
    journey.check_settings('overlay-created', {'ui': {'reminders': value(
        reminders.sorted_records([*reminders.DEFAULTS, CUSTOM]))}})
    return journey


@pytest.mark.parametrize('fault', ['', 'id', 'text', 'value', 'defaults', 'language',
                                  'fullscreen', 'replay', 'missing-created'])
def test_kiosk_reopen_requires_exact_overlay_saved_record(tmp_path, fault):
    journey = prepared(tmp_path)
    current = value(reminders.sorted_records([*reminders.DEFAULTS, CUSTOM]))
    custom = current['records'][2]
    if fault == 'id': custom['id'] = 'replacement-id'
    if fault == 'text': custom['text'] = 'Save &lt;work&gt; &amp; games!'
    if fault == 'value': custom['value'] = 75
    if fault == 'defaults': current['records'].pop()
    if fault == 'language': current['language'] = 'de'
    if fault == 'fullscreen': current['show_in_fullscreen'] = False
    if fault == 'replay': journey.captures.add('riley-saved-read')
    if fault == 'missing-created': journey.custom_record = None
    if fault:
        with pytest.raises(EvidenceError):
            journey.check_settings('riley-saved-read', {'ui': {'reminders': current}})
    else:
        journey.check_settings('riley-saved-read', {'ui': {'reminders': current}})
        custom['text'] = 'changed after read'
        assert journey.custom_record == CUSTOM


@pytest.mark.parametrize('fault', ['', 'changed-id', 'old-value', 'jordan-row',
                                  'jordan-language', 'missing-jordan'])
def test_kiosk_edit_approver_child_switch_and_overlay_continuity(tmp_path, fault):
    journey = prepared(tmp_path)
    journey.check_settings('jordan-reminders-before', {'ui': {'reminders': value()}})
    edited = {**CUSTOM, 'value': 75}
    rows = reminders.sorted_records([*reminders.DEFAULTS, edited])
    for stage in ('riley-edited', 'riley-reopened', 'approver-reminders', 'riley-return-read'):
        journey.check_settings(stage, {'ui': {'reminders': value(rows)}})
    other = value()
    if fault == 'jordan-row': other['records'][0]['value'] = 20
    if fault == 'jordan-language': other['language'] = 'de'
    if fault == 'missing-jordan': journey.jordan_preferences = None
    current = value(rows)
    if fault == 'changed-id': current['records'][2]['id'] = 'replacement-id'
    if fault == 'old-value': current['records'][2]['value'] = 90
    def check():
        journey.check_settings('jordan-reminders-after', {'ui': {'reminders': other}})
        journey.check_settings('overlay-final-read', {'ui': {'reminders': current}})
    if fault:
        with pytest.raises(EvidenceError): check()
    else:
        check()
        other['records'][0]['value'] = 99
        assert journey.jordan_preferences['records'] == reminders.DEFAULTS


def request(child='fixture-child', approver='fixture-parent', surface='kiosk'):
    return {'surface': surface, 'form_count': 1, 'child': child, 'approver': approver,
            'duration_seconds': 1800, 'custom_text': None, 'allow_soft': False,
            'child_selector_enabled': surface != 'child-overlay', 'approver_selector_enabled': True,
            'duration_enabled': True, 'soft_choice_enabled': True, 'request_enabled': True,
            'cancel_enabled': True, 'message': '', 'mute': None}


@pytest.mark.parametrize('operation,child,approver', [
    ('binding-reminder-riley-select', 'fixture-child', 'fixture-parent'),
    ('binding-reminder-riley-select', 'fixture-child', 'other-fixture-parent'),
    ('binding-reminder-jordan-select', 'existing-fixture-child', 'other-fixture-parent'),
    ('binding-reminder-approver-select', 'fixture-child', 'other-fixture-parent'),
])
@pytest.mark.parametrize('fault', ['', 'child', 'surface', 'disabled', 'duration', 'extra'])
def test_real_decoder_and_journey_check_request_preserve_full_canonical_schema(
        tmp_path, operation, child, approver, fault):
    current = request(child=child, approver=approver)
    if fault == 'child':
        current['child'] = 'existing-fixture-child' if child == 'fixture-child' else 'fixture-child'
    if fault == 'surface': current['surface'] = 'child-overlay'
    if fault == 'disabled': current['request_enabled'] = False
    if fault == 'duration': current['duration_seconds'] = 75
    if fault == 'extra': current['foreign'] = True
    journey = reminders.KioskReminderJourney(SimpleNamespace(directory=tmp_path), Mock())
    observed = {'ui': {'operation': operation, 'request': current}}
    if fault:
        with pytest.raises(EvidenceError): RequestObservation.from_request(current, operation=operation)
        with pytest.raises(EvidenceError): journey.check_request('selection', observed)
        assert not journey.request_observations
    else:
        decoded = RequestObservation.from_request(current, operation=operation)
        journey.check_request('selection', observed)
        assert journey.request_observations['selection'] == decoded
        current['allow_soft'] = True
        assert journey.request_observations['selection'].allow_soft is False
        with pytest.raises(EvidenceError, match='request-replay'):
            journey.check_request('selection', observed)


@pytest.mark.parametrize('fault', ['', 'wrong-approver', 'unknown-field'])
def test_observer_decodes_selected_child_before_releasing_request(tmp_path, fault):
    current = request(approver='other-fixture-parent')
    if fault == 'wrong-approver': current['approver'] = 'fixture-parent'
    if fault == 'unknown-field': current['foreign'] = True
    payload = {'operation': 'binding-reminder-approver-select', 'outcome': 'passed',
               'interface': 'ApplicationUI+external-provider', 'request': current}
    raw = json.dumps(payload).encode()
    def deliver(*args, **kwargs):
        kwargs['on_output'](raw + b'\n')
        return raw
    transport = SimpleNamespace(call=Mock(side_effect=deliver), commands=SimpleNamespace(progress=None))
    observer = UiObservations(transport)
    if fault:
        with pytest.raises(EvidenceError): observer.observe('binding-reminder-approver-select')
        with pytest.raises(EvidenceError, match='previous-failure'):
            observer.observe('binding-reminder-riley-open')
        transport.call.assert_called_once()
    else:
        assert observer.observe('binding-reminder-approver-select') == payload
        assert observer.binding_reminder_source is None


@pytest.mark.parametrize('fault', ['', 'child', 'approver', 'duration', 'soft', 'surface'])
def test_request_choices_remain_child_bound_across_approver_and_surface(tmp_path, fault):
    journey = reminders.KioskReminderJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.check_settings('riley-select', {'ui': {'request': request()}})
    journey.check_settings('approver-select', {'ui': {'request': request(approver='other-fixture-parent')}})
    journey.check_settings('jordan-select', {'ui': {'request': request(
        child='existing-fixture-child', approver='other-fixture-parent')}})
    current = request(approver='other-fixture-parent', surface='child-overlay')
    if fault == 'child': current['child'] = 'existing-fixture-child'
    if fault == 'approver': current['approver'] = 'fixture-parent'
    if fault == 'duration': current['duration_seconds'] = 75
    if fault == 'soft': current['allow_soft'] = True
    if fault == 'surface': current['surface'] = 'kiosk'
    observed = {'ui': {'language_form': {'request': current}}}
    if fault:
        with pytest.raises(EvidenceError): journey.check_settings('overlay-final-form', observed)
    else:
        journey.check_settings('overlay-final-form', observed)
        current['allow_soft'] = True
        assert journey.requests['fixture-child']['allow_soft'] is False


@pytest.mark.parametrize('fault', ['', 'grant', 'policy', 'time-increase', 'excess-usage', 'jordan-time'])
def test_public_policy_and_elapsed_time_are_preserved_for_both_children(tmp_path, fault):
    journey = reminders.KioskReminderJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.ui = SimpleNamespace(read_bounds=(100 * 10**9, 110 * 10**9))
    riley = {'settings': {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['30 minutes']},
             'rows': [], 'balances': {'daily': 1800, 'one_time': 0, 'total': 1800}}
    jordan = {'settings': {'child': 'existing-fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
              'rows': [], 'balances': {'daily': 0, 'one_time': 0, 'total': 0}}
    for child, policy in (('riley', riley), ('jordan', jordan)):
        journey.check_settings(child + '-policy-before', {'ui': {'language_policy': policy}})
    current = deepcopy(riley)
    current['balances'].update(daily=1770, total=1770)
    journey.ui.read_bounds = (125 * 10**9, 130 * 10**9)
    if fault == 'grant': current['balances']['one_time'] = 1
    if fault == 'policy': current['rows'].append(['changed'])
    if fault == 'time-increase': current['balances'].update(daily=1810, total=1810)
    if fault == 'excess-usage': current['balances'].update(daily=1760, total=1760)
    other = deepcopy(jordan)
    if fault == 'jordan-time': other['balances'].update(daily=1, total=1)
    def check():
        journey.check_settings('riley-policy-after', {'ui': {'language_policy': current}})
        journey.check_settings('jordan-policy-after', {'ui': {'language_policy': other}})
    if fault:
        with pytest.raises(EvidenceError): check()
    else:
        check()


@pytest.mark.parametrize('fault', ['', 'changed-id', 'durability'])
def test_saved_readback_is_checked_before_real_recorder_durable_reply(session, tmp_path, monkeypatch, fault):
    import installed_journey
    import session_control
    expected = session.payload['assertions'][0]
    tags = {'entry-start': 'system:parent-command-context', 'entry-one': 'system:parent-command-context',
            'entry-two': 'system:parent-command-context', 'riley-saved-read': 'ui:binding-reminder-riley-open'}
    plan = replace(reminders.PLAN, screen_tags=tags, invocations=(), challenges={},
        phases={'ready': 'setup', 'setup-detached': 'setup', 'entry-start': 'start',
                'entry-one': 'step-1', 'entry-two': 'step-2', 'riley-saved-read': expected['step_id']},
        assertions_after={'riley-saved-read': expected['assertion_id']})
    context = SimpleNamespace(directory=tmp_path / 'journey', product_free=True, asset_transfer=Mock(),
        verified=SimpleNamespace(inputs={}), credentials=Mock(), lease=Mock(), guestfs=Mock(), commands=Mock())
    context.directory.mkdir()
    recorder = session.recorder
    recorder.begin_case('E2E-001/gdm-observation')
    save_report = session.collector.save_report
    def save(name, report):
        if fault == 'durability' and report.get('event') == 'observation' and report.get('active_step') == expected['step_id']:
            raise OSError('storage failed')
        return save_report(name, report)
    monkeypatch.setattr(session.collector, 'save_report', save)
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={'outcome': 'passed'}))
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert isinstance(journey, reminders.KioskReminderJourney) and journey.plan is plan
        journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
        journey.custom_record = deepcopy(CUSTOM)
        journey.boot = 'a' * 64
        journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
        current = value(reminders.sorted_records([*reminders.DEFAULTS, CUSTOM]))
        if fault == 'changed-id': current['records'][2]['id'] = 'replacement-id'
        journey.ui = SimpleNamespace(boot_proof=journey.boot,
            observe=Mock(return_value={'outcome': 'passed', 'reminders': current}))
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
    monkeypatch.setattr(reminders.KioskReminderJourney, 'validate', lambda _: [])
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            installed_journey.record_installed_journey(recorder, context, plan, actions={},
                journey_type=reminders.KioskReminderJourney)
        assert not (context.directory / 'riley-saved-read.reply.json').exists()
    else:
        installed_journey.record_installed_journey(recorder, context, plan, actions={},
            journey_type=reminders.KioskReminderJourney)
