"""Private fault filesystem and public UI doubles; no host services or VM use."""
import json
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import UiError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node
from tests.support.e2e_kiosk import accounts_form
from tests.support.modules import load_module
from tests.support.paths import ROOT
from ui_observations import UiObservations


@pytest.fixture
def fault(tmp_path, monkeypatch):
    helper = load_module('private_kiosk_feedback', ROOT / 'tests/integration/system_kiosk_feedback.py')
    monkeypatch.setattr(helper, 'MASK', tmp_path / 'runtime/broker.service')
    helper.MASK.parent.mkdir()
    monkeypatch.setattr(helper, 'RECORD', tmp_path / 'private/fault.json')
    monkeypatch.setattr(helper, 'BOOT', tmp_path / 'boot')
    helper.BOOT.write_text('private-boot\n')
    monkeypatch.setattr(helper.guest, 'guard', Mock(return_value={'run': 'a' * 32}))
    original_lstat = helper.Path.lstat
    def metadata(path):
        original = original_lstat(path)
        if path == tmp_path or tmp_path in path.parents:
            values = list(original)
            values[4] = values[5] = 0
            return os.stat_result(values)
        return original
    monkeypatch.setattr(helper.Path, 'lstat', metadata)
    state = {'ActiveState': 'active', 'LoadState': 'loaded', 'InvocationID': 'b' * 32}
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        assert argv[0] == 'systemctl' and argv[-1] == helper.guest.BROKER
        if argv[1] == 'show':
            return '\n'.join(key + '=' + value for key, value in state.items())
        if argv[1] == 'mask':
            assert argv == ['systemctl', 'mask', '--runtime', helper.guest.BROKER]
            helper.MASK.symlink_to('/dev/null')
            state['LoadState'] = 'masked'
        elif argv[1] == 'stop':
            state.update(ActiveState='inactive', InvocationID='0' * 32)
        elif argv[1] == 'unmask':
            assert argv == ['systemctl', 'unmask', '--runtime', helper.guest.BROKER]
            helper.MASK.unlink()
            state['LoadState'] = 'loaded'
        elif argv[1] == 'start':
            state.update(ActiveState='active', InvocationID='c' * 32)
        else:
            pytest.fail('unreviewed command')
        return ''
    monkeypatch.setattr(helper.guest, 'run', run)
    return helper, state, calls


def test_fault_records_exact_runtime_mask_and_restores_broker(fault):
    helper, state, calls = fault
    assert helper.begin() == {'broker_unavailable': True, 'runtime_mask_owned': True}
    record = json.loads(helper.RECORD.read_text())
    assert record['state'] == 'stopped' and record['invocation'] == 'b' * 32
    assert record['mask'] == [helper.MASK.lstat().st_dev, helper.MASK.lstat().st_ino]
    assert helper.restore() == {'broker_restored': True}
    assert not helper.MASK.is_symlink() and state['ActiveState'] == 'active'
    assert [call[1] for call in calls if call[1] != 'show'] == ['mask', 'stop', 'unmask', 'start']
    helper.restore()  # Completed recovery performs no second mutation.
    assert [call[1] for call in calls].count('start') == 1


@pytest.mark.parametrize('replacement', ['mask', 'invocation', 'attempt', 'boot'])
def test_recovery_refuses_replaced_resources_without_mutation(fault, replacement):
    helper, state, calls = fault
    helper.begin()
    if replacement == 'mask':
        # Preserve the old link's inode while a distinct link replaces its path.
        helper.MASK.rename(helper.MASK.with_name('retained-original'))
        helper.MASK.symlink_to('/dev/null')
    elif replacement == 'invocation':
        state.update(ActiveState='active', InvocationID='d' * 32)
    elif replacement == 'attempt':
        helper.guest.guard.return_value = {'run': 'd' * 32}
    else:
        helper.BOOT.write_text('different-boot\n')
    before = len(calls)
    with pytest.raises(helper.guest.GuestError):
        helper.restore()
    assert all(call[1] == 'show' for call in calls[before:])
    assert helper.MASK.is_symlink()


