"""Complete App Limits collections must never infer absence from partial reads."""

from types import SimpleNamespace
from unittest.mock import Mock
import json

import pytest

import accessible_ui
from app_row_observations import AppRowJourney, PLAN
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from ui_observations import AppRowsObservation, UiObservations


ROW = 'parent-app-0123456789abcdef'


def app_ui():
    buttons = [Node(identity=ROW + '-access-' + access,
                    states=('visible', 'sensitive', 'pressed') if access == 'allowed'
                    else ('visible', 'sensitive'))
               for access in ('allowed', 'conditional', 'permanent')]
    match = Node(identity=ROW + '-match-precise', states=('visible',))
    row = Node(identity=ROW, states=('visible', 'sensitive'), children=[
        *buttons, Node(identity=ROW + '-match-rule', children=[match], states=('visible',))])
    rows = Node(identity='parent-app-rows', children=[row])
    page = Node(identity='parent-app-limits-page', children=[
        Node(identity='parent-app-search'), rows])
    picker = Node(identity='parent-child-selector', children=[
        Node('Riley (Child)', identity='parent-child-selected-1001')])
    root = Node(identity='parent-window', children=[picker, page])
    return ui_for(root), page, rows, row, buttons, match


def test_complete_rows_are_immutable_and_include_off_viewport_controls_without_input():
    ui, page, rows, row, buttons, match = app_ui()
    assert ui.app_rows(accessible_ui.CHILD, expected_ids=(ROW,)) == ((ROW, 'allowed', 'precise'),)
    for node in (row, *buttons, match):
        node.component.scroll_to.assert_not_called()
        node.action.do_action.assert_not_called()
    buttons[0].states.remove('pressed')
    buttons[1].states.add('pressed')
    assert ui.app_rows(accessible_ui.CHILD) == ((ROW, 'conditional', 'precise'),)


@pytest.mark.parametrize('fault', ['wrong-child', 'wrong-page', 'loading', 'missing-access',
    'duplicate', 'stale', 'incomplete', 'no-choice', 'two-choices', 'no-match',
    'two-matches', 'orphan', 'bound', 'expected-set', 'wrong-owner'])
def test_invalid_or_incomplete_rows_refuse(fault):
    ui, page, rows, row, buttons, match = app_ui()
    child = accessible_ui.CHILD
    options = {}
    if fault == 'wrong-child':
        child = accessible_ui.EXISTING_CHILD
    elif fault == 'wrong-page':
        page.states.clear()
    elif fault == 'loading':
        page.children[0].states.remove('sensitive')
    elif fault == 'missing-access':
        row.children.remove(buttons[2])
    elif fault == 'duplicate':
        rows.children.append(Node(identity=ROW))
    elif fault == 'stale':
        match.states.add('defunct')
    elif fault == 'incomplete':
        row.get_child_count = Mock(side_effect=LookupError('incomplete'))
    elif fault == 'no-choice':
        buttons[0].states.remove('pressed')
    elif fault == 'two-choices':
        buttons[1].states.add('pressed')
    elif fault == 'no-match':
        match.identity = ''
    elif fault == 'two-matches':
        row.children[-1].children.append(Node(identity=ROW + '-match-pattern'))
    elif fault == 'orphan':
        row.identity = ''
    elif fault == 'bound':
        options['maximum'] = 0
    elif fault == 'expected-set':
        options['expected_ids'] = ()
    elif fault == 'wrong-owner':
        ui.api.get_desktop(0).identity = 'unrelated.application'
    with pytest.raises((accessible_ui.UiError, LookupError)):
        ui.app_rows(child, **options)


def test_empty_set_requires_complete_ready_page_and_explicit_expectation():
    ui, page, rows, *_ = app_ui()
    rows.children.clear()
    assert ui.app_rows(accessible_ui.CHILD, expected_ids=()) == ()
    rows.get_child_count = Mock(side_effect=LookupError())
    with pytest.raises(LookupError):
        ui.app_rows(accessible_ui.CHILD, expected_ids=())


def test_app_row_deadline_bounds_the_entire_traversal(monkeypatch):
    ui, *_ = app_ui()
    monkeypatch.setattr(accessible_ui.time, 'monotonic', Mock(side_effect=[0, 46]))
    with pytest.raises(accessible_ui.UiError, match='app-row-deadline'):
        ui.app_rows(accessible_ui.CHILD)


def test_projection_validates_transport_and_does_not_embed_allowed_expectations():
    value = [[ROW, 'permanent', 'pattern']]
    projection = AppRowsObservation.from_rows(value)
    value[0][1] = 'allowed'
    assert projection.rows == ((ROW, 'permanent', 'pattern'),)
    with pytest.raises(EvidenceError):
        AppRowsObservation.from_rows(value + value)


