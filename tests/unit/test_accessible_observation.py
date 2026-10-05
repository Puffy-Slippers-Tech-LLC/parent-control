"""Read-boundary cost, freshness and shared-operation input safety."""

from unittest.mock import Mock
from types import SimpleNamespace

import pytest

import accessible_ui
from accessible_ui import UiError
from tests.support.accessible_ui import Node, ui_for


def arbitrary_ui(count=3):
    controls = [Node(role='push button', identity=f'future-control-{index}')
                for index in range(count)]
    surface = Node(identity='future-surface', children=controls)
    app = Node(role='application', identity='future-app', children=[surface])
    desktop = Node(role='desktop frame', children=[app])
    contracts = {'future-provider': {
        'application_id': 'future-app',
        'surfaces': {'future-surface': ('future-surface', {
            str(index): node.identity for index, node in enumerate(controls)})},
    }}
    ui = ui_for(desktop, provider_contracts=contracts)
    ui._read_nodes = Mock(wraps=ui._read_nodes)
    return ui, desktop, surface, controls


@pytest.mark.parametrize('windows,expected_error', [
    (1, None), (0, 'parent-window-count'),
    (2, 'ambiguous-automation-id'),
])
def test_parent_management_window_count_uses_complete_owned_ids(windows, expected_error):
    children = [Node(identity='parent-window', name='Oh No! Parent Control')
                for _ in range(windows)]
    app = Node(role='application', identity=accessible_ui.PARENT_APPLICATION,
               children=children)
    ui = ui_for(Node(role='desktop frame', children=[app]))
    if expected_error:
        with pytest.raises(UiError, match=expected_error):
            ui.parent_window_count()
    else:
        assert ui.parent_window_count() == 1


def lookup(ui, index):
    return ui.find_provider_control('future-provider', 'future-surface', str(index))


@pytest.mark.parametrize('fault,code', [
    ('child', 'wrong-child'), ('disabled', 'unusable-target'),
    ('textbox', 'allowance-textbox'), ('inactive', 'allowance-window'), ('owner', 'wrong-owner'),
])
def test_allowance_keyboard_refuses_unsafe_recipient(preset_ui, fault, code):
    ui, window, selector, choice = preset_ui
    window.states.add('active')
    with ui.observation():
        ui.activate_id(selector.identity)
    choice.states.add('focused')
    if fault == 'child':
        window.children[0].children[0].identity = 'parent-child-selected-1002'
    elif fault == 'disabled':
        selector.states.remove('sensitive')
    elif fault == 'textbox':
        selector.states.add('editable')
    elif fault == 'inactive':
        window.states.remove('active')
    else:
        ui.root().get_process_id = lambda: 101
    choice.action.do_action.reset_mock()
    with pytest.raises(UiError, match=code):
        ui.allowance_keyboard_recipient(accessible_ui.CHILD)
    choice.action.do_action.assert_not_called()


@pytest.mark.parametrize('expanded', [False, True])
def test_allowance_keyboard_does_not_require_popup_or_focus(preset_ui, expanded):
    ui, window, selector, _ = preset_ui
    window.states.add('active')
    if expanded:
        selector.states.add('expanded')
    assert ui.allowance_keyboard_recipient(accessible_ui.CHILD) is selector


def test_allowance_selected_reads_saved_value_without_popup_state(preset_ui):
    ui, _window, selector, _ = preset_ui
    ui.parent_save_snapshot = Mock()
    selector.states.add('expanded')  # This metadata is not an acceptance oracle.
    assert ui.allowance_keyboard(accessible_ui.CHILD, 15, 'selected') == {
        'value': 15, 'phase': 'selected'}
    ui.parent_save_snapshot.assert_called_once_with(accessible_ui.CHILD, True)


def test_allowance_ready_clicks_closed_selector_without_synthetic_focus(preset_ui):
    ui, window, selector, choice = preset_ui
    window.states.add('active')
    ui.parent_save_snapshot = Mock()
    ui.reach_time_explanation = Mock()
    ui.activate_id = Mock()
    ui.select_allowance = Mock()
    selector.component.get_extents = Mock(return_value=SimpleNamespace(x=100, y=200, width=80, height=40))
    assert ui.allowance_keyboard(accessible_ui.CHILD, 15, 'click') == {
        'value': 15, 'phase': 'click'}
    ui.select_allowance.assert_called_once_with(accessible_ui.CHILD, 15)
    ui.activate_id.assert_not_called()
    selector.action.do_action.assert_not_called()
    assert 'expanded' not in selector.states


@pytest.mark.parametrize('bounds', [(-2147483648, 0, 80, 40), (0, 0, 0, 40),
                                   (0, 0, 80, -1), (32760, 0, 80, 40),
                                   (True, 0, 80, 40)])
