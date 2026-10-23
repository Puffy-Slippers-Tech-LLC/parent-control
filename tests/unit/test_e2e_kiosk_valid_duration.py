"""Shared authentication input guards; private trees and mocked transports only."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
from accessible_ui import UiError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node
from tests.support.e2e_kiosk import accounts_form
from ui_observations import UiObservations
from request_flow import CHOICES


def valid_form():
    ui, selector, _, _ = accounts_form('approver')
    selector.setValue('1000')
    selector.setValue.reset_mock()
    form = ui.find_id('kiosk-request-form')
    status = Node('Estimated remaining time: 45m', 'label', identity='kiosk-request-status')
    custom = Node('Custom minutes', 'entry', identity='kiosk-custom-duration', states=('visible', 'sensitive', 'editable'))
    custom.value = '1.25'
    custom.get_text_iface = lambda: SimpleNamespace(
        get_character_count=lambda: len(custom.value), get_text=lambda start, end: custom.value[start:end])
    ui.api.Text = SimpleNamespace(get_character_count=lambda interface: interface.get_character_count(),
                                  get_text=lambda interface, start, end: interface.get_text(start, end))
    for node in (status, custom):
        node.parent = form
        form.children.append(node)
    for value in (300, 900, 1800, 3600, 7200, 14400, 0, 'custom'):
        node = ui.find_id(f'kiosk-duration-{value}')
        def select(_index, value=value):
            for other in form.children:
                if other.identity.startswith('kiosk-duration-'):
                    other.states.discard('pressed')
            ui.find_id(f'kiosk-duration-{value}').states.add('pressed')
            if value == 'custom':
                custom.states.add('showing')
                status.name = 'Estimated remaining time: 16m 15s'
            else:
                custom.states.discard('showing')
                status.name = ('If approved, access until midnight.' if value == 0 else
                               'Estimated remaining time: 20m')
            return True
        node.action.do_action.side_effect = select
    soft = ui.find_id('kiosk-soft-apps-toggle')
    def toggle(_):
        soft.states.symmetric_difference_update({'checked'})
        return True
    soft.action.do_action.side_effect = toggle
    return ui, status, custom




def mate_form():
    """Private public-tree double; no service, files, secret or display access."""
    from common.oh_no_parent_control_ui import messages as m

    ui, status, custom = valid_form()
    ui.kiosk_valid_choice('kiosk-valid-custom-open')
    ui.kiosk_valid_choice('kiosk-valid-fraction-soft-select')
    app = ui.root()
    desktop = Node('desktop', 'desktop frame', children=[app])
    ui.api.get_desktop = lambda _: desktop
    field = Node(role='password text', states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = lambda: SimpleNamespace(
        get_character_count=lambda: 0, get_text=Mock(side_effect=AssertionError('password content')))
    # Public accessible names are labels; never traverse or read secret contents.
    field.get_description = Mock(side_effect=AssertionError('protected description'))
    field.get_child_count = Mock(side_effect=AssertionError('protected children'))
    cancel = Node('Cancel', 'push button')
    message = Node(m.POLKIT_GRANT_SOFT_APPS.source % {
        'target': accessible_ui.CHILD, 'duration': '1 minute, 15 seconds'}, 'label')
    recipient = Node('Password for onpc-parent-jamie:', 'label')
    dialog = Node('Authenticate', 'dialog', children=[message, recipient, field, cancel])
    agent = Node('mate-polkit', 'application', children=[dialog])
    agent.parent = desktop
    submit = ui.find_id('kiosk-request-submit')
    submit.action.do_action.side_effect = lambda _: desktop.children.append(agent) or True
    cancel.action.do_action.side_effect = lambda _: desktop.children.remove(agent) or True
    ui.mate_agent_pid = Mock(return_value=100)
    ui.mate_provider_metadata = Mock(return_value={
        'version': '1.26.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]})
    return ui, desktop, agent, dialog, field, cancel, submit, message, recipient


@pytest.mark.parametrize('fault', [None, 'child', 'duration', 'soft', 'missing-time',
                                  'duplicate', 'hidden', 'legacy'])
def test_mate_approval_checks_complete_catalogue_request_before_secret_proofs(fault):
    ui, desktop, agent, dialog, field, cancel, submit, message, recipient = mate_form()
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    if fault == 'child':
        message.name = message.name.replace(accessible_ui.CHILD, 'unrelated')
    elif fault == 'duration':
        message.name = message.name.replace('1 minute, 15 seconds', '5 minutes')
    elif fault == 'soft':
        message.name = message.name.removesuffix('\nAllow soft blocked apps for this grant.')
    elif fault == 'missing-time':
        message.name = message.name.replace('\nRequested time: 1 minute, 15 seconds.', '')
    elif fault == 'duplicate':
        dialog.children.append(Node(message.name, 'label'))
    elif fault == 'hidden':
        message.states.discard('visible')
    elif fault == 'legacy':
        message.name = f'Grant {accessible_ui.CHILD} 1 minute, 15 seconds and allow soft blocked apps?'
    opening = 'kiosk-mate-open'
    if fault:
        with pytest.raises(UiError, match='ui:mate-request-context-missing'):
            ui.run(opening, '')
        ui.mate_challenge_identity.assert_not_called()
        with pytest.raises(UiError, match='uncertain-input'):
            ui.run(opening, '')
    else:
        expected = {'challenge_id': 'a' * 64}
        assert ui.run(opening, '')['approval'] == expected
        ui.expected_mate_challenge = 'a' * 64
        for operation in ('kiosk-mate-qualified', 'kiosk-mate-rechecked'):
            assert ui.run(operation, '')['approval'] == expected
    submit.action.do_action.assert_called_once()
    cancel.action.do_action.assert_not_called()
    field.get_child_count.assert_not_called()
    field.get_description.assert_not_called()


@pytest.mark.parametrize('fault', ['agent', 'owner', 'duplicate-owner', 'duplicate-field',
                                  'hidden', 'disabled', 'focus', 'nonempty', 'recipient',
                                  'context', 'cancel', 'incomplete', 'stale'])
def test_mate_prompt_refuses_before_cancel_and_latches_failure(fault):
    ui, desktop, agent, dialog, field, cancel, submit, message, recipient = mate_form()
    if fault == 'agent':
        agent.name = 'gnome-shell'
    elif fault == 'owner':
        agent.get_process_id = lambda: 999
    elif fault == 'duplicate-owner':
        desktop.children.append(Node('mate-polkit', 'application'))
    elif fault == 'duplicate-field':
        dialog.children.append(Node(role='password text'))
    elif fault in ('hidden', 'disabled', 'focus'):
        field.states.discard({'hidden': 'visible', 'disabled': 'sensitive', 'focus': 'focused'}[fault])
    elif fault == 'nonempty':
        field.get_text_iface = lambda: SimpleNamespace(get_character_count=lambda: 1)
    elif fault == 'recipient':
        recipient.name = 'Password for onpc-parent-casey:'
    elif fault == 'context':
        message.name = 'Authentication is required'
    elif fault == 'cancel':
        cancel.states.discard('sensitive')
    elif fault == 'incomplete':
        dialog.children.append(None)
    else:
        field.states.add('defunct')
    with pytest.raises(UiError):
        ui.run('kiosk-mate-cancel', '')
    cancel.action.do_action.assert_not_called()
    with pytest.raises(UiError, match='uncertain-input'):
        ui.run('kiosk-mate-cancel', '')
    submit.action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', [None, 'missing-form', 'same-challenge', 'changed-challenge', 'failed-read'])
def test_new_approval_after_rejection_requires_fresh_form_and_challenge(fault):
    observer = UiObservations(Mock())
    current = 'a'
    def call(_args, operation, **kwargs):
        approval = ({'rejected': True, 'cancelled': True, 'no_error': True}
                    if operation.endswith('submit-rejection') else {'challenge_id': current * 64})
        value = {'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
                 'approval': approval}
        if operation not in ('kiosk-mate-open', 'kiosk-mate-rejection-open'):
            value['boot_sha256'] = 'c' * 64
        return json.dumps(value).encode(), []
    observer.call = Mock(side_effect=call)
    for operation in accessible_ui.MATE_REJECTION_ORDER:
        observer.observe(operation)
    real_observe = observer._observe
    # Exercise the real order wrapper; the existing form decoder is tested separately.
    def form_read(operation):
        if operation == 'kiosk-valid-fraction-soft-read':
            if fault == 'failed-read':
                raise EvidenceError('form-failed')
            return {'valid_choice': {'request': dict(CHOICES)}}
        return real_observe(operation)
    observer._observe = form_read
    if fault == 'failed-read':
        with pytest.raises(EvidenceError):
            observer.observe('kiosk-valid-fraction-soft-read')
    elif fault != 'missing-form':
        observer.observe('kiosk-valid-fraction-soft-read')
    current = 'a' if fault == 'same-challenge' else 'b'
    if fault in ('missing-form', 'same-challenge', 'failed-read'):
        with pytest.raises(EvidenceError, match='ui:'):
            observer.observe('kiosk-mate-open')
        with pytest.raises(EvidenceError, match='ui:'):
            observer.observe('kiosk-mate-open')
    else:
        observer.observe('kiosk-mate-open')
        if fault == 'changed-challenge':
            current = 'c'
            with pytest.raises(EvidenceError, match='replacement'):
                observer.observe('kiosk-mate-qualified')
        else:
            observer.observe('kiosk-mate-qualified')
            observer.observe('kiosk-mate-rechecked')


@pytest.mark.parametrize('restarts', [False, True])
def test_new_mate_challenge_binds_service_after_request(monkeypatch, restarts):
    operation = 'kiosk-mate-open'
    ui, desktop, agent, dialog, field, cancel, submit, message, recipient = mate_form()
    service = {'pid': 100}
    current_pid = 200 if restarts else 100
    ui.timeout = 1

    def service_pid():
        # MainPID can be zero during RestartUnit. No visible challenge means
        # the observer must wait, without querying or accepting that process.
        assert service['pid'] is not None
        return service['pid']

    ui.mate_agent_pid.side_effect = service_pid
    for node in (agent, dialog, field, cancel, message, recipient):
        node.get_process_id = lambda: current_pid
    identity = f'{current_pid:064x}'
    ui.mate_challenge_identity = Mock(return_value=identity)

    def present(_seconds=None):
        service['pid'] = current_pid
        desktop.children.append(agent)

    def request(_index):
        if restarts:
            service['pid'] = None
        else:
            present()
        return True

    submit.action.do_action.side_effect = request
    sleep = Mock(side_effect=present)
    monkeypatch.setattr(accessible_ui.time, 'sleep', sleep)
    result = ui.run(operation, '')
    assert result['approval'] == {'challenge_id': identity}
    ui.mate_challenge_identity.assert_called_once_with(current_pid,
                                                      (agent, dialog, field, cancel))
    ui.expected_mate_challenge = identity
    for suffix in ('qualified', 'rechecked'):
        assert ui.run('kiosk-mate-' + suffix, '')['approval'] == {'challenge_id': identity}
    cancel.action.do_action.assert_not_called()
    assert sleep.call_count == int(restarts)
    submit.action.do_action.assert_called_once()
    field.get_child_count.assert_not_called()
    field.get_description.assert_not_called()


@pytest.mark.parametrize('fault', ['foreign-agent', 'foreign-control', 'service-raced',
                                  'service-replaced', 'challenge-replaced'])
def test_restarted_mate_agent_keeps_ownership_and_challenge_guards(fault):
    ui, desktop, agent, dialog, field, cancel, submit, message, recipient = mate_form()
    service = {'pid': 100}
    ui.mate_agent_pid.side_effect = lambda: service['pid']
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    for node in (agent, dialog, field, cancel, message, recipient):
        node.get_process_id = lambda: 200

    def request(_index):
        service['pid'] = 200
        desktop.children.append(agent)
        if fault == 'foreign-agent':
            agent.get_process_id = lambda: 300
        elif fault == 'foreign-control':
            field.get_process_id = lambda: 300
        elif fault == 'service-raced':
            # The service changes while the already observed prompt is proved.
            ui.mate_agent_pid.side_effect = [200, 300]
        return True

    submit.action.do_action.side_effect = request
    if fault in ('service-replaced', 'challenge-replaced'):
        assert ui.run('kiosk-mate-open', '')['approval'] == {'challenge_id': 'a' * 64}
        ui.expected_mate_challenge = 'a' * 64
        if fault == 'service-replaced':
            service['pid'] = 300
        else:
            ui.mate_challenge_identity.return_value = 'b' * 64
        operation = 'kiosk-mate-qualified'
    else:
        operation = 'kiosk-mate-open'
    with pytest.raises(UiError, match='ui:mate-owner|ui:mate-replacement'):
        ui.run(operation, '')
    with pytest.raises(UiError, match='uncertain-input'):
        ui.run(operation, '')
    submit.action.do_action.assert_called_once()
    cancel.action.do_action.assert_not_called()
    field.get_child_count.assert_not_called()
    field.get_description.assert_not_called()


@pytest.mark.parametrize('state', ['visible', 'focused'])
@pytest.mark.parametrize('recovers', [True, False])
def test_initial_mate_prompt_waits_for_field_without_replaying_request(monkeypatch, state, recovers):
    ui, desktop, agent, dialog, field, cancel, submit, *_ = mate_form()
    field.states.discard(state)
    ui.timeout = 1 if recovers else 0
    ui.mate_challenge_identity = Mock(return_value='a' * 64)

    def restore(_seconds):
        submit.action.do_action.assert_called_once()
        cancel.action.do_action.assert_not_called()
        ui.mate_challenge_identity.assert_not_called()
        field.states.add(state)

    sleep = Mock(side_effect=restore)
    monkeypatch.setattr(accessible_ui.time, 'sleep', sleep)
    if recovers:
        assert ui.run('kiosk-mate-open', '')['approval'] == {'challenge_id': 'a' * 64}
        sleep.assert_called_once()
        ui.mate_challenge_identity.assert_called_once_with(100, (agent, dialog, field, cancel))
    else:
        with pytest.raises(UiError, match='^ui:timeout:mate-prompt$') as caught:
            ui.run('kiosk-mate-open', '')
        assert caught.value.authentication_field_state == {
            'provider': 'mate', 'showing': state != 'visible', 'sensitive': True,
            'focused': state != 'focused', 'stale': False}
        with pytest.raises(UiError, match='uncertain-input'):
            ui.run('kiosk-mate-open', '')
        sleep.assert_not_called()
        ui.mate_challenge_identity.assert_not_called()
    submit.action.do_action.assert_called_once()
    cancel.action.do_action.assert_not_called()
    field.get_child_count.assert_not_called()
    field.get_description.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'owner', 'challenge', 'focus', 'recipient', 'request',
                                  'field', 'timeout'])
def test_consumed_mate_input_waits_only_for_same_owned_recipient(monkeypatch, fault):
    ui, desktop, agent, dialog, field, cancel, submit, message, recipient = mate_form()
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    ui.run('kiosk-pause-mate-open', '')
    ui.expected_mate_challenge = 'a' * 64
    ui.timeout = 1
    now, samples = [100.0], []
    get_text = Mock(side_effect=AssertionError('password contents'))
    def length():
        samples.append(now[0])
        return 5 if not fault and now[0] >= 100.4 else 0
    field.get_text_iface = lambda: SimpleNamespace(get_character_count=length, get_text=get_text)
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: now[0])
    def sleep(seconds):
        now[0] += seconds
        if fault == 'owner': ui.mate_agent_pid.return_value = 101
        if fault == 'challenge': ui.mate_challenge_identity.return_value = 'b' * 64
        if fault == 'focus': field.states.discard('focused')
        if fault == 'recipient': recipient.name = 'Password for wrong-parent:'
        if fault == 'request': message.name = 'Changed request'
        if fault == 'field':
            replacement = Node(role='password text', states=('showing', 'visible', 'sensitive', 'focused'))
            replacement.get_text_iface = field.get_text_iface
            replacement.parent = dialog
            dialog.children[dialog.children.index(field)] = replacement
    monkeypatch.setattr(accessible_ui.time, 'sleep', sleep)
    if fault:
        with pytest.raises(UiError):
            ui.wait_filled_mate_prompt(100)
    else:
        assert ui.wait_filled_mate_prompt(100)[2] is field
        assert len(samples) >= 3 and now[0] >= 100.4
    assert now[0] <= 101.2
    get_text.assert_not_called()
    submit.action.do_action.assert_called_once()  # Original Request only.
    cancel.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'replacement', 'empty', 'uncertain', 'denied'])
def test_approval_submits_once_and_requires_explicit_success(fault):
    ui, desktop, agent, dialog, field, cancel, submit, *_ = mate_form()
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    ui.run('kiosk-mate-open', '')
    ui.expected_mate_challenge = 'b' * 64 if fault == 'replacement' else 'a' * 64
    field.get_text_iface = lambda: SimpleNamespace(get_character_count=lambda: 0 if fault == 'empty' else 5)
    authenticate = Node('Authenticate', 'push button')
    authenticate.parent = dialog
    dialog.children.append(authenticate)
    window = ui.find_id('kiosk-request-window')
    result = Node(identity='kiosk-result-page', children=[Node(
        'Request denied' if fault == 'denied' else 'Request approved', 'label', identity='kiosk-result-title')])
    result.parent = window
    exit_action = Node('Return to Login (3)', 'push button', identity='kiosk-result-action')
    exit_action.parent = result
    result.children.append(exit_action)
    operation = 'kiosk-mate-submit-success'
    def approve(_):
        desktop.children.remove(agent)
        window.children.append(result)
        return True
    authenticate.action.do_action.side_effect = approve
    if fault == 'uncertain':
        authenticate.action.do_action.side_effect = RuntimeError('private failure')
    if fault:
        with pytest.raises((UiError, RuntimeError)):
            ui.run(operation, '')
        with pytest.raises(UiError, match='uncertain'):
            ui.run(operation, '')
    else:
        assert ui.run(operation, '')['approval'] == {'approved': True, 'form_success': True}
    assert authenticate.action.do_action.call_count == (0 if fault in ('replacement', 'empty') else 1)
    exit_action.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'replay', 'changed', 'intervening', 'out-of-order', 'stale'])
def test_approval_controller_reconciles_fresh_proofs_and_latches(fault):
    observer = UiObservations(Mock())
    operations = ('kiosk-mate-open', 'kiosk-mate-qualified', 'kiosk-mate-rechecked',
                  'kiosk-mate-submit-success')
    def call(_args, operation, **_kwargs):
        approval = ({'approved': True, 'form_success': True} if operation.endswith('success') else
                    {'challenge_id': ('b' if fault == 'changed' and operation.endswith('rechecked') else 'a') * 64})
        value = {'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider', 'approval': approval}
        if operation != operations[0]:
            value['boot_sha256'] = 'c' * 64
        return json.dumps(value).encode(), []
    observer.call = Mock(side_effect=call)
    observer.observe(operations[0])
    if fault == 'stale':
        observer.mate_approval_checked = float('-inf')
    if fault:
        operation = {'replay': operations[0], 'intervening': 'desktop',
                     'out-of-order': operations[3], 'changed': operations[2],
                     'stale': operations[1]}[fault]
        if fault == 'changed':
            observer.observe(operations[1])
        with pytest.raises(Exception, match='ui:'):
            observer.observe(operation)
        with pytest.raises(Exception, match='ui:'):
            observer.observe(operations[1])
    else:
        for operation in operations[1:]:
            observer.observe(operation)


@pytest.mark.parametrize('fault', [None, 'missing-rejection', 'disappeared', 'wrong-owner',
                                  'duplicate-rejection', 'uncertain-cancel', 'changed-form'])
def test_rejection_requires_explicit_message_then_one_cancel_and_public_form(fault):
    ui, desktop, agent, dialog, field, cancel, submit, *_ = mate_form()
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    observer = UiObservations(Mock())
    def call(_args, operation, **_kwargs):
        ui.expected_mate_challenge = getattr(observer, 'mate_approval_identity', None)
        result = ui.run(operation, '')
        if operation != accessible_ui.MATE_REJECTION_ORDER[0]:
            result['boot_sha256'] = 'c' * 64
        return json.dumps(result).encode(), []
    observer.call = Mock(side_effect=call)
    for operation in accessible_ui.MATE_REJECTION_ORDER[:3]:
        observer.observe(operation)
    field.get_text_iface = lambda: SimpleNamespace(get_character_count=lambda: 5)
    authenticate = Node('Authenticate', 'push button')
    authenticate.parent = dialog
    dialog.children.append(authenticate)
    def reject(_):
        field.get_text_iface = lambda: SimpleNamespace(get_character_count=lambda: 0)
        if fault == 'disappeared':
            desktop.children.remove(agent)
        elif fault != 'missing-rejection':
            for _ in range(2 if fault == 'duplicate-rejection' else 1):
                label = Node('Your authentication attempt was unsuccessful. Please try again.', 'label')
                label.parent = dialog
                dialog.children.append(label)
        if fault == 'wrong-owner':
            agent.get_process_id = lambda: 999
        if fault == 'changed-form':
            ui.find_id('kiosk-soft-apps-toggle').states.discard('checked')
        return True
    authenticate.action.do_action.side_effect = reject
    if fault == 'uncertain-cancel':
        cancel.action.do_action.side_effect = RuntimeError('private failure')
    if fault:
        with pytest.raises((UiError, RuntimeError)):
            observer.observe(accessible_ui.MATE_REJECTION_ORDER[3])
    else:
        assert observer.observe(accessible_ui.MATE_REJECTION_ORDER[3])['approval'] == {
            'rejected': True, 'cancelled': True, 'no_error': True}
    with pytest.raises(Exception, match='ui:'):
        observer.observe(accessible_ui.MATE_REJECTION_ORDER[3])
    authenticate.action.do_action.assert_called_once()
    assert cancel.action.do_action.call_count == (1 if fault in (None, 'uncertain-cancel', 'changed-form') else 0)
    field.get_child_count.assert_not_called()
