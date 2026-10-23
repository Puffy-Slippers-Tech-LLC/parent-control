"""Read-boundary cost, freshness and shared-operation input safety."""

from unittest.mock import Mock

import pytest

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


def test_uncertain_input_still_refuses_replay_after_cache_invalidation():
    ui, _desktop, _surface, controls = arbitrary_ui()
    controls[0].action.do_action.return_value = False
    with ui.observation():
        with pytest.raises(UiError, match='action-refused'):
            ui.activate_provider('future-provider', 'future-surface', '0')
        with pytest.raises(UiError, match='uncertain-input'):
            ui.activate_provider('future-provider', 'future-surface', '0')
    controls[0].action.do_action.assert_called_once_with(0)


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
