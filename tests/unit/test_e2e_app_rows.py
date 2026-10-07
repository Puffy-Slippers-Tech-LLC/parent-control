"""Complete App Limits collections must never infer absence from partial reads."""
from tools.test_storage import named_input

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
import json

import pytest

import accessible_ui
from app_row_observations import AppRowJourney, PLAN
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from ui_observations import AppRowsObservation, UiObservations


ROW = 'parent-app-0123456789abcdef'


@pytest.mark.parametrize('draft,row', [('match-wildcard', 'consumer-result'),
                                      ('match-rejected-directory', None)])
def test_match_edit_independent_invocation_and_every_failure_stop(draft, row):
    # Same private values and waited Perl children as the existing worker tests;
    # no new storage, VM, display or shared scheduling resource.
    from match_rules import match_edit
    from tests.support.perl import run_perl
    screens = match_edit(draft, 'consumer', editor=('owned-open', 'owned-read'), row=row)
    expected = ['owned-open', 'owned-read', 'consumer-draft-focus',
                'consumer-draft-selected', 'consumer-draft-read', 'consumer-save']
    if row is not None:
        expected.append(row)
    assert list(screens) == expected
    assert screens['consumer-save'] == ('ui:match-save' if row else 'ui:match-rejected')
    program = r'''
use strict; use warnings; use JSON::PP;
BEGIN {$INC{'testapi.pm'}=1;}
package testapi; sub record_info {} sub send_key {} sub type_string {}
package main;
use onpc_app_rows; use onpc_journey;
my ($draft, $row, $stop) = @ARGV;
my @events;
my $j = onpc_journey->new(prefix => 'independent-consumer', review => 0,
    exchange => sub {push @events, $_[0]; die 'refused' if $_[0] eq $stop;
                     return {observed => $_[0]};});
my $ok = eval {onpc_app_rows::match_edit($j, $draft, 'consumer',
    'owned-open', 'owned-read', length($row) ? $row : undef); 1;} ? 1 : 0;
print encode_json({ok => $ok, events => \@events});
'''
    for stop in ('', *expected):
        value = json.loads(run_perl(program, draft, row or '', stop).stdout)
        assert value == {'ok': int(not stop), 'events':
                         expected[:expected.index(stop) + 1] if stop else expected}
    changed = match_edit(draft, 'consumer', editor=('owned-open', 'owned-read'), row=row)
    changed.clear()
    assert match_edit(draft, 'consumer', editor=('owned-open', 'owned-read'), row=row) == screens


@pytest.mark.parametrize('draft,prefix,editor,row', [
    ('unknown', 'consumer', ('owned-open', 'owned-read'), 'result'),
    ('match-wildcard', 'bad prefix', ('owned-open', 'owned-read'), 'result'),
    ('match-wildcard', 'consumer', ('same', 'same'), 'result'),
    ('match-wildcard', 'consumer', ('owned-open', 'owned-read'), None),
    ('match-rejected-directory', 'consumer', ('owned-open', 'owned-read'), 'result'),
    ('match-wildcard', 'consumer', ('owned-open', 'owned-read'), 'consumer-save'),
])
def test_match_edit_invalid_binding_refuses_before_any_worker_observation(draft, prefix, editor, row):
    from match_rules import match_edit
    from tests.support.perl import run_perl
    with pytest.raises(EvidenceError):
        match_edit(draft, prefix, editor=editor, row=row)
    program = r'''
use strict; use warnings; use JSON::PP;
BEGIN {$INC{'testapi.pm'}=1;}
package testapi; sub record_info {} sub send_key {} sub type_string {}
package main;
use onpc_app_rows; use onpc_journey;
my ($draft, $prefix, $open, $read, $row) = @ARGV;
my @events;
my $j = onpc_journey->new(prefix => 'independent-consumer', review => 0,
    exchange => sub {push @events, $_[0]; return {observed => $_[0]};});
my $ok = eval {onpc_app_rows::match_edit($j, $draft, $prefix, $open, $read,
    length($row) ? $row : undef); 1;} ? 1 : 0;
print encode_json({ok => $ok, events => \@events});
'''
    assert json.loads(run_perl(program, draft, prefix, *editor, row or '').stdout) == {
        'ok': 0, 'events': []}


def match_ui():
    app = accessible_ui.MATCH_APP
    rule = accessible_ui.MATCH_RULES[0]
    entry = Node(role='text', identity='parent-match-rule-entry',
                 states=('showing', 'visible', 'sensitive', 'editable'))
    entry.get_text_iface = lambda: rule
    marker = Node(identity='parent-match-rule-app-' + app.removeprefix('parent-app-'), children=[entry])
    responses = [Node(identity='parent-match-rule-' + action) for action in ('save', 'cancel', 'reset')]
    dialog = Node(identity='parent-match-rule-dialog', states=('showing', 'visible', 'active'),
                  children=[marker, *responses])
    button = Node(identity=app + '-match-rule', description='Current match rule: ' + rule)
    row = Node(identity=app, children=[button])
    other = Node(identity=accessible_ui.MATCH_OTHER_APP, children=[
        Node(identity=accessible_ui.MATCH_OTHER_APP + '-match-rule')])
    page = Node(identity='parent-app-limits-page', children=[Node(identity='parent-app-search'),
        Node(identity='parent-app-rows', children=[row, other])])
    root = Node(identity='parent-window', states=('showing', 'visible', 'active'), children=[
        Node(identity='parent-child-selector', children=[Node(identity='parent-child-selected-1002')]), page])
    desktop = Node(children=[root, dialog])
    ui = ui_for(desktop)
    ui.api.Text = SimpleNamespace(get_character_count=len, get_text=lambda text, start, end: text[start:end])
    return ui, root, dialog, marker, entry, button, responses


def test_match_reads_independently_open_editor_and_row_without_input():
    ui, root, dialog, marker, entry, button, responses = match_ui()
    expected = {'app': accessible_ui.MATCH_APP, 'rule': accessible_ui.MATCH_RULES[0]}
    assert ui.read_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, editor=True) == expected
    assert ui.read_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP) == expected
    for node in (entry, button, *responses):
        node.action.do_action.assert_not_called()


@pytest.mark.parametrize('editor', [False, True])
@pytest.mark.parametrize('fault', ['transient', 'incomplete', 'persistent', 'wrong-child', 'wrong-value'])
def test_match_rule_read_retries_only_incomplete_public_observations(editor, fault):
    ui, root, dialog, marker, entry, button, responses = match_ui()
    ui.timeout = .5
    ui.query_errors = (LookupError,)
    stale = Node()
    dialog.children.append(stale)
    def vanished():
        if fault != 'persistent':
            dialog.children.remove(stale)
        if fault == 'wrong-child':
            root.children[0].children[0].identity = 'parent-child-selected-1001'
        if fault == 'wrong-value':
            button.description = 'Current match rule: unbound-value'
            entry.get_text_iface = lambda: 'unbound-value'
        if fault == 'incomplete':
            raise accessible_ui.UiError('ui:incomplete-tree')
        raise LookupError('object disappeared')
    stale.get_name = Mock(side_effect=vanished)
    if fault in ('transient', 'incomplete'):
        assert ui.read_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP,
                                  editor=editor) == {
            'app': accessible_ui.MATCH_APP, 'rule': accessible_ui.MATCH_RULES[0]}
        stale.get_name.assert_called_once()
    else:
        code = ('match-child' if fault == 'wrong-child' else
                'match-value' if fault == 'wrong-value' else 'timeout:match-rule')
        with pytest.raises(accessible_ui.UiError, match=code):
            ui.read_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, editor=editor)
    for node in (entry, button, *responses):
        node.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['wrong-child', 'wrong-app', 'duplicate', 'wrong-owner',
                                 'hidden', 'disabled', 'inactive', 'uncertain', 'ambiguous'])
def test_match_refuses_before_response_input(fault):
    ui, root, dialog, marker, entry, button, responses = match_ui()
    child, app, action = accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, 'save'
    if fault == 'wrong-child': child = accessible_ui.CHILD
    elif fault == 'wrong-app': app = accessible_ui.MATCH_OTHER_APP
    elif fault == 'duplicate':
        duplicate = Node(identity='parent-match-rule-save'); duplicate.parent = dialog
        dialog.children.append(duplicate)
    elif fault == 'wrong-owner': ui.api.get_desktop(0).identity = 'unrelated.application'
    elif fault == 'hidden': entry.states.remove('visible')
    elif fault == 'disabled': entry.states.remove('sensitive')
    elif fault == 'inactive': dialog.states.remove('active')
    elif fault == 'uncertain': ui.input_uncertain = True
    elif fault == 'ambiguous': action = ('save', 'cancel')
    with pytest.raises(accessible_ui.UiError):
        ui.respond_match_rule(child, app, action)
    for node in (entry, button, *responses):
        node.action.do_action.assert_not_called()


@pytest.mark.parametrize('action', ['save', 'cancel', 'reset'])
def test_match_response_inputs_once_then_observes_closure_and_saved_controls(action):
    ui, root, dialog, marker, entry, button, responses = match_ui()
    ui.parent_app_save_snapshot = Mock(return_value=True)
    def respond(_):
        dialog.parent.children.remove(dialog)
        return True
    target = responses[('save', 'cancel', 'reset').index(action)]
    target.action.do_action.side_effect = respond
    assert ui.respond_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, action) == {'closed': action}
    target.action.do_action.assert_called_once()
    ui.parent_app_save_snapshot.assert_called_once_with(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP)


@pytest.mark.parametrize('fault', [None, 'wrong-draft', 'no-report', 'wrong-owner', 'uncertain'])
def test_rejected_match_saves_once_and_leaves_report_open(fault):
    ui, root, dialog, marker, entry, button, responses = match_ui()
    ui.timeout = .2
    entry.get_text_iface = lambda: ('wrong' if fault == 'wrong-draft' else
        accessible_ui.TEXT_VALUES['match-rejected-directory'][1])
    report = Node(identity='feedback-dialog', states=('showing', 'visible', 'active'))
    report.relations = [SimpleNamespace(get_relation_type=lambda: 'controlled-by',
        get_n_targets=lambda: 1, get_target=lambda _: root)]
    if fault == 'uncertain': ui.input_uncertain = True
    if fault == 'wrong-owner': ui.api.get_desktop(0).identity = 'unrelated.application'
    def respond(_):
        desktop = dialog.parent
        desktop.children.remove(dialog)
        if fault != 'no-report':
            desktop.children.append(report); report.parent = desktop
        return True
    responses[0].action.do_action.side_effect = respond
    ui.parent_app_save_snapshot = Mock()
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.respond_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, 'rejected')
    else:
        assert ui.respond_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP,
                                     'rejected') == {'closed': 'rejected'}
        assert report in report.parent.children
    assert responses[0].action.do_action.call_count == (1 if fault in (None, 'no-report') else 0)
    ui.parent_app_save_snapshot.assert_not_called()


