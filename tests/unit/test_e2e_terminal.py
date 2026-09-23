"""The direct command route still requires the product management denial."""

import pytest

from accessible_ui import UiError
from tests.support.accessible_ui import Node, ui_for


@pytest.mark.parametrize('fault', [None, 'generic', 'echo', 'management', 'stale', 'inactive'])
def test_denial_requires_specific_visible_gui_and_complete_management_exclusion(fault):
    label = Node('Only an administrator can manage parental controls. '
                 'Sign in with an administrator account to open the Parent App.', 'label',
                 identity='parent-access-denied-message')
    window = Node('Administrator access required', children=[label,
                  Node('Close', 'push button', identity='parent-access-denied-close')],
                  states=('showing', 'visible', 'active'), identity='parent-access-denied-window')
    root = Node(children=[window])
    if fault == 'generic': label.name = 'Something went wrong'
    if fault == 'echo': label.role = 'terminal'
    if fault == 'management': root.children.append(Node('Oh No! Parent Control', identity='parent-window'))
    if fault == 'stale': root.children.append(Node(states=('defunct',)))
    if fault == 'inactive': window.states.remove('active')
    ui = ui_for(root)
    if fault:
        with pytest.raises(UiError): ui.management_denied()
    else:
        ui.management_denied()