def test_allowance_click_refuses_invalid_public_bounds(preset_ui, bounds):
    ui, window, selector, _ = preset_ui
    window.states.add('active')
    selector.component.get_extents = Mock(return_value=SimpleNamespace(
        **dict(zip(('x', 'y', 'width', 'height'), bounds))))
    with pytest.raises(UiError, match='allowance-click-bounds'):
        ui.allowance_click_target()


@pytest.fixture
def native_allowance_transport(preset_ui, monkeypatch):
    from gi.repository import Gio, GLib
    ui, window, selector, _ = preset_ui
    window.states.add('active')
    selector.component.get_extents = Mock(return_value=SimpleNamespace(
        x=100, y=200, width=80, height=40))
    transport = SimpleNamespace(events=[], calls=[], fail=None, on_call=None,
                                error_message='PRIVATE_PROVIDER_VALUE',
                                error_domain=Gio.io_error_quark(),
                                error_code=Gio.IOErrorEnum.FAILED)
    def invoke(_service, _path, _interface, method, arguments, *_rest):
        args = arguments.unpack() if arguments is not None else ()
        transport.events.append((method, args))
        transport.calls.append((_interface, method, args))
        if transport.on_call:
            transport.on_call(_interface, method, args)
        if transport.fail and transport.fail(_interface, method, args):
            raise GLib.Error.new_literal(transport.error_domain, transport.error_message,
                                        transport.error_code)
        values = {'CreateSession': ('/session',), 'Get': ('session-id',),
                  'RecordWindow': ('/stream',)}.get(method, ())
        return SimpleNamespace(unpack=lambda: values)
    connection = SimpleNamespace(call_sync=invoke, close_sync=Mock())
    transport.connection = connection
    monkeypatch.setattr(Gio.DBusConnection, 'new_for_address_sync', Mock(return_value=connection))
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/fixture-bus')
    monkeypatch.setattr(accessible_ui.time, 'sleep',
                        lambda delay: transport.events.append(('dispatch', delay)))
    return ui, window, selector, transport


@pytest.mark.parametrize('failure,interface,method,arguments,uncertain', [
    (None, None, None, None, False),
    ('remote-start', 'RemoteDesktop.Session', 'Start', (), False),
    ('stream-start', 'ScreenCast.Stream', 'Start', (), False),
    ('record-window', 'ScreenCast.Session', 'RecordWindow', ({},), False),
    ('motion', 'RemoteDesktop.Session', 'NotifyPointerMotionAbsolute', ('/stream', 140.0, 220.0), True),
    ('button', 'RemoteDesktop.Session', 'NotifyPointerButton', (272, True), True),
    ('shift-press', 'RemoteDesktop.Session', 'NotifyKeyboardKeysym', (0xffe1, True), True),
    ('shift-release', 'RemoteDesktop.Session', 'NotifyKeyboardKeysym', (0xffe1, False), True),
    ('product-key', 'RemoteDesktop.Session', 'NotifyKeyboardKeysym', (ord('1'), True), True),
    ('stop', 'RemoteDesktop.Session', 'Stop', (), True),
])
def test_allowance_native_click_delivery_and_failure_lifetime(
        native_allowance_transport, failure, interface, method, arguments, uncertain):
    ui, _window, selector, transport = native_allowance_transport
    events = transport.events
    transport.fail = lambda actual_interface, actual_method, args: (
        actual_interface == 'org.gnome.Mutter.' + interface
        and actual_method == method and args == arguments) if failure else False
    if failure:
        with pytest.raises(UiError, match='allowance-click-transport:' + method) as raised:
            ui.select_allowance(accessible_ui.CHILD, 15)
        assert 'PRIVATE_' not in str(raised.value)
        assert ui.input_uncertain == uncertain
        if ui.input_uncertain:
            delivered = list(events)
            with pytest.raises(UiError, match='input-uncertain'):
                ui.select_allowance(accessible_ui.CHILD, 15)
            assert events == delivered
        if failure in ('remote-start', 'stream-start', 'record-window', 'shift-press', 'shift-release'):
            assert not any(name in ('NotifyPointerMotionAbsolute', 'NotifyPointerButton')
                           for name, _ in events)
            assert all(args[0] == 0xffe1 for name, args in events
                       if name == 'NotifyKeyboardKeysym')
    else:
        ui.select_allowance(accessible_ui.CHILD, 15)
        warm_keyboard = events.index(('NotifyKeyboardKeysym', (0xffe1, False)))
        bind_window = events.index(('RecordWindow', ({},)))
        motion = events.index(('NotifyPointerMotionAbsolute', ('/stream', 140.0, 220.0)))
        assert warm_keyboard < bind_window < motion
        assert [args for name, args in events[:motion] if name == 'NotifyKeyboardKeysym'] == [
            (0xffe1, True), (0xffe1, False)]
        assert ('org.gnome.Mutter.RemoteDesktop.Session', 'Start', ()) in transport.calls
        assert ('org.gnome.Mutter.ScreenCast.Stream', 'Start', ()) in transport.calls
        assert events[bind_window + 1] == ('Start', ())
        assert events[motion:] == [
            ('NotifyPointerMotionAbsolute', ('/stream', 140.0, 220.0)),
            ('dispatch', .1), ('NotifyPointerButton', (272, True)),
            ('dispatch', .15), ('NotifyPointerButton', (272, False)),
            ('dispatch', .1),
            *[event for key in (ord('1'), ord('5'), ord('m'), 0xff0d)
              for event in (('NotifyKeyboardKeysym', (key, True)), ('dispatch', .05),
                            ('NotifyKeyboardKeysym', (key, False)), ('dispatch', .05))],
            ('Stop', ())]
        assert not ui.input_uncertain
    assert sum(name == 'Stop' for name, _ in events) == (failure != 'remote-start')
    transport.connection.close_sync.assert_called_once_with(None)
    selector.action.do_action.assert_not_called()