@pytest.mark.parametrize('operation', ['parent-report-read', 'parent-report-actions', 'parent-report-refused'])
@pytest.mark.parametrize('fault', [None, 'extra', 'wrong'])
def test_parent_report_projection_crosses_real_controller_decoder(operation, fault):
    key = 'report' if operation.endswith('refused') else 'feedback'
    value = ({'refusal': 'absent'} if key == 'report' else {
        'draft': 'parent-rule-error' if operation.endswith('read') else 'synthetic-first',
        'attachments': ['diagnostic-logs.zip'], 'collection': 'ready',
        'validation': 'none', 'controls': 'ready'})
    if fault == 'extra': value['private'] = 'canary'
    elif fault == 'wrong': value['refusal' if key == 'report' else 'draft'] = 'initial-empty'
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider', key: value}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps({**result,
        'boot_sha256': 'b' * 64}).encode()))
    observer = UiObservations(transport)
    observer.boot_guard = ''
    if fault:
        with pytest.raises(EvidenceError): observer.observe(operation)
    else:
        assert observer.observe(operation) == result


def test_report_review_is_reusable_with_renamed_stages_and_stops_at_every_boundary():
    from parent_reports import report_review
    from tests.support.perl import run_perl
    screens = report_review('renamed')
    program = r'''
use strict; use warnings; use JSON::PP;
BEGIN {$INC{'testapi.pm'}=1;}
our @events;
package testapi;
sub send_key {push @events, ['key', $_[0]];}
sub type_string {push @events, ['text', $_[0]];}
sub record_info {}
package main;
require onpc_feedback_privacy;
my $stop = $ARGV[0];
my $j = onpc_journey->new(prefix=>'independent', review=>0, exchange=>sub {
    push @events, ['observe', $_[0]]; die 'injected-refusal' if $_[0] eq $stop;
    return {observed=>$_[0]};
});
eval {onpc_feedback_privacy::review_parent_report($j, 'renamed');};
print encode_json(\@events);
'''
    full = json.loads(run_perl(program, '').stdout)
    assert [value for kind, value in full if kind == 'observe'] == list(screens)
    assert not any(kind in ('key', 'text') for kind, _value in full)
    assert all('send' not in value for kind, value in full if kind == 'observe')
    for stage in screens:
        events = json.loads(run_perl(program, stage).stdout)
        index = full.index(['observe', stage])
        assert events == full[:index + 1]


def test_parent_report_comparison_refuses_missing_or_changed_draft_after_privacy(tmp_path):
    from installed_journey import JourneyPlan
    from parent_reports import ParentReportJourney, report_review
    plan = JourneyPlan('independent-report', 'independent', report_review('renamed'), {})
    journey = ParentReportJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    def observed(draft='synthetic-first', attachments=('diagnostic-logs.zip',)):
        return {'ui': {'feedback': {'draft': draft, 'attachments': list(attachments),
            'collection': 'ready', 'validation': 'none', 'controls': 'ready'}}}
    with pytest.raises(EvidenceError, match='preserved-draft'):
        journey.check_settings('renamed-feedback-privacy-returned', observed())
    journey.check_settings('renamed-report', observed('parent-rule-error'))
    captured = observed()
    journey.check_settings('renamed-actions', captured)
    captured['ui']['feedback']['attachments'].clear()
    assert journey.report_draft.attachments == ('diagnostic-logs.zip',)
    with pytest.raises(EvidenceError, match='feedback-response'):
        journey.check_settings('renamed-feedback-privacy-returned', captured)
    journey.check_settings('renamed-feedback-privacy-returned', observed())
    journey.check_settings('renamed-feedback-draft-reread', observed())
    with pytest.raises(EvidenceError, match='draft-replay'):
        journey.check_settings('renamed-actions', observed())
    journey.check_settings('renamed-report', observed('parent-rule-error'))
    with pytest.raises(EvidenceError, match='preserved-draft'):
        journey.check_settings('renamed-feedback-draft-reread', observed())


def test_report_close_uses_a_fresh_automatic_report_proof_and_stops_before_input():
    from parent_reports import report_close
    from tests.support.perl import run_perl
    screens = report_close('renamed')
    program = r'''
use strict; use warnings; use JSON::PP;
BEGIN {$INC{'testapi.pm'}=1;}
our @events;
package testapi;
sub send_key {push @events, ['key', $_[0]];} sub record_info {}
package main;
require onpc_feedback_privacy;
my $stop = $ARGV[0];
my $j = onpc_journey->new(prefix=>'independent', review=>0, exchange=>sub {
    push @events, ['observe', $_[0]]; die 'injected-refusal' if $_[0] eq $stop;
    return {observed=>$_[0]};
});
eval {onpc_feedback_privacy::close_parent_report($j, 'renamed');};
print encode_json(\@events);
'''
    full = [['observe', 'renamed-report'],
            ['observe', 'renamed-feedback-draft-closed']]
    assert json.loads(run_perl(program, '').stdout) == full
    for stage in screens:
        assert json.loads(run_perl(program, stage).stdout) == full[:full.index(['observe', stage]) + 1]
    changed = report_close('renamed'); changed.clear()
    assert report_close('renamed') == screens
    for prefix in ('', 'wrong/name', None):
        with pytest.raises(EvidenceError, match='invocation'): report_close(prefix)


@pytest.mark.parametrize('stage', ['restored-rule', 'final-rule', 'review-feedback-privacy-returned'])
@pytest.mark.parametrize('changed', [False, True])
def test_report_case_real_step_compares_before_durable_reply(tmp_path, stage, changed):
    from parent_error_report import PLAN
    from parent_reports import ParentReportJourney
    journey = ParentReportJourney(SimpleNamespace(directory=tmp_path), Mock(), PLAN,
        actions={'native-refuse': Mock(), 'native-verify': Mock()})
    journey.check_settings('confirmed-rule', {'ui': {'match': {
        'app': accessible_ui.MATCH_APP, 'rule': accessible_ui.MATCH_RULES[1]}}})
    feedback = {'draft': 'synthetic-first', 'attachments': ['diagnostic-logs.zip'],
                'collection': 'ready', 'validation': 'none', 'controls': 'ready'}
    journey.check_settings('review-actions', {'ui': {'feedback': feedback}})
    if stage == 'review-feedback-privacy-returned':
        value = {'feedback': {**feedback, 'draft': 'initial-empty' if changed else 'synthetic-first'}}
    else:
        value = {'match': {'app': accessible_ui.MATCH_APP,
                          'rule': accessible_ui.MATCH_RULES[int(not changed)]}}
    journey.steps = [{'stage': s} for s in PLAN.stages[:PLAN.stages.index(stage)]]
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value={
        'operation': PLAN.screen_tags[stage][3:], **value}))
    journey.boot = 'b' * 64
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    check = Mock(wraps=journey.check_settings); journey.check_settings = check
    if changed:
        with pytest.raises(EvidenceError, match='exact-rule|synthetic-draft'): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        assert journey.failed
        journey.progress.assert_not_called()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        journey.progress.assert_called_once()
    check.assert_called_once()


def test_report_case_uses_real_recorder_entry_through_worker_startup(tmp_path):
    from parent_error_report import execute, PLAN
    from parent_reports import ParentReportJourney
    recorder = MagicMock(assertion=Mock())
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
                              verified=SimpleNamespace(inputs={}), guestfs=Mock(),
                              commands=Mock(), recorder=recorder)
    def worker(**options):
        controller = options['guarded_observe'].__self__
        assert type(controller) is ParentReportJourney and controller.plan is PLAN
        assert set(controller.actions) == {'native-refuse', 'native-verify'}
        assert options['validate'].__self__ is controller
        assert options['timeout'] == 1800 and options['authenticate'] is True
        raise EvidenceError('synthetic-worker-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'): execute(recorder, context)
    context.run_worker.assert_called_once()
    assert recorder.step.return_value.__exit__.call_args.args[0] is EvidenceError
    recorder.assertion.assert_not_called()


def test_rejected_report_selector_uses_existing_guarded_snapshot_and_fixture_route(tmp_path, monkeypatch):
    import parent_setup_qualification as qualification
    import check_graphical_smoke as smoke
    from rejected_parent_rule import PLAN
    from parent_reports import ParentReportJourney
    from owned_commands import CommandError
    import runpy
    from tests.support.paths import ROOT
    from tools.test_storage import named_input
    source = tmp_path / 'source'; (source / 'data').mkdir(parents=True)
    (source / 'data/app.json').write_text(json.dumps({'version': '9.8.7'}))
    monkeypatch.setattr(qualification.smoke, 'ROOT', source)
    context = SimpleNamespace()
    result = qualification.RejectedParentRuleQualification.journey(context, Mock())
    assert type(result) is ParentReportJourney and result.plan is PLAN
    assert context.installed_snapshot == 'onpc-v9.8.7'
    with pytest.raises(CommandError, match='rejected-parent-rule-prerequisites'):
        smoke.main(rejected_parent_rule=True)
    execute = Mock(return_value=0); monkeypatch.setattr(smoke, 'main', execute)
    with pytest.raises(SystemExit):
        runpy.run_path(str(ROOT / 'tests/integration/check_e2e_review_a_rejected_parent_rule_s_report.py'), run_name='__main__')
    assert execute.call_args.kwargs == {'assets': named_input(fixture_source=True),
        'provision_credentials': True, 'app_row_observations': True,
        'native_fixtures': True, 'rejected_parent_rule': True}


