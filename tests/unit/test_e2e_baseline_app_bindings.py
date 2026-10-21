"""Finite policy/native bindings: private records, doubles and waited Perl only.

No VM, display, bus, shared storage, live process or cleanup owner is added.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui as ui_module
from accessible_ui import MATCH_APPS, MATCH_RULES, UiError
from access_choices import AccessChoiceJourney
from installed_journey import JourneyPlan
from journey_blocks import native_usable_app
from native_fixtures import CATALOGUE_QUERIES, expected_rows, search_rows
from policy_edits import policy_edit
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.perl import run_perl
from ui_observations import UiObservations


BASELINE_TEXT_WORKER = r'''
use strict; use warnings; use JSON::PP;
BEGIN {$INC{'testapi.pm'}=1;}
package testapi;
sub record_info {}
sub send_key {die 'unexpected native input'}
sub type_string {die 'unexpected native input'}
package main; use onpc_text; use onpc_journey;
my ($binding,$stop)=@ARGV; my @events;
my $j=onpc_journey->new(prefix=>'independent',review=>0,exchange=>sub {
    push @events,$_[0]; die 'refused' if $_[0] eq $stop;
    return {observed=>$_[0]};});
my $ok=eval {onpc_text::replace_text($j,$binding,'field');1;} ? 1:0;
print encode_json({ok=>$ok,events=>\@events});
'''


@pytest.mark.parametrize('binding,control,value', [
    ('catalogue-hard', 'parent-app-search', 'com.puffyslippers.ONPCTest.H.desktop'),
    ('catalogue-soft', 'parent-app-search', 'com.puffyslippers.ONPCTest.S.desktop'),
    ('match-hard-precise', 'parent-match-rule-entry',
     '/opt/onpc-test-fixtures/Applications/Path With Spaces.AppImage'),
    ('match-soft-wildcard', 'parent-match-rule-entry',
     '/opt/onpc-test-fixtures/Applications/Versioned/Lunar Client-*.AppImage')])
def test_baseline_text_bindings_execute_real_shared_worker_and_each_refusal(binding, control, value):
    assert ui_module.TEXT_VALUES[binding] == (control, value)
    expected = ['field-focus', 'field-selected', 'field-read']
    for action in ('focus', 'selected', 'read'):
        operation = 'text-' + binding + '-' + action
        assert operation in ui_module.OPERATIONS
        assert ui_module.TEXT_OPERATIONS[operation] == (binding, action)
    for stop in ('', *expected):
        assert json.loads(run_perl(BASELINE_TEXT_WORKER, binding, stop).stdout) == {
            'ok': int(not stop), 'events':
            expected[:expected.index(stop) + 1] if stop else expected}


@pytest.mark.parametrize('binding', [
    'catalogue-unknown', 'catalogue-H', 'match-hard-wildcard', 'match-soft-precise'])
def test_baseline_text_worker_refuses_unregistered_values_before_observation(binding):
    assert binding not in ui_module.TEXT_VALUES
    assert json.loads(run_perl(BASELINE_TEXT_WORKER, binding, '').stdout) == {
        'ok': 0, 'events': []}


def test_soft_match_oracle_uses_only_the_isolated_active_directory():
    pattern = '/opt/onpc-test-fixtures/Applications/Versioned/Lunar Client-*.AppImage'
    assert MATCH_RULES[-1] == pattern
    assert ui_module.TEXT_VALUES['match-soft-wildcard'][1] == pattern
    assert '/opt/onpc-test-fixtures/Applications/Lunar Client-*.AppImage' not in MATCH_RULES


def catalogue_ui(binding, selected_child):
    """Real public text/row readers with explicit account and fixture rows."""
    expected = expected_rows() if binding == 'catalogue-clear' else search_rows(binding)
    rows = []
    for identity, access, match in expected:
        buttons = [Node(identity=identity + '-access-' + choice,
            states=('visible', 'sensitive', *(('pressed',) if choice == access else ())))
            for choice in ui_module.ACCESS_CHOICES]
        rows.append(Node(identity=identity, children=[*buttons,
            Node(identity=identity + '-match-rule', children=[
                Node(identity=identity + '-match-' + match, states=('visible',))])]))
    search = Node(identity='parent-app-search', states=('showing', 'visible', 'sensitive', 'editable'))
    search.get_text_iface = lambda: CATALOGUE_QUERIES[binding]
    selected_uid = {'child': 1001, 'existing': 1002}[selected_child]
    selected_name = ui_module.CHILD if selected_child == 'child' else ui_module.EXISTING_CHILD
    picker = Node(identity='parent-child-selector', children=[
        Node(selected_name, role='label', identity='parent-child-selected-' + str(selected_uid))])
    page = Node(identity='parent-app-limits-page', children=[search,
        Node(identity='parent-app-rows', children=rows)])
    ui = ui_for(Node(identity='parent-window', children=[picker, page]))
    ui.api.Text = SimpleNamespace(get_character_count=len,
        get_text=lambda text, start, end: text[start:end])
    ui.parent_page = Mock()
    return ui, expected, [search, *rows]


@pytest.mark.parametrize('operation', tuple(ui_module.CATALOGUE_ROW_OPERATIONS))
@pytest.mark.parametrize('child', [None, 'child', 'existing'])
def test_catalogue_rows_bind_actual_selected_child_through_run_and_decoder(operation, child):
    binding = ui_module.CATALOGUE_ROW_OPERATIONS[operation]
    ui, rows, controls = catalogue_ui(binding, child or 'existing')
    result = ui.run(operation, '', **({'child': child} if child else {}))
    assert result['apps']['rows'] == rows
    account = ui_module.CHILD if child == 'child' else ui_module.EXISTING_CHILD
    assert ui.parent_page.call_args_list == ([
        ((account, 'Screen Limits'),), ((account, 'App Limits'),)]
        if operation.endswith('reopened') else [])
    public_result = json.loads(json.dumps(result))
    response = {**public_result, **({'boot_sha256': 'b' * 64} if child else {})}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(response).encode()))
    assert UiObservations(transport).observe(operation,
        **({'child': child} if child else {})) == public_result
    for control in controls:
        control.action.do_action.assert_not_called()
        control.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('operation', [
    'catalogue-identifier-rows', 'catalogue-clear-rows', 'catalogue-name-reopened'])
def test_catalogue_rows_wrong_selected_child_refuses_before_any_input(operation):
    binding = ui_module.CATALOGUE_ROW_OPERATIONS[operation]
    ui, _rows, controls = catalogue_ui(binding, 'child')
    with pytest.raises(UiError, match='ui:wrong-child'):
        ui.run(operation, '', child='existing')
    for control in controls:
        control.action.do_action.assert_not_called()
        control.component.grab_focus.assert_not_called()


def test_catalogue_rows_invalid_child_refuses_before_unavailable_discovery():
    ui = ui_for(Node())
    ui.snapshot_owned_target = Mock(side_effect=AssertionError('discovery unavailable'))
    with pytest.raises(UiError, match='custom-child-binding'):
        ui.run('catalogue-identifier-rows', '', child='unknown')
    ui.snapshot_owned_target.assert_not_called()
    transport = SimpleNamespace(call=Mock(side_effect=AssertionError('transport unavailable')))
    with pytest.raises(EvidenceError, match='custom-child-binding'):
        UiObservations(transport).observe('catalogue-identifier-rows', child='unknown')
    transport.call.assert_not_called()


@pytest.mark.parametrize('role,name,draft', [
    ('H', 'hard', 'match-hard-precise'), ('S', 'soft', 'match-soft-wildcard')])
def test_policy_declarations_execute_actual_worker_and_stop_at_each_refusal(role, name, draft):
    screens = policy_edit(MATCH_APPS[role], draft, 'permanent', 'consumer')
    assert screens['consumer-found'] == 'ui:catalogue-' + name + '-rows'
    assert screens['consumer-open'] == 'ui:match-' + name + '-open'
    assert screens['consumer-access-save'] == 'ui:access-' + name + '-permanent'
    assert len(search_rows('catalogue-' + name)) == 1
    assert search_rows('catalogue-' + name)[0][0] == MATCH_APPS[role]
    program = r'''
use strict; use warnings; use JSON::PP;
BEGIN {$INC{'testapi.pm'}=1;}
package testapi; sub record_info {} sub send_key {die 'unexpected input'} sub type_string {die 'unexpected input'}
package main; use onpc_app_rows; use onpc_journey;
my ($app,$draft,$stop)=@ARGV; my @events;
my $j=onpc_journey->new(prefix=>'independent',review=>0,exchange=>sub {
    push @events,$_[0]; die 'refused' if $_[0] eq $stop; return {observed=>$_[0]};});
my $ok=eval {onpc_app_rows::edit_policy($j,$app,$draft,'permanent','consumer',[]);1;} ? 1:0;
print encode_json({ok=>$ok,events=>\@events});
'''
    for stop in ('', *screens):
        actual = json.loads(run_perl(program, MATCH_APPS[role], draft, stop).stdout)
        expected = list(screens)
        assert actual == {'ok': int(not stop), 'events':
            expected[:expected.index(stop) + 1] if stop else expected}


@pytest.mark.parametrize('app,draft', [
    (MATCH_APPS['A'], 'match-hard-precise'), (MATCH_APPS['H'], 'match-precise'),
    (MATCH_APPS['S'], 'match-hard-precise'), ('unknown', 'match-soft-wildcard')])
def test_policy_rejects_crossed_app_draft_before_worker_input(app, draft):
    with pytest.raises(EvidenceError, match='policy:binding'):
        policy_edit(app, draft, 'allowed', 'consumer')


@pytest.mark.parametrize('role,name', [('H', 'hard'), ('S', 'soft')])
@pytest.mark.parametrize('kind,value', [('match', MATCH_RULES[-1]), ('access', 'conditional')])
@pytest.mark.parametrize('crossed', [False, True])
def test_policy_decoder_requires_operation_bound_actual_app(role, name, kind, value, crossed):
    operation = kind + '-' + name + '-row'
    result = {'operation': operation, 'outcome': 'passed',
        'interface': 'ApplicationUI+external-provider', kind: {
            'app': MATCH_APPS['A'] if crossed else MATCH_APPS[role],
            'rule' if kind == 'match' else 'choice': value}}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps({
        **result, 'boot_sha256': 'b' * 64}).encode()))
    observer = UiObservations(transport)
    if crossed:
        with pytest.raises(EvidenceError, match=kind + '-response'):
            observer.observe(operation, child='child')
    else:
        assert observer.observe(operation, child='child') == result


def test_exact_comparisons_preserve_actual_app_for_literal_and_captured_expectations(tmp_path):
    plan = JourneyPlan('sample', 'sample', {
        'before': 'ui:match-soft-row', 'after': 'ui:match-soft-row',
        'access': 'ui:access-soft-row'}, {},
        match_checks={'before': (MATCH_APPS['S'], MATCH_RULES[-1]), 'after': 'before'},
        access_checks={'access': (MATCH_APPS['S'], 'conditional')})
    journey = AccessChoiceJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    first = {'ui': {'match': {'app': MATCH_APPS['S'], 'rule': MATCH_RULES[-1]}}}
    journey.check_settings('before', first)
    first['ui']['match']['app'] = MATCH_APPS['A']
    with pytest.raises(EvidenceError, match='exact-rule'):
        journey.check_settings('after', first)
    with pytest.raises(EvidenceError, match='exact-choice'):
        journey.check_settings('access', {'ui': {'access': {
            'app': MATCH_APPS['A'], 'choice': 'conditional'}}})
    journey.check_settings('after', {'ui': {'match': {
        'app': MATCH_APPS['S'], 'rule': MATCH_RULES[-1]}}})
    journey.check_settings('access', {'ui': {'access': {
        'app': MATCH_APPS['S'], 'choice': 'conditional'}}})


@pytest.mark.parametrize('role,name', [('A', 'allowed'), ('S', 'soft')])
def test_native_worker_uses_declared_role_and_actual_submit_result(role, name):
    screens = native_usable_app('command', child='child', role=role)
    assert screens['submit'] == 'ui:overlay-native-' + name + '-submit'
    assert screens['submitted'] == 'ui:overlay-native-' + name + '-submitted'
    program = r'''
use strict; use warnings; use JSON::PP;
BEGIN {$INC{'testapi.pm'}=1;}
package testapi; sub record_info {} sub send_key {die 'unexpected input'} sub type_string {die 'unexpected input'}
package main; use onpc_app_rows; use onpc_journey;
my ($role,$stop)=@ARGV; my @events;
my $j=onpc_journey->new(prefix=>'independent',review=>0,exchange=>sub {
    push @events,$_[0]; die 'refused' if $_[0] eq $stop; return {observed=>$_[0]};});
my $ok=eval {onpc_app_rows::native_usable_app($j,'command',$j->seen('desktop'),'child',$role);1;} ? 1:0;
print encode_json({ok=>$ok,events=>\@events});
'''
    for stop in ('', *screens):
        expected = list(screens)
        assert json.loads(run_perl(program, role, stop).stdout) == {
            'ok': int(not stop), 'events':
            expected[:expected.index(stop) + 1] if stop else expected}


@pytest.mark.parametrize('role,child,route', [
    ('H', 'child', 'command'), ('S', 'parent', 'command'),
    ('S', 'child', 'grid'), ('A', 'other-child', 'command')])
def test_new_native_roles_refuse_unsupported_routes(role, child, route):
    with pytest.raises(EvidenceError, match='native-role-binding'):
        native_usable_app(route, child=child, role=role)


def launch_ui(monkeypatch):
    ui = ui_for(Node())
    monkeypatch.setattr(ui_module, 'require_active_launch_session', Mock())
    ui.require_child_overlay_session = Mock()
    ui.desktop_result = Mock()
    ui.native_app_closed = Mock(return_value=True)
    ui.handle_system_prompt = Mock()
    ui.prepare_launch_desktop = Mock()
    return ui


@pytest.mark.parametrize('role,instance,executable', [
    ('A', 'primary', '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage'),
    ('S', 'secondary', '/opt/onpc-test-fixtures/Applications/Versioned/Lunar Client-3.7.17.AppImage')])
def test_native_launch_role_binds_executable_instance_and_single_use(monkeypatch, role, instance, executable):
    ui = launch_ui(monkeypatch)
    submit = Mock()
    monkeypatch.setattr(ui_module.subprocess, 'run', submit)
    ui.native_launch_command(instance, child=ui_module.CHILD, role=role)
    assert submit.call_count == 1
    assert submit.call_args.args[0][-3:] == [
        executable, '--instance', instance]
    assert all(call.args == (instance,) for call in ui.native_app_closed.call_args_list)
    with pytest.raises(UiError, match='uncertain-input'):
        ui.native_launch_command(instance, child=ui_module.CHILD, role=role)
    assert submit.call_count == 1


@pytest.mark.parametrize('fault', ['instance', 'child', 'fixture', 'uncertain'])
def test_role_refusals_precede_unavailable_discovery_and_release_no_input(monkeypatch, fault):
    ui = launch_ui(monkeypatch)
    ui.native_app_closed.side_effect = AssertionError('discovery unavailable')
    submit = Mock()
    monkeypatch.setattr(ui_module.subprocess, 'run', submit)
    ui.input_uncertain = fault == 'uncertain'
    with pytest.raises(UiError):
        ui.native_launch_command('primary' if fault == 'instance' else 'secondary',
            child=ui_module.PARENT if fault == 'child' else ui_module.CHILD,
            fixture='activity' if fault == 'fixture' else 'policy', role='S')
    ui.require_child_overlay_session.assert_not_called()
    submit.assert_not_called()


@pytest.mark.parametrize('locked', [False, True])
@pytest.mark.parametrize('permission', [False, True])
def test_soft_denial_needs_attributed_permission_and_stable_public_boundary(monkeypatch, locked, permission):
    ui = launch_ui(monkeypatch)
    ui.wait = lambda predicate, *_args, **_kwargs: predicate()
    ui.require_lock_session = Mock(return_value='owned-session')
    ui.shell_lock_snapshot = Mock(return_value=object())
    monkeypatch.setattr(ui_module.time, 'monotonic', Mock(side_effect=[0, 2.1]))
    submit = Mock(return_value=SimpleNamespace(returncode=203, stdout=b'', stderr=b''))
    monkeypatch.setattr(ui_module.subprocess, 'run', submit)
    journal = Mock(return_value={'status': 'read', 'entries': 1,
        'exec_errors': ['permission-denied'] if permission else ['missing-file']})
    monkeypatch.setattr(ui_module, 'native_execution_journal_diagnostic', journal)
    if permission:
        ui.native_launch_command('secondary', child=ui_module.CHILD,
            role='S', blocked=True, locked=locked)
    else:
        with pytest.raises(UiError, match='native-execution-denial'):
            ui.native_launch_command('secondary', child=ui_module.CHILD,
                role='S', blocked=True, locked=locked)
    assert submit.call_count == 1
    assert journal.call_args.kwargs == {'executable':
        '/opt/onpc-test-fixtures/Applications/Versioned/Lunar Client-3.7.17.AppImage'}
    assert '--wait' in submit.call_args.args[0] and '--pipe' in submit.call_args.args[0]
    if locked:
        ui.desktop_result.assert_not_called()
        ui.native_app_closed.assert_not_called()
        assert ui.shell_lock_snapshot.call_count == 1 + int(permission)
    else:
        assert ui.native_app_closed.call_count == 1 + int(permission)
    ui.prepare_launch_desktop.assert_not_called()
    assert ui.input_uncertain


@pytest.mark.parametrize('role,wrong', [('A', False), ('S', False), ('S', True), ('S', 'legacy')])
def test_instance_owner_requires_declared_native_parent_and_uid(tmp_path, monkeypatch, role, wrong):
    ui = ui_for(Node())
    process = tmp_path / '100'
    owner = tmp_path / '200'
    process.mkdir()
    owner.mkdir()
    # /proc/stat fields 3..22: state, parent, and start time retain identity.
    (process / 'stat').write_text('100 (gui) S 200 ' + '0 ' * 17 + '10')
    (owner / 'stat').write_text('200 (native) S 1 ' + '0 ' * 17 + '11')
    instance = 'secondary' if role == 'S' else 'primary'
    expected = '/opt/onpc-test-fixtures/Applications/' + {
        'A': 'Exact Fixture.AppImage', 'S': 'Versioned/Lunar Client-3.7.17.AppImage'}[role]
    executable = ('/opt/onpc-test-fixtures/Applications/Lunar Client-3.7.17.AppImage'
                  if wrong == 'legacy' else '/private/foreign' if wrong else expected)
    (owner / 'exe').symlink_to(executable)
    (owner / 'cmdline').write_bytes(b'\0'.join([
        expected.encode(), b'--instance', instance.encode(), b'']))
    monkeypatch.setattr(ui_module, 'Path', lambda value: tmp_path / value.removeprefix('/proc/'))
    if wrong:
        with pytest.raises(UiError, match='native-owner'):
            ui.native_app_owner(Node(), role, instance)
    else:
        ui.native_app_owner(Node(), role, instance)


@pytest.mark.parametrize('legacy', [False, True])
def test_soft_journal_diagnostic_accepts_only_the_active_full_path(monkeypatch, legacy):
    unit = 'onpc-test-native-' + 'a' * 32 + '.service'
    executable = '/opt/onpc-test-fixtures/Applications/' + (
        '' if legacy else 'Versioned/') + 'Lunar Client-3.7.17.AppImage'
    entry = {'USER_UNIT': unit, 'EXECUTABLE': executable, 'ERRNO': '13',
        'MESSAGE': unit + ': Failed at step EXEC spawning ' + executable + ': Permission denied'}
    reader = Mock(return_value=SimpleNamespace(stdout=json.dumps(entry).encode(), stderr=b''))
    monkeypatch.setattr(ui_module.subprocess, 'run', reader)
    assert ui_module.native_execution_journal_diagnostic(unit, executable=executable) == {
        'status': 'unavailable' if legacy else 'read', 'entries': 0 if legacy else 1,
        'exec_errors': [] if legacy else ['permission-denied']}
    assert reader.call_count == int(not legacy)


@pytest.mark.parametrize('role,name,instance', [
    ('A', 'allowed', 'primary'), ('S', 'soft', 'secondary')])
def test_native_snapshot_submit_close_bind_same_instance_and_decoder(monkeypatch, role, name, instance):
    import fixture_ui
    ui = ui_for(Node())
    root = Node()
    ui.snapshot_owned_target = Mock(return_value=root)
    ui.surface_available = Mock(return_value=True)
    ui.native_app_owner = Mock()
    fixture = SimpleNamespace(text=Mock(return_value='Ready'), snapshot=Mock(return_value={
        'draft': 'ONPC fixture draft', 'submitted': 'No submitted draft', 'score': 'Moves: 0; token: 0'}))
    constructor = Mock(return_value=fixture)
    monkeypatch.setattr(fixture_ui, 'FixtureUI', constructor)
    ui.require_child_overlay_session = Mock()
    result = ui.run('overlay-native-' + name + '-opened', '')
    constructor.assert_called_once_with(ui, 'native', instance, require=ui_module.require)
    ui.native_app_owner.assert_called_once_with(root, role, instance)
    transport = SimpleNamespace(call=Mock(return_value=json.dumps({
        **result, 'boot_sha256': 'b' * 64}).encode()))
    observer = UiObservations(transport)
    observer.boot_guard = 'b' * 64
    assert observer.observe(result['operation']) == result
    ui.activate_id = Mock()
    ui.native_app_submit(instance, role=role)
    ui.activate_id.assert_called_once_with('onpc-fixture-native-' + instance + '-submit')
    fixture.snapshot.return_value['submitted'] = 'ONPC fixture draft'
    ui.baseline_native_operation('overlay-native-' + name + '-close')
    assert ui.activate_id.call_args.args == ('onpc-fixture-native-' + instance + '-close',)
    ui.input_uncertain = True
    before = ui.native_app_owner.call_count
    with pytest.raises(UiError, match='uncertain-input'):
        ui.baseline_native_operation('overlay-native-' + name + '-close')
    assert ui.native_app_owner.call_count == before


@pytest.mark.parametrize('boundary', ['session', 'restriction'])
def test_locked_denial_ownership_refuses_before_any_execution(monkeypatch, boundary):
    ui = launch_ui(monkeypatch)
    ui.require_lock_session = Mock(side_effect=UiError('ui:lock-session')
        if boundary == 'session' else None)
    ui.shell_lock_snapshot = Mock(side_effect=UiError('ui:lock-restriction'))
    submit = Mock()
    monkeypatch.setattr(ui_module.subprocess, 'run', submit)
    with pytest.raises(UiError, match='ui:lock-'):
        ui.baseline_native_operation('overlay-native-soft-locked-command-blocked')
    submit.assert_not_called()
    ui.desktop_result.assert_not_called()
    ui.native_app_closed.assert_not_called()
