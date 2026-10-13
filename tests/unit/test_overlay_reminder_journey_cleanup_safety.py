"""Private decoder/recorder doubles; no live product or resource ownership."""
from copy import deepcopy
import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import overlay_reminders as reminders
from private_artifacts import EvidenceError
from ui_observations import UiObservations
from tests.support.e2e_evidence import attempt
from tests.support.e2e_recording import session


CUSTOM = {'id': 'reminder-customer-choice', 'value': 90, 'unit': 'second',
          'text': 'Save <work> & games!'}


def reminder_value(records=None):
    records = deepcopy(reminders.DEFAULTS if records is None else records)
    return {'records': records, 'show_in_fullscreen': True, 'fullscreen_enabled': bool(records),
            'language': 'en', 'source': 'a' * 64}


@pytest.mark.parametrize('fault', ['', 'extra', 'duplicate', 'id', 'uppercase-id', 'underscore-id', 'seconds', 'bool-seconds',
                                  'unit', 'text', 'language', 'source', 'fullscreen'])
def test_decoder_rejects_malformed_record_and_latches_failure(fault):
    value = reminder_value()
    if fault == 'extra': value['extra'] = True
    if fault == 'duplicate': value['records'].append(deepcopy(value['records'][0]))
    if fault == 'id': value['records'][0]['id'] = '../foreign'
    if fault == 'uppercase-id': value['records'][0]['id'] = 'A'
    if fault == 'underscore-id': value['records'][0]['id'] = '_'
    if fault == 'seconds': value['records'][0]['value'] = 0
    if fault == 'bool-seconds': value['records'][0]['value'] = True
    if fault == 'unit': value['records'][0]['unit'] = 'hour'
    if fault == 'text': value['records'][0]['text'] = 'foreign\x00value'
    if fault == 'language': value['language'] = 'unknown'
    if fault == 'source': value['source'] = 'not-a-digest'
    if fault == 'fullscreen': value['fullscreen_enabled'] = 1
    payload = {'operation': 'overlay-reminder-read', 'outcome': 'passed',
               'interface': 'ApplicationUI+external-provider', 'reminders': value}
    raw = json.dumps(payload).encode()
    def deliver(*args, **kwargs):
        if kwargs.get('on_output') is not None:
            for offset in range(0, len(raw), 37):
                kwargs['on_output'](raw[offset:offset + 37])
            kwargs['on_output'](b'\n')
        return raw
    transport = SimpleNamespace(call=Mock(side_effect=deliver), commands=SimpleNamespace(progress=None))
    observer = UiObservations(transport)
    if fault:
        with pytest.raises(EvidenceError): observer.observe('overlay-reminder-read')
        with pytest.raises(EvidenceError, match='previous-failure'):
            observer.observe('overlay-reminder-save')
        transport.call.assert_called_once()
    else:
        assert observer.observe('overlay-reminder-read') == payload
        assert observer.overlay_reminder_source == value['source']


@pytest.mark.parametrize('operation', [
    'overlay-reminder-create', 'overlay-reminder-edit', 'overlay-reminder-delete',
    'overlay-reminder-delete-all', 'overlay-reminder-save', 'overlay-reminder-cancel'])
def test_mutation_requires_prior_draft_and_carries_exact_source(operation):
    transport = SimpleNamespace(call=Mock(), commands=SimpleNamespace(progress=None))
    observer = UiObservations(transport)
    with pytest.raises(EvidenceError, match='reminder-source-required'):
        observer.observe(operation)
    transport.call.assert_not_called()
    observer = UiObservations(transport)
    observer.overlay_reminder_source = 'b' * 64
    observer.boot_guard = 'c' * 64
    value = reminder_value()
    payload = {'operation': operation, 'outcome': 'passed',
               'interface': 'ApplicationUI+external-provider'}
    if operation not in ('overlay-reminder-save', 'overlay-reminder-cancel'):
        payload['reminders'] = value
    payload['boot_sha256'] = observer.boot_guard
    raw = json.dumps(payload).encode()

    def deliver(argv, **kwargs):
        assert argv[-2:] == ['c' * 64, 'b' * 64]
        kwargs['on_output'](raw + b'\n')
        return raw

    transport.call.side_effect = deliver
    result = observer.observe(operation)
    assert 'boot_sha256' not in result
    assert observer.overlay_reminder_source == (None if operation.endswith(('-save', '-cancel')) else 'a' * 64)