@pytest.mark.parametrize('fault', [None, 'wrong-draft', 'wrong-message', 'closed'])
def test_match_invalid_response_observes_retained_draft_and_exact_explanation(fault):
    ui, root, dialog, marker, entry, button, responses = match_ui()
    entry.get_text_iface = lambda: 'wrong' if fault == 'wrong-draft' else ''
    entry.description = ''
    def reject(_):
        if fault == 'closed': dialog.parent.children.remove(dialog)
        entry.description = 'wrong' if fault == 'wrong-message' else accessible_ui.MATCH_INVALID['empty']
        return True
    responses[0].action.do_action.side_effect = reject
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.respond_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, 'empty')
        assert responses[0].action.do_action.call_count == (0 if fault == 'wrong-draft' else 1)
    else:
        assert ui.respond_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, 'empty') == {
            'invalid': 'empty', 'message': accessible_ui.MATCH_INVALID['empty']}
        responses[0].action.do_action.assert_called_once()


def test_match_unobserved_response_is_never_replayed():
    ui, root, dialog, marker, entry, button, responses = match_ui()
    with pytest.raises(accessible_ui.UiError, match='timeout:match-closed'):
        ui.respond_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, 'save')
    responses[0].action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', ['query', 'incomplete', 'defunct', 'persistent',
                                 'missing-anchor', 'already-open', 'opened-after-query',
                                 'duplicate', 'wrong-child'])
def test_match_open_distinguishes_indeterminate_absence_from_visible_editor(fault):
    ui, root, dialog, marker, entry, button, responses = match_ui()
    ui.timeout = .5
    ui.query_errors = (LookupError,)
    desktop = dialog.parent
    if fault not in ('already-open', 'opened-after-query', 'duplicate'):
        desktop.children.remove(dialog)
    if fault == 'duplicate':
        desktop.children.append(Node(identity='parent-match-rule-dialog'))
    if fault == 'missing-anchor':
        root.identity = 'unidentified-window'
    else:
        stale = Node(states=('visible', 'showing', 'defunct') if fault == 'defunct'
                     else ('visible', 'showing'))
        desktop.children.append(stale)
        if fault == 'defunct':
            def defunct_state():
                if stale in desktop.children:
                    desktop.children.remove(stale)
                return SimpleNamespace(contains=lambda state: state in stale.states)
            stale.get_state_set = defunct_state
        elif fault not in ('already-open', 'duplicate'):
            def vanished():
                if fault != 'persistent':
                    desktop.children.remove(stale)
                if fault == 'wrong-child':
                    root.children[0].children[0].identity = 'parent-child-selected-1001'
                if fault == 'incomplete':
                    raise accessible_ui.UiError('ui:incomplete-tree')
                raise LookupError('object disappeared')
            stale.get_name = Mock(side_effect=vanished)
    def open_editor(_):
        desktop.children.append(dialog)
        return True
    button.action.do_action.side_effect = open_editor
    if fault in ('query', 'incomplete', 'defunct'):
        assert ui.open_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP) == {
            'app': accessible_ui.MATCH_APP, 'rule': accessible_ui.MATCH_RULES[0]}
        button.action.do_action.assert_called_once()
    else:
        code = ('match-already-open' if fault in ('already-open', 'opened-after-query') else
                'ambiguous-automation-id' if fault == 'duplicate' else
                'match-child' if fault == 'wrong-child' else 'timeout:match-before-open')
        with pytest.raises(accessible_ui.UiError, match=code):
            ui.open_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP)
        button.action.do_action.assert_not_called()
    for node in (entry, *responses):
        node.action.do_action.assert_not_called()


def test_match_open_uncertain_action_is_never_replayed():
    ui, root, dialog, marker, entry, button, responses = match_ui()
    dialog.parent.children.remove(dialog)
    button.action.do_action.side_effect = LookupError('uncertain dispatch')
    with pytest.raises(LookupError):
        ui.open_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP)
    assert ui.input_uncertain
    button.action.do_action.assert_called_once()
    with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
        ui.open_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP)
    button.action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', ['transient', 'incomplete', 'persistent', 'wrong-child'])
def test_match_response_retries_only_preinput_reads_with_fresh_recipient(fault):
    ui, root, dialog, marker, entry, button, responses = match_ui()
    ui.timeout = .5
    ui.query_errors = (LookupError,)
    # The invalid-draft toast may disappear during the next complete read.
    stale = Node()
    dialog.children.append(stale)
    def vanished():
        if fault != 'persistent':
            dialog.children.remove(stale)
        if fault == 'wrong-child':
            root.children[0].children[0].identity = 'parent-child-selected-1001'
        if fault == 'incomplete':
            raise accessible_ui.UiError('ui:incomplete-tree')
        raise LookupError('object disappeared')
    stale.get_name = Mock(side_effect=vanished)
    ui.parent_app_save_snapshot = Mock(return_value=True)
    def cancel(_):
        dialog.parent.children.remove(dialog)
        return True
    responses[1].action.do_action.side_effect = cancel
    if fault in ('transient', 'incomplete'):
        assert ui.respond_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP,
                                     'cancel') == {'closed': 'cancel'}
        stale.get_name.assert_called_once()
        responses[1].action.do_action.assert_called_once()
    else:
        with pytest.raises(accessible_ui.UiError, match=(
                'match-child' if fault == 'wrong-child' else 'timeout:match-response-entry')):
            ui.respond_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, 'cancel')
        responses[1].action.do_action.assert_not_called()
        ui.parent_app_save_snapshot.assert_not_called()
    for node in (entry, button, responses[0], responses[2]):
        node.action.do_action.assert_not_called()


def test_match_response_query_error_during_action_is_not_retried():
    ui, root, dialog, marker, entry, button, responses = match_ui()
    ui.query_errors = (LookupError,)
    responses[1].action.do_action.side_effect = LookupError('uncertain dispatch')
    with pytest.raises(accessible_ui.UiError, match='match-response-query:action'):
        ui.respond_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, 'cancel')
    assert ui.input_uncertain
    responses[1].action.do_action.assert_called_once()
    with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
        ui.respond_match_rule(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, 'cancel')
    responses[1].action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', ['transient', 'persistent', 'wrong-child'])
def test_match_selected_observation_retries_only_reads_before_further_input(fault):
    ui, root, dialog, marker, entry, button, responses = match_ui()
    ui.timeout = .5  # Permit one read-only retry after the shared 0.2s interval.
    entry.states.add('focused')
    ui.query_errors = (LookupError,)
    stale = Node()
    dialog.children.append(stale)
    def vanished():
        if fault != 'persistent': dialog.children.remove(stale)
        raise LookupError('object disappeared')
    stale.get_name = Mock(side_effect=vanished)
    child = accessible_ui.CHILD if fault == 'wrong-child' else accessible_ui.EXISTING_CHILD
    if fault == 'transient':
        assert ui.text_operation('text-match-precise-selected', child=child) is None
        stale.get_name.assert_called_once()
    else:
        with pytest.raises(accessible_ui.UiError, match='match-child' if fault == 'wrong-child' else 'timeout:text-recipient'):
            ui.text_operation('text-match-precise-selected', child=child)
    if fault == 'transient':
        entry.setText.assert_called_once_with(accessible_ui.TEXT_VALUES['match-precise'][1])
    else:
        entry.setText.assert_not_called()
    for node in (entry, button, *responses):
        node.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'changed', 'missing', 'extra', 'wrong-app'])
def test_match_projection_crosses_real_controller_decoder(fault):
    value = {'app': accessible_ui.MATCH_APP, 'rule': accessible_ui.MATCH_RULES[1]}
    if fault == 'changed': value['rule'] = 'private-rule'
    elif fault == 'missing': value.pop('rule')
    elif fault == 'extra': value['private'] = 'value'
    elif fault == 'wrong-app': value['app'] = accessible_ui.MATCH_OTHER_APP
    result = {'operation': 'match-row', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider', 'match': value}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps({**result, 'boot_sha256': 'b' * 64}).encode()))
    if fault:
        with pytest.raises(EvidenceError, match='match-response'):
            UiObservations(transport).observe('match-row', child='existing')
    else:
        assert UiObservations(transport).observe('match-row', child='existing') == result


def test_match_comparison_has_renamed_endpoints_immutable_capture_and_refusals(tmp_path):
    from installed_journey import JourneyPlan
    from match_rules import MatchRuleJourney
    plan = JourneyPlan('independent-match', 'independent',
        {'before': 'ui:match-row', 'after': 'ui:match-row'}, {},
        match_checks={'before': accessible_ui.MATCH_RULES[0], 'after': 'before'})
    journey = MatchRuleJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    def observed(rule):
        return {'ui': {'match': {'app': accessible_ui.MATCH_APP, 'rule': rule}}}
    original = observed(accessible_ui.MATCH_RULES[0])
    with pytest.raises(EvidenceError, match='missing-capture'):
        journey.check_settings('after', original)
    journey.check_settings('before', original)
    original['ui']['match']['rule'] = accessible_ui.MATCH_RULES[1]
    plan.match_checks.clear()
    with pytest.raises(EvidenceError, match='exact-rule'):
        journey.check_settings('after', original)
    journey.check_settings('after', observed(accessible_ui.MATCH_RULES[0]))
    with pytest.raises(EvidenceError, match='replay'):
        journey.check_settings('after', observed(accessible_ui.MATCH_RULES[0]))


@pytest.mark.parametrize('changed', [False, True])
@pytest.mark.parametrize('reset', [False, True])
def test_match_real_step_compares_before_durable_reply(tmp_path, changed, reset):
    from match_save_cancel import journey as make_journey, PLAN, EDITOR_PLAN
    match_plan = EDITOR_PLAN if reset else PLAN
    journey = make_journey(SimpleNamespace(directory=tmp_path), Mock(), match_plan, actions={
        'native-refuse': Mock(), 'native-verify': Mock()})
    journey.steps = [{'stage': stage} for stage in match_plan.stages[:-1]]
    if reset: journey.match_values['initial-rule'] = (accessible_ui.MATCH_APP, accessible_ui.MATCH_RULES[0])
    stage = 'final-rule' if reset else 'saved-rule'
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value={
        'operation': 'match-row', 'match': {'app': accessible_ui.MATCH_APP,
        'rule': accessible_ui.MATCH_RULES[int(changed) if reset else int(not changed)]}}))
    journey.boot = 'b' * 64
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if changed:
        with pytest.raises(EvidenceError, match='exact-rule'): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('editor', [False, True])