@pytest.mark.parametrize('boundary,fault,code', [
    ('warm-up', 'owner', 'wrong-owner'),
    ('warm-up', 'child', 'wrong-child'),
    ('stream-start', 'inactive', 'allowance-window'),
    ('stream-start', 'bounds', 'allowance-click-moved'),
])
def test_allowance_native_click_rechecks_identity_and_bounds_before_delivery(
        native_allowance_transport, boundary, fault, code):
    ui, window, selector, transport = native_allowance_transport
    def change_target(interface, method, args):
        if ((boundary == 'warm-up' and method == 'NotifyKeyboardKeysym'
             and args == (0xffe1, False)) or
                (boundary == 'stream-start' and interface == 'org.gnome.Mutter.ScreenCast.Stream'
                 and method == 'Start')):
            if fault == 'owner':
                ui.root().get_process_id = lambda: 101
            elif fault == 'child':
                window.children[0].children[0].identity = 'parent-child-selected-1002'
            elif fault == 'inactive':
                window.states.remove('active')
            else:
                selector.component.get_extents.return_value.x += 1
    transport.on_call = change_target
    with ui.observation():
        with pytest.raises(UiError, match=code):
            ui.select_allowance(accessible_ui.CHILD, 15)
    assert not ui.input_uncertain
    assert not any(name in ('NotifyPointerMotionAbsolute', 'NotifyPointerButton')
                   for name, _ in transport.events)
    assert [args for name, args in transport.events if name == 'NotifyKeyboardKeysym'] == [
        (0xffe1, True), (0xffe1, False)]
    assert sum(name == 'RecordWindow' for name, _ in transport.events) == (boundary == 'stream-start')
    assert transport.events[-1] == ('Stop', ())
    transport.connection.close_sync.assert_called_once_with(None)


@pytest.mark.parametrize('message,reason', [
    ('GDBus.Error:org.freedesktop.DBus.Error.Failed: Window not found', 'window-not-found'),
    ('Failed to record window: Main logical monitor not found', 'window-monitor'),
    ('Permission denied', 'permission-denied'),
    ('PRIVATE_PROVIDER_VALUE', 'other'),
    ('PRIVATE_PROVIDER_VALUE', 'unknown-method'),
])
def test_allowance_native_window_error_uses_finite_diagnostic(
        native_allowance_transport, message, reason):
    ui, _window, _selector, transport = native_allowance_transport
    transport.fail = lambda _interface, method, _args: method == 'RecordWindow'
    transport.error_message = message
    if reason == 'unknown-method':
        from gi.repository import Gio
        transport.error_domain = Gio.dbus_error_quark()
        transport.error_code = Gio.DBusError.UNKNOWN_METHOD
    with pytest.raises(UiError) as raised:
        ui.select_allowance(accessible_ui.CHILD, 15)
    assert str(raised.value) == 'ui:allowance-click-transport:RecordWindow:' + reason
    assert not ui.input_uncertain
    assert transport.events[-1] == ('Stop', ())
    transport.connection.close_sync.assert_called_once_with(None)