@pytest.mark.parametrize('fault', ['', 'changed-id', 'text', 'lost-default', 'language', 'fullscreen',
                                  'storage', 'replay'])
def test_saved_read_is_checked_before_durable_reply(tmp_path, fault):
    stage = 'saved-read'
    progress = Mock(side_effect=OSError('storage')) if fault == 'storage' else Mock()
    journey = reminders.OverlayReminderJourney(SimpleNamespace(directory=tmp_path), progress)
    journey.boot = 'a' * 64
    journey.steps = [{'stage': name} for name in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.custom_record = deepcopy(CUSTOM)
    journey.saved_records = reminders.sorted_records([*reminders.DEFAULTS, CUSTOM])
    value = reminder_value(journey.saved_records)
    custom = next(row for row in value['records'] if row['id'] == CUSTOM['id'])
    if fault == 'changed-id': custom['id'] = 'replacement'
    if fault == 'text': custom['text'] = 'Save &lt;work&gt; &amp; games!'
    if fault == 'lost-default': value['records'].pop()
    if fault == 'language': value['language'] = 'de'
    if fault == 'fullscreen': value['show_in_fullscreen'] = False
    if fault == 'replay': journey.reminder_captures.add(stage)
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={'reminders': value}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        custom['text'] = 'changed after read'
        assert journey.saved_records[2]['text'] == CUSTOM['text']


def test_draft_cancel_and_saved_empty_list_require_independent_reads(tmp_path):
    journey = reminders.OverlayReminderJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.check_settings('defaults-open', {'ui': {'reminders': reminder_value()}})
    created = {**CUSTOM, 'value': 75, 'text': 'Save <work>!'}
    for stage, rows in (
            ('created', reminders.sorted_records([*reminders.DEFAULTS, created])),
            ('edited', reminders.sorted_records([*reminders.DEFAULTS, CUSTOM])),
            ('saved-read', reminders.sorted_records([*reminders.DEFAULTS, CUSTOM])),
            ('deleted-draft', reminders.DEFAULTS),
            ('cancel-read', reminders.sorted_records([*reminders.DEFAULTS, CUSTOM])),
            ('cleared-draft', []), ('empty-read', [])):
        journey.check_settings(stage, {'ui': {'reminders': reminder_value(rows)}})
    assert journey.saved_records == reminders.sorted_records([*reminders.DEFAULTS, CUSTOM])
    fresh = reminders.OverlayReminderJourney(SimpleNamespace(directory=tmp_path), Mock())
    with pytest.raises(EvidenceError, match='records-or-stored-id'):
        fresh.check_settings('empty-read', {'ui': {'reminders': reminder_value()}})


@pytest.mark.parametrize('fault', ['', 'request', 'accessible-name', 'visible-label'])
def test_request_preservation_checks_choices_and_tolerates_incidental_captions(tmp_path, fault):
    journey = reminders.OverlayReminderJourney(SimpleNamespace(directory=tmp_path), Mock())
    form = {'request': {'surface': 'child-overlay', 'form_count': 1, 'child': 'fixture-child',
        'approver': 'other-fixture-parent', 'duration_seconds': 1800, 'custom_text': None,
        'allow_soft': False}, 'texts': {'kiosk-request-submit': 'Request access',
        'kiosk-request-cancel': 'Cancel request'}, 'labels': {'kiosk-request-submit': 'REQUEST',
        'kiosk-request-cancel': 'CANCEL'}, 'chooser_absent': True}
    journey.check_settings('initial-form', {'ui': {'language_form': form}})
    current = deepcopy(form)
    if fault == 'request': current['request']['allow_soft'] = True
    if fault == 'accessible-name': current['texts']['kiosk-request-submit'] = 'Changed action'
    if fault == 'visible-label': current['labels']['kiosk-request-submit'] = 'Changed label'
    if fault == 'request':
        with pytest.raises(EvidenceError):
            journey.check_settings('final-form', {'ui': {'language_form': current}})
    else:
        journey.check_settings('final-form', {'ui': {'language_form': current}})
    form['request']['allow_soft'] = True
    assert journey.request_projection['allow_soft'] is False


@pytest.mark.parametrize('fault', ['', 'grant', 'policy', 'increased-time', 'excess-usage'])
def test_policy_and_balance_preservation_include_observation_latency(tmp_path, fault):
    journey = reminders.OverlayReminderJourney(SimpleNamespace(directory=tmp_path), Mock())
    policy = {'settings': {'child': 'fixture-child', 'limit_enabled': True,
        'allowance': ['30 minutes']}, 'rows': [],
        'balances': {'daily': 1800, 'one_time': 0, 'total': 1800}}
    journey.ui = SimpleNamespace(read_bounds=(100 * 10**9, 110 * 10**9))
    journey.check_settings('policy-before', {'ui': {'language_policy': policy}})
    current = deepcopy(policy)
    current['balances'].update(daily=1770, total=1770)
    journey.ui.read_bounds = (125 * 10**9, 130 * 10**9)
    if fault == 'grant': current['balances']['one_time'] = 1
    if fault == 'policy': current['rows'].append(['changed-policy'])
    if fault == 'increased-time': current['balances'].update(daily=1810, total=1810)
    if fault == 'excess-usage': current['balances'].update(daily=1760, total=1760)
    if fault:
        with pytest.raises(EvidenceError):
            journey.check_settings('policy-after', {'ui': {'language_policy': current}})
    else:
        journey.check_settings('policy-after', {'ui': {'language_policy': current}})


@pytest.mark.parametrize('fault', ['', 'changed-default', 'durability'])
def test_real_recorder_constructor_startup_and_assertion_gate(session, tmp_path, monkeypatch, fault):
    import installed_journey
    import session_control
    expected = session.payload['assertions'][0]
    tags = {'entry-start': 'system:parent-command-context', 'entry-one': 'system:parent-command-context',
            'entry-two': 'system:parent-command-context', 'defaults-open': 'ui:overlay-reminder-defaults'}
    plan = replace(reminders.PLAN, screen_tags=tags, invocations=(), challenges={},
        phases={'ready': 'setup', 'setup-detached': 'setup', 'entry-start': 'start',
                'entry-one': 'step-1', 'entry-two': 'step-2', 'defaults-open': expected['step_id']},
        assertions_after={'defaults-open': expected['assertion_id']})
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
        assert isinstance(journey, reminders.OverlayReminderJourney) and journey.plan is plan
        journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
        journey.boot = 'a' * 64
        journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
        value = reminder_value()
        if fault == 'changed-default': value['records'][0]['value'] = 14
        journey.ui = SimpleNamespace(boot_proof=journey.boot,
            observe=Mock(return_value={'outcome': 'passed', 'reminders': value}))
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
    monkeypatch.setattr(reminders.OverlayReminderJourney, 'validate', lambda _: [])
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            installed_journey.record_installed_journey(recorder, context, plan, actions={},
                journey_type=reminders.OverlayReminderJourney)
        assert not (context.directory / 'defaults-open.reply.json').exists()
    else:
        installed_journey.record_installed_journey(recorder, context, plan, actions={},
            journey_type=reminders.OverlayReminderJourney)