def test_match_qualification_selects_snapshot_and_fixture_asset_route(tmp_path, monkeypatch, editor):
    import parent_setup_qualification as qualification
    import check_graphical_smoke as smoke
    from match_save_cancel import PLAN, EDITOR_PLAN
    match_plan = EDITOR_PLAN if editor else PLAN
    from match_rules import MatchRuleJourney
    from owned_commands import CommandError
    import runpy
    from tests.support.paths import ROOT
    from tools.test_storage import named_input
    source = tmp_path / 'source'; (source / 'data').mkdir(parents=True)
    (source / 'data/app.json').write_text(json.dumps({'version': '9.8.7'}))
    monkeypatch.setattr(qualification.smoke, 'ROOT', source)
    context = SimpleNamespace()
    selected = qualification.MatchEditorQualification if editor else qualification.MatchSaveCancelQualification
    flag = 'match_editor' if editor else 'match_save_cancel'
    result = selected.journey(context, Mock())
    assert type(result) is MatchRuleJourney and result.plan is match_plan
    assert context.installed_snapshot == 'onpc-v9.8.7'
    with pytest.raises(CommandError, match='match-editor-prerequisites' if editor else 'match-save-cancel-prerequisites'):
        smoke.main(**{flag: True})
    execute = Mock(return_value=0); monkeypatch.setattr(smoke, 'main', execute)
    with pytest.raises(SystemExit):
        runpy.run_path(str(ROOT / 'tests/integration' / ('check_e2e_' + flag + '.py')), run_name='__main__')
    assert execute.call_args.kwargs == {'assets': named_input(fixture_source=True),
        'provision_credentials': True, 'app_row_observations': True,
        'native_fixtures': True, flag: True}


@pytest.mark.parametrize('fault', [None, 'message', 'extra'])
def test_match_invalid_projection_crosses_real_decoder(fault):
    value = {'invalid': 'empty', 'message': accessible_ui.MATCH_INVALID['empty']}
    if fault == 'message': value['message'] = 'wrong'
    if fault == 'extra': value['private'] = 'value'
    result = {'operation': 'match-invalid-empty', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider', 'match': value}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps({**result, 'boot_sha256': 'b' * 64}).encode()))
    if fault:
        with pytest.raises(EvidenceError, match='match-response'):
            UiObservations(transport).observe('match-invalid-empty', child='existing')
    else:
        assert UiObservations(transport).observe('match-invalid-empty', child='existing') == result


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


@pytest.mark.parametrize('boundary', ['control', 'finished'])
def test_debounced_row_visibility_discards_whole_projection_before_retry(boundary):
    ui, _, _, row, buttons, match = app_ui()
    original = ui.snapshot_owned_target
    transient = True
    finished = False
    def lookup(identity, **kwargs):
        nonlocal transient, finished
        node = original(identity, **kwargs)
        if transient and identity == ROW + ('-access-allowed' if boundary == 'control'
                                            else '-match-precise'):
            transient = False
            if boundary == 'control':
                row.states.discard('visible')
                buttons[0].states.discard('visible')
            else:
                finished = True
        return node
    def name():
        if finished:
            row.states.discard('visible')
        return 'Fixture application'
    ui.snapshot_owned_target = lookup
    row.get_name = name
    with pytest.raises(accessible_ui.UiError, match='^ui:incomplete-tree$'):
        ui.app_rows(accessible_ui.CHILD, include_names=boundary == 'finished')
    # A fresh read observes the settled filter result without repeating input.
    assert ui.app_rows(accessible_ui.CHILD, expected_ids=()) == ()
    for node in (row, *buttons, match):
        node.action.do_action.assert_not_called()


def test_child_visibility_preceding_row_visibility_reacquires_one_complete_projection():
    ui, _, _, row, buttons, match = app_ui()
    buttons[0].states.discard('visible')
    original = ui.nodes
    traversals = 0
    def nodes(*args, **kwargs):
        nonlocal traversals
        traversals += 1
        if traversals == 2:
            row.states.discard('visible')
        return original(*args, **kwargs)
    ui.nodes = nodes
    assert ui.app_rows(accessible_ui.CHILD, expected_ids=()) == ()
    assert traversals == 2
    for node in (row, *buttons, match):
        node.action.do_action.assert_not_called()


def test_hidden_policy_control_in_stable_visible_row_remains_terminal_after_one_complete_recheck():
    ui, _, _, _, buttons, _ = app_ui()
    buttons[0].states.discard('visible')
    ui.nodes = Mock(wraps=ui.nodes)
    with pytest.raises(accessible_ui.UiError, match='^ui:app-row-target$'):
        ui.app_rows(accessible_ui.CHILD)
    assert ui.nodes.call_count == 2
    buttons[0].action.do_action.assert_not_called()


@pytest.mark.parametrize('name', ['Fixture application', '', 'x' * 513])
def test_language_names_share_complete_owned_policy_projection(name):
    ui, page, rows, row, buttons, match = app_ui()
    row.name = name
    if name and len(name) <= 512:
        assert ui.app_rows(accessible_ui.CHILD, include_names=True) == ((ROW, 'allowed', 'precise', name),)
    else:
        with pytest.raises(accessible_ui.UiError, match='app-row-name'):
            ui.app_rows(accessible_ui.CHILD, include_names=True)
    for node in (row, *buttons, match): node.action.do_action.assert_not_called()


def access_ui():
    ui, page, rows, row, buttons, match = app_ui()
    root = ui.find_id('parent-window')
    root.states.add('active')
    root.children[0].children[0].identity = 'parent-child-selected-1002'
    row.identity = accessible_ui.MATCH_APP
    for node in (*buttons, row.children[-1], match):
        node.identity = node.identity.replace(ROW, accessible_ui.MATCH_APP)
    row.children[-1].states.add('sensitive')
    return ui, root, buttons


@pytest.mark.parametrize('fault', ['missing', 'outside-scope', 'hidden', 'defunct'])
def test_access_target_diagnostic_identifies_refusal_without_input_or_private_text(fault):
    ui, root, buttons = access_ui()
    target = buttons[0]
    target.name = 'private name must not be exported'
    target.description = 'private description must not be exported'
    if fault in ('missing', 'outside-scope'):
        target.parent.children.remove(target)
        if fault == 'outside-scope':
            root.children.append(target)
            target.parent = root
    elif fault == 'hidden':
        target.states.remove('visible')
    else:
        target.states.add('defunct')
    with pytest.raises(accessible_ui.UiError, match='^ui:match-target$') as caught:
        ui.choose_app_access(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP,
                             target.identity)
    caught.value.add_note('ui:match-target:private-id:missing')
    caught.value.add_note('ui:match-target:' + target.identity + ':private-reason')
    diagnostic = accessible_ui.adapter_failure_diagnostic(caught.value)
    assert diagnostic['match_targets'] == [{'id': target.identity, 'reason': fault}]
    assert 'private' not in json.dumps(diagnostic)
    assert not ui.input_uncertain
    for button in buttons:
        button.action.do_action.assert_not_called()


@pytest.mark.parametrize('choice', accessible_ui.ACCESS_CHOICES)
def test_access_one_action_save_wait_and_independent_row_read(choice):
    ui, root, buttons = access_ui()
    target = next(node for node in buttons if node.identity.endswith('-access-' + choice))
    def select(_):
        for button in buttons:
            button.states.discard('pressed')
        target.states.add('pressed')
        return True
    target.action.do_action.side_effect = select
    assert ui.choose_app_access(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP,
                               target.identity) == {'chosen': choice}
    assert ui.read_app_access(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP) == {
        'app': accessible_ui.MATCH_APP, 'choice': choice}
    target.action.do_action.assert_called_once()
    for button in buttons:
        button.component.grab_focus.assert_not_called()
        if button is not target: button.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['wrong-row', 'wrong-child', 'disabled', 'inactive',
                                 'hidden', 'duplicate', 'wrong-owner', 'uncertain'])
def test_access_refuses_before_any_choice_input(fault):
    ui, root, buttons = access_ui()
    target = buttons[0]
    child = accessible_ui.EXISTING_CHILD
    control = target.identity
    if fault == 'wrong-row': control = accessible_ui.MATCH_OTHER_APP + '-access-allowed'
    elif fault == 'wrong-child': child = accessible_ui.CHILD
    elif fault == 'disabled': target.states.remove('sensitive')
    elif fault == 'inactive': root.states.remove('active')
    elif fault == 'hidden': target.states.remove('visible')
    elif fault == 'duplicate': target.parent.children.append(Node(identity=control))
    elif fault == 'wrong-owner': ui.api.get_desktop(0).identity = 'foreign.application'
    elif fault == 'uncertain': ui.input_uncertain = True
    with pytest.raises(accessible_ui.UiError):
        ui.choose_app_access(child, accessible_ui.MATCH_APP, control)
    for button in buttons: button.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['uncertain-action', 'save-failure'])
def test_access_input_is_not_repeated_after_action_or_observation_failure(fault):
    ui, root, buttons = access_ui()
    if fault == 'uncertain-action':
        buttons[0].action.do_action.side_effect = LookupError('uncertain action')
    else:
        ui.parent_app_save_snapshot = Mock(side_effect=accessible_ui.UiError('ui:parent-save-error-report'))
    with pytest.raises((LookupError, accessible_ui.UiError)):
        ui.choose_app_access(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, buttons[0].identity)
    buttons[0].action.do_action.assert_called_once()
    if fault == 'uncertain-action':
        assert ui.input_uncertain
        with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
            ui.choose_app_access(accessible_ui.EXISTING_CHILD, accessible_ui.MATCH_APP, buttons[0].identity)
        buttons[0].action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', [None, 'choice', 'app', 'extra', 'missing'])