def test_allowance_native_cleanup_preserves_primary_uncertain_input_error(native_allowance_transport):
    ui, _window, _selector, transport = native_allowance_transport
    transport.fail = lambda _interface, method, args: (
        method == 'Stop' or method == 'NotifyKeyboardKeysym' and args == (ord('1'), True))
    with pytest.raises(UiError) as raised:
        ui.select_allowance(accessible_ui.CHILD, 15)
    assert str(raised.value) == 'ui:allowance-click-transport:NotifyKeyboardKeysym:other'
    assert raised.value.__notes__ == ['ui:allowance-click-transport:Stop:other']
    assert ui.input_uncertain
    assert transport.events[-1] == ('Stop', ())
    transport.connection.close_sync.assert_called_once_with(None)


@pytest.fixture
def preset_ui():
    label = Node('15 minutes', 'label')
    allowance = Node(identity='parent-daily-limit-selector', children=[label])
    choice = Node(identity='parent-daily-limit-15',
                  description='Selected daily allowance: 15 minutes')
    choices = Node(identity='parent-daily-limit-choices', children=[choice])
    selected = Node(identity='parent-child-selected-1001',
                    children=[Node(accessible_ui.CHILD, 'label')])
    picker = Node(identity='parent-child-selector', children=[selected])
    toggle = Node(identity='parent-screen-limit-toggle',
                  states=('showing', 'visible', 'sensitive', 'checked'))
    window = Node(identity='parent-window', children=[picker, toggle, allowance])
    ui = ui_for(window)
    ui.owner_pids = lambda: {100}
    ui._read_nodes = Mock(wraps=ui._read_nodes)

    def open_picker(_index):
        assert ui._observation_cache == []
        choices.parent = allowance
        allowance.children = [label, choices]
        allowance.states.add('expanded')
        return True

    def select(_index):
        assert ui._observation_cache == []
        # Replace the accessible as GTK may do; a stale tree cannot read this result.
        replacement = Node('15 minutes', 'label')
        replacement.parent = allowance
        allowance.children = [replacement]
        allowance.states.discard('expanded')
        return True

    allowance.action.do_action.side_effect = open_picker
    choice.action.do_action.side_effect = select
    return ui, window, allowance, choice


def test_preset_final_read_never_activates_a_choice(preset_ui):
    ui, _window, selector, choice = preset_ui
    assert ui.allowance_preset(accessible_ui.CHILD, 15, action='read')['saved']
    selector.action.do_action.assert_not_called()
    choice.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault,code', [('duplicate', 'ambiguous-automation-id'),
                                     ('owner', 'wrong-owner'), ('child', 'wrong-child')])
def test_independent_preset_calls_recheck_identity(preset_ui, fault, code):
    ui, window, allowance, _choice = preset_ui
    ui.allowance_preset(accessible_ui.CHILD, 15, action='read')
    if fault == 'duplicate':
        window.children.append(Node(identity=allowance.identity))
    elif fault == 'owner':
        ui.root().get_process_id = lambda: 101
    else:
        window.children[0].children[0].identity = 'parent-child-selected-1002'
    ui.select_allowance = Mock()
    with pytest.raises(UiError, match=code):
        ui.allowance_preset(accessible_ui.CHILD, 15, action='select')
    ui.select_allowance.assert_not_called()


@pytest.mark.parametrize('fault', ['pending', 'incomplete', 'query-error'])
def test_preset_result_retry_reacquires_without_replaying_input(preset_ui, monkeypatch, fault):
    ui, _window, allowance, _choice = preset_ui
    ui.timeout = .4
    ui.query_errors = (LookupError,)
    ui.dispatch = Mock(return_value=False)
    now = [0.0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: now[0])
    original_attributes = allowance.get_attributes
    def select(_child, _value):
        ui.invalidate_observation()
        allowance.children = [Node('0 minutes', 'label')]
        if fault != 'pending':
            allowance.get_attributes = Mock(side_effect=(LookupError() if fault == 'query-error'
                                                        else UiError('ui:incomplete-tree')))
    ui.select_allowance = Mock(side_effect=select)
    def settle(delay):
        now[0] += delay
        allowance.get_attributes = original_attributes
        allowance.children = [Node('15 minutes', 'label')]
    monkeypatch.setattr(accessible_ui.time, 'sleep', settle)
    assert ui.allowance_preset(accessible_ui.CHILD, 15, action='select')['saved']
    ui.select_allowance.assert_called_once_with(accessible_ui.CHILD, 15)


