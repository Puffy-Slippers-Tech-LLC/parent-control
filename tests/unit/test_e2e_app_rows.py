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
@pytest.mark.parametrize('operation', ['parent-app-rows', 'parent-app-rows-reopened',
    'existing-parent-app-rows', 'existing-parent-app-rows-reopened'])
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


@pytest.mark.parametrize('existing', [False, True])
def test_row_operations_bind_read_reopening_and_refusals_to_same_child(existing):
    ui, page, rows, *_ = app_ui()
    child = accessible_ui.EXISTING_CHILD if existing else accessible_ui.CHILD
    other = accessible_ui.CHILD if existing else accessible_ui.EXISTING_CHILD
    prefix = 'existing-' if existing else ''
    if existing:
        picker = ui.find_id('parent-child-selector')
        picker.children[0].identity = 'parent-child-selected-1002'
    ui.parent_page = Mock(side_effect=lambda selected, name: (
        page.states.add('visible') if name == 'App Limits' else page.states.discard('visible')))
    assert ui.app_row_operation(prefix + 'parent-app-rows') == {
        'rows': ((ROW, 'allowed', 'precise'),)}
    assert ui.app_row_operation(prefix + 'parent-app-rows-wrong-child') == {'refusal': 'wrong-child'}
    with pytest.raises(accessible_ui.UiError, match='app-row-child'):
        ui.app_rows(other)
    assert ui.app_row_operation(prefix + 'parent-app-rows-wrong-page') == {'refusal': 'wrong-page'}
    assert ui.app_row_operation(prefix + 'parent-app-rows-reopened') == {
        'rows': ((ROW, 'allowed', 'precise'),)}
    assert ui.parent_page.call_args_list == [
        ((child, 'Screen Limits'),), ((child, 'Screen Limits'),), ((child, 'App Limits'),)]


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


def test_catalogue_comparison_keeps_exact_rows_empty_expectations_and_clear_baseline():
    from catalogue_search import CatalogueSearchJourney, PLAN as search_plan
    from native_fixtures import expected_rows, search_rows, CATALOGUE_QUERIES
    journey = CatalogueSearchJourney(SimpleNamespace(), Mock(),
                                    actions={'native-refuse': Mock(), 'native-verify': Mock()})
    def observed(rows):
        return {'ui': {'apps': {'rows': [list(row) for row in rows]}}}
    for binding, value in CATALOGUE_QUERIES.items():
        assert accessible_ui.TEXT_VALUES[binding] == ('parent-app-search', value)
    assert set(search_plan.child_bindings.values()) == {'existing'}
    original = observed(expected_rows())
    journey.check_settings('initial-rows', original)
    original['ui']['apps']['rows'].clear()
    for stage in ('name-rows', 'reopened-name'):
        journey.check_settings(stage, observed(search_rows('catalogue-name')))
        with pytest.raises(EvidenceError, match='exact-results'):
            journey.check_settings(stage, observed(()))
    for stage in ('absent-rows', 'reopened-absent'):
        journey.check_settings(stage, observed(()))
        with pytest.raises(EvidenceError, match='exact-results'):
            journey.check_settings(stage, observed(expected_rows()))
    journey.check_settings('cleared-rows', observed(expected_rows()))
    with pytest.raises(EvidenceError, match='catalogue:clear'):
        journey.check_settings('cleared-rows', observed(()))


@pytest.mark.parametrize('worker', ['catalogue_search', 'catalogue_filters'])
def test_catalogue_worker_sequence_and_every_refusal_stop(worker):
    from catalogue_search import PLAN as search_plan
    from catalogue import PLAN as filter_plan
    from tests.support.perl import run_perl
    program = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'}=1; $INC{'onpc_parent.pm'}=1; $INC{'onpc_gdm.pm'}=1; }
package testapi; sub record_info {} sub send_key {} sub type_string {}
sub power {push @main::events, 'power'} sub check_shutdown {1}
sub console {bless {}, 'Console'}
package Console; sub disable {}
package onpc_gdm; sub reattach_functional {}
package onpc_parent;
sub enter_desktop {my ($j,@args)=@_; die 'entry' unless join(',',@args) eq 'gdm,parent,fresh,success';
    for ('installed-greeter','parent-focused','recipient-qualified','recipient-rechecked') {$j->seen($_)}
    return $j->seen('desktop');}
