"""Generic read-boundary cost and freshness, independent of any product UI."""

from unittest.mock import Mock

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


def lookup(ui, index):
    return ui.find_provider_control('future-provider', 'future-surface', str(index))


@pytest.mark.parametrize('count', [3, 100, 1000])
def test_future_controls_share_one_tree_across_nested_helpers_and_waits(count):
    ui, desktop, surface, controls = arbitrary_ui(count)
    ui.prompt_enabled = True
    ui.prompt_session = 'desktop'
    ui.dispatch = Mock(return_value=False)
    for control in controls:
        control.get_attributes = Mock(wraps=control.get_attributes)
        control.get_accessible_id = Mock(wraps=control.get_accessible_id)

    def operation(_name, _version):
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
    def action(_index):
        assert ui._observation_cache == []
        duplicate = Node(identity=controls[1].identity)
        duplicate.parent = surface
        surface.children.append(duplicate)
        return True
    controls[0].action.do_action.side_effect = action

    with ui.observation():
        assert lookup(ui, 1) is controls[1]
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


def test_new_operation_and_explicit_client_reset_reacquire_complete_tree():
    ui, _desktop, surface, controls = arbitrary_ui()
    ui._run = lambda *_: lookup(ui, 0)
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