@pytest.mark.parametrize('count', [3, 100, 1000])
def test_future_controls_share_one_tree_across_nested_helpers_and_waits(count):
    ui, desktop, surface, controls = arbitrary_ui(count)
    ui.prompt_enabled = True
    ui.prompt_session = 'desktop'
    ui.dispatch = Mock(return_value=False)
    for control in controls:
        control.get_attributes = Mock(wraps=control.get_attributes)
        control.get_accessible_id = Mock(wraps=control.get_accessible_id)

    def operation(_name, _version, *, child):
        for index in (0, count // 2, count - 1):
            assert ui.wait(lambda: lookup(ui, index), 'future-ready') is controls[index]
        # The generic ID reader can project the same complete snapshot too.
        assert ui.find_id(controls[0].identity, root=surface) is controls[0]
        return True

    ui._run = operation  # A future operation needs no element-specific cache code.
    assert ui.run('future-operation', '')
    assert ui._observation_cache is None
    ui._read_nodes.assert_called_once()
    ui.dispatch.assert_called_once_with()
    for control in controls:
        control.get_attributes.assert_called_once_with()
        control.get_accessible_id.assert_called_once_with()


def test_public_input_invalidates_every_scope_before_dispatch_and_rechecks_ambiguity():
    ui, _desktop, surface, controls = arbitrary_ui()
    ui.api.invalidate_snapshot = Mock()
    def action(_index):
        assert ui._observation_cache == []
        ui.api.invalidate_snapshot.assert_called_once_with()
        duplicate = Node(identity=controls[1].identity)
        duplicate.parent = surface
        surface.children.append(duplicate)
        return True
    controls[0].action.do_action.side_effect = action

    with ui.observation():
        assert lookup(ui, 1) is controls[1]
        assert ui._projection_cache
        ui.activate_provider('future-provider', 'future-surface', '0')
        with pytest.raises(UiError, match='ambiguous-automation-id'):
            lookup(ui, 1)
    assert ui._read_nodes.call_count == 2
    controls[0].action.do_action.assert_called_once_with(0)


def test_uncertain_input_still_refuses_replay_after_cache_invalidation():
    ui, _desktop, _surface, controls = arbitrary_ui()
    controls[0].action.do_action.return_value = False
    with ui.observation():
        with pytest.raises(UiError, match='action-refused'):
            ui.activate_provider('future-provider', 'future-surface', '0')
        with pytest.raises(UiError, match='uncertain-input'):
            ui.activate_provider('future-provider', 'future-surface', '0')
    controls[0].action.do_action.assert_called_once_with(0)


def test_nested_retry_discards_outer_snapshot_and_dispatches_before_reacquisition(monkeypatch):
    ui, _desktop, surface, controls = arbitrary_ui()
    ui.timeout = 1
    clock = [0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: clock[0])
    replacement = Node(identity=controls[1].identity)
    replacement.parent = surface
    def tick(seconds):
        assert ui._observation_cache == []
        clock[0] += seconds
        surface.children[1] = replacement
    monkeypatch.setattr(accessible_ui.time, 'sleep', tick)
    ui.dispatch = Mock(return_value=False)

    def predicate():
        target = lookup(ui, 1)
        return target if target is replacement else None
    with ui.observation():
        assert lookup(ui, 1) is controls[1]
        assert ui.wait(predicate, 'replacement') is replacement
        assert lookup(ui, 1) is replacement
    assert ui._read_nodes.call_count == 2
    ui.dispatch.assert_called_once_with()


@pytest.mark.parametrize('failure', ['pending', 'query-error', 'incomplete', 'prompt'])
def test_wait_trace_distinguishes_retries_without_changing_deadline(monkeypatch, failure):
    from tests.support.ui_timing import Timings
    ui, _desktop, _surface, _controls = arbitrary_ui()
    now = [0.0]
    events = []
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda delay: now.__setitem__(0, now[0] + delay))
    recorder = Timings(lambda kind, **fields: events.append(fields), lambda: now[0])
    ui.wait_trace = recorder.wait_trace
    ui.timeout = .4
    ui.query_errors = (LookupError,)
    error = (LookupError('private query') if failure == 'query-error'
             else UiError('ui:incomplete-tree'))
    predicate = Mock(return_value=False)
    if failure == 'prompt':
        ui.handle_system_prompt = Mock(side_effect=error)
    elif failure != 'pending':
        predicate.side_effect = error
    with pytest.raises(UiError, match='ui:timeout:original'):
        ui.wait(predicate, 'original')
    assert now[0] == .4
    outcomes = [event for event in events if event.get('stage') in
                ('pending', 'query-error', 'incomplete')]
    assert [event['attempt'] for event in outcomes] == [1, 2, 3]
    assert {event['stage'] for event in outcomes} == {
        'incomplete' if failure == 'prompt' else failure}
    assert predicate.call_count == (0 if failure == 'prompt' else 3)
    assert events[-1]['failed']
    assert events[-1]['stages']['sleep'] == pytest.approx(.4)
    assert recorder.spans == []
    assert 'private query' not in str(events)