@pytest.mark.parametrize('streamed', [False, True])
@pytest.mark.parametrize('operation', ['parent-app-rows', 'parent-app-rows-reopened'])
@pytest.mark.parametrize('count', [46, 256])
def test_collection_transport_accepts_complete_installed_sized_reply(streamed, operation, count):
    rows = [[f'parent-app-{index:016x}', 'allowed', 'precise'] for index in range(count)]
    result = {'operation': operation, 'interface': 'AT-SPI', 'outcome': 'passed',
              'apps': {'rows': rows}}
    raw = (json.dumps(result) + '\n').encode()
    assert len(raw) > (8192 if count == 256 else 2048)
    observer, transport, commands, previous = collection_transport(raw, streamed)
    assert observer.observe(operation) == result
    transport.call.assert_called_once()
    assert commands.progress is previous


def collection_transport(raw, streamed):
    previous = Mock()
    commands = SimpleNamespace(progress=previous)
    def call(*_, **kwargs):
        if streamed:
            commands.progress = kwargs['on_output']
            for offset in range(0, len(raw), 137):
                commands.progress(raw[offset:offset + 137])
        return raw
    transport = SimpleNamespace(commands=commands, call=Mock(side_effect=call))
    observer = UiObservations(transport, system_prompt=Mock() if streamed else None)
    return observer, transport, commands, previous


@pytest.mark.parametrize('streamed', [False, True])
@pytest.mark.parametrize('fault,code', [
    ('bytes', 'response-size'), ('row-count', 'app-rows'), ('malformed', 'app-rows'),
    ('ordinary-operation', 'response-size'), ('refusal-operation', 'response-size'),
])
def test_collection_transport_preserves_size_and_schema_refusals(streamed, fault, code):
    operation = 'parent-app-rows'
    rows = [[f'parent-app-{index:016x}', 'allowed', 'precise'] for index in range(46)]
    if fault == 'row-count':
        rows = [[f'parent-app-{index:016x}', 'allowed', 'precise'] for index in range(257)]
    elif fault == 'malformed':
        rows[-1][1] = 'unknown'
    elif fault == 'ordinary-operation':
        operation = 'parent-window'
    elif fault == 'refusal-operation':
        operation = 'parent-app-rows-wrong-child'
    result = {'operation': operation, 'interface': 'AT-SPI', 'outcome': 'passed',
              'apps': {'rows': rows}}
    raw = json.dumps(result).encode() + b'\n'
    if fault == 'bytes':
        raw = raw[:-1] + b' ' * 32768 + b'\n'
    observer, transport, commands, previous = collection_transport(raw, streamed)
    with pytest.raises(EvidenceError, match=code):
        observer.observe(operation)
    transport.call.assert_called_once()
    assert commands.progress is previous


def test_qualification_requires_nonempty_allowed_and_independent_identical_set(tmp_path):
    def observed(rows):
        return {'ui': {'apps': {'rows': rows}}}
    journey = AppRowJourney(SimpleNamespace(directory=tmp_path), Mock())
    for rows in ([], [[ROW, 'permanent', 'precise']]):
        with pytest.raises(EvidenceError, match='initial-allowed'):
            journey.check_settings('app-rows', observed(rows))
    initial = [[ROW, 'allowed', 'precise']]
    journey.check_settings('app-rows', observed(initial))
    with pytest.raises(EvidenceError, match='independent-read'):
        journey.check_settings('reopened-rows', observed([[ROW, 'allowed', 'pattern']]))
    journey.check_settings('reopened-rows', observed(initial))


@pytest.mark.parametrize('conflict', ['parent_toggle', 'kiosk_entry', 'customer_reboot'])
def test_slice_rejects_conflicting_modes_before_vm_work(conflict):
    import check_graphical_smoke
    from owned_commands import CommandError
    with pytest.raises(CommandError, match='app-rows-prerequisites'):
        check_graphical_smoke.main(assets='unused', provision_credentials=True,
                                  app_row_observations=True, **{conflict: True})


def test_slice_reuses_snapshot_and_fixed_asset_route(tmp_path):
    from parent_setup_qualification import AppRowQualification, KioskEntryQualification
    import check_e2e_app_row_observations as check
    assert issubclass(AppRowQualification, KioskEntryQualification)
    context = SimpleNamespace(directory=tmp_path)
    journey = AppRowQualification.journey(context, Mock())
    assert journey.plan is PLAN
    assert context.installed_snapshot.startswith('onpc-v')
    assert check.ASSETS.name == 'onpc-parent-setup-input'


def test_worker_uses_shared_parent_entry_and_consumes_all_results():
    from tests.support.perl import run_perl
    result = run_perl(r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_parent.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; }
package testapi;
sub record_info { }
sub power { push @main::events, 'power'; }
sub check_shutdown { 1 }
sub console { bless {}, 'Console' }
package Console;
sub disable { }
package onpc_gdm;
sub reattach_functional { }
package onpc_parent;
sub open_for_child {
    my ($j, @args) = @_;
    die 'entry' unless join(',', @args) eq 'gdm,fresh,new,child';
    return $j->seen('parent-selected');
}
package main;
require onpc_app_rows;
onpc_app_rows::run(sub { push @events, $_[0]; return {observed => $_[0]}; });
print encode_json(\@events);
''')
    assert json.loads(result.stdout) == ['parent-selected', 'apps-page', 'app-rows',
        'wrong-child', 'wrong-page', 'reopened-rows', 'power']