def test_access_projection_crosses_real_controller_decoder(fault):
    value = {'app': accessible_ui.MATCH_APP, 'choice': 'permanent'}
    if fault == 'choice': value['choice'] = 'private-choice'
    elif fault == 'app': value['app'] = accessible_ui.MATCH_OTHER_APP
    elif fault == 'extra': value['private'] = 'value'
    elif fault == 'missing': value.pop('choice')
    result = {'operation': 'access-row', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider', 'access': value}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps({**result, 'boot_sha256': 'b' * 64}).encode()))
    if fault:
        with pytest.raises(EvidenceError, match='access-response'):
            UiObservations(transport).observe('access-row', child='existing')
    else:
        assert UiObservations(transport).observe('access-row', child='existing') == result


@pytest.mark.parametrize('changed', [False, True])
def test_access_independent_plan_real_step_compares_before_durable_reply(tmp_path, changed):
    from installed_journey import JourneyPlan
    from access_choices import AccessChoiceJourney
    plan = JourneyPlan('independent-access', 'independent', {'renamed': 'ui:access-row'}, {},
        child_bindings={'renamed': 'existing'}, access_checks={'renamed': 'permanent'})
    journey = AccessChoiceJourney(SimpleNamespace(directory=tmp_path), Mock(), plan, actions={})
    plan.access_checks.clear()  # The comparison declaration is captured immutably.
    journey.steps = [{'stage': stage} for stage in plan.stages[:-1]]
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value={
        'operation': 'access-row', 'access': {'app': accessible_ui.MATCH_APP,
                                           'choice': 'allowed' if changed else 'permanent'}}))
    journey.boot = 'b' * 64
    (tmp_path / 'renamed.request.json').write_text(json.dumps({'stage': 'renamed', 'screenshot': None}))
    if changed:
        with pytest.raises(EvidenceError, match='exact-choice'): journey.step(Mock())
        assert not (tmp_path / 'renamed.reply.json').exists()
    else:
        journey.step(Mock())
        assert (tmp_path / 'renamed.reply.json').exists()
        with pytest.raises(EvidenceError, match='replay'):
            journey.check_settings('renamed', {'ui': {'access': {
                'app': accessible_ui.MATCH_APP, 'choice': 'permanent'}}})


@pytest.mark.parametrize('boundary', [None, 'renamed-choice', 'renamed-row'])
def test_access_composite_independent_names_and_refusal_stop(boundary):
    from tests.support.perl import run_perl
    program = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN {$INC{'testapi.pm'}=1;}
package testapi; sub record_info {}
package main;
require onpc_app_rows;
my $journey = onpc_journey->new(prefix=>'independent', review=>0, exchange=>sub {
    push @events, $_[0]; FAIL return {observed=>$_[0]};
});
eval {onpc_app_rows::access_choice($journey, 'renamed-choice', 'renamed-row');};
print encode_json(\@events);
'''
    stop = "die 'refused' if $_[0] eq '" + boundary + "';" if boundary else ''
    assert json.loads(run_perl(program.replace('FAIL', stop)).stdout) == (
        ['renamed-choice'] if boundary == 'renamed-choice' else ['renamed-choice', 'renamed-row'])


def test_access_qualification_selects_snapshot_and_fixture_assets(tmp_path, monkeypatch):
    import parent_setup_qualification as qualification
    import check_graphical_smoke as smoke
    from access_choices import PLAN, AccessChoiceJourney
    from owned_commands import CommandError
    import runpy
    from tests.support.paths import ROOT
    from tools.test_storage import named_input
    source = tmp_path / 'source'; (source / 'data').mkdir(parents=True)
    (source / 'data/app.json').write_text(json.dumps({'version': '9.8.7'}))
    monkeypatch.setattr(qualification.smoke, 'ROOT', source)
    context = SimpleNamespace()
    result = qualification.AccessChoicesQualification.journey(context, Mock())
    assert type(result) is AccessChoiceJourney and result.plan is PLAN
    assert context.installed_snapshot == 'onpc-v9.8.7'
    with pytest.raises(CommandError, match='access-choices-prerequisites'):
        smoke.main(access_choices=True)
    execute = Mock(return_value=0); monkeypatch.setattr(smoke, 'main', execute)
    with pytest.raises(SystemExit):
        runpy.run_path(str(ROOT / 'tests/integration/check_e2e_access_choices.py'), run_name='__main__')
    assert execute.call_args.kwargs == {'assets': named_input(fixture_source=True),
        'provision_credentials': True, 'app_row_observations': True,
        'native_fixtures': True, 'access_choices': True}


def test_policy_qualification_pattern_is_representable_with_baseline_fixtures(tmp_path):
    from pathlib import Path
    from oh_no_parent_control.execution_policy import FapolicydPolicy
    from tests.fixtures.build_test_applications import NATIVE_NAMES
    from policy_qualification import PLAN as policy_plan

    for name in NATIVE_NAMES:
        target = tmp_path / name
        target.write_bytes(b'\x7fELF fixture ' + name.encode())
        target.chmod(0o755)
    pattern = str(tmp_path / Path(policy_plan.match_checks['filtered-match']).name)
    issues = []
    rules = FapolicydPolicy.render(
        {1002: (str(tmp_path / NATIVE_NAMES[0]),)}, {1002: (pattern,)}, issues=issues)
    assert issues == []
    assert f'deny_syslog perm=execute uid=1002 : dir={tmp_path}/' in rules


@pytest.mark.parametrize('filters', [(), (('match-rule', 3), ('access-rule', 7))])
@pytest.mark.parametrize('draft', ['match-wildcard', 'match-wildcard-appimages'])
def test_policy_composite_independent_names_and_every_refusal_stop(filters, draft):
    from policy_edits import policy_edit
    from tests.support.perl import run_perl
    screens = policy_edit(accessible_ui.MATCH_APP, draft, 'permanent',
                          'renamed', filters=filters)
    program = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN {$INC{'testapi.pm'}=1;}
package testapi;
sub record_info {} sub send_key {push @main::events, ['key', $_[0]];}
sub type_string {push @main::events, ['text', $_[0]];}
package main;
require onpc_app_rows;
my ($app, $filters, $draft) = @ARGV;
my $journey = onpc_journey->new(prefix=>'independent', review=>0, exchange=>sub {
    push @events, ['observe', $_[0]]; FAIL return {observed=>$_[0]};
});
eval {onpc_app_rows::edit_policy($journey, $app, $draft, 'permanent', 'renamed', decode_json($filters));};
print encode_json(\@events);
'''
    full = json.loads(run_perl(program.replace('FAIL', ''), accessible_ui.MATCH_APP,
                               json.dumps(filters), draft).stdout)
    assert [value for kind, value in full if kind == 'observe'] == list(screens)
    assert not any(kind in ('text', 'key') for kind, _value in full)
    assert screens['renamed-draft-selected'] == 'ui:text-' + draft + '-selected'
    for stage in screens:
        stop = "die 'refused' if $_[0] eq '" + stage + "';"
        events = json.loads(run_perl(program.replace('FAIL', stop), accessible_ui.MATCH_APP,
                                     json.dumps(filters), draft).stdout)
        assert events == full[:full.index(['observe', stage]) + 1]


@pytest.mark.parametrize('fault', ['app', 'duplicate', 'kind', 'mask'])
def test_policy_declarations_and_worker_refuse_invalid_binding_before_input(fault):
    from policy_edits import policy_edit
    from tests.support.perl import run_perl
    app = accessible_ui.MATCH_OTHER_APP if fault == 'app' else accessible_ui.MATCH_APP
    filters = {'app': (), 'duplicate': (('match-rule', 3), ('match-rule', 3)),
               'kind': (('unknown', 1),), 'mask': (('match-rule', 4),)}[fault]
    with pytest.raises(EvidenceError, match='policy:'):
        policy_edit(app, 'match-wildcard', 'permanent', 'renamed', filters=filters)
    program = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN {$INC{'testapi.pm'}=1;}