def test_failed_start_retains_owned_unmasked_recovery(fault, monkeypatch):
    helper, state, calls = fault
    helper.begin()
    original = helper.guest.run
    def run(argv, **kwargs):
        if argv[1] == 'start':
            raise helper.guest.GuestError('private-start-failure')
        return original(argv, **kwargs)
    monkeypatch.setattr(helper.guest, 'run', run)
    with pytest.raises(helper.guest.GuestError, match='private-start-failure'):
        helper.restore()
    assert json.loads(helper.RECORD.read_text())['state'] == 'unmasked'
    monkeypatch.setattr(helper.guest, 'run', original)
    assert helper.restore() == {'broker_restored': True}
    assert [call[1] for call in calls].count('unmask') == 1


def test_unrecorded_mask_is_retained_for_explicit_recovery(fault):
    helper, state, calls = fault
    helper.MASK.symlink_to('/dev/null')
    with pytest.raises(helper.guest.GuestError, match='kiosk-feedback:mask-exists'):
        helper.begin()
    with pytest.raises(helper.guest.GuestError, match='kiosk-feedback:unrecorded-fault'):
        helper.restore()
    assert helper.MASK.is_symlink() and not calls


def diagnostic_ui():
    ui, selector, _, _ = accounts_form('approver')
    selector.setValue('1000')
    window = ui.find_id('kiosk-request-window')
    window.bus, window.path = ':1.42', '/public/window'
    controls = [Node('Request unavailable', 'label', identity='kiosk-result-title'),
        Node('The request could not be completed. Please return to login and try again later.', 'label',
             identity='kiosk-result-detail'),
        Node(identity='kiosk-report-toggle', value=True), Node(identity='kiosk-result-action')]
    editor = Node(identity='feedback-editor-input', states=('visible', 'showing', 'sensitive', 'editable'))
    document = Node(identity='feedback-editor-document', value={'ops': [{'insert': 'Error report\n'}]})
    download = Node(identity='feedback-download-logs', states=())
    logs = Node('diagnostic-logs.zip', identity='feedback-logs-row')
    send = Node(identity='feedback-send')
    privacy_link = Node(role='link', identity='feedback-privacy-link')
    dialog = Node(identity='feedback-dialog', children=[editor, document, download, logs, send,
                                                       privacy_link])
    dialog.bus, dialog.path = window.bus, '/public/feedback'
    dialog.relations = [SimpleNamespace(get_relation_type=lambda: 'controlled-by',
        get_n_targets=lambda: 1, get_target=lambda _: window)]
    def append(nodes):
        for node in nodes:
            window.children.append(node)
            node.parent = window
    ui.find_id('kiosk-request-submit').action.do_action.side_effect = lambda _: append(controls) or True
    controls[-1].action.do_action.side_effect = lambda _: append([dialog]) or True
    disclosure = ('Feedback, reply email addresses, attachments, and diagnostic logs are emailed to support. '
        'Retention depends on our support mailbox and service providers, including their backup policies. '
        'We do not currently guarantee deletion within a fixed period. '
        'Diagnostic logs do not collect account names, email addresses, file contents, raw system journals, or exception messages. '
        'Automatic diagnostics contain validated technical events, health checks, and system information: '
        'Your own feedback, reply email, and selected files are separate and may contain personal information. '
        'Review them before sending.')
    privacy_close = Node(role='button', identity='feedback-privacy-close')
    privacy = Node(identity='feedback-privacy-dialog', states=('visible', 'showing', 'sensitive', 'modal'), children=[
        Node(disclosure, role='label', identity='feedback-privacy-text'), privacy_close,
        Node(role='link', identity='feedback-full-privacy-link', states=())])
    privacy.bus, privacy.path = dialog.bus, '/public/privacy'
    privacy.relations = [SimpleNamespace(get_relation_type=lambda: 'controlled-by',
        get_n_targets=lambda: 1, get_target=lambda _: dialog)]
    def open_privacy(_):
        dialog.children.append(privacy)
        privacy.parent = dialog
        return True
    privacy_link.action.do_action.side_effect = open_privacy
    privacy_close.action.do_action.side_effect = lambda _: privacy._close() or True
    editor.setText.side_effect = lambda text: setattr(document, 'value', {'ops': [{'insert': text + '\n'}]})
    return ui, controls, editor, document, download, send


