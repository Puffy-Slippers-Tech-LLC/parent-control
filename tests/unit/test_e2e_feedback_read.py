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


@pytest.mark.parametrize('binding', accessible_ui.TEXT_VALUES)
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
