"""Functional GUI selection tolerates decoration but refuses unusable controls."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
from accessible_ui import UiError, greeter_account, session_environment
from private_artifacts import EvidenceError
from ui_observations import UiObservations
from tests.support.accessible_ui import Node, ui_for


@pytest.mark.parametrize('fault', ['unknown-fields', 'symlink', 'other-owner', 'oversized'])
def test_crash_report_diagnostic_bounds_and_ownership(tmp_path, monkeypatch, fault):
    report = tmp_path / 'PRIVATE_REPORT.crash'
    if fault == 'symlink':
        target = tmp_path / 'PRIVATE_TARGET'
        target.write_text('ExecutablePath: /usr/bin/oh-no-parent-control\n')
        report.symlink_to(target)
    else:
        report.write_text('ExecutablePath: /home/PRIVATE_ACCOUNT/PRIVATE_PROGRAM\n'
                          'Signal: PRIVATE_PASSWORD\nProblemType: PRIVATE_DOCUMENT\n'
                          + ('X' * 200000 if fault == 'oversized' else ''))
    if fault == 'other-owner':
        monkeypatch.setattr(accessible_ui.os, 'geteuid', lambda: report.stat().st_uid + 1)
    value = accessible_ui.crash_report_diagnostic(str(tmp_path))
    if fault in ('symlink', 'other-owner'):
        assert value['reports'] == []
        assert value['unavailable'] == (1 if fault == 'symlink' else 0)
    else:
        summary = value['reports'][0]
        assert summary['executable'] == 'other' and summary['problem'] == 'other'
        assert summary['signal'] is None and summary['python'] is False
        assert summary['middle_omitted'] == (fault == 'oversized')
    assert 'PRIVATE_' not in json.dumps(value)


@pytest.mark.parametrize('expected', ['', 'b' * 64])
def test_ui_boot_guard_shares_one_transport_call_without_changing_ui_projection(expected):
    transport = SimpleNamespace(call=Mock(return_value=json.dumps({
        'operation': 'desktop', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
        'boot_sha256': 'b' * 64,
    }).encode()))
    observer = UiObservations(transport)
    observer.boot_guard = expected
    assert observer.observe('desktop') == {
        'operation': 'desktop', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
    assert observer.boot_proof == 'b' * 64
    transport.call.assert_called_once()
    assert transport.call.call_args.args[0][-1] == expected


@pytest.mark.parametrize('proof', [None, 'c' * 64, 'private-value', 1])
def test_ui_boot_proof_must_match_and_never_reuses_a_previous_reply(proof):
    result = {'operation': 'desktop', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
    if proof is not None:
        result['boot_sha256'] = proof
    observer = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode())))
    observer.boot_guard = 'b' * 64
    observer.boot_proof = 'b' * 64
    with pytest.raises(EvidenceError, match='ui:boot-changed'):
        observer.observe('desktop')
    assert observer.boot_proof is None


@pytest.mark.parametrize('raw,expected,code', [
    (b'00000000-0000-0000-0000-000000000001\n', 'b' * 64, 'boot-changed'),
    (b'invalid\n', '', 'boot-identity'),
    (b'', 'invalid', 'boot-binding'),
])
def test_guest_boot_refusal_precedes_identity_switch_and_ui_access(monkeypatch, raw, expected, code):
    monkeypatch.setattr(accessible_ui.sys, 'argv', ['observer', 'desktop', '1.1', expected])
    monkeypatch.setattr(accessible_ui, 'Path', Mock(return_value=SimpleNamespace(read_bytes=lambda: raw)))
    identity = Mock(side_effect=AssertionError('account access before boot refusal'))
    monkeypatch.setattr(accessible_ui.os, 'geteuid', identity)
    with pytest.raises(UiError, match=code):
        accessible_ui.main()
    identity.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'root', 'wrong-euid', 'foreign-user', 'remote',
                                   'inactive', 'wrong-seat', 'tty', 'duplicate', 'missing'])
def test_direct_parent_launch_requires_one_active_local_graphical_user(monkeypatch, fault):
    monkeypatch.setattr(accessible_ui.os, 'getuid', lambda: 0 if fault == 'root' else 1001)
    monkeypatch.setattr(accessible_ui.os, 'geteuid', lambda: 0 if fault in ('root', 'wrong-euid') else 1001)
    props = {'User': '1001', 'Active': 'yes', 'Remote': 'no', 'Class': 'user',
             'Type': 'wayland', 'Seat': 'seat0'}
    for kind, key, value in [('foreign-user', 'User', '1002'), ('remote', 'Remote', 'yes'),
                             ('inactive', 'Active', 'no'), ('wrong-seat', 'Seat', 'seat1'),
                             ('tty', 'Type', 'tty')]:
        if fault == kind:
            props[key] = value
    def call(argv, **kwargs):
        if argv[1] == 'list-sessions':
            value = '' if fault == 'missing' else '1 1001 fixture seat0\n'
            if fault == 'duplicate':
                value += '2 1001 fixture seat0\n'
        else:
            value = '\n'.join(key + '=' + value for key, value in props.items())
        return SimpleNamespace(stdout=value)
    monkeypatch.setattr(accessible_ui.subprocess, 'run', call)
    if fault:
        with pytest.raises(UiError):
            accessible_ui.require_active_launch_session()
    else:
        accessible_ui.require_active_launch_session()


def parent_save_ui(*, enabled=True, controls_enabled=True, child_uid=1001):
    control_states = ['showing', 'visible']
    if controls_enabled:
        control_states.append('sensitive')
    toggle_states = [*control_states, *(['checked'] if enabled else [])]
    allowance_states = [
        'showing', 'visible',
        *(['sensitive'] if enabled and controls_enabled else []),
    ]
    selected = Node(
        '', 'panel', identity=f'parent-child-selected-{child_uid}',
        children=[Node('Riley (Child)', 'label')])
    picker = Node(
        'Selected child', 'button', states=control_states,
        identity='parent-child-selector', children=[selected], value=str(child_uid))
    toggle = Node(
        'Screen time limit', 'switch', states=toggle_states,
        identity='parent-screen-limit-toggle')
    allowance = Node(
        '30 minutes', 'button', states=allowance_states,
        identity='parent-daily-limit-selector', value='30m')
    root = Node(
        'Oh No! Parent Control', identity='parent-window',
        children=[picker, toggle, allowance])
    return ui_for(root), root, picker, toggle, allowance


def time_explanation_ui():
    ui, root, picker, _toggle, _allowance = parent_save_ui()
    explanation = Node('Daily allowance remaining: 15m\nOne-time grant remaining: 0m\n'
                       'Remaining time: 15m — the larger of the two amounts.', 'label',
                       identity='parent-time-explanation')
    collapse = Node(identity='parent-time-calculation-collapse')
    section = Node(identity='parent-time-status', children=[explanation, collapse])
    root.children.append(section)
    section.parent = root
    return ui, root, picker, section, explanation, collapse


@pytest.mark.parametrize('fault', ['', 'authority', 'child', 'warning', 'disabled', 'duplicate', 'uncertain'])
def test_revoke_confirm_requires_explicit_authority_and_fresh_owned_target(fault):
    ui, root, picker, *_ = time_explanation_ui()
    warning = Node('This will revoke one-time screen time and access to soft blocked apps '
        'granted to Riley (Child), close their running blocked apps, and lock their desktop '
        'when no time remains. Their remaining daily time allowance is not impacted.',
        'label', identity='parent-revoke-warning')
    cancel, confirm = Node(identity='parent-revoke-cancel'), Node(identity='parent-revoke-confirm')
    dialog = Node(identity='parent-revoke-dialog', children=[warning, cancel, confirm],
                  states=('showing', 'visible', 'sensitive', 'active', 'modal'))
    application = ui.root()
    application.children.append(dialog)
    dialog.parent = application
    dialog.relations = [SimpleNamespace(get_relation_type=lambda: 'controlled-by',
        get_n_targets=lambda: 1, get_target=lambda _: root)]
    confirm.action.do_action.side_effect = lambda _: (application.children.remove(dialog) or True)
    if fault == 'authority': ui.revoke_warning = Mock(side_effect=AssertionError('no discovery'))
    if fault == 'child': picker.children[0].identity = 'parent-child-selected-1002'
    if fault == 'warning': warning.name = warning.name.replace('Riley', 'Jordan')
    if fault == 'disabled': confirm.states.remove('sensitive')
    if fault == 'duplicate': dialog.children.append(Node(identity='parent-revoke-confirm'))
    if fault == 'uncertain': ui.input_uncertain = True
    if fault:
        with pytest.raises(UiError): ui.confirm_revoke(accessible_ui.CHILD, confirm=fault != 'authority')
        confirm.action.do_action.assert_not_called()
    else:
        assert ui.confirm_revoke(accessible_ui.CHILD, confirm=True) == {
            'child': 'fixture-child', 'confirmed': True}
        confirm.action.do_action.assert_called_once()
    cancel.action.do_action.assert_not_called()


def semantic_gdm_ui(*, rows=(), recipient=None, field=None, applications=()):
    children = list(rows)
    if recipient is not None:
        children.append(recipient)
    if field is not None:
        children.append(field)
    shell = Node('GNOME Shell', 'application', children=children)
    root = Node(role='desktop frame', children=[shell, *applications])
    ui = ui_for(root)
    ui.api.Text = SimpleNamespace(
        get_character_count=Mock(side_effect=AssertionError('password length read')),
        get_text=Mock(side_effect=AssertionError('password text read')),
    )
    return ui, shell


def semantic_gdm_rows(*, focused=None, other=False, standard=False):
    parent = Node('Jamie (Parent)', 'push button')
    station = Node('Oh No! Parent Control', 'push button')
    if focused == 'parent': parent.states.add('focused')
    if focused == 'station': station.states.add('focused')
    if not other and not standard:
        return parent, station
    rows = [parent]
    other_parent = Node('Casey (Parent)', 'push button')
    if focused == 'other-parent': other_parent.states.add('focused')
    if other:
        rows.append(other_parent)
    standard_user = Node('Jordan (Child)', 'push button')
    if focused == 'standard': standard_user.states.add('focused')
    if standard:
        rows.append(standard_user)
    return (*rows, station)


def semantic_keyring_ui(*, fault=None):
    field = Node('', 'password text', states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = lambda: field
    field.get_child_count = Mock(side_effect=AssertionError('secret traversed'))
    cancel = Node('Cancel', 'push button')
    controls = [field, cancel]
    if fault == 'duplicate-cancel': controls.append(Node('Cancel', 'push button'))
    if fault == 'unfocused': field.states.remove('focused')
    if fault == 'hidden': cancel.states.remove('showing')
    if fault == 'disabled': cancel.states.remove('sensitive')
    if fault == 'unmasked': field.role = 'text'
    dialog = Node('Unlock Login Keyring', 'dialog', children=controls)
    dialogs = [dialog]
    if fault == 'extra-modal': dialogs.append(Node('Unexpected', 'dialog'))
    owner = Node('gcr Prompter', 'application', children=dialogs,
                 states=('defunct',) if fault == 'stale-owner' else ())
    if fault == 'wrong-owner': owner.name = 'Unknown Agent'
    if fault == 'wrong-dialog': dialog.name = 'Authentication Required'
    shell = Node('GNOME Shell', 'application', children=[Node('Activities', 'toggle button')])
    root = Node(role='desktop frame', children=[shell, owner])
    ui = ui_for(root, provider_contracts={})
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: 1 if fault == 'nonempty' else 0,
                                  get_text=Mock(side_effect=AssertionError('secret read')))
    return ui, root, owner, field, cancel


@pytest.mark.parametrize('fault', ['duplicate-cancel', 'extra-modal', 'unfocused', 'hidden', 'disabled',
                                   'unmasked', 'wrong-owner', 'stale-owner', 'wrong-dialog', 'nonempty'])
def test_semantic_keyring_cancel_refuses_unsafe_target_without_input(fault):
    ui, _root, _owner, field, cancel = semantic_keyring_ui(fault=fault)
    with pytest.raises(UiError):
        ui.keyring_cancel_target()
    cancel.action.do_action.assert_not_called()
    field.get_child_count.assert_not_called()
    ui.api.Text.get_text.assert_not_called()


def test_semantic_keyring_cancel_latches_uncertain_action():
    ui, _root, _owner, _field, cancel = semantic_keyring_ui()
    cancel.action.do_action.return_value = False
    ui.standard_shell_desktop = Mock()
    with pytest.raises(UiError, match='action-refused'):
        ui.cancel_keyring_prompt()
    assert ui.input_uncertain
    with pytest.raises(UiError, match='uncertain-input'):
        ui.cancel_keyring_prompt()
    cancel.action.do_action.assert_called_once_with(0)
    ui.standard_shell_desktop.assert_not_called()


@pytest.mark.parametrize('operation', [
    'gdm-parent-recipient',
])
@pytest.mark.parametrize('fault', [
    None, 'wrong-recipient', 'duplicate-recipient', 'missing-field', 'duplicate-field',
    'unfocused', 'hidden', 'disabled', 'nonempty', 'unmasked', 'list-visible',
])
def test_semantic_gdm_recipient_requires_one_bound_identity_and_empty_masked_focus(
        operation, fault):
    expected = (accessible_ui.EXISTING_CHILD
                if operation.startswith('gdm-standard-') else accessible_ui.CHILD
                if operation.startswith('gdm-child-') else accessible_ui.PARENT)
    recipient = Node(
        'Casey (Parent)' if fault == 'wrong-recipient' else expected, 'label')
    field = Node('Password', 'text' if fault == 'unmasked' else 'password text',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    if fault in ('unfocused', 'hidden', 'disabled'):
        field.states.remove({
            'unfocused': 'focused', 'hidden': 'showing', 'disabled': 'sensitive'}[fault])
    field.get_text_iface = lambda: field
    field.get_child_count = Mock(side_effect=AssertionError('password traversed'))
    rows = []
    if fault == 'list-visible':
        rows = list(semantic_gdm_rows())
    ui, shell = semantic_gdm_ui(
        rows=rows, recipient=recipient,
        field=None if fault == 'missing-field' else field)
    if fault == 'duplicate-recipient':
        duplicate = Node(expected, 'label')
        duplicate.parent = shell
        shell.children.append(duplicate)
    if fault == 'duplicate-field':
        duplicate = Node('Other password', 'password text')
        duplicate.parent = shell
        shell.children.append(duplicate)
    ui.api.Text = SimpleNamespace(
        get_character_count=Mock(return_value=1 if fault == 'nonempty' else 0),
        get_text=Mock(side_effect=AssertionError('password text read')),
    )
    if fault is None:
        assert ui.run(operation, '')['outcome'] == 'passed'
    else:
        with pytest.raises(UiError):
            ui.run(operation, '')
    ui.api.Text.get_text.assert_not_called()
    field.get_child_count.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'missing', 'symlink', 'regular',
                                   'wrong-owner', 'runtime-symlink', 'runtime-wrong-owner'])
def test_public_bus_discovery_is_owned_and_bounded(short_runtime, fault, monkeypatch, capsys):
    monkeypatch.setattr('accessible_ui.runtime_failure_diagnostic', Mock())
    import os
    import socket
    from pathlib import Path
    tmp_path = short_runtime
    account = SimpleNamespace(pw_uid=os.getuid())
    runtime = tmp_path / str(account.pw_uid)
    directory = runtime
    directory.mkdir(parents=True)
    bus = directory / 'bus'
    sockets = []
    try:
        if fault == 'regular': bus.touch()
        elif fault != 'missing':
            connection = socket.socket(socket.AF_UNIX)
            sockets.append(connection)
            connection.bind(str(bus))
        if fault == 'symlink':
            bus.rename(directory / 'original')
            bus.symlink_to(directory / 'original')
        if fault == 'runtime-symlink':
            directory.rename(tmp_path / 'original')
            directory.symlink_to(tmp_path / 'original')
        if fault in ('wrong-owner', 'runtime-wrong-owner'):
            original = Path.lstat
            def wrong_owner(path):
                info = original(path)
                if path == (runtime if fault == 'runtime-wrong-owner' else bus):
                    return SimpleNamespace(st_mode=info.st_mode, st_uid=account.pw_uid + 1)
                return info
            monkeypatch.setattr(Path, 'lstat', wrong_owner)
        if fault:
            with pytest.raises(UiError):
                session_environment(account, runtime_root=tmp_path, timeout=0)
            if fault != 'missing':
                import json
                diagnostic = json.loads(capsys.readouterr().err)
                assert diagnostic['event'] == 'ui-runtime-binding-refused'
                assert diagnostic['object'] == ('runtime' if fault.startswith('runtime-')
                                                else 'session-bus')
                assert diagnostic['owner'] == ('other' if fault.endswith('wrong-owner')
                                               else 'expected')
                assert diagnostic['elapsed_ms'] >= 0
        else:
            result = session_environment(account, runtime_root=tmp_path, timeout=0)
            key = 'DBUS_SESSION_BUS_ADDRESS'
            assert result == {'XDG_RUNTIME_DIR': str(runtime), key: 'unix:path=' + str(bus)}
    finally:
        for connection in sockets: connection.close()


@pytest.mark.parametrize('fault', [None, 'duplicate', 'remote', 'inactive', 'desktop', 'wrong-seat', 'root'])
def test_greeter_identity_uses_unique_active_local_session_not_legacy_uid(monkeypatch, fault):
    import accessible_ui
    clock = [0.0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda delay: clock.__setitem__(0, clock[0] + delay))
    props = {'Class': 'greeter', 'Active': 'yes', 'Remote': 'no', 'Type': 'wayland',
             'Seat': 'seat0', 'User': '61234'}
    if fault == 'remote': props['Remote'] = 'yes'
    if fault == 'inactive': props['Active'] = 'no'
    if fault == 'desktop': props['Class'] = 'user'
    if fault == 'wrong-seat': props['Seat'] = 'seat1'
    if fault == 'root': props['User'] = '0'
    def call(argv, **kwargs):
        assert argv[0] == '/usr/bin/loginctl' and 0 < kwargs['timeout'] <= 5
        if argv[1] == 'list-sessions':
            return SimpleNamespace(stdout='c1 private-name\n' + ('c2 private-name\n' if fault == 'duplicate' else ''))
        return SimpleNamespace(stdout='\n'.join(key + '=' + value for key, value in props.items()))
    monkeypatch.setattr(accessible_ui.subprocess, 'run', call)
    account = SimpleNamespace(pw_uid=61234)
    lookup = Mock(return_value=account)
    monkeypatch.setattr(accessible_ui.pwd, 'getpwuid', lookup)
    if fault:
        with pytest.raises(UiError): greeter_account()
        lookup.assert_not_called()
        if fault in ('duplicate', 'root'):
            assert clock[0] == 0
    else:
        assert greeter_account() is account
        lookup.assert_called_once_with(61234)


@pytest.mark.parametrize('keys', [[], ['esc'], ['ret'], ['esc', 'esc'], 'esc', None, ['home']])
def test_system_prompt_checkpoint_cannot_authorize_unobserved_keyboard_input(keys):
    result = {'operation': 'standard-system-prompt', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
              'navigation': keys}
    session = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode())))
    with pytest.raises(EvidenceError, match='response'):
        session.observe('standard-system-prompt')


def test_streamed_prompt_input_is_narrow_ordered_and_restores_command_parser():
    operation = 'standard-system-prompt'
    prompt = {'event': 'system-prompt', 'kind': 'login-keyring', 'pointer': {'x': 200, 'y': 330}}
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
    values = [prompt, result]
    raw = b''.join(json.dumps(value).encode() + b'\n' for value in values)
    previous = Mock()
    commands = SimpleNamespace(progress=previous)
    def call(*_, on_output, **__):
        commands.progress = on_output
        # Exercise arbitrary SSH output chunk boundaries.
        for offset in range(0, len(raw), 13): commands.progress(raw[offset:offset + 13])
        return raw
    def cancel(_):
        assert commands.progress is previous
    handler = Mock(side_effect=cancel)
    session = UiObservations(SimpleNamespace(commands=commands, call=call), system_prompt=handler)
    with pytest.raises(EvidenceError, match='prompt-coordinate-route-refused'):
        session.observe(operation)
    handler.assert_not_called()
    assert commands.progress is previous