sub launch {my($j,$desktop,$expected)=@_; die 'launch' unless $expected eq 'management';
    $j->consume_observation('desktop',$desktop); $j->seen('parent-command'); $j->seen('parent-window');}
sub select_child {my($j,$child,$opened)=@_; die 'child' unless $child eq 'existing';
    $j->consume_observation('child-picker-opened',$opened); $j->seen('child-choice-highlighted');
    return $j->seen('parent-selected');}
package main;
require onpc_app_rows;
eval {onpc_app_rows::catalogue_search(sub {push @events,$_[0]; FAIL return {observed=>$_[0]};});};
print encode_json(\@events);
'''
    program = program.replace('onpc_app_rows::catalogue_search', 'onpc_app_rows::' + worker)
    expected = list((search_plan if worker == 'catalogue_search' else filter_plan).screen_tags)
    for boundary in (None, *expected):
        stop = "die 'refused' if $_[0] eq '" + boundary + "';" if boundary else ''
        result = run_perl(program.replace('FAIL', stop))
        assert json.loads(result.stdout) == (expected[:expected.index(boundary) + 1]
                                            if boundary else expected + ['power'])


def test_filter_leaves_use_owned_options_explicit_state_and_independent_selection():
    ui, page, *_ = app_ui()
    root = ui.find_id('parent-window')
    root.states.add('active')
    ui.find_id('parent-child-selector').children[0].role = 'label'
    search = ui.find_id('parent-app-search')
    search.states.add('editable')
    options = [Node(identity='parent-filter-match-rule-' + option,
                    states=('visible', 'showing', 'sensitive', 'checked'))
               for option in accessible_ui.FILTER_OPTIONS['match-rule']]
    choices = Node(identity='parent-filter-match-rule-choices', children=options)
    choices.parent = root
    def toggle(target):
        if 'checked' in target.states:
            target.states.remove('checked')
        else:
            target.states.add('checked')
    ui._invoke_target = Mock(side_effect=toggle)
    ui.activate_id = Mock(side_effect=lambda *_, **__: root.children.append(choices))
    assert ui.catalogue_filter(accessible_ui.CHILD, 'match-rule', 2, 'open') == {'opened': 'match-rule'}
    ui.activate_id.assert_called_once_with('parent-filter-match-rule', action_name='menu.popup')
    assert ui.catalogue_filter(accessible_ui.CHILD, 'match-rule', 2, 'pattern') == {
        'state': False, 'activated': True}
    assert ui.catalogue_filter(accessible_ui.CHILD, 'match-rule', 2, 'precise') == {
        'state': True, 'activated': False}
    assert ui.catalogue_filter(accessible_ui.CHILD, 'match-rule', 2, 'read') == {
        'filter': 'match-rule', 'selected': ['precise']}
    ui._invoke_target.assert_called_once_with(options[0])
    with pytest.raises(accessible_ui.UiError, match='wrong-child'):
        ui.catalogue_filter(accessible_ui.EXISTING_CHILD, 'match-rule', 2, 'pattern')
    options[1].states.remove('checked')
    with pytest.raises(accessible_ui.UiError, match='filter-selection'):
        ui.catalogue_filter(accessible_ui.CHILD, 'match-rule', 2, 'read')
    root.children.remove(choices)
    assert ui.catalogue_filter(accessible_ui.CHILD, 'match-rule', 2, 'closed') == {'closed': 'match-rule'}
    with pytest.raises(accessible_ui.UiError):
        ui.catalogue_filter(accessible_ui.CHILD, 'match-rule', 2, 'pattern')
    ui._invoke_target.assert_called_once()


def test_filter_composite_is_independently_reusable_and_refusal_stops_escape():
    from journey_blocks import filter_screens
    from tests.support.perl import run_perl
    assert filter_screens('match-rule', 2, 'renamed') == {
        f'renamed-{action}': f'ui:filter-match-rule-2-{action}'
        for action in ('open', 'pattern', 'precise', 'read', 'closed')}
    with pytest.raises(EvidenceError):
        filter_screens('match-rule', 4, 'renamed')
    program = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'}=1; }
package testapi; sub record_info {} sub send_key {push @main::events, 'key:' . $_[0]}
package main;
require onpc_app_rows;
my $journey = onpc_journey->new(prefix=>'independent', review=>0, exchange=>sub {
    push @events, $_[0]; FAIL return {observed=>$_[0]}; });
eval {onpc_app_rows::filter($journey, 'match-rule', 2, 'renamed');};
print encode_json(\@events);
'''
    expected = ['renamed-open', 'renamed-pattern', 'renamed-precise', 'renamed-read',
                'key:esc', 'renamed-closed']
    for boundary in (None, *[stage for stage in expected if not stage.startswith('key:')]):
        stop = "die 'refused' if $_[0] eq '" + boundary + "';" if boundary else ''
        result = run_perl(program.replace('FAIL', stop))
        assert json.loads(result.stdout) == (expected[:expected.index(boundary) + 1]
                                            if boundary else expected)