def test_wait_trace_records_predicate_entry_before_blocking_and_propagates_interrupt():
    from tests.support.ui_timing import Timings
    ui, _desktop, _surface, _controls = arbitrary_ui()
    events = []
    recorder = Timings(lambda kind, **fields: events.append(fields))
    ui.wait_trace = recorder.wait_trace
    cancelled = KeyboardInterrupt()
    def predicate():
        assert events[-1]['stage'] == 'predicate'
        assert events[-1]['attempt'] == 1
        assert not any(event['status'] == 'end' for event in events)
        raise cancelled
    with pytest.raises(KeyboardInterrupt) as caught:
        ui.wait(predicate, 'private description')
    assert caught.value is cancelled
    assert events[-1]['failed']
    assert 'private description' not in str(events)


@pytest.mark.parametrize('fault', ['missing-child', 'query-error'])
def test_incomplete_tree_never_becomes_reusable(fault):
    ui, _desktop, surface, controls = arbitrary_ui()
    if fault == 'missing-child':
        surface.children.append(None)
    else:
        ui.query_errors = (LookupError,)
        controls[-1].get_attributes = Mock(side_effect=LookupError)
    with ui.observation():
        with pytest.raises((UiError, LookupError)):
            lookup(ui, 0)
        assert ui._observation_cache == []
        if fault == 'missing-child':
            surface.children.pop()
        else:
            controls[-1].get_attributes = Mock(return_value={})
        assert lookup(ui, 0) is controls[0]
    assert ui._read_nodes.call_count == 2


def test_tolerant_read_cannot_authorize_later_strict_completeness():
    ui, _desktop, surface, controls = arbitrary_ui()
    ui.query_errors = (LookupError,)
    controls[-1].get_attributes = Mock(side_effect=LookupError)
    with ui.observation():
        assert controls[0] in list(ui.nodes(surface))
        assert ui._observation_cache == []
        with pytest.raises(LookupError):
            lookup(ui, 0)


@pytest.mark.parametrize('recovers', [True, False])
def test_prompt_query_failure_reacquires_before_predicate_and_still_fails_closed(monkeypatch, recovers):
    ui, _desktop, _surface, controls = arbitrary_ui()
    ui.prompt_enabled = True
    ui.prompt_session = 'desktop'
    ui.query_errors = (LookupError,)
    ui.timeout = .4
    clock = [0.0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: clock[0])
    controls[-1].get_attributes = Mock(side_effect=LookupError)
    def tick(seconds):
        assert not ui._observation_cache
        clock[0] += seconds
        if recovers:
            controls[-1].get_attributes = Mock(return_value={})
    monkeypatch.setattr(accessible_ui.time, 'sleep', tick)
    predicate = Mock(side_effect=lambda: lookup(ui, 0))
    if recovers:
        assert ui.wait(predicate, 'future-ready') is controls[0]
        predicate.assert_called_once_with()
        assert ui._read_nodes.call_count == 2
    else:
        with pytest.raises(UiError, match='system-prompt-observation-failed'):
            ui.wait(predicate, 'future-ready')
        predicate.assert_not_called()
    assert clock[0] <= ui.timeout
    assert ui._observation_cache is None
    for control in controls:
        control.action.do_action.assert_not_called()


def test_text_protection_and_tolerant_projection_preserve_their_exact_scopes():
    text_child = Node(identity='text-child')
    text = Node(role='text', identity='text-field', children=[text_child])
    password = Node(role='password text')
    password.get_child_count = Mock(side_effect=AssertionError('secret traversal'))
    root = Node(children=[text, password])
    ui = ui_for(root)
    with ui.observation():
        assert text_child not in list(ui.nodes(strict=True, protect_text=True))
        assert text_child in list(ui.nodes(strict=True))
        edges = {}
        assert text_child not in list(ui.nodes(snapshot=edges))
        assert edges[text] == []
        assert text_child not in list(ui.nodes(strict=True, protected_ids=('text-field',)))
    password.get_child_count.assert_not_called()


@pytest.mark.parametrize('snapshot', [False, True])
def test_one_shot_protected_ids_are_applied_before_traversal(snapshot):
    secret = Node(identity='future-secret')
    secret.get_child_count = Mock(side_effect=AssertionError('protected traversal'))
    root = Node(children=[secret])
    ui = ui_for(root)
    with ui.observation():
        protected = (identity for identity in ('future-secret',))
        if snapshot:
            nodes, edges, _identities, _facts = ui.read_snapshot(protected_ids=protected)
            assert edges[secret] == ()
        else:
            nodes = tuple(ui.nodes(strict=True, protected_ids=protected))
        assert nodes == (root, secret)
        assert ui.read_snapshot(protected_ids=('future-secret',))[0] == nodes
    secret.get_child_count.assert_not_called()


