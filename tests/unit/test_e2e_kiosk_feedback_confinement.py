"""Private fault filesystem and public UI doubles; no host services or VM use."""
import json
import os
from pathlib import Path
import signal
import time
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
    controls = [Node('Something went wrong', 'label', identity='kiosk-result-title'),
        Node('The operation could not be completed. Please try again later.', 'label',
             identity='kiosk-result-detail'),
        Node(identity='kiosk-report-toggle', value=True), Node(identity='kiosk-result-action')]
    editor = Node(identity='feedback-editor-input', states=('visible', 'showing', 'sensitive', 'editable'))
    document = Node(identity='feedback-editor-document', value={'ops': [{'insert': 'Error report\n'}]})
    download = Node(identity='feedback-download-logs')
    send = Node(identity='feedback-send')
    dialog = Node(identity='feedback-dialog', children=[editor, document, download, send])
    dialog.bus, dialog.path = window.bus, '/public/feedback'
    dialog.relations = [SimpleNamespace(get_relation_type=lambda: 'controlled-by',
        get_n_targets=lambda: 1, get_target=lambda _: window)]
    def append(nodes):
        for node in nodes:
            window.children.append(node)
            node.parent = window
    ui.find_id('kiosk-request-submit').action.do_action.side_effect = lambda _: append(controls) or True
    controls[-1].action.do_action.side_effect = lambda _: append([dialog]) or True
    editor.setText.side_effect = lambda text: setattr(document, 'value', {'ops': [{'insert': text + '\n'}]})
    return ui, controls, editor, document, download, send


def test_real_public_error_report_editor_sequence_never_sends():
    ui, controls, editor, document, download, send = diagnostic_ui()
    error = ui.run('kiosk-diagnostic-error', '')['diagnostic']
    report = ui.run('kiosk-diagnostic-report', '')['diagnostic']
    result = ui.run('kiosk-diagnostic-editor', '')['diagnostic']
    assert error['error_shown'] and error['report_default'] and report['report_open']
    assert error['source'] == report['source'] == result['source']
    assert result == {'source': error['source'], 'editor_usable': True,
                      'diagnostics_ready': True, 'sent': False}
    editor.setText.assert_called_once_with('Installed kiosk diagnostic qualification.')
    assert document.getValue.call_count >= 1
    assert ui.find_id('kiosk-request-submit').action.do_action.call_count == 1
    assert controls[-1].action.do_action.call_count == 1
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


def test_engineering_journey_restores_before_report_and_restores_unknown_fault(tmp_path):
    from kiosk_feedback_confinement import KioskFeedbackConfinementJourney, PLAN
    from kiosk_eligible_choices import PLAN as original
    from parent_setup_qualification import KioskFeedbackConfinementQualification
    context = SimpleNamespace(directory=tmp_path)
    journey = KioskFeedbackConfinementJourney(context, Mock())
    assert PLAN.screen_tags.keys() >= original.screen_tags.keys()
    assert PLAN.worker_mode == 'kiosk_feedback_confinement'
    journey.engineering = Mock(side_effect=[{'broker_unavailable': True, 'runtime_mask_owned': True},
                                          {'broker_restored': True}, {'scanner_observer_started': True}])
    journey.check_request('selections-read', {})
    assert journey.fault_pending
    observed = {}
    journey.check_request('kiosk-diagnostic-error', observed)
    assert observed['engineering_recovery'] == {'broker_restored': True}
    assert not journey.fault_pending
    assert journey.scanner_pending
    assert observed['engineering_scanner_start'] == {'scanner_observer_started': True}
    journey.engineering = Mock(return_value={'scanner_observed': False, 'observation': 'not-observed'})
    assert journey.stop_scanner()['observation'] == 'not-observed'
    assert not journey.scanner_pending
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


@pytest.mark.parametrize('observed', [False, True])
def test_strict_census_requires_webkit_and_reports_only_actual_scanner(monkeypatch, observed):
    helper = load_module('private_kiosk_feedback_census', ROOT / 'tests/integration/system_kiosk_feedback.py')
    import system_kiosk_confinement
    value = {'backend': 'apparmor', 'confined_thread_roles': {
        'onpc-kiosk-webkit': 7, **({'onpc-kiosk-scanner': 1} if observed else {})}}
    census = Mock(return_value=value)
    monkeypatch.setattr(system_kiosk_confinement, 'census', census)
    assert helper.feedback_census() == {'census': value, 'scanner_observed': observed}
    assert 'webkit' in census.call_args.kwargs['required_roles']


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
        assert result['ok'] and stages[-3:] == list(EXTRA)
        assert [stage for stage in PLAN.screen_tags if stage in stages] == stages
    # Product actions after station entry remain controller API operations.
    boundary = result['events'].index(['stage', 'selections-read'])
    assert not any(event[0] in ('key', 'secret') for event in result['events'][boundary + 1:])


@pytest.fixture
def scanner_observer(fault, monkeypatch):
    helper, _, _ = fault
    for name, filename in (('SCANNER', 'observer.json'), ('SCANNER_STOP', 'stop'),
                           ('SCANNER_RESULT', 'result.json')):
        monkeypatch.setattr(helper, name, helper.RECORD.parent / filename)
    real_fstat = os.fstat
    def fstat(fd):
        info = real_fstat(fd)
        path = Path(os.readlink('/proc/self/fd/' + str(fd)))
        if path.is_relative_to(helper.RECORD.parent):
            values = list(info)
            values[4] = values[5] = 0
            return os.stat_result(values)
        return info
    monkeypatch.setattr(helper.os, 'fstat', fstat)
    import system_kiosk_confinement as confinement
    real_identity = confinement.process_identity
    def identity(path):
        value = real_identity(path)
        return (*value[:2], ('0',) * 4)
    monkeypatch.setattr(confinement, 'process_identity', identity)
    def observe(stop_fd, ready):
        ready()
        deadline = time.monotonic() + 2
        while not os.pread(stop_fd, 6, 0) and time.monotonic() < deadline:
            time.sleep(0.005)
        return {'scanner_observed': False, 'observation': 'not-observed', 'backend': 'apparmor'}
    monkeypatch.setattr(confinement, 'observe_scanner', observe)
    return helper