@pytest.mark.parametrize('operation', list(accessible_ui.FILTER_OPERATIONS))
def test_filter_transport_checks_every_option_set_and_explicit_state(operation):
    kind, mask, action = accessible_ui.FILTER_OPERATIONS[operation]
    options = accessible_ui.FILTER_OPTIONS[kind]
    value = ({'opened' if action == 'open' else 'closed': kind}
        if action in ('open', 'closed') else {'filter': kind, 'selected': [
            option for index, option in enumerate(options) if mask & (1 << index)]}
        if action == 'read' else {'state': bool(mask & (1 << options.index(action))), 'activated': False})
    result = {'operation': operation, 'interface': 'AT-SPI', 'outcome': 'passed', 'filter': value}
    observer, *_ = collection_transport((json.dumps(result) + '\n').encode(), False)
    assert observer.observe(operation) == result
    result['filter'] = {'unexpected': True}
    observer, *_ = collection_transport((json.dumps(result) + '\n').encode(), False)
    with pytest.raises(EvidenceError, match='filter-response'):
        observer.observe(operation)


def test_independent_filter_caller_and_finite_oracle_retain_empty_results_and_policies():
    from catalogue import CatalogueJourney, PLAN as filter_plan
    from native_fixtures import expected_rows, catalogue_rows
    from dataclasses import replace
    # Rename every invocation; comparisons resolve through the registered operation.
    screens = {'renamed-' + stage: operation for stage, operation in filter_plan.screen_tags.items()}
    plan = replace(filter_plan, screen_tags=screens, phases={
        'ready': 'setup', 'setup-detached': 'setup', **{stage: 'step-1' for stage in screens}},
        advance_after={}, stage_actions={}, child_bindings={})
    journey = CatalogueJourney(SimpleNamespace(), Mock(), plan, actions={})
    def observed(rows):
        return {'ui': {'apps': {'rows': [list(row) for row in rows]}}}
    initial = observed(expected_rows())
    journey.check_settings('renamed-initial-rows', initial)
    initial['ui']['apps']['rows'].clear()
    for stage in ('name-rows', 'filtered-rows', 'reopened-entry', 'independent-filtered-rows'):
        rows = catalogue_rows('catalogue-name', expected_rows(), match_mask=2, access_mask=1)
        journey.check_settings('renamed-' + stage, observed(rows))
        with pytest.raises(EvidenceError, match='exact-results'):
            journey.check_settings('renamed-' + stage, observed(()))
    journey.check_settings('renamed-cleared-rows', observed(expected_rows()))
    with pytest.raises(EvidenceError, match='catalogue:clear'):
        journey.check_settings('renamed-cleared-rows', observed(()))
    for binding in ('catalogue-name', 'catalogue-description', 'catalogue-identifier'):
        assert catalogue_rows(binding, expected_rows()) == rows
        assert catalogue_rows(binding, expected_rows(), match_mask=0) == ()
        assert catalogue_rows(binding, expected_rows(), access_mask=0) == ()