@pytest.mark.parametrize('count,code', [(-1, 'incomplete-tree'), (6001, 'tree-bound')])
def test_invalid_child_count_cannot_authorize_input_or_seed_a_complete_snapshot(count, code):
    ui, _desktop, _surface, controls = arbitrary_ui()
    controls[-1].get_child_count = Mock(return_value=count)
    controls[-1].get_child_at_index = Mock(side_effect=AssertionError('unbounded traversal'))
    with ui.observation():
        with pytest.raises(UiError, match=code):
            ui._invoke_target(lookup(ui, 0))
        assert ui._observation_cache == []
    controls[-1].get_child_at_index.assert_not_called()
    controls[0].action.do_action.assert_not_called()


def test_new_operation_and_explicit_client_reset_reacquire_complete_tree():
    ui, _desktop, surface, controls = arbitrary_ui()
    ui._run = lambda *_, child: lookup(ui, 0)
    assert ui.run('future-operation', '') is controls[0]
    replacement = Node(identity=controls[0].identity)
    replacement.parent = surface
    surface.children[0] = replacement
    assert ui.run('future-operation', '') is replacement
    with ui.observation():
        assert lookup(ui, 0) is replacement
        surface.children[0] = controls[0]
        ui.invalidate_observation()
        assert lookup(ui, 0) is controls[0]
    assert ui._read_nodes.call_count == 4


def test_input_during_suspended_traversal_cannot_publish_mixed_facts():
    ui, _desktop, _surface, controls = arbitrary_ui()
    iterator = ui.nodes(strict=True)
    next(iterator)
    ui.input_uncertain = True
    ui.input_uncertain = False
    with pytest.raises(UiError, match='incomplete-tree'):
        list(iterator)
    assert ui._observation_cache is None
    assert lookup(ui, 0) is controls[0]


def test_invalidation_during_snapshot_construction_cannot_seed_reuse():
    ui, _desktop, _surface, controls = arbitrary_ui()
    original = controls[-1].get_attributes
    def interrupt():
        ui.invalidate_observation()
        return original()
    controls[-1].get_attributes = interrupt
    with ui.observation():
        with pytest.raises(UiError, match='incomplete-tree'):
            ui.read_snapshot()
        assert not ui._observation_cache
        controls[-1].get_attributes = original
        assert lookup(ui, 0) is controls[0]


def test_prompt_scans_descendants_only_for_candidate_dialogs():
    ui, _desktop, surface, controls = arbitrary_ui(1000)
    ui.snapshot_scope = Mock(wraps=ui.snapshot_scope)
    assert ui.system_prompt_kind() is None
    # One application scope; no descendant scan for its ordinary controls.
    assert ui.snapshot_scope.call_count == 1
    dialog = Node(role='dialog', children=[Node(role='password text')])
    dialog.parent = surface
    surface.children.append(dialog)
    assert ui.system_prompt_kind() == 'unknown'


def test_id_checks_reuse_facts_but_state_guards_remain_live():
    ui, _desktop, _surface, controls = arbitrary_ui(100)
    for node in controls:
        node.get_state_set = Mock(wraps=node.get_state_set)
        node.get_accessible_id = Mock(wraps=node.get_accessible_id)
    with ui.observation():
        assert lookup(ui, 0) is controls[0]
        for node in controls:
            for _ in range(3):
                assert ui.showing(node)
                assert ui.has_state(node, ui.api.StateType.SENSITIVE)
                assert ui.observed_id(node) == node.identity
            assert node.get_state_set.call_count > 1
            node.get_accessible_id.assert_called_once_with()
        controls[1].states.discard('sensitive')
        assert not ui.has_state(controls[1], ui.api.StateType.SENSITIVE)
        ui.activate_provider('future-provider', 'future-surface', '0')
        assert lookup(ui, 1) is controls[1]
        assert not ui.has_state(controls[1], ui.api.StateType.SENSITIVE)


def test_tree_preserves_depth_first_order_with_shared_children_and_cycles():
    ui, desktop, surface, controls = arbitrary_ui(50)
    nested = Node(identity='nested', children=[controls[-1]])
    nested.parent = controls[0]
    controls[0].children.extend([nested, desktop])
    assert list(ui.nodes(strict=True)) == [
        desktop, desktop.children[0], surface, controls[0], nested,
        controls[-1], *controls[1:-1]]