def reap_observer(pid):
    # This fixture's explicitly spawned unreaped direct child cannot recycle.
    try:
        waited, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return
    if waited == 0:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)


def test_scanner_observer_owned_start_stop_reaps_child_and_keeps_missing_proof_explicit(scanner_observer):
    helper = scanner_observer
    assert helper.scanner_start() == {'scanner_observer_started': True}
    pid = json.loads(helper.SCANNER.read_text())['pid']
    try:
        assert helper.scanner_finish() == {
            'scanner_observed': False, 'observation': 'not-observed', 'backend': 'apparmor'}
        with pytest.raises(ChildProcessError):
            os.waitpid(pid, os.WNOHANG)
        assert helper.scanner_finish()['observation'] == 'not-observed'
    finally:
        reap_observer(pid)


@pytest.mark.parametrize('replacement', ['stop', 'result', 'attempt', 'boot', 'starttime'])
def test_scanner_observer_refuses_replaced_identity_before_stopping(scanner_observer, replacement):
    helper = scanner_observer
    helper.scanner_start()
    original = json.loads(helper.SCANNER.read_text())
    try:
        if replacement in ('stop', 'result'):
            path = helper.SCANNER_STOP if replacement == 'stop' else helper.SCANNER_RESULT
            path.rename(path.with_name('retained-original'))
            path.touch(mode=0o600)
        elif replacement == 'attempt':
            helper.guest.guard.return_value = {'run': 'd' * 32}
        elif replacement == 'boot':
            helper.BOOT.write_text('another boot\n')
        else:
            value = dict(original, starttime='1')
            helper.SCANNER.write_text(json.dumps(value))
        with pytest.raises(helper.guest.GuestError, match='kiosk-scanner:'):
            helper.scanner_finish()
        assert helper.SCANNER_STOP.read_bytes() == b''
    finally:
        reap_observer(original['pid'])


def test_scanner_observer_pidfd_acquisition_failure_reaps_own_fork(scanner_observer, monkeypatch):
    helper = scanner_observer
    real_fork = os.fork
    children = []
    def fork():
        pid = real_fork()
        if pid:
            children.append(pid)
        return pid
    monkeypatch.setattr(helper.os, 'fork', fork)
    monkeypatch.setattr(helper.os, 'pidfd_open', Mock(side_effect=OSError('private pidfd unavailable')))
    with pytest.raises(OSError, match='private pidfd unavailable'):
        helper.scanner_start()
    assert len(children) == 1
    with pytest.raises(ChildProcessError):
        os.waitpid(children[0], os.WNOHANG)


def test_scanner_observer_rejects_unknown_remaining_files(scanner_observer):
    helper = scanner_observer
    helper.SCANNER.parent.mkdir(mode=0o700)
    helper.SCANNER_STOP.touch(mode=0o600)
    with pytest.raises(helper.guest.GuestError, match='unrecorded-observer'):
        helper.scanner_finish()


def test_scanner_observer_timeout_kills_and_reaps_only_recorded_child(scanner_observer, monkeypatch):
    helper = scanner_observer
    helper.scanner_start()
    pid = json.loads(helper.SCANNER.read_text())['pid']
    polls = iter([[], [(pid, 1)]])
    monkeypatch.setattr(helper.select, 'poll', lambda: SimpleNamespace(
        register=lambda fd, flags: None, poll=lambda timeout: next(polls)))
    signals = []
    real_signal = signal.pidfd_send_signal
    def send(pidfd, sig):
        assert '\nPid:\t' + str(pid) + '\n' in Path('/proc/self/fdinfo/' + str(pidfd)).read_text()
        signals.append(sig)
        return real_signal(pidfd, sig)
    monkeypatch.setattr(helper.signal, 'pidfd_send_signal', send)
    try:
        with pytest.raises(helper.guest.GuestError, match='observer-stop-timeout'):
            helper.scanner_finish()
        assert signals == [signal.SIGKILL]
        with pytest.raises(ChildProcessError):
            os.waitpid(pid, os.WNOHANG)
    finally:
        reap_observer(pid)


def test_feedback_failure_restores_fault_and_stops_recorded_observer_even_on_recovery_failure(tmp_path):
    from kiosk_feedback_confinement import KioskFeedbackConfinementJourney
    from parent_setup_qualification import KioskFeedbackConfinementQualification
    journey = KioskFeedbackConfinementJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.fault_pending = journey.scanner_pending = True
    journey.engineering = Mock(side_effect=[RuntimeError('private recovery error'),
        {'scanner_observed': False, 'observation': 'not-observed'}])
    journey.collect_failure = Mock()
    qualification = KioskFeedbackConfinementQualification.__new__(KioskFeedbackConfinementQualification)
    qualification.failure = Mock()
    with pytest.raises(RuntimeError, match='private recovery error'):
        qualification.journey_failure(journey, 'engineering', 'private-failure')
    assert [call.args[0] for call in journey.engineering.call_args_list] == ['restore', 'scanner-finish']
    assert not journey.scanner_pending