def test_real_public_error_report_editor_sequence_never_sends():
    ui, controls, editor, document, download, send = diagnostic_ui()
    error = ui.run('kiosk-diagnostic-error', '')['diagnostic']
    report = ui.run('kiosk-diagnostic-report', '')['diagnostic']
    result = ui.run('kiosk-diagnostic-editor', '')['diagnostic']
    privacy = ui.run('kiosk-diagnostic-privacy', '')['diagnostic']
    assert error['error_shown'] and error['report_default'] and report['report_open']
    assert error['source'] == report['source'] == result['source']
    assert result == {'source': error['source'], 'editor_usable': True,
                      'diagnostics_ready': True, 'sent': False}
    assert privacy == {'source': error['source'], 'privacy_read': True,
                      'actions_confined': True, 'draft_preserved': True, 'sent': False}
    editor.setText.assert_called_once_with('Installed kiosk diagnostic qualification.')
    assert document.getValue.call_count >= 1
    assert ui.find_id('kiosk-request-submit').action.do_action.call_count == 1
    assert controls[-1].action.do_action.call_count == 1
    send.action.do_action.assert_not_called()


@pytest.mark.parametrize('role,identity', [('button', 'feedback-manage'),
    ('button', 'feedback-arbitrary-program'), ('link', 'feedback-external'),
    ('link', 'feedback-format-link')])
def test_report_inventory_refuses_extra_actions_before_editor_input(role, identity):
    ui, _, editor, _, _, send = diagnostic_ui()
    ui.run('kiosk-diagnostic-error', '')
    ui.run('kiosk-diagnostic-report', '')
    dialog = ui.find_id('feedback-dialog')
    extra = Node(role=role, identity=identity)
    dialog.children.append(extra)
    extra.parent = dialog
    with pytest.raises(UiError, match='ui:kiosk-diagnostic-external-action'):
        ui.run('kiosk-diagnostic-editor', '')
    editor.setText.assert_not_called()
    extra.action.do_action.assert_not_called()
    send.action.do_action.assert_not_called()


@pytest.mark.parametrize('failure', ['external', 'management', 'readonly', 'disclosure', 'draft'])
def test_kiosk_privacy_refuses_external_actions_or_lost_report(failure):
    ui, _, editor, document, _, send = diagnostic_ui()
    ui.run('kiosk-diagnostic-error', '')
    ui.run('kiosk-diagnostic-report', '')
    ui.run('kiosk-diagnostic-editor', '')
    link = ui.find_id('feedback-privacy-link')
    original = link.action.do_action.side_effect
    def open_privacy(index):
        result = original(index)
        # Simulate the application's mutation without invoking the observer
        # inside input dispatch and caching a half-mutated result snapshot.
        modal = next(node for node in link.parent.children
                     if node.identity == 'feedback-privacy-dialog')
        controls = {node.identity: node for node in modal.children}
        if failure == 'external':
            controls['feedback-full-privacy-link'].states = {'visible', 'showing', 'sensitive'}
        elif failure == 'management':
            extra = Node(role='button', identity='feedback-manage')
            modal.children.append(extra)
            extra.parent = modal
        elif failure == 'readonly':
            controls['feedback-privacy-text'].role = 'button'
        elif failure == 'disclosure':
            controls['feedback-privacy-text'].name = 'Incomplete disclosure'
        else:
            close = controls['feedback-privacy-close']
            close_action = close.action.do_action.side_effect
            def lose_draft(index):
                document.value = {'ops': [{'insert': 'lost\n'}]}
                return close_action(index)
            close.action.do_action.side_effect = lose_draft
        return result
    link.action.do_action.side_effect = open_privacy
    category = ('document' if failure == 'draft' else 'external-action' if failure in
                ('external', 'management', 'readonly') else None)
    with pytest.raises(UiError, match='ui:kiosk-diagnostic-' + category if category else
                       'ui:feedback-privacy-disclosure'):
        ui.run('kiosk-diagnostic-privacy', '')
    assert link.action.do_action.call_count == 1
    assert editor.setText.call_count == 1
    send.action.do_action.assert_not_called()


