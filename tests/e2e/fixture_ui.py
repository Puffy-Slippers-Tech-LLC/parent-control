"""Public GUI activity projections for repository-owned application fixtures.

Host qualification does not qualify package installation or product enforcement.
Installed consumers must launch the declared package/route themselves.
"""

import re

from tests.e2e.accessible_ui import require


class FixtureUI:
    def __init__(self, ui, kind, instance='primary'):
        require(kind in ('native', 'flatpak', 'snap', 'game')
                and instance in ('primary', 'secondary'), 'ui:fixture-binding')
        self.ui = ui
        self.scope = f'onpc-fixture-{kind}-{instance}'

    def target(self, control):
        require(control in ('status', 'draft', 'edit', 'submit', 'submitted', 'score', 'move', 'close'),
                'ui:fixture-control')
        return self.ui.id_target(self.target_id(control))

    def target_id(self, control):
        require(control in ('status', 'draft', 'edit', 'submit', 'submitted', 'score', 'move', 'close'),
                'ui:fixture-control')
        return self.scope + '-' + control

    def text(self, control):
        node = self.target(control)
        require(node.get_role_name() != 'password text', 'ui:masked-text')
        value = node.get_name()
        if control == 'draft':
            text = node.get_text_iface()
            require(text is not None, 'ui:fixture-text')
            count = self.ui.api.Text.get_character_count(text)
            require(type(count) is int and 0 <= count <= 256, 'ui:fixture-text-bound')
            value = self.ui.api.Text.get_text(text, 0, count)
        require(type(value) is str and len(value) <= 256, 'ui:fixture-text-bound')
        return value

    def ready(self):
        return self.ui.wait(lambda: self.text('status') == 'Ready', 'fixture-ready')

    def focus_draft(self):
        node = self.target('draft')
        require(self.ui.has_state(node, self.ui.api.StateType.SENSITIVE), 'ui:unusable-target')
        self.ui.activate_id(self.target_id('edit'))
        self.ui.wait(lambda: self.ui.has_state(self.target('draft'), self.ui.api.StateType.FOCUSED),
                     'fixture-draft-focus')

    def snapshot(self):
        score = self.text('score')
        require(re.fullmatch(r'Moves: [0-9]+; token: [0-3]', score), 'ui:fixture-score')
        return {'draft': self.text('draft'), 'submitted': self.text('submitted'), 'score': score}

    def submit(self):
        expected = self.text('draft')
        self.ui.activate_id(self.target_id('submit'))
        self.ui.wait(lambda: self.text('submitted') == expected, 'fixture-submitted')

    def move(self):
        before = self.snapshot()
        moves = int(before['score'].split(';')[0].removeprefix('Moves: ')) + 1
        self.ui.activate_id(self.target_id('move'))
        self.ui.wait(lambda: self.text('score') == f'Moves: {moves}; token: {moves % 4}',
                     'fixture-moved')
        return self.snapshot()

    def closed(self, *, surrounding_id):
        # Absence needs a positive, independently identified destination.
        return self.ui.wait(
            lambda: self.ui.absent_id(self.scope, within=surrounding_id),
            'fixture-closed')
