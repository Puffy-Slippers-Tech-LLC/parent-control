"""Feedback reads refuse private drafts, incomplete sets and wrong entry."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import Mock
import json

import pytest
import accessible_ui
import check_e2e_feedback_read as check
import check_graphical_smoke as smoke
from feedback_read import FeedbackReadJourney, PLAN
from private_artifacts import EvidenceError
from owned_commands import CommandError
from tests.support.accessible_ui import Node, ui_for
from ui_observations import FeedbackObservation
import check_e2e_text
from text_qualification import PLAN as TEXT_PLAN
from feedback_privacy import FeedbackPrivacyJourney, PLAN as PRIVACY_PLAN
import check_e2e_feedback_privacy
import check_e2e_feedback_states
from feedback_states import FeedbackStatesJourney, PLAN as STATES_PLAN
from ui_observations import FeedbackStateObservation

# Added Privacy checks retain this module's reviewed isolation: in-memory UI
# doubles, pytest-owned paths and waited, private Perl subprocesses only.
# FEED09 additions use those same resources and require no scheduler change.
# UI24/FEED04 additions retain the same in-memory and private Perl resources.
# DESK10 uses the same isolated doubles and waited private Perl processes.


@pytest.mark.parametrize('fault', ['', 'absent', 'wrong-owner', 'duplicate', 'hidden',
                                  'disabled', 'already-active', 'focus-lost', 'uncertain'])
def test_existing_window_preparation_refuses_unsafe_or_uncertain_targets(fault):
    ui, parent, dialog, _ = synthetic_feedback_ui()
    dialog.states.discard('active')
    parent.states.add('active')
    dialog.bus, dialog.path = ':1.123', '/org/a11y/atspi/accessible/42'
    if fault == 'absent':
        parent.children.clear()
    elif fault == 'wrong-owner':
        ui.api.get_desktop(0).identity = 'unrelated.application'
    elif fault == 'duplicate':
        parent.children.append(Node(identity='feedback-dialog'))
    elif fault in ('hidden', 'disabled'):
        dialog.states.discard('showing' if fault == 'hidden' else 'sensitive')
    elif fault == 'already-active':
        dialog.states.add('active')
    elif fault == 'focus-lost':
        parent.states.discard('active')
    elif fault == 'uncertain':
        ui.input_uncertain = True
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.window_switch_ready('feedback', 'parent')
    else:
        assert ui.window_switch_ready('feedback', 'parent')['active'] is False
        with pytest.raises(accessible_ui.UiError, match='switch-active'):
            ui.window_switch_proof('feedback')
    dialog.component.grab_focus.assert_not_called()


def test_window_switch_public_proof_decoder_and_retained_identity(tmp_path):
    import copy
    from window_switch import WindowSwitchJourney
    from ui_observations import UiObservations
    ui, _, dialog, controls = synthetic_feedback_ui()
    dialog.bus, dialog.path = ':1.123', '/org/a11y/atspi/accessible/42'
    value = ui.window_switch_proof('feedback')
    reader = UiObservations(Mock())
    reply = {'operation': 'switch-feedback', 'outcome': 'passed', 'interface': 'AT-SPI',
             'window': value}
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    assert reader.observe('switch-feedback') == reply
    journey = WindowSwitchJourney(SimpleNamespace(directory=tmp_path), Mock())
    with pytest.raises(EvidenceError, match='window-or-draft-changed'):
        journey.check_settings('switch-feedback', {'ui': reply})
    journey.check_settings('switch-draft-before', {'ui': copy.deepcopy(reply)})
    ready = copy.deepcopy(reply)
    ready['operation'] = 'switch-feedback-ready'
    ready['window'].pop('feedback')
    ready['window']['active'] = False
    reader.call.return_value = (json.dumps(ready).encode(), [])
    assert reader.observe('switch-feedback-ready') == ready
    journey.check_settings('switch-feedback-ready', {'ui': ready})
    journey.check_settings('switch-feedback', {'ui': reply})
    value['endpoint'][1] += '1'
    with pytest.raises(EvidenceError, match='window-or-draft-changed'):
        journey.check_settings('switch-feedback-again', {'ui': reply})
    value['active'] = False
    reader.call.return_value = (json.dumps(reply).encode(), [])
    with pytest.raises(EvidenceError, match='switch-response'):
        reader.observe('switch-feedback')
    controls['feedback-editor-input'].text.value = 'X' * controls['feedback-editor-input'].text.count
    with pytest.raises(accessible_ui.UiError, match='nonempty-draft'):
        ui.window_switch_proof('feedback')


def test_window_switch_absent_target_never_launches(monkeypatch):
    ui, _, dialog, _ = synthetic_feedback_ui()
    dialog.bus, dialog.path = ':1.123', '/org/a11y/atspi/accessible/42'
    ui.license_viewer_snapshot = Mock(return_value=(None, None, None))
    launch = Mock(side_effect=AssertionError('must not launch'))
    monkeypatch.setattr(accessible_ui.subprocess, 'run', launch)
    assert ui.window_switch_operation('switch-viewer-absent')['binding'] == 'feedback'
    launch.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'wrong-owner', 'ambiguous', 'unrelated', 'hidden', 'wrong-pid'])
def test_window_switch_viewer_reacquires_inactive_public_document(fault):
    content = Node(identity='view', role='text')
    text = 'GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007'
    content.get_text_iface = lambda: content
    window = Node(children=[content])
    owner = Node(identity='org.gnome.TextEditor', role='application', children=[window])
    ui = ui_for(Node(role='desktop frame', children=[owner]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: len(text),
                                  get_text=lambda _, start, end: text[start:end])
    if fault == 'wrong-owner':
        owner.identity = 'unrelated'
    elif fault == 'ambiguous':
        owner.children.append(Node())
    elif fault == 'unrelated':
        text = 'Unrelated document'
    elif fault == 'hidden':
        content.states.discard('showing')
    elif fault == 'wrong-pid':
        content.get_process_id = lambda: 999
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.existing_window('viewer')
        window.component.grab_focus.assert_not_called()
    else:
        with pytest.raises(accessible_ui.UiError, match='document-owner'):
            ui.read_document(content, 'gpl-heading', maximum=1024)
        assert ui.existing_window('viewer') is window
        assert ui.existing_window_active('viewer') is None
        window.states.add('active')
        assert ui.existing_window_active('viewer') is window
        window.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'switch-viewer-launch', 'switch-parent',
                                  'switch-viewer-ready', 'switch-feedback-ready',
                                  'switch-viewer', 'switch-feedback', 'switch-viewer-absent'])
def test_window_switch_worker_preserves_order_and_stops_before_later_input(fault):
    from window_switch import STAGES
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type'; }
package main;
require onpc_feedback_read;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_read::run_window_switch(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    stages = ['parent-selected', *STAGES]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')
    if not fault:
        assert result['events'].count('alt-tab') == 6
    elif fault.endswith('-ready'):
        assert result['events'][-1] != 'alt-tab'


def test_window_switch_selector_uses_guarded_envelope(monkeypatch):
    import check_e2e_window_switch
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_window_switch, 'smoke', run)
    assert check_e2e_window_switch.main() == 0
    assert run.call_args.kwargs['window_switch'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(window_switch=True)
    with pytest.raises(CommandError, match='window-switch-prerequisites'):
        smoke.main(window_switch=True, format_qualification=True)


@pytest.mark.parametrize('fault', ['', 'missing', 'stalled', 'mixed', 'private', 'range'])
def test_format_range_public_runs_refuse_unavailable_or_invalid_attributes(fault):
    ui, _, _, controls = synthetic_feedback_ui()
    ui.api.Text.get_attribute_run = Mock(side_effect=lambda text, offset, defaults: (
        {'weight': '700' if offset < 9 else '400'}, 0 if offset < 9 else 9,
        9 if offset < 9 else 23))
    if fault == 'missing':
        ui.api.Text.get_attribute_run.return_value = ({}, 0, 23)
        ui.api.Text.get_attribute_run.side_effect = None
    elif fault == 'stalled':
        ui.api.Text.get_attribute_run.side_effect = lambda *args: ({'weight': '700'}, 0, 0)
    elif fault == 'private':
        controls['feedback-editor-input'].text.value = 'private'
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.formatting_attributes(-1 if fault == 'range' else 0, 23 if fault == 'mixed' else 9)
    else:
        assert ui.formatting_attributes(0, 9) == {'start': 0, 'end': 9, 'weight': 'bold'}
        assert ui.formatting_attributes(9, 23) == {'start': 9, 'end': 23, 'weight': 'normal'}
        # No ambiguous boundary lookup; full public bounds still prove coverage.
        assert [call.args[1] for call in ui.api.Text.get_attribute_run.call_args_list] == [4, 16]


def test_format_decoder_and_independent_recorder(tmp_path):
    from format_qualification import FormatJourney
    from ui_observations import UiObservations
    value = [{'start': 0, 'end': 9, 'weight': 'bold'},
             {'start': 9, 'end': 23, 'weight': 'normal'}]
    reader = UiObservations(Mock())
    reply = {'operation': 'format-read', 'outcome': 'passed', 'interface': 'AT-SPI',
             'formatting': value}
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    assert reader.observe('format-read') == reply
    journey = FormatJourney(SimpleNamespace(directory=tmp_path), Mock())
    with pytest.raises(EvidenceError, match='format:independent-entry'):
        journey.check_settings('format-reopen', {'ui': reply})
    journey.check_settings('format-read', {'ui': reply})
    journey.check_settings('format-reopen', {'ui': reply})
    value[1]['weight'] = 'bold'
    reader.call.return_value = (json.dumps(reply).encode(), [])
    with pytest.raises(EvidenceError, match='ui:format-response'):
        reader.observe('format-read')


@pytest.mark.parametrize('fault', ['', 'format-home', 'format-selected', 'format-read', 'format-reopen'])
def test_format_worker_stops_on_refusal(fault):
    from format_qualification import STAGES
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type'; }
package main;
require onpc_format;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_format::run(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    stages = ['parent-selected', *STAGES]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')


def test_format_selector_preserves_guarded_envelope(monkeypatch):
    import check_e2e_format
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_format, 'smoke', run)
    assert check_e2e_format.main() == 0
    assert run.call_args.kwargs['format_qualification'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(format_qualification=True)
    with pytest.raises(CommandError, match='format-prerequisites'):
        smoke.main(format_qualification=True, feedback_states=True)


@pytest.mark.parametrize('projection', sorted(set(accessible_ui.FEEDBACK_STATE_PROJECTIONS.values())))
@pytest.mark.parametrize('enabled', [True, False])
@pytest.mark.parametrize('explanation', list(accessible_ui.FEEDBACK_VALIDATION))
def test_state_reads_public_send_and_validation_independently(projection, enabled, explanation):
    ui, _, dialog, controls = feedback_ui()
    for binding in accessible_ui.FEEDBACK_PROJECTIONS[projection]:
        identity, text = accessible_ui.TEXT_VALUES[binding]
        controls[identity].text.count = len(text)
        controls[identity].text.value = text
    ui.api.Text.get_text = Mock(side_effect=lambda text, start, end: text.value[start:end])
    if not enabled:
        controls['feedback-send'].states.remove('sensitive')
    if explanation:
        dialog.children.append(Node(explanation, identity='feedback-status'))
    state = FeedbackStateObservation.from_value(ui.feedback_snapshot(projection, states=True))
    assert state.send_enabled is enabled
    assert state.validation == accessible_ui.FEEDBACK_VALIDATION[explanation]
    for node in controls.values():
        node.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['private-status', 'private-body', 'missing-send',
                                  'duplicate-send', 'wrong-owner', 'inactive', 'wrong-entry'])
def test_state_refuses_unsafe_reads_without_input(fault):
    ui, parent, dialog, controls = synthetic_feedback_ui()
    if fault == 'private-status':
        dialog.children.append(Node('unregistered private text', identity='feedback-status'))
    elif fault == 'private-body':
        controls['feedback-editor-input'].text.count = 10000
    elif fault == 'missing-send':
        dialog.children.remove(controls['feedback-send'])
    elif fault == 'duplicate-send':
        dialog.children.append(Node(identity='feedback-send', states=()))
    elif fault == 'wrong-owner':
        ui.api.get_desktop(0).identity = 'unrelated.application'
    elif fault == 'inactive':
        dialog.states.remove('active')
    elif fault == 'wrong-entry':
        parent.children.clear()
        assert ui.feedback_state_operation('feedback-state-wrong-entry') is None
    with pytest.raises(accessible_ui.UiError):
        ui.feedback_snapshot('synthetic-first', states=True)
    for node in controls.values():
        node.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'send', 'validation', 'projection', 'missing-prior'])
def test_state_controller_and_actual_decoder_reject_unexpected_results(tmp_path, fault):
    from ui_observations import UiObservations
    ui, _, _, controls = synthetic_feedback_ui()
    value = ui.feedback_snapshot('synthetic-first', states=True)
    reader = UiObservations(Mock())
    reply = {'operation': 'feedback-state-valid', 'outcome': 'passed', 'interface': 'AT-SPI',
             'feedback_state': value}
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    assert reader.observe('feedback-state-valid') == reply
    journey = FeedbackStatesJourney(SimpleNamespace(directory=tmp_path), Mock())
    if fault == 'send':
        value['send_enabled'] = False
    elif fault == 'validation':
        value['validation'] = 'reply-invalid'
    elif fault == 'projection':
        value['draft'] = 'initial-empty'
    if fault:
        with pytest.raises(EvidenceError):
            journey.check_settings('feedback-state-reopen' if fault == 'missing-prior'
                                   else 'feedback-state-valid', {'ui': reply})
    else:
        journey.check_settings('feedback-state-valid', {'ui': reply})
        journey.check_settings('feedback-state-reopen', {'ui': reply})
    value['send_enabled'] = 'true'
    reader.call.return_value = (json.dumps(reply).encode(), [])
    with pytest.raises(EvidenceError, match='ui:feedback-state-response'):
        reader.observe('feedback-state-valid')


def test_states_selector_preserves_existing_guarded_envelope(monkeypatch):
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_feedback_states, 'smoke', run)
    assert check_e2e_feedback_states.main() == 0
    assert run.call_args.kwargs['feedback_states'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_states=True)
    with pytest.raises(CommandError, match='feedback-states-prerequisites'):
        smoke.main(feedback_states=True, feedback_privacy=True)


@pytest.mark.parametrize('fault', ['', 'feedback-state-whitespace', 'text-reply-malformed-selected',
                                  'feedback-state-valid', 'feedback-state-wrong-entry',
                                  'feedback-state-reopen'])
def test_states_worker_order_and_failure_stop_later_input(fault):
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages, @typed);
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type'; push @typed, $_[0]; }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_states::run(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages, typed => \@typed});
''', fault).stdout)
    stages = list(STATES_PLAN.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    if fault:
        assert result['events'][-1] == fault
    else:
        from feedback_states import EDITS
        assert result['typed'] == [accessible_ui.TEXT_VALUES[binding][1] for binding, _ in EDITS]
        assert result['events'][-1] == 'finish'


def synthetic_feedback_ui():
    ui, parent, dialog, controls = feedback_ui()
    for binding in ('body-first', 'reply-first'):
        identity, value = accessible_ui.TEXT_VALUES[binding]
        controls[identity].text.count = len(value)
        controls[identity].text.value = value
    ui.api.Text.get_text = Mock(side_effect=lambda text, start, end: text.value[start:end])
    return ui, parent, dialog, controls


@pytest.mark.parametrize('fault', ['', 'body', 'reply', 'controls', 'attachments'])
def test_nonempty_projection_compares_fields_and_controls_without_input(fault):
    ui, _, dialog, controls = synthetic_feedback_ui()
    if fault in ('body', 'reply'):
        identity = 'feedback-editor-input' if fault == 'body' else 'feedback-reply-email'
        controls[identity].text.value = 'X' * controls[identity].text.count
    elif fault == 'controls':
        controls['feedback-send'].states.remove('sensitive')
    elif fault == 'attachments':
        dialog.children.append(Node(identity='feedback-attachment-0123456789abcdef'))
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.feedback_snapshot('synthetic-first')
    else:
        assert FeedbackObservation.from_value(ui.feedback_snapshot('synthetic-first')).draft == 'synthetic-first'
    for node in controls.values():
        node.action.do_action.assert_not_called()


def test_feedback_close_proof_refuses_wrong_window_without_input():
    ui, parent, dialog, controls = synthetic_feedback_ui()
    ui.window_ready_to_close('feedback')
    dialog.states.remove('active')
    with pytest.raises(accessible_ui.UiError, match='ui:feedback-entry'):
        ui.window_ready_to_close('feedback')
    parent.children.clear()
    assert ui.feedback_privacy_operation('feedback-close-refused') is None
    for node in controls.values():
        node.action.do_action.assert_not_called()


@pytest.mark.parametrize('missing', [False, True])
def test_privacy_reads_actual_disclosure_and_never_follows_external_link(missing):
    import ast
    # The shipped disclosure supplies the fixture; remove an essential promise
    # to prove a mere visible dialog cannot satisfy the observation.
    from tests.support.paths import ROOT
    tree = ast.parse((ROOT / 'common/oh_no_parent_control_ui/feedback.py').read_text())
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == '_show_log_privacy')
    suffix = method.body[0].value.right.value
    disclosure = ('Feedback, reply email addresses, attachments, and diagnostic logs are emailed '
                  'to support. Retention depends on our support mailbox and service providers, '
                  'including their backup policies. We do not currently guarantee deletion '
                  'within a fixed period.')
    ui, _, _, _ = synthetic_feedback_ui()
    ui.activate_id = Mock()
    ui.window_ready_to_close = Mock()
    root = Node(identity='feedback-privacy-dialog')
    text = Node(name=('' if missing else disclosure) + suffix, identity='feedback-privacy-text')
    ui.id_target = Mock(side_effect=[root, text])
    if missing:
        with pytest.raises(accessible_ui.UiError, match='ui:feedback-privacy-disclosure'):
            ui.feedback_privacy('synthetic-first')
    else:
        ui.feedback_privacy('synthetic-first')
    ui.activate_id.assert_called_once_with('feedback-privacy-link')


def test_privacy_selector_and_controller_preserve_explicit_prior_draft(tmp_path, monkeypatch):
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_feedback_privacy, 'smoke', run)
    assert check_e2e_feedback_privacy.main() == 0
    assert run.call_args.kwargs['feedback_privacy'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_privacy=True)
    with pytest.raises(CommandError, match='feedback-privacy-prerequisites'):
        smoke.main(feedback_privacy=True, feedback_read=True)
    journey = FeedbackPrivacyJourney(SimpleNamespace(directory=tmp_path), Mock())
    ui, _, _, _ = synthetic_feedback_ui()
    observed = {'ui': {'feedback': ui.feedback_snapshot('synthetic-first')}}
    with pytest.raises(EvidenceError, match='preserved-draft'):
        journey.check_settings('feedback-draft-reopen', observed)
    journey.check_settings('feedback-draft', observed)
    journey.check_settings('feedback-draft-reopen', observed)
    observed['ui']['feedback']['draft'] = 'initial-empty'
    with pytest.raises(EvidenceError, match='expected-draft'):
        journey.check_settings('feedback-draft-reopen', observed)


def test_nonempty_feedback_roundtrips_actual_controller_decoder():
    from ui_observations import UiObservations
    ui, _, _, _ = synthetic_feedback_ui()
    reader = UiObservations(Mock())
    reply = {'operation': 'feedback-draft-reopen', 'outcome': 'passed', 'interface': 'AT-SPI',
             'feedback': ui.feedback_snapshot('synthetic-first')}
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    assert reader.observe('feedback-draft-reopen') == reply
    reply['feedback']['draft'] = 'initial-empty'
    reader.call.return_value = (json.dumps(reply).encode(), [])
    with pytest.raises(EvidenceError, match='ui:feedback-response'):
        reader.observe('feedback-draft-reopen')


@pytest.mark.parametrize('fault', ['', 'feedback-privacy-open', 'feedback-draft-reread',
                                  'feedback-draft-reopen', 'privacy-independent'])
def test_privacy_worker_sequence_and_failed_proofs_stop_later_input(fault):
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages);
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type'; }
package main;
require onpc_feedback_privacy;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_privacy::run(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    stages = list(PRIVACY_PLAN.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    if fault:
        assert result['events'][-1] == fault
    else:
        assert result['events'].count('alt-f4') == 3
        assert result['events'].count('type') == 2
        assert result['events'][-1] == 'finish'


def feedback_ui():
    controls = {identity: Node(identity=identity) for identity in (
        'feedback-editor-input', 'feedback-reply-email', 'feedback-logs-row',
        'feedback-close', 'feedback-send', 'feedback-add-files',
        'feedback-download-logs', 'feedback-toggle-logs')}
    for identity in ('feedback-editor-input', 'feedback-reply-email'):
        node = controls[identity]
        node.states.add('editable')
        node.role = 'text'
        node.text = SimpleNamespace(count=0)
        node.get_text_iface = lambda node=node: node.text
    controls['feedback-logs-row'].name = 'diagnostic-logs.zip'
    dialog = Node(identity='feedback-dialog', children=list(controls.values()),
                  states=('showing', 'visible', 'sensitive', 'active'))
    parent = Node(identity='parent-window', children=[dialog])
    ui = ui_for(parent)
    ui.api.Text = SimpleNamespace(get_character_count=lambda text: text.count,
                                 get_text=Mock(side_effect=AssertionError('no raw text')))
    return ui, parent, dialog, controls


def test_initial_draft_snapshot_is_bounded_and_immutable_without_input():
    ui, _, _, controls = feedback_ui()
    value = ui.feedback_snapshot()
    frozen = FeedbackObservation.from_value(value)
    value['attachments'].clear()
    assert frozen.attachments == ('diagnostic-logs.zip',)
    with pytest.raises(FrozenInstanceError):
        frozen.draft = 'private'
    ui.api.Text.get_text.assert_not_called()
    for node in controls.values():
        node.action.do_action.assert_not_called()


def test_feedback_ignores_reused_toolkit_ids_but_refuses_hidden_owned_duplicates():
    ui, _, dialog, _ = feedback_ui()
    dialog.children.extend(Node(identity=identity) for identity in ('box', 'box', 'title', 'title'))
    assert ui.feedback_snapshot()['draft'] == 'initial-empty'
    dialog.children.append(Node(identity='feedback-send', states=()))
    with pytest.raises(accessible_ui.UiError, match='ui:feedback-duplicate'):
        ui.feedback_snapshot()


@pytest.mark.parametrize('value,accepted', [('\n', True), ('x', False), (' ', False)])
def test_rich_editor_empty_paragraph_is_an_exact_bounded_comparison(value, accepted):
    ui, _, _, controls = feedback_ui()
    controls['feedback-editor-input'].text.count = 1
    ui.api.Text.get_text = Mock(return_value=value)
    if accepted:
        assert ui.feedback_snapshot()['draft'] == 'initial-empty'
    else:
        with pytest.raises(accessible_ui.UiError, match='ui:feedback-nonempty-draft'):
            ui.feedback_snapshot()
    ui.api.Text.get_text.assert_called_once_with(controls['feedback-editor-input'].text, 0, 1)


def test_reply_field_does_not_accept_the_rich_editor_empty_paragraph():
    ui, _, _, controls = feedback_ui()
    controls['feedback-reply-email'].text.count = 1
    with pytest.raises(accessible_ui.UiError, match='ui:feedback-nonempty-draft'):
        ui.feedback_snapshot()
    ui.api.Text.get_text.assert_not_called()


@pytest.mark.parametrize('fault', ['private', 'reply', 'duplicate', 'attachment',
    'missing', 'disabled', 'inactive', 'stale', 'incomplete', 'collecting',
    'validation', 'wrong-owner', 'projection', 'wrong-entry'])
def test_feedback_refuses_unsafe_or_unready_observations(fault):
    ui, parent, dialog, controls = feedback_ui()
    projection = 'initial-empty'
    if fault in ('private', 'reply'):
        controls['feedback-editor-input' if fault == 'private' else 'feedback-reply-email'].text.count = 5
    elif fault == 'duplicate':
        dialog.children.append(Node(identity='feedback-send'))
    elif fault == 'attachment':
        dialog.children.append(Node(identity='feedback-attachment-0123456789abcdef'))
    elif fault == 'missing':
        dialog.children.remove(controls['feedback-editor-input'])
    elif fault == 'disabled':
        controls['feedback-send'].states.remove('sensitive')
    elif fault == 'inactive':
        dialog.states.remove('active')
    elif fault == 'stale':
        controls['feedback-send'].states.add('defunct')
    elif fault == 'incomplete':
        dialog.get_child_count = Mock(side_effect=LookupError('incomplete'))
    elif fault == 'collecting':
        dialog.children.append(Node(identity='feedback-collection-status'))
    elif fault == 'validation':
        dialog.children.append(Node('Validation failed', identity='feedback-status'))
    elif fault == 'wrong-owner':
        ui.api.get_desktop(0).identity = 'unrelated.application'
    elif fault == 'projection':
        projection = 'arbitrary-private-text'
    elif fault == 'wrong-entry':
        parent.children.clear()
    with pytest.raises((accessible_ui.UiError, LookupError)):
        ui.feedback_snapshot(projection)
    ui.api.Text.get_text.assert_not_called()


def test_wrong_entry_live_operation_is_read_only():
    ui, parent, _, _ = feedback_ui()
    parent.children.clear()
    assert ui.feedback_read_operation('feedback-wrong-entry') is None


@pytest.mark.parametrize('binding', [binding for binding in accessible_ui.TEXT_VALUES
                                     if binding.startswith(('body-', 'reply-'))])
def test_synthetic_text_exact_bounded_readback(binding):
    ui, _, _, controls = feedback_ui()
    identity, value = accessible_ui.TEXT_VALUES[binding]
    controls[identity].text.count = len(value)
    ui.api.Text.get_text = Mock(return_value=value)
    assert ui.read_synthetic_text(binding) == {
        'binding': binding, 'exact': True, 'length': len(value)}
    if value:
        ui.api.Text.get_text.assert_called_once_with(controls[identity].text, 0, len(value))
    else:
        ui.api.Text.get_text.assert_not_called()


@pytest.mark.parametrize('fault', ['masked', 'disabled', 'wrong-owner', 'wrong-entry',
                                 'unfocused', 'uncertain', 'wrong-value', 'long-value'])
def test_text_refuses_before_input_or_private_projection(fault):
    ui, parent, _, controls = feedback_ui()
    node = controls['feedback-editor-input']
    component = SimpleNamespace(grab_focus=Mock())
    node.get_component_iface = Mock(return_value=component)
    value = accessible_ui.TEXT_VALUES['body-first'][1]
    node.text.count = len(value)
    ui.api.Text.get_text = Mock(return_value='x' * len(value))
    if fault == 'masked':
        node.role = 'password text'
    elif fault == 'disabled':
        node.states.remove('sensitive')
    elif fault == 'wrong-owner':
        ui.api.get_desktop(0).identity = 'unrelated.application'
    elif fault == 'wrong-entry':
        parent.children.clear()
    elif fault == 'uncertain':
        ui.input_uncertain = True
    elif fault == 'long-value':
        node.text.count = 10000
    with pytest.raises(accessible_ui.UiError):
        if fault in ('wrong-value', 'long-value'):
            ui.read_synthetic_text('body-first')
        else:
            ui.text_recipient('feedback-editor-input', focused=True)
    component.grab_focus.assert_not_called()
    if fault != 'wrong-value':
        ui.api.Text.get_text.assert_not_called()


def test_text_qualification_selector_and_gate(monkeypatch):
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_text, 'smoke', run)
    assert check_e2e_text.main() == 0
    assert run.call_args.kwargs['text_qualification'] is True
    with pytest.raises(CommandError, match='text-prerequisites'):
        smoke.main(text_qualification=True)
    with pytest.raises(CommandError, match='text-prerequisites'):
        smoke.main(assets=object(), provision_credentials=True,
                   text_qualification=True, feedback_read=True)
    assert TEXT_PLAN.worker_mode == 'text_qualification'


def test_text_focus_is_public_and_independently_verified_with_failure_latch():
    ui, _, _, controls = feedback_ui()
    node = controls['feedback-editor-input']
    ui.focus_text('feedback-editor-input')
    node.component.grab_focus.assert_called_once()
    assert ui.text_recipient('feedback-editor-input', focused=True) is node
    node.component.grab_focus.side_effect = None
    node.component.grab_focus.return_value = False
    with pytest.raises(accessible_ui.UiError, match='ui:text-focus-refused'):
        ui.focus_text('feedback-editor-input')
    assert ui.input_uncertain
    with pytest.raises(accessible_ui.UiError, match='ui:uncertain-input'):
        ui.focus_text('feedback-editor-input')
    assert node.component.grab_focus.call_count == 2


def test_live_text_refusals_perform_no_focus_or_text_read():
    ui, parent, _, controls = feedback_ui()
    parent.children.clear()
    disabled = Node(identity='parent-daily-limit-selector', states=('showing', 'visible'))
    parent.children.append(disabled)
    assert ui.text_operation('text-disabled') is None
    assert ui.text_operation('text-wrong-entry') is None
    disabled.component.grab_focus.assert_not_called()
    for node in controls.values():
        node.component.grab_focus.assert_not_called()
    ui.api.Text.get_text.assert_not_called()


def test_native_reply_focus_uses_verified_editor_anchor_without_native_grab():
    ui, _, _, controls = feedback_ui()
    editor = controls['feedback-editor-input']
    reply = controls['feedback-reply-email']
    reply.component.grab_focus.side_effect = AssertionError('GTK has no GrabFocus')
    ui.text_operation('text-reply-first-anchor')
    editor.component.grab_focus.assert_called_once()
    reply.states.add('focused')
    ui.text_operation('text-reply-first-focus')
    ui.text_operation('text-reply-first-selected')
    reply.component.grab_focus.assert_not_called()


def test_reply_anchor_refuses_disabled_destination_before_focusing_editor():
    ui, _, _, controls = feedback_ui()
    controls['feedback-reply-email'].states.remove('sensitive')
    with pytest.raises(accessible_ui.UiError, match='ui:text-disabled'):
        ui.text_operation('text-reply-first-anchor')
    controls['feedback-editor-input'].component.grab_focus.assert_not_called()


def test_text_controller_order_matches_actual_worker_exchange():
    from tests.support.perl import run_perl
    stages = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our @stages;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { }
sub type_string { }
package main;
require onpc_text;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub {
    return $_[0]->seen('parent-selected');
};
*onpc_journey::finish = sub { };
onpc_text::run(sub {
    push @stages, $_[0];
    return {observed => $_[0]};
});
print encode_json(\@stages);
''').stdout)
    planned = list(TEXT_PLAN.screen_tags)
    assert stages == planned[planned.index('parent-selected'):]


@pytest.mark.parametrize('binding,fault', [
    (binding, fault)
    for binding in ('body-first', 'body-clear', 'reply-second', 'reply-clear')
    for fault in ('', 'focus', 'selected', 'read', *(
        ('anchor',) if binding.startswith('reply-') else ()))
])
def test_text_worker_stops_at_failed_proof_without_replaying_input(binding, fault):
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our @events;
our ($binding, $fault) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, $_[0]; }
sub type_string {
    die 'pace' unless $_[1] eq 'max_interval' && $_[2] == 20;
    push @main::events, 'type';
}
package main;
require onpc_text;
no warnings 'redefine';
*onpc_journey::seen = sub {
    my ($self, $stage) = @_;
    push @events, $stage;
    die 'failed proof' if $fault && $stage eq "text-$binding-$fault";
    return {observed => $stage};
};
*onpc_journey::consume_observation = sub { };
my $ok = eval { onpc_text::replace_text(bless({}, 'onpc_journey'), $binding); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', binding, fault).stdout)
    stages = [f'text-{binding}-focus', 'ctrl-a', f'text-{binding}-selected',
              'backspace' if binding.endswith('clear') else 'type', f'text-{binding}-read']
    if binding.startswith('reply-'):
        stages = [f'text-{binding}-anchor', 'ctrl-tab', *stages]
    assert result['events'] == (stages[:stages.index(f'text-{binding}-{fault}') + 1]
                                if fault else stages)
    assert bool(result['ok']) is (not fault)


def test_qualification_selector_and_gate(monkeypatch):
    run = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == 0
    assert run.call_args.kwargs['feedback_read'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_read=True)
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(assets=object(), provision_credentials=True,
                   feedback_read=True, parent_about=True)


def test_controller_requires_initial_evidence_before_independent_comparison(tmp_path):
    journey = FeedbackReadJourney(SimpleNamespace(directory=tmp_path), Mock())
    ui, _, _, _ = feedback_ui()
    observed = {'ui': {'feedback': ui.feedback_snapshot()}}
    with pytest.raises(EvidenceError, match='independent-read'):
        journey.check_settings('feedback-reread', observed)
    journey.check_settings('feedback-read', observed)
    journey.check_settings('feedback-reread', observed)
    with pytest.raises(EvidenceError, match='replay'):
        journey.check_settings('feedback-read', observed)
    assert PLAN.worker_mode == 'feedback_read'


@pytest.mark.parametrize('fault', ['', 'feedback-read', 'feedback-wrong-entry', 'feedback-reread'])
def test_real_worker_stops_before_further_input_on_failed_observation(fault):
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our @events;
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
package main;
require onpc_feedback_read;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub {
    my ($journey, @args) = @_;
    die 'wrong entry' unless join(',', @args) eq 'gdm,fresh,new,child';
    return $journey->seen('parent-selected');
};
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_read::run(sub {
        push @events, $_[0];
        die 'failed observation' if $_[0] eq $fault;
        return {observed => $_[0]};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', fault).stdout)
    stages = ['parent-selected', 'feedback-open', 'feedback-read', 'feedback-close',
              'feedback-wrong-entry', 'feedback-reopen', 'feedback-reread',
              'feedback-finished', 'finish']
    assert result['events'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