@pytest.mark.parametrize('failure', ['modal', 'surface', 'owner'])
def test_privacy_entry_refuses_unexpected_scene_before_input(failure):
    ui, _, editor, _, _, send = diagnostic_ui()
    ui.run('kiosk-diagnostic-error', '')
    ui.run('kiosk-diagnostic-report', '')
    ui.run('kiosk-diagnostic-editor', '')
    link = ui.find_id('feedback-privacy-link')
    if failure == 'owner':
        ui.find_id('kiosk-request-window').bus = ':1.99'
    elif failure == 'modal':
        link.action.do_action.side_effect(0)
    else:
        window = ui.find_id('kiosk-request-window')
        extra = Node(role='dialog', identity='parent-window')
        window.children.append(extra)
        extra.parent = window
    with pytest.raises(UiError, match='ui:kiosk-diagnostic-(?:modal|extra-surface|owner)'):
        ui.run('kiosk-diagnostic-privacy', '')
    link.action.do_action.assert_not_called()
    assert editor.setText.call_count == 1
    send.action.do_action.assert_not_called()


def test_editor_failure_never_replays_input_or_sends():
    ui, controls, editor, document, download, send = diagnostic_ui()
    ui.run('kiosk-diagnostic-error', '')
    ui.run('kiosk-diagnostic-report', '')
    document.getValue.return_value = {'ops': [{'insert': 'different\n'}]}
    document.getValue.side_effect = None
    with pytest.raises(UiError, match='ui:kiosk-diagnostic-document'):
        ui.run('kiosk-diagnostic-editor', '')
    assert editor.setText.call_count == 1
    send.action.do_action.assert_not_called()


@pytest.mark.parametrize('failure', ['ui:incomplete-tree', 'ui:kiosk-valid-disabled'])
def test_error_request_waits_only_for_read_completion_before_single_input(monkeypatch, failure):
    ui, controls, editor, document, download, send = diagnostic_ui()
    ui.timeout = 1
    request = ui.find_id('kiosk-request-submit')
    target = ui.kiosk_valid_target
    reads = []
    def resolve(identity):
        reads.append(identity)
        if len(reads) == 1:
            request.action.do_action.assert_not_called()
            raise UiError(failure)
        return target(identity)
    monkeypatch.setattr(ui, 'kiosk_valid_target', resolve)
    if failure == 'ui:incomplete-tree':
        assert ui.run('kiosk-diagnostic-error', '')['diagnostic']['error_shown']
        assert len(reads) == 2 and request.action.do_action.call_count == 1
    else:
        with pytest.raises(UiError, match=failure):
            ui.run('kiosk-diagnostic-error', '')
        assert len(reads) == 1
        request.action.do_action.assert_not_called()
    send.action.do_action.assert_not_called()


def test_dedicated_kiosk_report_refuses_exposed_download_without_activating_it():
    ui, controls, editor, document, download, send = diagnostic_ui()
    ui.run('kiosk-diagnostic-error', '')
    ui.run('kiosk-diagnostic-report', '')
    download.states = {'visible', 'showing', 'sensitive'}
    with pytest.raises(UiError, match='ui:kiosk-diagnostic-external-action'):
        ui.run('kiosk-diagnostic-editor', '')
    download.action.do_action.assert_not_called()
    send.action.do_action.assert_not_called()