package testapi; sub record_info {} sub send_key {push @main::events,'input';}
sub type_string {push @main::events,'input';}
package main; require onpc_app_rows;
my ($app, $filters)=@ARGV;
my $j=onpc_journey->new(prefix=>'independent', review=>0, exchange=>sub {push @events,$_[0];});
eval {onpc_app_rows::edit_policy($j, $app, 'match-wildcard', 'permanent', 'renamed', decode_json($filters));};
die 'expected refusal' unless $@ =~ /^policy:/;
print encode_json(\@events);
'''
    assert json.loads(run_perl(program, app, json.dumps(filters)).stdout) == []


@pytest.mark.parametrize('changed', [None, 'match', 'access', 'missing-capture'])
def test_policy_exact_comparisons_use_real_step_and_refuse_before_reply(tmp_path, changed):
    from access_choices import AccessChoiceJourney
    from installed_journey import JourneyPlan
    plan = JourneyPlan('renamed-policy', 'independent', {
        'capture': 'ui:match-row', 'reread': 'ui:match-row', 'choice': 'ui:access-row'}, {},
        match_checks={'capture': accessible_ui.MATCH_RULES[1], 'reread': 'capture'},
        access_checks={'choice': 'permanent'})
    journey = AccessChoiceJourney(SimpleNamespace(directory=tmp_path), Mock(), plan, actions={})
    plan.match_checks.clear(); plan.access_checks.clear()
    captured = {'ui': {'match': {'app': accessible_ui.MATCH_APP, 'rule': accessible_ui.MATCH_RULES[1]}}}
    if changed != 'missing-capture':
        journey.check_settings('capture', captured)
        captured['ui']['match']['rule'] = accessible_ui.MATCH_RULES[0]
    journey.boot = 'b' * 64
    stage = 'choice' if changed in (None, 'access') else 'reread'
    journey.steps = [{'stage': value} for value in plan.stages[:plan.stages.index(stage)]]
    result = ({'access': {'app': accessible_ui.MATCH_APP,
                         'choice': 'allowed' if changed == 'access' else 'permanent'}}
              if stage == 'choice' else {'match': {'app': accessible_ui.MATCH_APP,
                  'rule': accessible_ui.MATCH_RULES[int(changed != 'match')]}})
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={
        'operation': plan.screen_tags[stage][3:], **result}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if changed:
        with pytest.raises(EvidenceError, match='exact-rule|exact-choice|missing-capture'):
            journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
    if changed != 'missing-capture':
        with pytest.raises(EvidenceError, match='replay'):
            journey.check_settings('capture', captured)


def test_policy_qualification_selects_snapshot_and_fixture_assets(tmp_path, monkeypatch):
    import parent_setup_qualification as qualification
    import check_graphical_smoke as smoke
    from policy_qualification import PLAN
    from access_choices import AccessChoiceJourney
    from owned_commands import CommandError
    import runpy
    from tests.support.paths import ROOT
    from tools.test_storage import named_input
    source = tmp_path / 'source'; (source / 'data').mkdir(parents=True)
    (source / 'data/app.json').write_text(json.dumps({'version': '9.8.7'}))
    monkeypatch.setattr(qualification.smoke, 'ROOT', source)
    context = SimpleNamespace()
    result = qualification.PolicyQualification.journey(context, Mock())
    assert type(result) is AccessChoiceJourney and result.plan is PLAN
    assert context.installed_snapshot == 'onpc-v9.8.7'
    with pytest.raises(CommandError, match='policy-prerequisites'):
        smoke.main(policy_edit=True)
    with pytest.raises(CommandError, match='policy-prerequisites'):
        smoke.main(native_fixtures=True, policy_edit=True, access_choices=True)
    execute = Mock(return_value=0); monkeypatch.setattr(smoke, 'main', execute)
    with pytest.raises(SystemExit):
        runpy.run_path(str(ROOT / 'tests/integration/check_e2e_policy.py'), run_name='__main__')
    assert execute.call_args.kwargs == {'assets': named_input(fixture_source=True),
        'provision_credentials': True, 'app_row_observations': True,
        'native_fixtures': True, 'policy_edit': True}


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
    ui.nodes = Mock(wraps=ui.nodes)
    with pytest.raises((accessible_ui.UiError, LookupError)):
        ui.app_rows(child, **options)
    assert ui.nodes.call_count == 1


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
    result = {'operation': operation, 'interface': 'ApplicationUI+external-provider', 'outcome': 'passed',
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
    result = {'operation': operation, 'interface': 'ApplicationUI+external-provider', 'outcome': 'passed',
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
    assert check.ASSETS == named_input()


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
        with pytest.raises(EvidenceError, match='exact-results'):
            journey.check_settings(stage, observed(()))
        journey.check_settings(stage, observed(search_rows('catalogue-name')))
    for stage in ('absent-rows', 'reopened-absent'):
        with pytest.raises(EvidenceError, match='exact-results'):
            journey.check_settings(stage, observed(expected_rows()))
        journey.check_settings(stage, observed(()))
    with pytest.raises(EvidenceError, match='unchanged-policies'):
        journey.check_settings('cleared-rows', observed(()))
    journey.check_settings('cleared-rows', observed(expected_rows()))


@pytest.mark.parametrize('worker', ['catalogue_search', 'catalogue_filters', 'match_save_cancel', 'match_editor_validation', 'access_choices', 'policy_edit', 'rejected_parent_rule', 'parent_error_report'])
def test_catalogue_worker_sequence_and_every_refusal_stop(worker):
    from catalogue_search import PLAN as search_plan
    from catalogue import PLAN as filter_plan
    from match_save_cancel import PLAN as match_plan
    from match_save_cancel import EDITOR_PLAN as editor_plan
    from access_choices import PLAN as access_plan
    from policy_qualification import PLAN as policy_plan
    from rejected_parent_rule import PLAN as report_plan
    from parent_error_report import PLAN as report_case_plan
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
require onpc_fresh_thirty_allowance;
eval {onpc_app_rows::catalogue_search(sub {push @events,$_[0]; FAIL return {observed=>$_[0]};});};
print encode_json(\@events);
'''
    program = program.replace('onpc_app_rows::catalogue_search',
        'onpc_fresh_thirty_allowance::parent_error_report' if worker == 'parent_error_report' else 'onpc_app_rows::' + worker)
    expected = list({'catalogue_search': search_plan, 'catalogue_filters': filter_plan,
                     'match_save_cancel': match_plan, 'match_editor_validation': editor_plan,
                     'access_choices': access_plan, 'policy_edit': policy_plan,
                     'rejected_parent_rule': report_plan,
                     'parent_error_report': report_case_plan}[worker].screen_tags)
    for boundary in (None, *expected):
        stop = "die 'refused' if $_[0] eq '" + boundary + "';" if boundary else ''
        result = run_perl(program.replace('FAIL', stop))
        assert json.loads(result.stdout) == (expected[:expected.index(boundary) + 1]
                                            if boundary else expected + ['power'])


def test_filter_leaves_use_canonical_values_and_final_state():
    ui, page, *_ = app_ui()
    root = ui.find_id('parent-window')
    root.states.add('active')
    ui.find_id('parent-child-selector').children[0].role = 'label'
    search = ui.find_id('parent-app-search')
    search.states.add('editable')
    selector = Node(identity='parent-filter-match-rule')
    selector.value = list(accessible_ui.FILTER_OPTIONS['match-rule'])
    selector.parent = root
    root.children.append(selector)
    ui._invoke_target = Mock()
    ui.activate_id = Mock()
    assert ui.catalogue_filter(accessible_ui.CHILD, 'match-rule', 2, 'open') == {'ready': 'match-rule'}
    ui.activate_id.assert_not_called()
    assert ui.catalogue_filter(accessible_ui.CHILD, 'match-rule', 2, 'pattern') == {
        'state': False, 'activated': True}
    assert ui.catalogue_filter(accessible_ui.CHILD, 'match-rule', 2, 'precise') == {
        'state': True, 'activated': False}
    selector.setValue.assert_called_once_with(['precise'])
    assert selector.getValue() == ['precise']
    ui._invoke_target.assert_not_called()
    with pytest.raises(accessible_ui.UiError, match='wrong-child'):
        ui.catalogue_filter(accessible_ui.EXISTING_CHILD, 'match-rule', 2, 'pattern')
    root.children.remove(selector)
    with pytest.raises(accessible_ui.UiError):
        ui.catalogue_filter(accessible_ui.CHILD, 'match-rule', 2, 'pattern')
    selector.setValue.assert_called_once()


def test_filter_composite_is_independently_reusable_and_refusal_stops_later_input():
    from journey_blocks import filter_screens
    from tests.support.perl import run_perl
    assert filter_screens('match-rule', 2, 'renamed') == {
        f'renamed-{action}': f'ui:filter-match-rule-2-{action}'
        for action in ('open', 'pattern', 'precise')}
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
    expected = ['renamed-open', 'renamed-pattern', 'renamed-precise']
    for boundary in (None, *[stage for stage in expected if not stage.startswith('key:')]):
        stop = "die 'refused' if $_[0] eq '" + boundary + "';" if boundary else ''
        result = run_perl(program.replace('FAIL', stop))
        assert json.loads(result.stdout) == (expected[:expected.index(boundary) + 1]
                                            if boundary else expected)


@pytest.mark.parametrize('operation', list(accessible_ui.FILTER_OPERATIONS))
def test_filter_transport_checks_every_option_set_and_explicit_state(operation):
    kind, mask, action = accessible_ui.FILTER_OPERATIONS[operation]
    options = accessible_ui.FILTER_OPTIONS[kind]
    value = ({'ready': kind} if action == 'open'
             else {'state': bool(mask & (1 << options.index(action))), 'activated': False})
    result = {'operation': operation, 'interface': 'ApplicationUI+external-provider', 'outcome': 'passed', 'filter': value}
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
    # Rename every invocation and its declared comparison endpoint together.
    screens = {'renamed-' + stage: operation for stage, operation in filter_plan.screen_tags.items()}
    plan = replace(filter_plan, screen_tags=screens, phases={
        'ready': 'setup', 'setup-detached': 'setup', **{stage: 'step-1' for stage in screens}},
        advance_after={}, stage_actions={}, child_bindings={},
        catalogue_checks={'renamed-' + stage: check
                          for stage, check in filter_plan.catalogue_checks.items()})
    journey = CatalogueJourney(SimpleNamespace(), Mock(), plan, actions={})
    def observed(rows):
        return {'ui': {'apps': {'rows': [list(row) for row in rows]}}}
    initial = observed(expected_rows())
    journey.check_settings('renamed-initial-rows', initial)
    initial['ui']['apps']['rows'].clear()
    for stage in ('name-rows', 'filtered-rows', 'reopened-entry', 'independent-filtered-rows'):
        rows = catalogue_rows('catalogue-name', expected_rows(), match_mask=2, access_mask=1)
        with pytest.raises(EvidenceError, match='exact-results'):
            journey.check_settings('renamed-' + stage, observed(()))
        journey.check_settings('renamed-' + stage, observed(rows))
    with pytest.raises(EvidenceError, match='unchanged-policies'):
        journey.check_settings('renamed-cleared-rows', observed(()))
    journey.check_settings('renamed-cleared-rows', observed(expected_rows()))
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
    (source / 'data/app.json').write_text(json.dumps({'version': '9.8.7'}))
    monkeypatch.setattr(qualification.smoke, 'ROOT', source)
    context = SimpleNamespace()
    journey = qualification.CatalogueQualification.journey(context, Mock())
    assert type(journey) is CatalogueJourney and journey.plan is filter_plan
    assert context.installed_snapshot == 'onpc-v9.8.7'
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


def test_catalogue_text_entry_binds_nondefault_child_without_focus_input():
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
    ui.activate_id.assert_not_called()
    with pytest.raises(accessible_ui.UiError, match='wrong-child'):
        ui.focus_text('parent-app-search', child=accessible_ui.CHILD)
    page.states.discard('visible')
    with pytest.raises(accessible_ui.UiError, match='app-row-page'):
        ui.focus_text('parent-app-search', child=accessible_ui.EXISTING_CHILD)
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('operation', list(accessible_ui.CATALOGUE_ROW_OPERATIONS))
def test_catalogue_results_use_complete_controller_schema(operation):
    rows = [] if 'absent' in operation else [[ROW, 'allowed', 'precise']]
    result = {'operation': operation, 'interface': 'ApplicationUI+external-provider', 'outcome': 'passed',
              'apps': {'rows': rows}}
    observer, *_ = collection_transport((json.dumps(result) + '\n').encode(), False)
    assert observer.observe(operation) == result


def legend_ui(*, expanded=False):
    labels = [Node(value, role='label', states=('visible',)) for value in (
        'App Access (What happens)', 'Match Rule (How apps are matched)',
        'Always Allowed', 'App can always be used',
        'Soft Blocked', 'App is blocked and can be granted one-time extension per child request if time limit is enabled',
        'Hard Blocked', 'App is completely blocked and can only be allowed by admins',
        'Pattern Match', 'Matches by pattern\n to cover exec path with changing version numbers (e.g., Lunar Client-*-ow_*.AppImage)',
        'Precise execution path', 'Matches exact app path\n(e.g., /usr/bin/firefox)')]
    content = Node(identity='parent-legend-content', children=labels, states=('visible',))
    toggle = Node(identity='parent-legend-toggle',
                  states=('visible', 'sensitive', *(('pressed',) if expanded else ())))
    page = Node(identity='parent-app-limits-page', children=[
        Node(identity='parent-app-search'), toggle, content])
    picker = Node(identity='parent-child-selector', children=[
        Node('Jordan (Child)', role='label', identity='parent-child-selected-1002')])
    root = Node(identity='parent-window', states=('active', 'visible', 'showing'),
                children=[picker, page])
    ui = ui_for(root)
    def expand(_):
        toggle.states.add('pressed')
        return True
    toggle.action.do_action.side_effect = expand
    return ui, root, page, toggle, content