def test_catalogue_qualification_selects_its_fresh_plan_and_refuses_missing_native_entry(tmp_path, monkeypatch):
    from catalogue import CatalogueJourney, PLAN as filter_plan
    import parent_setup_qualification as qualification
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    import runpy
    from tests.support.paths import ROOT
    from tools.test_storage import named_input
    source = tmp_path / 'source'
    (source / 'data').mkdir(parents=True)
    (source / 'data/app.json').write_text(json.dumps({'version': '1.1'}))
    monkeypatch.setattr(qualification.smoke, 'ROOT', source)
    context = SimpleNamespace()
    journey = qualification.CatalogueQualification.journey(context, Mock())
    assert type(journey) is CatalogueJourney and journey.plan is filter_plan
    assert context.installed_snapshot == 'onpc-v1.1'
    with pytest.raises(CommandError, match='catalogue-filter-prerequisites'):
        smoke.main(catalogue_filters=True)
    execute = Mock(return_value=0)
    monkeypatch.setattr(smoke, 'main', execute)
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(ROOT / 'tests/integration/check_e2e_catalogue.py'), run_name='__main__')
    assert exited.value.code == 0
    assert execute.call_args.kwargs == {
        'assets': named_input(fixture_source=True),
        'provision_credentials': True, 'app_row_observations': True,
        'native_fixtures': True, 'catalogue_filters': True}


def test_catalogue_adapter_refuses_incomplete_result_and_observes_debounce():
    ui, *_ = app_ui()
    ui.read_synthetic_text = Mock()
    ui.parent_page = Mock()
    ui.app_rows = Mock(side_effect=[accessible_ui.UiError('ui:app-row-set'), ()])
    ui.wait = lambda fn, _: fn() or fn()
    assert ui.app_row_operation('catalogue-absent-reopened') == {'rows': ()}
    assert ui.parent_page.call_args_list == [
        ((accessible_ui.EXISTING_CHILD, 'Screen Limits'),),
        ((accessible_ui.EXISTING_CHILD, 'App Limits'),)]
    ui.read_synthetic_text.assert_called_once_with('catalogue-absent', child=accessible_ui.EXISTING_CHILD)
    ui.app_rows = Mock(side_effect=accessible_ui.UiError('ui:app-row-set'))
    assert ui.app_row_operation('catalogue-incomplete-refused') == {'refusal': 'incomplete-result'}
    ui.app_rows = Mock(side_effect=accessible_ui.UiError('ui:app-row-child'))
    with pytest.raises(accessible_ui.UiError, match='app-row-child'):
        ui.app_row_operation('catalogue-absent-rows')


def test_catalogue_text_entry_binds_nondefault_child_before_focus_input():
    ui, page, *_ = app_ui()
    root = ui.find_id('parent-window')
    root.states.add('active')
    picker = ui.find_id('parent-child-selector')
    picker.children[0].identity = 'parent-child-selected-1002'
    picker.children[0].name = accessible_ui.EXISTING_CHILD
    picker.children[0].role = 'label'
    search = ui.find_id('parent-app-search')
    search.states.add('editable')
    ui.activate_id = Mock(side_effect=lambda *_, **__: search.states.add('focused'))
    ui.focus_text('parent-app-search', child=accessible_ui.EXISTING_CHILD)
    ui.activate_id.assert_called_once_with('parent-window', action_name='focus.parent-app-search')
    ui.activate_id.reset_mock()
    with pytest.raises(accessible_ui.UiError, match='wrong-child'):
        ui.focus_text('parent-app-search', child=accessible_ui.CHILD)
    page.states.discard('visible')
    with pytest.raises(accessible_ui.UiError, match='app-row-page'):
        ui.focus_text('parent-app-search', child=accessible_ui.EXISTING_CHILD)
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('operation', list(accessible_ui.CATALOGUE_ROW_OPERATIONS))
def test_catalogue_results_use_complete_controller_schema(operation):
    rows = [] if 'absent' in operation else [[ROW, 'allowed', 'precise']]
    result = {'operation': operation, 'interface': 'AT-SPI', 'outcome': 'passed',
              'apps': {'rows': rows}}
    observer, *_ = collection_transport((json.dumps(result) + '\n').encode(), False)
    assert observer.observe(operation) == result