def test_feedback_qualification_requires_strict_census(tmp_path):
    from kiosk_feedback_confinement import KioskFeedbackConfinementJourney
    journey = KioskFeedbackConfinementJourney(SimpleNamespace(directory=tmp_path), Mock())
    census = {'census': {'backend': 'apparmor'}}
    journey.engineering = Mock(return_value=census)
    observed = {}
    journey.check_request('kiosk-diagnostic-editor', observed)
    assert observed == {'engineering_confinement': census}
    journey.engineering.assert_called_once_with('census')


def test_report_replaced_owner_refuses_before_dismissal():
    ui, controls, editor, document, download, send = diagnostic_ui()
    ui.run('kiosk-diagnostic-error', '')
    ui.find_id('kiosk-request-window').bus = ':1.99'
    with pytest.raises(UiError, match='ui:kiosk-diagnostic-owner'):
        ui.run('kiosk-diagnostic-report', '')
    controls[-1].action.do_action.assert_not_called()
    editor.setText.assert_not_called()
    send.action.do_action.assert_not_called()


def test_transport_checks_same_owner_order_and_exact_unsent_projection():
    transport = SimpleNamespace(call=Mock(), commands=SimpleNamespace(progress=None))
    def stream(argv, *, on_output, **kwargs):
        on_output(transport.call.return_value + b'\n')
        return transport.call.return_value
    transport.call.side_effect = stream
    observations = UiObservations(transport)
    observations.boot_guard = 'b' * 64
    def reply(operation, **fields):
        transport.call.return_value = json.dumps({'operation': operation, 'outcome': 'passed',
            'interface': 'ApplicationUI+external-provider', 'boot_sha256': 'b' * 64,
            'diagnostic': {'source': 'a' * 64, **fields}}).encode()
        return observations.observe(operation)
    with pytest.raises(EvidenceError, match='ui:kiosk-diagnostic-order'):
        reply('kiosk-diagnostic-report', report_open=True)
    reply('kiosk-diagnostic-error', error_shown=True, report_default=True)
    reply('kiosk-diagnostic-report', report_open=True)
    assert transport.call.call_args.args[0][-2:] == ['b' * 64, 'a' * 64]
    with pytest.raises(EvidenceError, match='ui:kiosk-diagnostic-response'):
        reply('kiosk-diagnostic-editor', editor_usable=True, diagnostics_ready=True, sent=True)
    reply('kiosk-diagnostic-editor', editor_usable=True, diagnostics_ready=True, sent=False)
    with pytest.raises(EvidenceError, match='ui:kiosk-diagnostic-response'):
        reply('kiosk-diagnostic-privacy', privacy_read=True, actions_confined=True,
              draft_preserved=False, sent=False)
    reply('kiosk-diagnostic-privacy', privacy_read=True, actions_confined=True,
          draft_preserved=True, sent=False)
    with pytest.raises(EvidenceError, match='ui:kiosk-diagnostic-order'):
        reply('kiosk-diagnostic-privacy', privacy_read=True, actions_confined=True,
              draft_preserved=True, sent=False)


def test_engineering_journey_prepares_rest_of_day_before_fault_and_restores_before_report(tmp_path):
    from kiosk_feedback_confinement import KioskFeedbackConfinementJourney, PLAN
    from kiosk_eligible_choices import PLAN as original
    from parent_setup_qualification import KioskFeedbackConfinementQualification
    journey = KioskFeedbackConfinementJourney(SimpleNamespace(directory=tmp_path), Mock())
    assert PLAN.screen_tags.keys() >= original.screen_tags.keys()
    assert PLAN.worker_mode == 'kiosk_feedback_confinement'
    order = []
    journey.ui = SimpleNamespace(observe=Mock(side_effect=lambda operation:
        order.append(operation) or {'valid_choice': 'independently-read'}))
    responses = iter([{'broker_unavailable': True, 'runtime_mask_owned': True},
                      {'broker_restored': True}])
    journey.engineering = Mock(side_effect=lambda action: order.append(action) or next(responses))
    observed = {}
    journey.check_request('selections-read', observed)
    assert observed['diagnostic_preparation'] == {'valid_choice': 'independently-read'}
    assert order == ['kiosk-valid-rest-select', 'begin']
    assert journey.fault_pending
    observed = {}
    journey.check_request('kiosk-diagnostic-error', observed)
    assert observed['engineering_recovery'] == {'broker_restored': True}
    assert not journey.fault_pending
    journey.engineering = Mock(side_effect=RuntimeError('uncertain transport reply'))
    with pytest.raises(RuntimeError):
        journey.check_request('selections-read', {})
    assert journey.fault_pending
    journey.engineering = Mock(return_value={'broker_restored': True})
    qualification = KioskFeedbackConfinementQualification.__new__(KioskFeedbackConfinementQualification)
    qualification.failure = Mock()
    journey.collect_failure = Mock()
    qualification.journey_failure(journey, 'engineering', 'private-failure')
    journey.engineering.assert_called_once_with('restore')