def test_legend_expands_once_and_independent_open_read_never_replays_input():
    ui, root, page, toggle, content = legend_ui()
    result = ui.expand_policy_legend(accessible_ui.EXISTING_CHILD)
    assert result['activated'] is True
    assert len(result['rules']) == 5 and len(result['headings']) == 2
    assert ui.read_policy_legend(accessible_ui.EXISTING_CHILD) == {
        key: value for key, value in result.items() if key != 'activated'}
    assert ui.expand_policy_legend(accessible_ui.EXISTING_CHILD)['activated'] is False
    toggle.action.do_action.assert_called_once_with(0)
    toggle.component.scroll_to.assert_not_called()
    toggle.component.grab_focus.assert_not_called()
    # An independent invocation starts with the legend already open.
    independent, _, _, button, _ = legend_ui(expanded=True)
    assert independent.read_policy_legend(accessible_ui.EXISTING_CHILD)['rules'] == result['rules']
    button.action.do_action.assert_not_called()


def test_legend_delayed_reveal_retries_only_observation(monkeypatch):
    ui, _, _, toggle, _ = legend_ui()
    read = ui.read_policy_legend
    calls = []
    def delayed(child):
        calls.append(child)
        if len(calls) == 1:
            raise accessible_ui.UiError('ui:legend-explanations')
        return read(child)
    ui.read_policy_legend = delayed
    ui.timeout = 1
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda _: None)
    assert ui.expand_policy_legend(accessible_ui.EXISTING_CHILD)['activated'] is True
    assert calls == [accessible_ui.EXISTING_CHILD] * 2
    toggle.action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', ['child', 'page', 'owner', 'missing-toggle',
    'missing-content', 'duplicate-toggle', 'duplicate-content', 'misplaced',
    'hidden', 'disabled', 'stale', 'incomplete', 'uncertain', 'inactive'])
def test_legend_guard_refuses_before_input(fault):
    ui, root, page, toggle, content = legend_ui(expanded=fault == 'missing-content')
    child = accessible_ui.EXISTING_CHILD
    if fault == 'child':
        child = accessible_ui.CHILD
    elif fault == 'page':
        page.states.clear()
    elif fault == 'owner':
        ui.api.get_desktop(0).identity = 'unrelated.application'
    elif fault.startswith('missing-'):
        page.children.remove(toggle if fault.endswith('toggle') else content)
    elif fault.startswith('duplicate-'):
        root.children.append(Node(identity='parent-legend-' + fault.split('-')[1]))
    elif fault == 'misplaced':
        page.children.remove(toggle)
        root.children.append(toggle)
        toggle.parent = root
    elif fault == 'hidden':
        toggle.states.discard('visible')
    elif fault == 'disabled':
        toggle.states.discard('sensitive')
    elif fault == 'stale':
        toggle.states.add('defunct')
    elif fault == 'incomplete':
        content.get_child_count = Mock(side_effect=LookupError('incomplete'))
    elif fault == 'uncertain':
        ui.input_uncertain = True
    elif fault == 'inactive':
        root.states.discard('active')
    with pytest.raises((accessible_ui.UiError, LookupError)):
        ui.expand_policy_legend(child)
    toggle.action.do_action.assert_not_called()


def test_legend_collapsed_gtk_subtree_can_be_omitted_until_expansion():
    ui, _, page, toggle, content = legend_ui()
    page.children.remove(content)
    def reveal(_):
        toggle.states.add('pressed')
        page.children.append(content)
        return True
    toggle.action.do_action.side_effect = reveal
    assert ui.expand_policy_legend(accessible_ui.EXISTING_CHILD)['activated'] is True
    toggle.action.do_action.assert_called_once()


def test_legend_pressed_before_content_retries_fresh_snapshots_without_input(monkeypatch):
    ui, _, page, toggle, content = legend_ui()
    page.children.remove(content)
    snapshots = []
    read = ui.read_snapshot
    def observed(*args, **kwargs):
        result = read(*args, **kwargs)
        snapshots.append((ui.has_state(toggle, ui.api.StateType.PRESSED),
                          content in result[0]))
        return result
    ui.read_snapshot = observed
    ui.timeout = 1
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda _: page.children.append(content))
    assert ui.expand_policy_legend(accessible_ui.EXISTING_CHILD)['activated'] is True
    assert snapshots == [(False, False), (True, False), (True, True)]
    toggle.action.do_action.assert_called_once_with(0)


def test_legend_persistent_missing_content_times_out_without_replay(monkeypatch):
    ui, _, page, toggle, content = legend_ui()
    page.children.remove(content)
    clock = [0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    ui.timeout = .3
    with pytest.raises(accessible_ui.UiError, match='ui:timeout:legend-expanded'):
        ui.expand_policy_legend(accessible_ui.EXISTING_CHILD)
    toggle.action.do_action.assert_called_once()
    with pytest.raises(accessible_ui.UiError, match='ui:legend-content-missing'):
        ui.read_policy_legend(accessible_ui.EXISTING_CHILD)
    with pytest.raises(accessible_ui.UiError, match='ui:timeout:legend-expanded'):
        ui.expand_policy_legend(accessible_ui.EXISTING_CHILD)
    toggle.action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', ['misplaced', 'duplicate', 'owner', 'page', 'child'])
def test_legend_post_input_identity_faults_refuse_immediately(monkeypatch, fault):
    ui, root, page, toggle, content = legend_ui()
    def change(_):
        toggle.states.add('pressed')
        if fault == 'misplaced':
            page.children.remove(content)
            root.children.append(content)
            content.parent = root
        elif fault == 'duplicate':
            root.children.append(Node(identity='parent-legend-content'))
        elif fault == 'owner':
            ui.api.get_desktop(0).identity = 'unrelated.application'
        elif fault == 'page':
            page.states.clear()
        else:
            root.children[0].children[0].identity = 'parent-child-selected-1001'
        return True
    toggle.action.do_action.side_effect = change
    sleep = Mock()
    monkeypatch.setattr(accessible_ui.time, 'sleep', sleep)
    with pytest.raises(accessible_ui.UiError):
        ui.expand_policy_legend(accessible_ui.EXISTING_CHILD)
    sleep.assert_not_called()
    toggle.action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', ['closed', 'missing', 'truncated', 'duplicate',
                                  'hidden', 'stale', 'bound'])
def test_legend_read_requires_every_full_explanation(fault):
    ui, root, page, toggle, content = legend_ui(expanded=True)
    if fault == 'closed':
        toggle.states.discard('pressed')
        page.children.remove(content)
    elif fault == 'missing':
        content.children.pop()
    elif fault == 'truncated':
        content.children[-1].name = 'Matches exact app path'
    elif fault == 'duplicate':
        content.children.append(Node(content.children[-1].name, role='label'))
    elif fault == 'hidden':
        content.children[-1].states.discard('visible')
    elif fault == 'stale':
        content.children[-1].states.add('defunct')
    elif fault == 'bound':
        content.children.append(Node('x' * 4097, role='label'))
    with pytest.raises(accessible_ui.UiError):
        ui.read_policy_legend(accessible_ui.EXISTING_CHILD)
    toggle.action.do_action.assert_not_called()


@pytest.mark.parametrize('change', ['child', 'page', 'content', 'uncertain-action'])
def test_legend_post_input_reacquires_guards_and_failure_never_replays(change):
    ui, root, page, toggle, content = legend_ui()
    def changed(_):
        toggle.states.add('pressed')
        if change == 'child':
            root.children[0].children[0].identity = 'parent-child-selected-1001'
        elif change == 'page':
            page.states.clear()
        elif change == 'content':
            content.children.pop()
        else:
            return False
        return True
    toggle.action.do_action.side_effect = changed
    with pytest.raises(accessible_ui.UiError):
        ui.expand_policy_legend(accessible_ui.EXISTING_CHILD)
    toggle.action.do_action.assert_called_once()
    if change == 'uncertain-action':
        assert ui.input_uncertain is True
        with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
            ui.expand_policy_legend(accessible_ui.EXISTING_CHILD)
        toggle.action.do_action.assert_called_once()


@pytest.mark.parametrize('streamed', [False, True])
@pytest.mark.parametrize('operation', list(accessible_ui.LEGEND_OPERATIONS))
def test_legend_complete_projection_uses_real_controller_decoder(streamed, operation):
    ui, *_ = legend_ui(expanded=True)
    projection = ({'refusal': operation.removeprefix('policy-legend-')}
        if operation.endswith(('wrong-child', 'wrong-page')) else
        ui.read_policy_legend(accessible_ui.EXISTING_CHILD))
    if operation.endswith('expand'):
        projection['activated'] = False
    result = {'operation': operation, 'interface': 'ApplicationUI+external-provider', 'outcome': 'passed',
              'legend': projection}
    observer, *_ = collection_transport((json.dumps(result) + '\n').encode(), streamed)
    assert observer.observe(operation) == result
    result['legend']['extra'] = 'incomplete cannot pass'
    observer, *_ = collection_transport((json.dumps(result) + '\n').encode(), streamed)
    with pytest.raises(EvidenceError, match='legend-response'):
        observer.observe(operation)


def test_legend_worker_order_reuses_jordan_setup_and_stops_at_every_refusal():
    from policy_legend import PLAN as legend_plan
    from tests.support.perl import run_perl
    program = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'}=1; $INC{'onpc_parent.pm'}=1; $INC{'onpc_gdm.pm'}=1; }