def test_cached_snapshot_and_scopes_are_immutable_but_projections_are_independent():
    ui, _desktop, surface, controls = arbitrary_ui()
    with ui.observation():
        nodes, edges, identities, facts = ui.read_snapshot()
        scope = ui.snapshot_scope(nodes, edges, surface)
        assert ui.snapshot_scope(nodes, edges, surface) is scope
        assert ui.read_snapshot()[0] is nodes
        with pytest.raises(TypeError):
            edges[surface] = ()
        with pytest.raises(TypeError):
            facts[controls[0]]['identity'] = 'forged'
        assert type(scope) is tuple
        projected_edges, projected_ids, projected_facts = {}, {}, {}
        projected = list(ui.nodes(strict=True, snapshot=projected_edges,
                                  identities=projected_ids, facts=projected_facts))
        projected.clear()
        projected_edges[surface].clear()
        projected_ids[controls[0]] = 'forged'
        projected_facts[controls[0]]['identity'] = 'forged'
        assert lookup(ui, 0) is controls[0]
        assert ui.snapshot_scope(nodes, edges, surface) == scope
    ui._read_nodes.assert_called_once()


def test_snapshot_construction_uses_snapshot_names_without_changing_public_reads():
    ui, _desktop, _surface, controls = arbitrary_ui()
    controls[0].get_name = Mock(return_value='live result')
    controls[0].snapshot_name = Mock(return_value='fresh batched observation')
    with ui.observation():
        _nodes, _edges, _identities, facts = ui.read_snapshot()
        assert facts[controls[0]]['name'] == 'fresh batched observation'
        controls[0].get_name.assert_not_called()
        assert controls[0].get_name() == 'live result'
    controls[0].snapshot_name.assert_called_once_with()


def test_mutable_projection_changes_cannot_reuse_a_stale_scope_or_id_index():
    ui, _desktop, surface, controls = arbitrary_ui()
    with ui.observation():
        edges, identities = {}, {}
        nodes = list(ui.nodes(strict=True, snapshot=edges, identities=identities))
        assert controls[0] in ui.snapshot_scope(nodes, edges, surface)
        assert ui.snapshot_matches(controls[0].identity, nodes, identities=identities) is controls[0]
        edges[surface].remove(controls[0])
        assert controls[0] not in ui.snapshot_scope(nodes, edges, surface)
        identities[controls[1]] = controls[0].identity
        with pytest.raises(UiError, match='ambiguous-automation-id'):
            ui.snapshot_matches(controls[0].identity, nodes, identities=identities)
        nodes.remove(controls[1])
        assert ui.snapshot_matches(controls[0].identity, nodes, identities=identities) is controls[0]


def test_snapshot_index_does_not_alias_different_protected_or_nested_scopes():
    ui, desktop, surface, controls = arbitrary_ui()
    with ui.observation():
        full = ui.read_snapshot()
        scoped = ui.read_snapshot(surface)
        assert scoped[0] == (surface, *controls)
        assert desktop not in scoped[0]
        assert ui.snapshot_matches('future-control-0', scoped[0], identities=scoped[2]) is controls[0]
        protected = ui.read_snapshot(protected_ids=('future-surface',))
        assert controls[0] not in protected[0]
        assert ui.snapshot_matches('future-control-0', protected[0], identities=protected[2]) is None
        assert ui.snapshot_matches('future-control-0', full[0], identities=full[2]) is controls[0]
    assert not ui._projection_cache
    assert ui._observation_cache is None


def test_timing_reports_reader_and_action_intervals_without_observed_text(monkeypatch):
    ui, _desktop, _surface, controls = arbitrary_ui()
    clock = [10.0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: clock[0])
    original = ui._walk_nodes
    def walk(*args, **kwargs):
        yield from original(*args, **kwargs)
        clock[0] += .125
    ui._walk_nodes = walk
    controls[0].action.do_action.side_effect = lambda _index: clock.__setitem__(0, clock[0] + .25) or True
    records = []
    ui.timing = records.append
    ui._run = lambda *_, child: ui.activate_provider('future-provider', 'future-surface', '0')
    ui.run('child-picker-opened', '')
    assert records == [{'event': 'ui-operation-timing', 'operation': 'child-picker-opened',
                        'started_monotonic_ms': 10000.0, 'elapsed_ms': 375.0,
                        'tree_reads': 1, 'nodes_read': 6, 'reader_ms': 125.0,
                        'input_ms': [125.0]}]
    assert ui._timing is None


def test_timing_failure_does_not_replay_uncertain_input():
    ui, _desktop, _surface, controls = arbitrary_ui()
    ui.timing = Mock()
    controls[0].action.do_action.return_value = False
    ui._run = lambda *_, child: ui.activate_provider('future-provider', 'future-surface', '0')
    with pytest.raises(UiError, match='action-refused'):
        ui.run('child-picker-opened', '')
    assert ui.input_uncertain
    assert ui._timing is None
    assert ui._observation_cache is None
    ui.timing.assert_called_once()
    controls[0].action.do_action.assert_called_once_with(0)