def test_preparation_refusal_never_starts_broker_fault(tmp_path):
    from kiosk_feedback_confinement import KioskFeedbackConfinementJourney
    journey = KioskFeedbackConfinementJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.ui = SimpleNamespace(observe=Mock(side_effect=EvidenceError('ui:unavailable')))
    journey.engineering = Mock()
    with pytest.raises(EvidenceError, match='ui:unavailable'):
        journey.check_request('selections-read', {})
    assert not journey.fault_pending
    journey.engineering.assert_not_called()


def test_strict_census_requires_webkit(monkeypatch):
    helper = load_module('private_kiosk_feedback_census', ROOT / 'tests/integration/system_kiosk_feedback.py')
    import system_kiosk_confinement
    value = {'backend': 'apparmor', 'confined_thread_roles': {
        'onpc-kiosk-webkit': 7}}
    census = Mock(return_value=value)
    monkeypatch.setattr(system_kiosk_confinement, 'census', census)
    assert helper.feedback_census() == {'census': value}
    assert census.call_args.kwargs['required_roles'] == (
        'manager', 'app', 'service', 'wellbeing', 'pipewire', 'webkit',
        'notifications', 'notification-client')


@pytest.mark.parametrize('refused', ['', 'kiosk-diagnostic-error'])
def test_worker_composes_public_station_steps_and_stops_on_fault_result_refusal(monkeypatch, refused):
    from kiosk_feedback_confinement import EXTRA, PLAN
    from tests.support.e2e_kiosk import WORKER
    from tests.support.perl import run_perl
    # Reuse the maintained worker probe; only its fixed engineering flag differs.
    ending = '    });\n    1;'
    assert WORKER.count(ending) == 1
    program = WORKER.replace(ending, '    }, 1);\n    1;')
    if refused:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refused)
    result = json.loads(run_perl(program).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    if refused:
        assert not result['ok'] and stages[-1] == refused
        assert 'kiosk-diagnostic-report' not in stages
    else:
        assert result['ok'] and stages[-len(EXTRA):] == list(EXTRA)
        assert [stage for stage in PLAN.screen_tags if stage in stages] == stages
    # Product actions after station entry remain controller API operations.
    boundary = result['events'].index(['stage', 'selections-read'])
    assert not any(event[0] in ('key', 'secret') for event in result['events'][boundary + 1:])


def test_feedback_failure_retains_pending_fault_when_recovery_fails(tmp_path):
    from kiosk_feedback_confinement import KioskFeedbackConfinementJourney
    from parent_setup_qualification import KioskFeedbackConfinementQualification
    journey = KioskFeedbackConfinementJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.fault_pending = True
    journey.engineering = Mock(side_effect=RuntimeError('private recovery error'))
    journey.collect_failure = Mock()
    qualification = KioskFeedbackConfinementQualification.__new__(KioskFeedbackConfinementQualification)
    qualification.failure = Mock()
    with pytest.raises(RuntimeError, match='private recovery error'):
        qualification.journey_failure(journey, 'engineering', 'private-failure')
    journey.engineering.assert_called_once_with('restore')
    assert journey.fault_pending