package testapi; sub record_info {} sub power {push @main::events,'power'}
sub check_shutdown {1} sub console {bless {},'Console'}
package Console; sub disable {}
package onpc_gdm; sub reattach_functional {}
package onpc_parent;
sub set_allowance {
    my ($j,@args)=@_; die 'binding' unless join(',',@args) eq 'gdm,parent,fresh,new,existing,0,30,1';
    for (ENTRY) {$j->consume_observation($_,$j->seen($_))}
    return $j->seen('allowance-configured');
}
package main;
require onpc_app_rows;
eval {onpc_app_rows::policy_legend(sub {push @events,$_[0]; FAIL return {observed=>$_[0]};});};
print encode_json(\@events);
'''
    expected = list(legend_plan.screen_tags)
    entry = expected[:expected.index('allowance-configured')]
    program = program.replace('ENTRY', ','.join("'" + stage + "'" for stage in entry))
    for boundary in (None, *expected):
        stop = "die 'refused' if $_[0] eq '" + boundary + "';" if boundary else ''
        result = run_perl(program.replace('FAIL', stop))
        assert json.loads(result.stdout) == (expected[:expected.index(boundary) + 1]
                                            if boundary else expected + ['power'])


def test_search_filters_worker_matches_case_plan_and_stops_at_every_refusal():
    from search_filters import PLAN as case_plan
    from tests.support.perl import run_perl
    program = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'}=1; $INC{'onpc_parent.pm'}=1; $INC{'onpc_gdm.pm'}=1; }
package testapi; sub record_info {} sub send_key {} sub type_string {}
sub power {push @main::events,'power'} sub check_shutdown {1} sub console {bless {},'Console'}
package Console; sub disable {}
package onpc_gdm; sub reattach_functional {}
package onpc_parent;
sub set_allowance {
    my ($j,@args)=@_; die 'binding' unless join(',',@args) eq 'gdm,parent,fresh,new,existing,0,30,1';
    for (ENTRY) {$j->consume_observation($_,$j->seen($_))}
    return $j->seen('allowance-configured');
}
package main;
require onpc_fresh_thirty_allowance;
eval {onpc_fresh_thirty_allowance::search_filters(sub {push @events,$_[0]; FAIL return {observed=>$_[0]};});};
print encode_json(\@events);
'''
    expected = list(case_plan.screen_tags)
    entry = expected[:expected.index('allowance-configured')]
    program = program.replace('ENTRY', ','.join("'" + stage + "'" for stage in entry))
    for boundary in (None, *expected):
        stop = "die 'refused' if $_[0] eq '" + boundary + "';" if boundary else ''
        result = run_perl(program.replace('FAIL', stop))
        assert json.loads(result.stdout) == (expected[:expected.index(boundary) + 1]
                                            if boundary else expected + ['power'])


@pytest.mark.parametrize('stage', ['name-rows', 'filtered-rows', 'cleared-rows'])
@pytest.mark.parametrize('changed', [False, True])
def test_case_catalogue_comparison_runs_through_real_step_before_reply(tmp_path, stage, changed):
    from search_filters import PLAN as case_plan
    from native_fixtures import CataloguePolicyJourney, expected_rows, catalogue_rows
    journey = CataloguePolicyJourney(SimpleNamespace(directory=tmp_path), Mock(), case_plan,
        actions={'native-refuse': Mock(), 'native-verify': Mock()})
    baseline = [list(row) for row in expected_rows()]
    journey.check_settings('initial-rows', {'ui': {'apps': {'rows': baseline}}})
    baseline.clear()
    check = journey.row_checks[stage]
    rows = [list(row) for row in (expected_rows() if check == 'unchanged' else
            catalogue_rows(check[0], expected_rows(), match_mask=check[1], access_mask=check[2]))]
    if changed:
        rows[0][1] = 'permanent'
    journey.steps = [{'stage': s} for s in case_plan.stages[:case_plan.stages.index(stage)]]
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value={
        'operation': case_plan.screen_tags[stage][3:], 'apps': {'rows': rows}}))
    journey.boot = 'b' * 64
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({
        'stage': stage, 'screenshot': None}))
    inherited = Mock(wraps=journey.check_settings)
    journey.check_settings = inherited
    if changed:
        with pytest.raises(EvidenceError, match='unchanged-policies|exact-results'):
            journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        journey.progress.assert_not_called()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        assert stage in journey.compared_rows
        assert len(journey.initial_rows.rows) == 4
        journey.progress.assert_called_once()
    inherited.assert_called_once()


def test_case_catalogue_comparison_preserves_empty_oracle_and_refuses_missing_baseline():
    from installed_journey import JourneyPlan
    from native_fixtures import CataloguePolicyJourney, expected_rows
    plan = JourneyPlan('sample', 'sample', {'initial': 'ui:existing-parent-app-rows',
                       'empty': 'ui:catalogue-absent-rows'}, {},
                       catalogue_checks={'initial': 'initial', 'empty': ('catalogue-absent', 0, 0)})
    journey = CataloguePolicyJourney(SimpleNamespace(), Mock(), plan)
    with pytest.raises(EvidenceError, match='missing-initial'):
        journey.check_settings('empty', {'ui': {'apps': {'rows': []}}})
    journey.check_settings('initial', {'ui': {'apps': {'rows': [list(row) for row in expected_rows()]}}})
    journey.check_settings('empty', {'ui': {'apps': {'rows': []}}})
    with pytest.raises(EvidenceError, match='comparison-replay'):
        journey.check_settings('empty', {'ui': {'apps': {'rows': []}}})


@pytest.mark.parametrize('checks', [
    {}, {'missing': 'initial'}, {'initial': 'unchanged'},
    {'initial': 'initial', 'empty': 'initial'},
    {'initial': ('catalogue-name', 3, 7), 'empty': 'initial'},
    {'initial': 'initial', 'empty': ('unknown', 3, 7)},
    {'initial': 'initial', 'empty': ('catalogue-name', 4, 7)},
])
def test_catalogue_declarations_refuse_missing_ambiguous_or_late_baselines(checks):
    from installed_journey import JourneyPlan
    from native_fixtures import CataloguePolicyJourney
    plan = JourneyPlan('independent', 'independent', {
        'initial': 'ui:existing-parent-app-rows', 'empty': 'ui:catalogue-absent-rows'}, {},
        catalogue_checks=checks)
    with pytest.raises(EvidenceError, match='catalogue:'):
        CataloguePolicyJourney(SimpleNamespace(), Mock(), plan, actions={})


def test_catalogue_case_and_qualifications_share_comparisons_without_recipe_state():
    from native_fixtures import CataloguePolicyJourney, expected_rows, catalogue_rows
    from dataclasses import replace
    from catalogue_search import PLAN as search_plan
    from catalogue import PLAN as filter_plan
    from policy_legend import PLAN as legend_plan
    from search_filters import PLAN as case_plan
    for original in (search_plan, filter_plan, legend_plan, case_plan):
        screens = {'independent-' + stage: value for stage, value in original.screen_tags.items()}
        checks = {'independent-' + stage: value for stage, value in original.catalogue_checks.items()}
        plan = replace(original, screen_tags=screens, catalogue_checks=checks,
            phases={}, advance_after={}, stage_actions={}, child_bindings={},
            settings_checks={}, balance_checks={})
        journey = CataloguePolicyJourney(SimpleNamespace(), Mock(), plan, actions={})
        plan.catalogue_checks.clear()  # Consumer mutation cannot rewrite accepted bindings.
        for stage, check in journey.row_checks.items():
            expected = (expected_rows() if check in ('initial', 'unchanged') else
                        catalogue_rows(check[0], expected_rows(),
                                       match_mask=check[1], access_mask=check[2]))
            observed = {'ui': {'apps': {'rows': [list(row) for row in expected]}}}
            journey.check_settings(stage, observed)
            observed['ui']['apps']['rows'].clear()
        assert journey.initial_rows.rows == expected_rows()
        assert journey.compared_rows == set(journey.row_checks)


@pytest.mark.parametrize('changed', [False, True])
def test_legend_real_step_keeps_immutable_rows_and_checks_before_reply(tmp_path, changed):
    from policy_legend import PolicyLegendJourney, PLAN as legend_plan
    from native_fixtures import expected_rows
    journey = PolicyLegendJourney(SimpleNamespace(directory=tmp_path), Mock(), actions={
        'native-refuse': Mock(), 'native-verify': Mock()})
    baseline = [list(row) for row in expected_rows()]
    journey.check_settings('initial-rows', {'ui': {'apps': {'rows': baseline}}})
    baseline.clear()
    journey.steps = [{'stage': stage} for stage in legend_plan.stages[:-1]]
    rows = [list(row) for row in expected_rows()]
    if changed:
        rows[-1][2] = 'pattern' if rows[-1][2] == 'precise' else 'precise'
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value={
        'operation': 'existing-parent-app-rows', 'apps': {'rows': rows}}))
    journey.boot = 'b' * 64
    (tmp_path / 'final-rows.request.json').write_text(json.dumps({
        'stage': 'final-rows', 'screenshot': None}))
    inherited = Mock(wraps=journey.check_settings)
    journey.check_settings = inherited
    if changed:
        with pytest.raises(EvidenceError, match='unchanged-policies'):
            journey.step(Mock())
        assert not (tmp_path / 'final-rows.reply.json').exists()
        journey.progress.assert_not_called()
    else:
        journey.step(Mock())
        assert (tmp_path / 'final-rows.reply.json').exists()
        assert 'final-rows' in journey.compared_rows
        rows.clear()
        assert len(journey.initial_rows.rows) > 0
        journey.progress.assert_called_once()
    inherited.assert_called_once()


def test_legend_qualification_selects_fresh_snapshot_and_registered_asset_route(tmp_path, monkeypatch):
    import parent_setup_qualification as qualification
    import check_graphical_smoke as smoke
    from policy_legend import PolicyLegendJourney, PLAN as legend_plan
    from owned_commands import CommandError
    import runpy
    from tests.support.paths import ROOT
    from tools.test_storage import named_input
    source = tmp_path / 'source'
    (source / 'data').mkdir(parents=True)
    (source / 'data/app.json').write_text(json.dumps({'version': '9.8.7'}))
    monkeypatch.setattr(qualification.smoke, 'ROOT', source)
    context = SimpleNamespace()
    journey = qualification.PolicyLegendQualification.journey(context, Mock())
    assert type(journey) is PolicyLegendJourney and journey.plan is legend_plan
    assert context.installed_snapshot == 'onpc-v9.8.7'
    with pytest.raises(CommandError, match='policy-legend-prerequisites'):
        smoke.main(policy_legend=True)
    execute = Mock(return_value=0)
    monkeypatch.setattr(smoke, 'main', execute)
    with pytest.raises(SystemExit):
        runpy.run_path(str(ROOT / 'tests/integration/check_e2e_policy_legend.py'), run_name='__main__')
    assert execute.call_args.kwargs == {'assets': named_input(fixture_source=True),
        'provision_credentials': True, 'app_row_observations': True,
        'native_fixtures': True, 'policy_legend': True}
