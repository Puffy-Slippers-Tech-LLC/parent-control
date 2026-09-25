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
