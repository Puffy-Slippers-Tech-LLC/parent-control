"""Fixture activity stays ID-scoped, independent and guarded on failures."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.e2e.fixture_ui import FixtureUI
from tests.e2e.accessible_ui import AccessibleUI, UiError
from tests.support.accessible_ui import Node


def fixture(kind='native', instance='primary'):
    scope = f'onpc-fixture-{kind}-{instance}'
    nodes = {key: Node(value, 'label', identity=scope + '-' + key) for key, value in {
        'status': 'Ready', 'score': 'Moves: 0; token: 0',
        'draft': 'draft', 'submitted': 'No submitted draft',
        'move': 'Move token', 'submit': 'Submit draft', 'edit': 'Edit draft', 'close': 'Close',
    }.items()}
    nodes['draft'].get_text_iface = lambda: nodes['draft']
    surface = Node('', identity=scope, children=list(nodes.values()))
    return surface, nodes


def adapter(root):
    def applications(node):
        if node.identity.startswith('onpc-fixture-') and len(node.identity.split('-')) == 4:
            kind, instance = node.identity.split('-')[-2:]
            return Node(identity=f'com.puffyslippers.ONPCFixture.{kind}.{instance}', children=[node])
        node.children = [applications(child) for child in node.children]
        return node
    root = applications(root)
    return AccessibleUI(SimpleNamespace(
        get_desktop=lambda _: root,
        StateType=SimpleNamespace(SHOWING='showing', VISIBLE='visible', SENSITIVE='sensitive',
                                  DEFUNCT='defunct', FOCUSED='focused', MODAL='modal'),
        Action=SimpleNamespace(get_n_actions=lambda a: 1, do_action=lambda a, i: a.do_action(i)),
        Text=SimpleNamespace(get_character_count=lambda n: len(n.name),
                             get_text=lambda n, a, b: n.name[a:b]),
    ), timeout=0)


@pytest.mark.parametrize('kind', ['native', 'flatpak', 'snap', 'game'])
def test_instance_state_is_read_by_id_despite_equal_titles_labels_and_order(kind):
    primary, first = fixture(kind)
    secondary, second = fixture(kind, 'secondary')
    first['draft'].name = 'first draft'
    second['draft'].name = 'second draft'
    root = Node(children=[secondary, primary])
    ui = adapter(root)
    first_view, second_view = FixtureUI(ui, kind), FixtureUI(ui, kind, 'secondary')
    assert first_view.snapshot()['draft'] == 'first draft'
    assert second_view.snapshot()['draft'] == 'second draft'
    root.children.reverse()
    assert first_view.snapshot()['draft'] == 'first draft'


@pytest.mark.parametrize('fault', ['duplicate-id', 'hidden', 'disabled', 'no-effect', 'uncertain'])
def test_move_requires_unique_usable_control_and_independent_result(fault):
    surface, nodes = fixture()
    if fault == 'duplicate-id':
        surface.children.append(Node('different label', identity=nodes['move'].identity))
    if fault == 'hidden': nodes['move'].states.remove('visible')
    if fault == 'disabled': nodes['move'].states.remove('sensitive')
    if fault == 'uncertain': nodes['move'].action.do_action.side_effect = LookupError('uncertain')
    with pytest.raises((UiError, LookupError)):
        FixtureUI(adapter(surface), 'native').move()
    assert nodes['move'].action.do_action.call_count == (1 if fault in ('no-effect', 'uncertain') else 0)


def test_move_and_submit_observe_the_result_and_leave_the_other_instance_intact():
    surface, nodes = fixture()
    second, second_nodes = fixture(instance='secondary')
    ui = adapter(Node(children=[surface, second]))
    nodes['move'].action.do_action.side_effect = lambda _: setattr(nodes['score'], 'name', 'Moves: 1; token: 1') or True
    nodes['submit'].action.do_action.side_effect = lambda _: setattr(nodes['submitted'], 'name', nodes['draft'].name) or True
    view = FixtureUI(ui, 'native')
    view.submit()
    assert view.move() == {'draft': 'draft', 'submitted': 'draft', 'score': 'Moves: 1; token: 1'}
    assert second_nodes['score'].name == 'Moves: 0; token: 0'


def test_password_projection_refuses_before_reading_text():
    surface, nodes = fixture()
    nodes['draft'].role = 'password text'
    nodes['draft'].get_text_iface = Mock(side_effect=AssertionError('secret read'))
    with pytest.raises(UiError, match='masked-text'):
        FixtureUI(adapter(surface), 'native').text('draft')
    nodes['draft'].get_text_iface.assert_not_called()


@pytest.mark.parametrize('fault', ['wrong-application', 'wrong-surface', 'duplicate-application'])
def test_fixture_targets_require_unique_application_and_surface_ownership(fault):
    surface, nodes = fixture()
    ui = adapter(surface)
    application = ui.api.get_desktop(0)
    if fault == 'wrong-application':
        application.identity = 'unrelated-application'
    elif fault == 'wrong-surface':
        surface.children.remove(nodes['move'])
        application.children.append(nodes['move'])
    else:
        duplicate = Node(identity=application.identity)
        desktop = Node(children=[application, duplicate])
        ui.api.get_desktop = lambda _: desktop
    with pytest.raises(UiError):
        FixtureUI(ui, 'native').move()
    nodes['move'].action.do_action.assert_not_called()
