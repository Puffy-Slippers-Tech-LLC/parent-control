"""Feedback reads refuse private drafts, incomplete sets and wrong entry."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
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
# Rejection checks retain these resources; no network, shared paths or new buses.
# UTF-16 checks retain the same in-memory doubles and waited private Perl children.
# Complete-case composition uses the same private values and waited Perl children;
# no added shared paths, VM resources, caches, buses or scheduler classification.
# FILE03 adds only in-memory provider doubles and waited private Perl children;
# it retains this module's reviewed unit scheduling and resource ownership.
# Attachment-item checks retain those same private resources and scheduling.
# Shared-fragment checks use the same waited private Perl processes and memory.
# Preview applicability adds only those same isolated resources.
# App-exit reset retains private values, pytest paths and waited Perl children;
# the existing compatible unit classification still applies.
# Boundary checks add bounded in-memory bytes (under 32 MiB), no shared resources.
# Block semantics add bounded trees and private, waited Perl/Python children;
# isolated observer import checks add no paths, sockets, buses or shared caches.
# Complete formatting uses these same bounded trees and waited private children.
# Linked-format qualification retains that isolation and existing unit bucket.
# Draft composition retains the same private paths, bounded values and waited
# Perl/Python children; there are no new shared resources or scheduler changes.
# Viewer-launch and switch-readiness retries use in-memory observers and mocked commands/clocks;
# they retain the compatible unit bucket and create no processes or shared state.
# Shared review fragments retain those same private, waited Perl children and
# in-memory observers; no scheduler or resource admission change is needed.
# Case 154 retains bounded in-memory profiles, pytest-owned paths and waited
# private Perl children. No VM, bus, display, cache or shared-path resources.
# Stable traces add only mocked clocks/transports and waited private Perl;
# existing compatible scheduling and resource ownership remain unchanged.
# Transition pumping uses the same mocks and pytest-owned immutable sample
# files. No threads, sockets, shared caches or scheduler changes are introduced.
# Accessibility-event checks retain mocked transports, private values and waited
# Perl children; no live bus, thread, display or new shared resource is allocated.
# Saving projections add only bounded in-memory public event sequences.
# Custom saving retains private pytest paths, mocked transports and waited Perl
# children; no new live bus, display, cache or scheduler resource is introduced.
# Named-child qualification retains those private paths, mocks and waited Perl
# children; unit scheduling and cleanup ownership are unchanged.
# Collection uses the same private mocks and waited Perl children; no additional
# mutable paths, buses, displays, caches or scheduling resources.
# Case 155 retains these private paths, bounded doubles and waited Perl children;
# no resource ownership, unit scheduler or cleanup classification changes.


@pytest.mark.parametrize('fault', ['', 'storage', 'input', 'terminal-only', 'terminal', 'order', 'boot'])
def test_collection_real_decoder_waits_for_finished_state(fault):
    from ui_observations import UiObservations
    reader = UiObservations(SimpleNamespace(commands=SimpleNamespace(progress=None)))
    reader.boot_guard = 'b' * 64
    operations, retained = [], []

    def retain(*args):
        if fault == 'storage':
            raise OSError('storage')
        retained.append(args)
    reader.trace_sink = retain

    def call(argv, *, input, timeout, on_output):
        operation = argv[3]
        operations.append(operation)
        if operation == 'feedback-collection-open':
            assert retained and argv[-1] == 'c' * 64
            if fault == 'input':
                raise OSError('uncertain input')
            value = {'opened': True}
        else:
            assert operation == 'feedback-collection-events'
            token = argv[-1]
            on_output(json.dumps({'event': 'accessibility-trace-ready', 'token': token,
                'source': 'c' * 64, 'boot_sha256': ('d' if fault == 'boot' else 'b') * 64,
                'checked': False}).encode() + b'\n')
            samples = [{'elapsed_ms': 10, 'collecting': True, 'download': False},
                       {'elapsed_ms': 20, 'collecting': False, 'download': True}]
            if fault == 'terminal-only': samples.pop(0)
            if fault == 'terminal': samples.pop()
            if fault == 'order': samples[-1]['elapsed_ms'] = 0
            value = {'token': token, 'source': 'c' * 64, 'terminal': True, 'samples': samples}
        on_output(json.dumps({'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
                              'boot_sha256': 'b' * 64, 'trace': value}).encode() + b'\n')
        return b''

    reader.transport.call = call
    if fault not in ('', 'terminal-only'):
        with pytest.raises((EvidenceError, OSError)):
            reader.observe_accessibility_input('feedback-collection-open', True, 'collection')
        assert reader.trace_failed and reader.accessibility_trace is None
        with pytest.raises(EvidenceError):
            reader.observe_accessibility_input('feedback-collection-open', True, 'collection')
    else:
        result = reader.observe_accessibility_input('feedback-collection-open', True, 'collection')
        assert result['operation'] == 'feedback-collection-trace'
        assert len(retained) == (2 if fault == 'terminal-only' else 3)
    assert operations.count('feedback-collection-open') == (0 if fault in ('storage', 'boot') else 1)


@pytest.mark.parametrize('fault', ['', 'first-collection', 'first-independent', 'first-refused',
                                  'first-close', 'second-collection', 'second-close'])
def test_collection_worker_composition_and_refusal(fault):
    from tests.support.perl import run_perl
    from feedback_collection import PLAN
    PLAN.__post_init__()
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@stages); our ($fault) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi; sub record_info { }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @stages, 'finish'; };
my $ok = eval { onpc_feedback_states::run_collection(sub {
    push @stages, $_[0]; die 'failed proof' if $_[0] eq $fault;
    return {observed => $_[0]};
}); 1; };
print encode_json({ok => $ok ? 1 : 0, stages => \@stages});
''', fault).stdout)
    stages = list(PLAN.screen_tags)
    stages = stages[stages.index('parent-selected'):] + ['finish']
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)


def test_collection_selector_and_exclusive_mode(monkeypatch):
    import check_e2e_feedback_collection as selector
    run = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', run)
    assert selector.main() == 0
    assert run.call_args.kwargs['feedback_collection'] is True
    with pytest.raises(CommandError, match='smoke:trace-prerequisites'):
        smoke.main(feedback_collection=True, parent_save_trace=True)


@pytest.mark.parametrize('initial', [None, {'collecting': True, 'download': False},
                                    {'collecting': False, 'download': True}])
def test_collection_guest_waits_for_finished_state(monkeypatch, initial):
    from itertools import count
    clock = count()
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: next(clock) / 100)
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda _: None)
    terminal = {'collecting': False, 'download': True}
    ui, parent, _dialog, _controls = feedback_ui()
    ui.timeout = 1
    ui.root().bus = parent.bus = ':1.2'
    parent.path = '/parent'
    ui.feedback_collection_sample = Mock(side_effect=[initial, terminal])
    assert ui.wait_feedback_collection() == terminal
    assert ui.feedback_collection_sample.call_count == (1 if initial == terminal else 2)


@pytest.mark.parametrize('state', [None, {'collecting': True, 'download': False},
                                  {'collecting': False, 'download': False}])
def test_collection_guest_refuses_unfinished_or_unavailable_download(monkeypatch, state):
    from itertools import count
    clock = count()
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: next(clock) * 10)
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda _: None)
    ui, parent, _dialog, _controls = feedback_ui()
    ui.root().bus = parent.bus = ':1.2'
    parent.path = '/parent'
    ui.feedback_collection_sample = Mock(return_value=state)
    with pytest.raises(accessible_ui.UiError, match='ui:timeout:feedback-collection-ready'):
        ui.wait_feedback_collection()


@pytest.mark.parametrize('value', [
    {'collecting': False, 'download': True},
    {'collecting': True, 'download': False},
    {'collecting': False, 'download': False},
    {'collecting': 0, 'download': 1}, None])
def test_collection_readiness_public_decoder(value):
    from ui_observations import UiObservations
    operation = 'feedback-collection-ready'
    reader = UiObservations(SimpleNamespace(commands=SimpleNamespace(progress=None)))
    reader.call = Mock(return_value=(json.dumps({
        'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
        'collection': value}).encode(), []))
    if value is not None and value['collecting'] is False and value['download'] is True:
        assert reader.observe(operation)['collection'] == value
    else:
        with pytest.raises(EvidenceError, match='ui:collection-not-ready'):
            reader.observe(operation)


def test_collection_sample_does_not_wait_for_unrelated_desktop_traversal():
    ui, parent, dialog, controls = feedback_ui()
    application = ui.root()
    parent.bus, parent.path = ':1.2', '/parent'
    dialog.bus, dialog.path = ':1.2', '/dialog'
    ui.collection_owner = (parent.bus, parent.path)
    ui.collection_application = application
    ui.collection_dialog = dialog
    row = Node('Collecting diagnostic information...', identity='feedback-collection-status')
    row.parent = dialog
    dialog.children.append(row)
    dialog.children.remove(controls['feedback-download-logs'])
    unrelated = Node(identity='unrelated-application')
    desktop = Node(children=[unrelated, application])
    ui.root = lambda: desktop
    visited = []

    def slow_unrelated_read():
        # GTK exposes initial states without collection/Download transitions.
        # Model completion during unrelated RPC traversal, without sleeping or
        # inventing signals that the real GTK regression shows do not arrive.
        visited.append('unrelated')
        dialog.children.remove(row)
        dialog.children.append(controls['feedback-download-logs'])
        return 0

    unrelated.get_child_count = slow_unrelated_read
    assert ui.feedback_collection_sample() == {'collecting': True, 'download': False}
    assert not visited
    dialog.children.remove(row)
    dialog.children.append(controls['feedback-download-logs'])
    assert ui.feedback_collection_sample() == {'collecting': False, 'download': True}


def test_collection_input_rejects_changed_source_before_opening():
    ui = SimpleNamespace(trace_request='a' * 64,
        feedback_collection_source=Mock(return_value='b' * 64), open_feedback=Mock())
    with pytest.raises(accessible_ui.UiError, match='ui:trace-source-changed'):
        accessible_ui.AccessibleUI.feedback_collection_events(ui, 'feedback-collection-open')
    ui.open_feedback.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'foreign', 'missing-dialog', 'defunct'])
def test_collection_event_requires_public_id_and_owned_dialog(monkeypatch, fault):
    dialog = SimpleNamespace(bus=':1.2', path='/dialog', get_parent=lambda: None)
    parent = SimpleNamespace(bus=':1.3' if fault == 'foreign' else ':1.2',
                             path='/parent', get_parent=lambda: dialog)
    row = SimpleNamespace(bus=':1.2', path='/row', get_parent=lambda: parent,
                          get_name=lambda: 'Collecting diagnostic information...')
    identities = {id(row): 'feedback-collection-status',
                  id(parent): 'container',
                  id(dialog): 'other' if fault == 'missing-dialog' else 'feedback-dialog'}
    monkeypatch.setattr(accessible_ui, 'public_automation_id',
                        lambda node: identities[id(node)])
    ui = SimpleNamespace(api=SimpleNamespace(node=lambda _: row,
                                             StateType=SimpleNamespace(DEFUNCT='defunct')),
                         collection_owner=(':1.2', '/parent'),
                         has_state=lambda _node, _state: fault == 'defunct')
    if fault:
        with pytest.raises(accessible_ui.UiError):
            accessible_ui.AccessibleUI.feedback_collection_event_target(ui, '/row')
    else:
        assert accessible_ui.AccessibleUI.feedback_collection_event_target(ui, '/row') == ('row', '/dialog')


def test_collection_ignores_hidden_row_sensitivity_before_reading_label(monkeypatch):
    row = SimpleNamespace(get_name=Mock(side_effect=AssertionError('hidden label read')))
    monkeypatch.setattr(accessible_ui, 'public_automation_id',
                        lambda _node: 'feedback-collection-status')
    ui = SimpleNamespace(api=SimpleNamespace(node=lambda _: row),
                         collection_owner=(':1.2', '/parent'))
    assert accessible_ui.AccessibleUI.feedback_collection_event_target(
        ui, '/row', 'sensitive') is None
    row.get_name.assert_not_called()


@pytest.mark.parametrize('download_exposed', [True, False])
@pytest.mark.parametrize('fault', ['', 'owner', 'duplicate', 'stale', 'stale-control', 'incomplete'])
def test_collection_sample_public_ids_and_owner(fault, download_exposed):
    ui, parent, dialog, controls = feedback_ui()
    ui.collection_application = ui.root()
    parent.bus, parent.path = ':1.2', '/parent'
    dialog.bus, dialog.path = ':1.2', '/feedback'
    ui.collection_owner = (parent.bus, parent.path)
    row = Node('Collecting diagnostic information...', identity='feedback-collection-status')
    row.parent = dialog
    dialog.children.append(row)
    controls['feedback-download-logs'].states.remove('sensitive')
    if not download_exposed:
        # Collection hides the attachment row containing Download. GTK omits
        # that subtree from the public tree until collection completes.
        dialog.children.remove(controls['feedback-download-logs'])
    if fault == 'owner': dialog.bus = ':1.3'
    if fault == 'duplicate':
        dialog.children.append(Node(identity='feedback-download-logs' if download_exposed
                                    else 'feedback-collection-status'))
    if fault == 'stale': dialog.states.add('defunct')
    if fault == 'stale-control':
        (controls['feedback-download-logs'] if download_exposed else row).states.add('defunct')
    if fault == 'incomplete': dialog.get_child_count = Mock(side_effect=LookupError())
    if fault:
        with pytest.raises((accessible_ui.UiError, LookupError)):
            ui.feedback_collection_sample()
    else:
        assert ui.feedback_collection_sample() == {'collecting': True, 'download': False}
        dialog.children.remove(row)
        if not download_exposed:
            assert ui.feedback_collection_sample() is None
            dialog.children.append(controls['feedback-download-logs'])
        controls['feedback-download-logs'].states.add('sensitive')
        assert ui.feedback_collection_sample() == {'collecting': False, 'download': True}
    for control in controls.values():
        control.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'duplicate', 'foreign'])
def test_collection_pins_unique_dialog_and_controls(fault):
    ui, parent, dialog, controls = feedback_ui()
    ui.collection_application = ui.root()
    parent.bus, parent.path = ':1.2', '/parent'
    dialog.bus, dialog.path = (':1.3' if fault == 'foreign' else ':1.2'), '/dialog'
    ui.collection_owner = (parent.bus, parent.path)
    row = Node('Collecting diagnostic information...', identity='feedback-collection-status')
    row.parent = dialog
    row.path = '/row'
    dialog.children.append(row)
    controls['feedback-download-logs'].path = '/download'
    if fault == 'duplicate':
        duplicate = Node(identity='feedback-collection-status')
        duplicate.parent = dialog
        dialog.children.append(duplicate)
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.feedback_collection_pins()
    else:
        assert ui.feedback_collection_pins() == {
            'dialog': '/dialog', 'row': '/row', 'download': '/download'}
        dialog.children.remove(row)
        assert ui.feedback_collection_pins() == {
            'dialog': '/dialog', 'row': None, 'download': '/download'}
        dialog.children.append(row)
        dialog.children.remove(controls['feedback-download-logs'])
        assert ui.feedback_collection_pins() == {
            'dialog': '/dialog', 'row': '/row', 'download': None}


@pytest.mark.parametrize('fault', ['', 'disabled-entry', 'editor-disabled', 'picker-disabled',
                                  'no-inhibition', 'no-recovery', 'input', 'source'])
@pytest.mark.parametrize('child', [None, 'existing'])
def test_custom_trace_real_decoder_preserves_enabled_editing_and_one_input(fault, child):
    from ui_observations import UiObservations
    reader = UiObservations(SimpleNamespace(commands=SimpleNamespace(progress=None)))
    reader.boot_guard = 'b' * 64
    retained, operations, inputs = [], [], []
    reader.trace_sink = lambda token, index, sample: retained.append((index, sample))
    sequence = [('child', False), ('toggle', False), ('child', True), ('toggle', True)]
    if fault == 'editor-disabled': sequence.insert(2, ('editor', False))
    if fault == 'picker-disabled': sequence.insert(2, ('allowance', False))
    if fault == 'no-inhibition': sequence = sequence[2:]
    if fault == 'no-recovery': sequence.pop()
    # Realistic multi-save output, large enough to exercise response limits.
    samples = [{'elapsed_ms': index * 10, 'target': target, 'state': 'sensitive', 'value': value}
               for index, (target, value) in enumerate(sequence * 4)]

    def call(argv, *, input, timeout, on_output):
        operation = argv[3]
        if child:
            assert argv[-1] == child
        argument = argv[-2] if child else argv[-1]
        operations.append(operation)
        reply = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
                 'boot_sha256': 'b' * 64}
        if operation == 'parent-custom-events':
            token = argument
            on_output((json.dumps({'event': 'accessibility-trace-ready', 'token': token,
                'source': 'c' * 64, 'boot_sha256': 'b' * 64,
                'checked': fault != 'disabled-entry'}) + '\n').encode())
            reply['trace'] = {'token': token, 'source': ('d' if fault == 'source' else 'c') * 64,
                              'terminal': True, 'samples': samples}
        else:
            assert operation == 'parent-custom-trace-focus'
            assert retained[0][0] == 0 and argument == 'c' * 64
            reply['trace'] = {'focused': True}
        on_output((json.dumps(reply) + '\n').encode())
        return b''

    def release(token, source):
        inputs.append((token, source))
        if fault == 'input': raise OSError('uncertain keyboard batch')

    reader.transport.call = call
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            reader.observe_accessibility_input('parent-custom-trace-focus', 6, 'custom-save', worker_input=release, child=child)
        assert reader.trace_failed
        with pytest.raises(EvidenceError, match='previous-failure'):
            reader.observe_accessibility_input('parent-custom-trace-focus', 6, 'custom-save', worker_input=release, child=child)
    else:
        result = reader.observe_accessibility_input('parent-custom-trace-focus', 6, 'custom-save', worker_input=release, child=child)
        assert result['samples'] == samples and len(retained) == len(samples) + 1
    assert len(inputs) == (0 if fault == 'disabled-entry' else 1)


@pytest.mark.parametrize('fault', ['', 'first-rapid', 'input', 'second-reopened',
    *[f'{entry}-{direction}-{step}' for entry in ('first', 'second')
      for direction in ('away', 'back') for step in ('open', 'focus', 'selected')]])
def test_custom_worker_actual_sequence_and_failed_input_stop(fault):
    from custom_save_trace import PLAN
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@stages, @keys); our ($fault) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::keys, $_[0]; die 'uncertain' if $main::fault eq 'input' && $_[0] eq 'ctrl-a'; }
sub type_string { push @main::keys, $_[0]; }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @stages, 'finish'; };
my $ok = eval { onpc_feedback_states::run_custom_save_trace(sub {
    my ($stage, $shot, $input) = @_;
    push @stages, $stage; die 'refused' if $stage eq $fault;
    $input->({binding => 'custom-rapid', child => 'child', values => [5, 6]}) if defined($input);
    return {observed => $stage};
}); 1; };
print encode_json({ok => $ok ? 1 : 0, stages => \@stages, keys => \@keys});
''', fault).stdout)
    stages = list(PLAN.screen_tags)
    stages = stages[stages.index('parent-selected'):] + ['finish']
    boundary = 'first-rapid' if fault == 'input' else fault
    assert result['stages'] == (stages[:stages.index(boundary) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    if not fault:
        assert result['keys'] == ['15m', 'ret', 'c', 'ret', 'ctrl-a', '5\n', 'ctrl-a', '6\n', 'ret', 'ret'] * 2


def test_custom_trace_renamed_stage_and_immutable_input_gate(tmp_path):
    from dataclasses import replace
    from installed_journey import InstalledJourney
    from custom_save_trace import PLAN
    plan = replace(PLAN, screen_tags={'renamed-input': 'ui:parent-custom-save-trace'},
                   accessibility_inputs={'renamed-input': ('parent-custom-trace-focus', 6, 'custom-save')},
                   keyboard_inputs={'renamed-input': (5, 6)}, settings_checks={}, advance_after={},
                   phases={'ready': 'setup', 'setup-detached': 'setup', 'renamed-input': 'step-1'})
    journey = InstalledJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    journey.publish_trace_input('renamed-input', 'a' * 32, 'b' * 64)
    with pytest.raises(EvidenceError, match='replay'):
        journey.publish_trace_input('renamed-input', 'a' * 32, 'b' * 64)
    with pytest.raises(EvidenceError, match='incomplete'):
        journey.verify_trace_input('renamed-input', 'a' * 32)
    (tmp_path / 'renamed-input.input-done.json').write_text(json.dumps(
        {'stage': 'renamed-input', 'token': 'a' * 32}))
    journey.verify_trace_input('renamed-input', 'a' * 32)
    with pytest.raises(EvidenceError, match='incomplete'):
        journey.verify_trace_input('renamed-input', 'c' * 32)


@pytest.mark.parametrize('named', [False, True])
def test_custom_trace_selector_and_mode_refusal(monkeypatch, named):
    import check_e2e_custom_save_trace as selector
    if named:
        import check_e2e_named_child_custom_saves as selector
    run = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', run)
    assert selector.main() == 0
    assert run.call_args.kwargs['custom_save_trace'] is True
    assert run.call_args.kwargs.get('named_child_custom_saves', False) is named
    with pytest.raises(CommandError, match='trace-prerequisites'):
        smoke.main(custom_save_trace=True, parent_save_trace=True)


def test_named_custom_worker_sequence_and_every_refusal():
    from named_child_custom_saves import PLAN
    from tests.support.perl import run_perl
    expected = list(PLAN.screen_tags)
    expected = expected[expected.index('parent-selected'):] + ['finish']
    for fault in ['', 'wrong-child-proof', *expected[:-1]]:
        result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@stages, @keys); our ($fault) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::keys, $_[0]; }
sub type_string { push @main::keys, $_[0]; }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub {
    die 'wrong child' unless $_[4] eq 'existing';
    return $_[0]->seen('parent-selected');
};
*onpc_journey::finish = sub { push @stages, 'finish'; };
my $ok = eval { onpc_feedback_states::run_named_child_custom_saves(sub {
    my ($stage, $shot, $input) = @_;
    push @stages, $stage; die 'refused' if $stage eq $fault;
    $input->({binding => 'custom-rapid', values => [5, 6],
              child => $fault eq 'wrong-child-proof' ? 'child' : 'existing'}) if defined($input);
    return {observed => $stage};
}); 1; };
print encode_json({ok => $ok ? 1 : 0, stages => \@stages, keys => \@keys});
''', fault).stdout)
        boundary = 'first-rapid' if fault == 'wrong-child-proof' else fault
        assert result['stages'] == (expected[:expected.index(boundary) + 1] if fault else expected)
        assert bool(result['ok']) is (not fault)
        if fault == 'wrong-child-proof':
            assert result['keys'] == ['c', 'ret']
        if not fault:
            assert result['keys'] == ['c', 'ret', 'ctrl-a', '5\n', 'ctrl-a', '6\n', 'ret', 'ret'] * 2 + [
                'ret', 'c', 'ret', 'ctrl-a', '7', 'ret', 'ret']
    assert PLAN.child_bindings['first-rapid'] == 'existing'
    assert PLAN.child_bindings['riley-text-read'] == 'child'
    assert PLAN.settings_checks['final-away-selected'].child == 'existing-fixture-child'


def test_save_order_worker_reuses_named_input_and_stops_at_failed_window_count():
    from save_order import PLAN
    from tests.support.perl import run_perl
    expected = list(PLAN.screen_tags)
    expected = expected[expected.index('parent-selected'):] + ['finish']
    for fault in ('', *expected[:-1]):
        result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@stages, @keys); our ($fault) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::keys, $_[0]; }
sub type_string { push @main::keys, $_[0]; }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub {
    die 'wrong child' unless $_[4] eq 'existing';
    return $_[0]->seen('parent-selected');
};
*onpc_journey::finish = sub { push @stages, 'finish'; };
my $ok = eval { onpc_feedback_states::run_save_order(sub {
    my ($stage, $shot, $input) = @_;
    push @stages, $stage; die 'refused' if $stage eq $fault;
    $input->({binding => 'custom-rapid', values => [5, 6], child => 'existing'})
        if defined($input);
    return {observed => $stage};
}); 1; };
print encode_json({ok => $ok ? 1 : 0, stages => \@stages, keys => \@keys});
''', fault).stdout)
        assert result['stages'] == (expected[:expected.index(fault) + 1] if fault else expected)
        assert bool(result['ok']) is (not fault)
        if fault == 'jordan-rapid':
            assert result['keys'] == ['15h', '0m', 'ret', '15h', 'esc', 'c', 'ret']
    assert PLAN.settings_checks['repeat-selected'] == 'final-back-selected'
    assert PLAN.child_bindings['jordan-rapid'] == 'existing'


@pytest.mark.parametrize('daily', [0, 900])
def test_save_order_checks_saved_balance_before_highlight_reply(tmp_path, daily):
    from journey_checks import AllowanceJourney
    from save_order import PLAN
    journey = AllowanceJourney(SimpleNamespace(directory=tmp_path), Mock(), PLAN)
    observed = {'ui': {'time_explanation': {
        'observed_monotonic_ns': 100,
        **{key: {'seconds': seconds, 'precision_seconds': 1}
           for key, seconds in (('daily', daily), ('one_time', 0), ('total', daily))}}}}
    if daily:
        with pytest.raises(EvidenceError, match='ordinary-balances'):
            journey.check_settings('jordan-preset-highlight-0', observed)
    else:
        journey.check_settings('jordan-preset-highlight-0', observed)
        assert observed['comparison']['ordinary_balances'] is True


@pytest.mark.parametrize('count,valid', [(1, True), (0, False), (2, False),
                                         (True, False), ('1', False)])
def test_parent_window_count_controller_requires_exact_numeric_one(count, valid):
    from ui_observations import UiObservations
    reader = UiObservations(Mock())
    payload = {'operation': 'parent-window-count', 'outcome': 'passed',
               'interface': 'AT-SPI', 'count': count}
    reader.call = lambda *args, **kwargs: (json.dumps(payload).encode(), [])
    if valid:
        assert reader._observe('parent-window-count')['count'] == 1
    else:
        with pytest.raises(EvidenceError, match='parent-window-count'):
            reader._observe('parent-window-count')


def test_named_custom_fragment_with_independent_stage_names():
    from journey_blocks import custom_save_entry
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi; sub record_info { } sub send_key { } sub type_string { }
package main;
require onpc_feedback_states;
my @stages;
my $journey = onpc_journey->new(prefix => 'consumer', review => 0, exchange => sub {
    my ($stage, $shot, $input) = @_; push @stages, $stage;
    $input->({binding => 'custom-rapid', child => 'existing', values => [5, 6]}) if $input;
    return {observed => $stage};
});
onpc_feedback_states::custom_save_entry($journey, 'renamed', 'existing', 5, 6);
print encode_json(\@stages);
''').stdout)
    assert result == list(custom_save_entry('renamed', 'existing'))


def test_ordinary_custom_fragment_renamed_sequence_and_every_refusal():
    from journey_blocks import ordinary_custom_save
    from tests.support.perl import run_perl
    expected = list(ordinary_custom_save('independent', 'child', 7))
    for fault in ('', *expected):
        result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@stages, @keys); our ($fault) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::keys, $_[0]; }
sub type_string { push @main::keys, $_[0]; }
package main;
require onpc_feedback_states;
my $journey = onpc_journey->new(prefix => 'consumer', review => 0, exchange => sub {
    my ($stage) = @_; push @stages, $stage;
    die 'refused' if $stage eq $fault;
    return {observed => $stage};
});
my $ok = eval { onpc_feedback_states::ordinary_custom_save($journey, 'independent', 7); 1; };
print encode_json({ok => $ok ? 1 : 0, stages => \@stages, keys => \@keys});
''', fault).stdout)
        assert result['stages'] == (expected[:expected.index(fault) + 1] if fault else expected)
        assert bool(result['ok']) is (not fault)
        if fault in expected[:2]:
            assert not result['keys']
        if not fault:
            assert result['keys'] == ['ret', 'c', 'ret', 'ctrl-a', '7']
    with pytest.raises(EvidenceError, match='ordinary-custom-value'):
        ordinary_custom_save('independent', 'child', 8)


def test_named_custom_source_digest_includes_child_and_rejects_unbound_plan():
    from dataclasses import replace
    from named_child_custom_saves import PLAN
    nodes = {identity: SimpleNamespace(bus=':1.7', path='/' + str(index))
             for index, identity in enumerate(('root', 'parent-screen-limit-toggle',
                 'parent-child-selector', 'parent-daily-limit-selector', 'parent-custom-daily-limit'))}
    ui = SimpleNamespace(settings=Mock(), parent=lambda: nodes['root'],
                         id_target=lambda identity, **kwargs: nodes[identity])
    riley = accessible_ui.AccessibleUI.parent_save_trace_source(ui, True, accessible_ui.CHILD)[0]
    jordan = accessible_ui.AccessibleUI.parent_save_trace_source(ui, True, accessible_ui.EXISTING_CHILD)[0]
    assert riley != jordan
    ui.settings.assert_called_with(accessible_ui.EXISTING_CHILD)
    with pytest.raises(EvidenceError, match='custom-child-plan'):
        replace(PLAN, child_bindings={'first-rapid': 'unregistered'})
    with pytest.raises(EvidenceError, match='custom-child-plan'):
        replace(PLAN, child_bindings={'installed-greeter': 'existing'})


@pytest.mark.parametrize('fault', ['', 'editor', 'allowance'])
def test_custom_event_collector_preserves_live_editor_and_source(monkeypatch, capsys, fault):
    from contextlib import contextmanager
    controls = {name: SimpleNamespace(bus=':1.20', path='/' + name)
                for name in ('toggle', 'child', 'allowance', 'editor')}
    sequence = [('child', False), ('toggle', False), ('child', True), ('toggle', True)]
    if fault: sequence.insert(2, (fault, False))
    @contextmanager
    def events(endpoints, receive):
        assert len(endpoints) == 5
        assert endpoints[(':1.20', '/editor', 'sensitive')] == 'editor'
        def iteration(_blocking):
            assert 'accessibility-trace-ready' in capsys.readouterr().out
            for name, value in sequence:
                receive(name, 'sensitive', value, None)
        yield SimpleNamespace(pending=lambda: False, iteration=iteration)
    ui = SimpleNamespace(
        trace_request='a' * 32, trace_boot='b' * 64,
        api=SimpleNamespace(StateType=SimpleNamespace(CHECKED=1, SENSITIVE=2), state_events=events),
        parent_save_snapshot=Mock(), parent_save_trace_source=Mock(return_value=('c' * 64, controls)),
        text_recipient=Mock(), has_state=lambda node, state: True,
        invalidate_observation=Mock(), read_custom_trace_draft=Mock())
    if fault:
        with pytest.raises(accessible_ui.UiError, match='custom-trace-controls'):
            accessible_ui.AccessibleUI.parent_save_events(ui, True)
    else:
        result = accessible_ui.AccessibleUI.parent_save_events(ui, True)
        assert len(result['samples']) == 4 and result['terminal'] is True
        ui.parent_save_snapshot.assert_called_with(accessible_ui.CHILD, True)
        ui.parent_save_trace_source.assert_called_with(True, accessible_ui.CHILD)


@pytest.mark.parametrize('disabled', [None, 'allowance', 'editor'])
def test_custom_trace_draft_allows_inhibited_child_selector(disabled):
    states = SimpleNamespace(ACTIVE='active', VISIBLE='visible', SENSITIVE='sensitive',
                             DEFUNCT='defunct', EDITABLE='editable')
    nodes = {name: SimpleNamespace(get_role_name=lambda: 'entry',
                                   get_text_iface=lambda: 'text')
             for name in ('root', 'child', 'allowance', 'editor')}
    identities = {'parent-child-selector': 'child',
                  'parent-daily-limit-selector': 'allowance',
                  'parent-custom-daily-limit': 'editor'}
    def state(node, field):
        name = next(name for name, candidate in nodes.items() if candidate is node)
        return field in {'active' if name == 'root' else 'visible', 'editable'} or (
            field == 'sensitive' and name not in ('child', disabled))
    ui = SimpleNamespace(
        api=SimpleNamespace(StateType=states, Text=SimpleNamespace(
            get_character_count=lambda value: 1,
            get_text=lambda value, start, end: '6')),
        parent=lambda: nodes['root'],
        id_target=lambda identity, **kwargs: nodes[identities[identity]],
        child_id_control=lambda *args, **kwargs: nodes['child'],
        has_state=state)
    if disabled:
        with pytest.raises(accessible_ui.UiError, match='ui:custom-trace-controls'):
            accessible_ui.AccessibleUI.read_custom_trace_draft(ui)
    else:
        accessible_ui.AccessibleUI.read_custom_trace_draft(ui)


@pytest.mark.parametrize('fault', ['', 'wrong-stage', 'wrong-token', 'uncertain'])
def test_actual_exchange_releases_only_one_validated_keyboard_batch(tmp_path, fault):
    from tests.support.perl import run_perl
    from tests.support.paths import ROOT
    source = (ROOT / 'tests/integration/graphical_smoke/tests/smoke.pm').read_text()
    exchange = source[source.index('sub exchange {'):source.index('\nsub capture {')]
    proof = {'stage': 'other' if fault == 'wrong-stage' else 'renamed',
             'token': 'invalid' if fault == 'wrong-token' else 'a' * 32,
             'source': 'b' * 64, 'binding': 'custom-rapid', 'values': [5, 6], 'child': 'child'}
    (tmp_path / 'renamed.input.json').write_text(json.dumps(proof))
    result = json.loads(run_perl('use strict; use warnings; use JSON::PP; use Time::HiRes qw(time sleep);\n' + exchange + r'''
my ($directory, $fault) = @ARGV; chdir($directory) or die 'chdir';
my $count = 0;
my $ok = eval { exchange('renamed', undef, sub {
    $count++; die 'uncertain' if $fault eq 'uncertain';
    open(my $reply, '>', 'renamed.reply.json') or die 'reply';
    print {$reply} encode_json({observed => 'renamed'}); close($reply);
}); 1; };
print encode_json({ok => $ok ? 1 : 0, count => $count});
''', str(tmp_path), fault).stdout)
    assert result == {'ok': int(not fault), 'count': int(fault not in ('wrong-stage', 'wrong-token'))}
    assert (tmp_path / 'renamed.input-done.json').exists() is (not fault)


@pytest.mark.parametrize('fault', ['', 'final-only', 'nonoverlap', 'no-recovery',
                                  'wrong-control', 'no-checked'])
def test_parent_save_trace_requires_event_derived_inhibition_and_recovery(fault):
    from ui_observations import save_trace_complete
    sequence = [('toggle', 'checked', True), ('allowance', 'sensitive', True),
                ('child', 'sensitive', False), ('toggle', 'sensitive', False),
                ('allowance', 'sensitive', False), ('child', 'sensitive', True),
                ('toggle', 'sensitive', True), ('allowance', 'sensitive', True)]
    if fault == 'final-only': sequence = sequence[:2] + sequence[-3:]
    if fault == 'nonoverlap': sequence.insert(3, ('child', 'sensitive', True))
    if fault == 'no-recovery': sequence.pop(-2)
    if fault == 'wrong-control': sequence[3] = ('allowance', 'sensitive', False)
    if fault == 'no-checked': sequence.pop(0)
    samples = [{'elapsed_ms': index, 'target': target, 'state': state, 'value': value}
               for index, (target, state, value) in enumerate(sequence)]
    assert save_trace_complete(samples) is (not fault)


def test_parent_save_trace_plan_and_controller_keep_readiness_before_one_input():
    from parent_save_trace import PLAN as SAVE_PLAN
    from ui_observations import UiObservations
    assert SAVE_PLAN.accessibility_inputs['first-observed-enable'] == (
        'parent-toggle-enabled', True, 'save')
    operations, retained = [], []
    transport = SimpleNamespace(commands=SimpleNamespace(progress=None))
    reader = UiObservations(transport)
    reader.boot_guard = 'b' * 64
    reader.trace_sink = lambda token, index, sample: retained.append((index, sample))
    samples = [{'elapsed_ms': index, 'target': target, 'state': state, 'value': value}
               for index, (target, state, value) in enumerate((
                   ('toggle', 'checked', True), ('allowance', 'sensitive', True),
                   ('child', 'sensitive', False), ('toggle', 'sensitive', False),
                   ('allowance', 'sensitive', False), ('child', 'sensitive', True),
                   ('toggle', 'sensitive', True), ('allowance', 'sensitive', True)))]

    def call(argv, *, input, timeout, on_output=None):
        operation = argv[3]
        operations.append(operation)
        if operation == 'parent-save-events':
            token = argv[-1]
            on_output((json.dumps({'event': 'accessibility-trace-ready', 'token': token,
                                   'source': 'c' * 64, 'boot_sha256': 'b' * 64,
                                   'checked': False}) + '\n').encode())
            reply = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
                     'boot_sha256': 'b' * 64, 'trace': {'token': token, 'source': 'c' * 64,
                                                     'terminal': True, 'samples': samples}}
        else:
            assert operation == 'parent-toggle-enabled'
            assert retained[0][0] == 0 and argv[-1] == 'save:' + 'c' * 64
            reply = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
                     'boot_sha256': 'b' * 64,
                     'toggle': {'state': True, 'activated': True}}
        on_output((json.dumps(reply) + '\n').encode())
        return b''

    transport.call = call
    result = reader.observe_accessibility_input('parent-toggle-enabled', True, 'save')
    assert result['operation'] == 'parent-save-trace'
    assert result['samples'] == samples
    assert operations == ['parent-save-events', 'parent-toggle-enabled']
    assert len(retained) == len(samples) + 1


@pytest.mark.parametrize('fault', ['', 'no-ready', 'duplicate', 'foreign', 'boot',
                                  'storage', 'input', 'observer', 'cancel', 'oversize', 'order'])
def test_accessibility_trace_stream_brackets_one_input_and_latches(monkeypatch, fault):
    from ui_observations import UiObservations
    operations, retained = [], []
    transport = SimpleNamespace(commands=SimpleNamespace(progress=None))
    reader = UiObservations(transport)
    reader.boot_guard = 'b' * 64

    def call(argv, *, input, timeout, on_output=None):
        operation = argv[3]
        operations.append(operation)
        if operation == 'parent-toggle-enabled':
            assert retained and argv[-1] == 'c' * 64
            if fault == 'input':
                raise OSError('uncertain action')
            reply = json.dumps({'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
                               'boot_sha256': 'b' * 64,
                               'toggle': {'state': True, 'activated': True}}).encode()
            assert on_output is not None  # The nested call must own its parser.
            on_output(reply + b'\n')
            return reply
        assert operation == 'parent-checked-events'
        token = argv[-1]
        ready = {'event': 'accessibility-trace-ready', 'token': token, 'source': 'c' * 64,
                 'boot_sha256': 'b' * 64, 'checked': False}
        if fault == 'foreign': ready['token'] = 'd' * 32
        if fault == 'boot': ready['boot_sha256'] = 'd' * 64
        if fault != 'no-ready':
            encoded = json.dumps(ready).encode() + b'\n'
            on_output(encoded[:17])
            on_output(encoded[17:])
        if fault == 'duplicate': on_output(encoded)
        if fault == 'observer': raise OSError('observer lost')
        if fault == 'cancel': raise KeyboardInterrupt()
        samples = [{'elapsed_ms': i, 'checked': True, 'source': 'event'} for i in range(32)]
        if fault == 'order': samples[-1]['elapsed_ms'] = 0
        if fault == 'oversize': samples.append(samples[-1])
        reply = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
                 'boot_sha256': 'b' * 64, 'trace': {'token': token, 'source': 'c' * 64,
                     'terminal': True, 'samples': samples}}
        on_output(json.dumps(reply).encode() + b'\n')
        return b''

    transport.call = call
    def retain(token, index, sample):
        if fault == 'storage': raise OSError('durable readiness failed')
        retained.append((token, index, sample))
    reader.trace_sink = retain
    if fault:
        with pytest.raises((EvidenceError, OSError, KeyboardInterrupt)):
            reader.observe_accessibility_input('parent-toggle-enabled', True)
        assert reader.trace_failed and reader.accessibility_trace is None
        with pytest.raises(EvidenceError):
            reader.observe_accessibility_input('parent-toggle-enabled', True)
        with pytest.raises(EvidenceError):
            reader.observe('parent-toggle-enabled')
        assert operations.count('parent-toggle-enabled') == (
            0 if fault in ('no-ready', 'foreign', 'boot', 'storage') else 1)
    else:
        result = reader.observe_accessibility_input('parent-toggle-enabled', True)
        assert result['operation'] == 'accessibility-input-trace'
        assert len(result['samples']) == 32 and len(retained) == 33
        assert operations == ['parent-checked-events', 'parent-toggle-enabled']
    assert transport.commands.progress is None


@pytest.mark.parametrize('worker', ['accessibility', 'save'])
@pytest.mark.parametrize('fault', ['', 'first-disabled', 'first-wrong-child', 'first-wrong-surface',
                                  'first-observed-enable', 'first-independent-saved',
                                  'restore-disabled', 'second-observed-enable'])
def test_accessibility_trace_worker_stops_at_failed_boundary(worker, fault):
    from tests.support.perl import run_perl
    from accessibility_input_trace import PLAN as checked_plan
    from parent_save_trace import PLAN as save_plan
    plan = save_plan if worker == 'save' else checked_plan
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@stages); our ($worker, $fault) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi; sub record_info { }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @stages, 'finish'; };
my $operation = $worker eq 'save' ? \&onpc_feedback_states::run_parent_save_trace
                               : \&onpc_feedback_states::run_accessibility_trace;
my $ok = eval { $operation->(sub {
    push @stages, $_[0]; die 'failed proof' if $_[0] eq $fault;
    return {observed => $_[0]};
}); 1; };
print encode_json({ok => $ok ? 1 : 0, stages => \@stages});
''', worker, fault).stdout)
    stages = list(plan.screen_tags)
    stages = stages[stages.index('parent-selected'):] + ['finish']
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)


def test_accessibility_trace_selector_and_explicit_plan(monkeypatch):
    from dataclasses import replace
    from accessibility_input_trace import PLAN as plan
    import check_e2e_accessibility_input_trace as check_trace
    run = Mock(return_value=0)
    monkeypatch.setattr(check_trace, 'smoke', run)
    assert check_trace.main() == 0
    assert run.call_args.kwargs['accessibility_input_trace'] is True
    with pytest.raises(CommandError, match='trace-prerequisites'):
        smoke.main(accessibility_input_trace=True, trace_transition=True)
    with pytest.raises(EvidenceError, match='accessibility-input-plan'):
        replace(plan, accessibility_inputs={})
    with pytest.raises(EvidenceError, match='accessibility-input-plan'):
        replace(plan, accessibility_inputs={s: ('parent-toggle-disabled', False)
                                            for s in plan.accessibility_inputs})


def test_parent_save_trace_selector_and_explicit_plan(monkeypatch):
    from dataclasses import replace
    from parent_save_trace import PLAN
    import check_e2e_parent_save_trace as check_trace
    run = Mock(return_value=0)
    monkeypatch.setattr(check_trace, 'smoke', run)
    assert check_trace.main() == 0
    assert run.call_args.kwargs['parent_save_trace'] is True
    with pytest.raises(CommandError, match='trace-prerequisites'):
        smoke.main(parent_save_trace=True, accessibility_input_trace=True)
    with pytest.raises(EvidenceError, match='accessibility-input-plan'):
        replace(PLAN, accessibility_inputs={})


@pytest.mark.parametrize('body,draft', [('', 'initial-empty'), ('S', 'trace-prefix'),
    ('Synthetic feedback first', 'states-no-reply'), ('Synthetic feedback first\n', 'states-no-reply')])
def test_transition_sample_reads_public_prefix_and_terminal_controls(body, draft):
    ui, _, _, controls = feedback_ui()
    controls['feedback-editor-input'].text.count = len(body)
    ui.api.Text.get_text = lambda text, first, last: body[first:last]
    assert ui.feedback_state_operation('feedback-trace-sample') == {
        'draft': draft, 'attachments': ['diagnostic-logs.zip'], 'collection': 'ready',
        'validation': 'none', 'controls': 'ready', 'send_enabled': True}


@pytest.mark.parametrize('body', ['private', 'Synthetic feedback firstX', 'S\n\n'])
def test_transition_sample_refuses_undeclared_text(body):
    ui, _, _, controls = feedback_ui()
    controls['feedback-editor-input'].text.count = len(body)
    ui.api.Text.get_text = lambda text, first, last: body[first:last]
    with pytest.raises(accessible_ui.UiError, match='feedback-nonempty-draft'):
        ui.feedback_state_operation('feedback-trace-sample')


@pytest.mark.parametrize('fault', ['', 'token', 'stale', 'boot', 'order', 'controls',
                                  'terminal', 'unobserved', 'storage', 'wrong-input'])
@pytest.mark.parametrize('binding', ['body-first', 'body-clear'])
def test_transition_trace_decodes_pumped_samples_and_latches(monkeypatch, fault, binding):
    reader, reply, clock = trace_reader(monkeypatch)
    retained = []
    reader.trace_sink = lambda token, index, sample: retained.append((index, sample))
    if binding == 'body-clear':
        reply['operation'] = 'feedback-state-no-reply'
        reply['feedback_state']['draft'] = 'states-no-reply'
        reader.call.return_value = (json.dumps(reply).encode(), [])
    ready = reader.start_trace(binding)
    from ui_observations import FeedbackStateObservation
    terminal = (FeedbackStateObservation('initial-empty', 'none', True)
                if binding == 'body-clear' else None)
    original = reader._observe
    # Input mechanics have separate actual-worker and adapter checks below;
    # samples still cross the real controller's bounded JSON decoder.
    reader._observe = lambda op: original(op) if op == 'feedback-trace-sample' else {}
    reader.observe('text-' + binding + '-focus')
    reader.observe('text-' + binding + '-selected')
    reply['operation'] = 'feedback-trace-sample'
    reply['feedback_state']['draft'] = 'trace-prefix'
    reader.call.return_value = (json.dumps(reply).encode(), [])
    if fault != 'unobserved':
        reader.poll_trace()
    reader.observe('text-' + binding + '-read')
    reply['feedback_state']['draft'] = 'initial-empty' if binding == 'body-clear' else 'states-no-reply'
    if fault == 'boot':
        reply['boot_sha256'] = 'c' * 64
    if fault == 'controls':
        reply['feedback_state']['send_enabled'] = False
    if fault == 'terminal':
        reply['feedback_state']['draft'] = 'trace-prefix'
    if fault in ('stale', 'order'):
        clock.side_effect = None
        clock.return_value = 61 if fault == 'stale' else 0
    if fault == 'storage':
        reader.trace_sink = Mock(side_effect=OSError('owned sample write failed'))
    reader.call.return_value = (json.dumps(reply).encode(), [])
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            if fault == 'wrong-input':
                reader.observe('feedback-close')
            else:
                reader.finish_trace('foreign' if fault == 'token' else ready['token'], terminal)
        assert reader.trace_failed and reader.trace is None
        with pytest.raises(EvidenceError, match='trace-previous-failure'):
            reader.start_trace('body-first')
    else:
        result = reader.finish_trace(ready['token'], terminal)
        assert result['terminal'] == binding + '-ready'
        assert [s['state']['draft'] for s in result['samples']] == [
            'states-no-reply' if binding == 'body-clear' else 'initial-empty',
            'trace-prefix', 'initial-empty' if binding == 'body-clear' else 'states-no-reply']
        assert [index for index, _ in retained] == [0, 1, 2]
        with pytest.raises(EvidenceError, match='trace-token'):
            reader.finish_trace(ready['token'])


def test_transition_pump_runs_without_worker_checkpoint_and_storage_is_immutable(tmp_path):
    from installed_journey import InstalledJourney
    from trace_transition import PLAN as plan
    context = SimpleNamespace(directory=tmp_path)
    journey = InstalledJourney(context, Mock(), plan)
    journey.trace_token = 'a' * 32
    journey.ui = SimpleNamespace(poll_trace=Mock())
    guard = Mock()
    journey.step(guard)
    journey.ui.poll_trace.assert_called_once_with()
    journey.retain_trace_sample('a' * 32, 0, {'state': 'public'})
    with pytest.raises(FileExistsError):
        journey.retain_trace_sample('a' * 32, 0, {'state': 'replacement'})
    assert json.loads((tmp_path / ('trace-' + 'a' * 32 + '-000.json')).read_text()) == {'state': 'public'}
    journey.ui.poll_trace.side_effect = EvidenceError('ui:trace-terminal')
    with pytest.raises(EvidenceError, match='trace-terminal'):
        journey.step(guard)
    with pytest.raises(EvidenceError, match='previous-failure'):
        journey.step(guard)


def test_transition_selector_preserves_guarded_envelope(monkeypatch):
    import check_e2e_trace
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_trace, 'smoke', run)
    assert check_e2e_trace.main() == 0
    assert run.call_args.kwargs['trace_transition'] is True
    assert run.call_args.kwargs['provision_credentials'] is True
    with pytest.raises(CommandError, match='trace-prerequisites'):
        smoke.main(trace_transition=True, trace_stable_state=True)


@pytest.mark.parametrize('fault', ['binding', 'input', 'missing', 'nested', 'action'])
def test_transition_plan_refuses_unbound_or_unsafe_compositions(fault):
    from dataclasses import replace
    from trace_transition import PLAN as plan
    tags = dict(plan.screen_tags)
    bindings = dict(plan.trace_bindings)
    actions = {}
    if fault == 'binding':
        bindings['trace-first-start'] = 'reply-first'
    elif fault == 'missing':
        del tags['first-selected']
    elif fault == 'input':
        tags['first-selected'] = 'ui:feedback-close'
    elif fault == 'nested':
        tags['first-selected'] = 'ui:feedback-trace-start'
    else:
        actions['first-selected'] = 'extra-input'
    with pytest.raises(EvidenceError, match='trace-plan'):
        replace(plan, screen_tags=tags, trace_bindings=bindings, stage_actions=actions)


@pytest.mark.parametrize('fault', ['', 'trace-first-start', 'first-selected', 'first-read',
                                  'trace-first-finish', 'trace-wrong-entry', 'trace-second-start'])
@pytest.mark.parametrize('composition', [False, True])
def test_transition_worker_composes_text_and_stops_before_followup_input(fault, composition):
    from tests.support.perl import run_perl
    from trace_transition import PLAN as plan
    if composition:
        from compose_observation import PLAN as plan
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages);
our $fault = shift @ARGV;
our $run = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, 'key:' . $_[0]; }
sub type_string { push @main::events, 'type:' . $_[0]; }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    my $call = onpc_feedback_states->can($run);
    $call->(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0], ui_focused => JSON::PP::true};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault, 'run_composition' if composition else 'run_transition').stdout)
    stages = list(plan.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')
    if not fault:
        assert result['events'].count('type:Synthetic feedback first') == 2
        if composition:
            assert result['events'].count('key:backspace') == 2


def test_clear_trace_refuses_empty_entry_and_blocks_input(monkeypatch):
    reader, _, _ = trace_reader(monkeypatch)
    with pytest.raises(EvidenceError):
        reader.start_trace('body-clear')
    with pytest.raises(EvidenceError, match='trace-intervening-operation'):
        reader.observe('text-body-clear-focus')
    assert reader.trace_failed


def test_composition_selector_uses_guarded_envelope(monkeypatch):
    import check_e2e_compose_observation_around_one_caller_input as check
    run = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == 0
    assert run.call_args.kwargs['compose_observation'] is True


@pytest.mark.parametrize('uncertain', [False, True])
def test_observed_text_independent_caller_never_replays_uncertain_input(uncertain):
    from tests.support.perl import run_perl
    from journey_blocks import observed_text
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages);
our $uncertain = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key {
    push @main::events, $_[0];
    die 'uncertain input' if $main::uncertain && $_[0] eq 'backspace';
}
package main;
require onpc_feedback_states;
my $journey = onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {
    push @stages, $_[0];
    return {observed => $_[0], ui_focused => JSON::PP::true};
});
my $ok = eval { onpc_feedback_states::observed_text($journey, 'renamed', 'body-clear'); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', '1' if uncertain else '0').stdout)
    expected = list(observed_text('renamed', 'body-clear'))
    assert result['stages'] == (expected[:3] if uncertain else expected)
    assert result['events'] == ['ctrl-a', 'backspace']
    assert bool(result['ok']) is (not uncertain)


def trace_reader(monkeypatch):
    import ui_observations
    ui, _, _, _ = feedback_ui()
    value = ui.feedback_snapshot(states=True)
    reply = {'operation': 'feedback-state-empty', 'outcome': 'passed', 'interface': 'AT-SPI',
             'feedback_state': value, 'boot_sha256': 'b' * 64}
    reader = ui_observations.UiObservations(Mock())
    reader.boot_guard = 'b' * 64
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    clock = Mock(side_effect=range(100))
    monkeypatch.setattr(reader, '_trace_clock', clock)
    return reader, reply, clock


def test_stable_trace_decodes_samples_and_consumes_explicit_token(monkeypatch):
    reader, reply, _ = trace_reader(monkeypatch)
    ready = reader.start_trace()
    assert ready['ready'] is True and len(ready['token']) == 32
    assert reader.call.call_count == 1
    result = reader.finish_trace(ready['token'])
    assert result['terminal'] == 'three-unchanged-samples'
    assert [sample['state'] for sample in result['samples']] == [reply['feedback_state']] * 3
    assert [sample['elapsed_ms'] for sample in result['samples']] == [1000, 3000, 5000]
    assert reader.trace is None and reader.call.call_count == 3
    with pytest.raises(EvidenceError, match='trace-token'):
        reader.finish_trace(ready['token'])
    assert reader.call.call_count == 3


@pytest.mark.parametrize('fault', ['duplicate', 'missing', 'foreign', 'stale', 'input',
                                  'changed', 'boot', 'malformed', 'wrong-entry'])
def test_stable_trace_refuses_and_latches_without_replay(monkeypatch, fault):
    reader, reply, clock = trace_reader(monkeypatch)
    if fault == 'wrong-entry':
        reader.call.side_effect = accessible_ui.UiError('ui:feedback-entry')
        with pytest.raises(accessible_ui.UiError, match='feedback-entry'):
            reader.start_trace()
    elif fault == 'missing':
        with pytest.raises(EvidenceError, match='trace-token'):
            reader.finish_trace(None)
    else:
        ready = reader.start_trace()
        if fault == 'stale':
            clock.side_effect = None
            clock.return_value = 61
        if fault == 'changed':
            reply['feedback_state']['send_enabled'] = False
        if fault == 'boot':
            reply['boot_sha256'] = 'c' * 64
        if fault == 'malformed':
            reply['feedback_state']['private'] = 'must refuse'
        reader.call.return_value = (json.dumps(reply).encode(), [])
        with pytest.raises(EvidenceError):
            if fault == 'duplicate':
                reader.start_trace()
            elif fault == 'input':
                reader.observe('feedback-close')
            else:
                reader.finish_trace('foreign' if fault == 'foreign' else ready['token'])
    calls = reader.call.call_count
    assert reader.trace_failed and reader.trace is None
    with pytest.raises(EvidenceError, match='trace-previous-failure'):
        reader.start_trace()
    assert reader.call.call_count == calls


def test_trace_selector_preserves_guarded_envelope(monkeypatch):
    import check_e2e_trace_stable_state as check_trace
    run = Mock(return_value=0)
    monkeypatch.setattr(check_trace, 'smoke', run)
    assert check_trace.main() == 0
    assert run.call_args.kwargs['trace_stable_state'] is True
    assert run.call_args.kwargs['provision_credentials'] is True
    with pytest.raises(CommandError, match='trace-prerequisites'):
        smoke.main(trace_stable_state=True, feedback_states=True)


def test_stable_trace_new_entry_cannot_consume_prior_token(monkeypatch):
    reader, _, _ = trace_reader(monkeypatch)
    old = reader.start_trace()['token']
    reader.finish_trace(old)
    new = reader.start_trace()['token']
    assert new != old
    with pytest.raises(EvidenceError, match='trace-token'):
        reader.finish_trace(old)
    assert reader.call.call_count == 4


@pytest.mark.parametrize('tags,actions', [
    ({'start': 'ui:feedback-trace-start'}, {}),
    ({'end': 'ui:feedback-trace-finish'}, {}),
    ({'start': 'ui:feedback-trace-start', 'input': 'ui:feedback-close',
      'end': 'ui:feedback-trace-finish'}, {}),
    ({'start': 'ui:feedback-trace-start', 'end': 'ui:feedback-trace-finish'}, {'start': 'input'}),
])
def test_stable_trace_plan_refuses_missing_pairs_and_intervening_input(tags, actions):
    from installed_journey import JourneyPlan
    with pytest.raises(EvidenceError, match='trace-plan'):
        JourneyPlan(prefix='test', worker_mode='trace', screen_tags=tags,
                    phases={}, stage_actions=actions)


@pytest.mark.parametrize('fault', ['', 'trace-first-start', 'trace-first-finish',
                                  'feedback-state-wrong-entry', 'trace-second-start'])
def test_trace_worker_uses_shared_sequence_and_stops_on_refusal(fault):
    from tests.support.perl import run_perl
    from trace_stable_state import PLAN as trace_plan
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages);
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { die 'unexpected input'; }
sub type_string { die 'unexpected input'; }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_states::run_trace(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    stages = list(trace_plan.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')


@pytest.mark.parametrize('fault', ['', 'text-body-first-selected', 'format-home',
                                  'text-scalar-body-smoke-caret'])
def test_host_gui_blocks_share_worker_input_and_stop_at_refused_observation(monkeypatch, fault):
    from tests.support import gui_blocks
    events = []
    ui = Mock()
    def observe(stage, version):
        events.append(('observe', stage))
        if stage == fault:
            raise ValueError('refused')
        return {'stage': stage}
    ui.run.side_effect = observe
    monkeypatch.setattr(gui_blocks.keyboard, 'key_combo',
        lambda _ui, identity, key, **_: events.append(('key', identity, key)))
    monkeypatch.setattr(gui_blocks.keyboard, 'repeat_cursor',
        lambda _ui, identity, key, count: events.extend([('key', identity, key)] * count))
    monkeypatch.setattr(gui_blocks.keyboard, 'type_text',
        lambda _ui, identity, value, **_: events.append(('text', identity, value)))
    def execute():
        gui_blocks.run_block(ui, 'replace', 'body-first')
        gui_blocks.run_block(ui, 'bold')
        gui_blocks.run_block(ui, 'scalar', 'body-smoke')
    if fault:
        with pytest.raises(ValueError, match='refused'):
            execute()
        assert events[-1] == ('observe', fault)
    else:
        execute()
        assert ('text', 'feedback-editor-input', 'Synthetic feedback first') in events
        assert events.count(('key', 'feedback-editor-input', '<Shift>Right')) == 9
        assert ('text', 'feedback-editor-input', '1f600') in events
        assert events[-1] == ('observe', 'text-scalar-body-smoke-read')


@pytest.mark.parametrize('fault', ['', 'filter-access-rule-3-read',
                                  'filter-access-rule-3-closed', 'transient-closed'])
def test_host_filter_escape_uses_result_polling_and_keeps_closure_gate(monkeypatch, fault):
    from tests.support import gui_blocks
    events = []
    ui = ui_for(Node())
    ui.timeout = 1
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda _: None)
    def observe(stage, version):
        events.append(('observe', stage))
        if stage == fault:
            raise ValueError('refused')
        if (fault == 'transient-closed' and stage.endswith('-closed')
                and events.count(('observe', stage)) == 1):
            raise accessible_ui.UiError('ui:incomplete-tree')
        return {'stage': stage}
    ui.run = observe
    bounded_wait = ui.wait
    def wait(predicate, code, **options):
        events.append(('wait', code, options))
        return bounded_wait(predicate, code, **options)
    ui.wait = wait
    monkeypatch.setattr(gui_blocks.keyboard, 'key_combo',
        lambda _ui, identity, key, **options: events.append(('key', identity, key, options)))
    def execute():
        gui_blocks.run_block(ui, 'filter', 'access-rule', '3', 'filter-access-rule-3')
        events.append(('next-input',))
    if fault.startswith('filter-'):
        with pytest.raises(ValueError, match='refused'):
            execute()
        assert events[-1] == ('observe', fault)
        assert ('next-input',) not in events
    else:
        execute()
        assert events[-2:] == [('observe', 'filter-access-rule-3-closed'), ('next-input',)]
    keys = [event for event in events if event[0] == 'key']
    assert keys == ([] if fault.endswith('-read') else [
        ('key', 'parent-window', 'Escape', {'state': 'active', 'post_delay': 0.05})])
    assert [event for event in events if event[0] == 'wait'] == (
        [] if fault.endswith('-read') else [
            ('wait', 'host-filter-closed', {'prompt_in_predicate': True})])
    assert events[:5] == [('observe', 'filter-access-rule-3-' + action)
                         for action in ('open', 'allowed', 'conditional', 'permanent', 'read')]
    assert events.count(('observe', 'filter-access-rule-3-closed')) == (
        0 if fault.endswith('-read') else 2 if fault == 'transient-closed' else 1)


@pytest.mark.parametrize('fragment', ['window', 'privacy'])
@pytest.mark.parametrize('prefix', ['', 'independent-'])
def test_review_fragments_match_declarations_and_stop_before_later_input(fragment, prefix):
    from tests.support.perl import run_perl
    from window_switch import window_switch_entry
    from feedback_composition import privacy_review
    stages = list(window_switch_entry(prefix) if fragment == 'window'
                  else privacy_review(prefix=prefix))
    script = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, ['key', @_]; }
package main;
require onpc_feedback_read;
require onpc_feedback_privacy;
my ($fragment, $prefix, $fault, @stages) = @ARGV;
my $journey = onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {
    push @events, ['stage', $_[0]];
    die 'proof refused' if $_[0] eq $fault;
    return {observed => $_[0]};
});
$journey->declare_invocations(\@stages) if length $prefix;
my $ok = eval {
    if ($fragment eq 'window') { onpc_feedback_read::prepare_window_switch($journey, $prefix); }
    else { onpc_feedback_privacy::review_privacy($journey, $prefix); }
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => "$@", events => \@events});
'''
    success = json.loads(run_perl(script, fragment, prefix, '', *stages).stdout)
    assert success['ok'], success['error']
    assert [event[1] for event in success['events'] if event[0] == 'stage'] == stages
    assert [event for event in success['events'] if event[0] == 'key'] == [
        ['key', 'alt-tab' if fragment == 'window' else 'alt-f4']]
    for stage in stages:
        result = json.loads(run_perl(script, fragment, prefix, stage, *stages).stdout)
        assert not result['ok'] and 'proof refused' in result['error']
        assert result['events'] == success['events'][:success['events'].index(['stage', stage]) + 1]
    result = json.loads(run_perl(script, fragment, 'bad prefix', '', *stages).stdout)
    assert not result['ok'] and not result['events']


def test_window_history_uses_declared_operations_for_renamed_invocations():
    from installed_journey import JourneyPlan
    from window_switch import WindowSwitchJourney, window_switch_entry
    plan = JourneyPlan(prefix='consumer', worker_mode='consumer', phases={},
                       screen_tags=window_switch_entry('independent-'))
    journey = WindowSwitchJourney(SimpleNamespace(), Mock(), plan)
    parent = {'binding': 'parent', 'pid': 42, 'endpoint': [':1.42', '/window'], 'active': True}
    journey.check_settings('independent-switch-parent-before', {'ui': {'window': dict(parent)}})
    journey.check_settings('independent-switch-parent-ready', {'ui': {'window': {**parent, 'active': False}}})
    journey.check_settings('independent-switch-parent', {'ui': {'window': dict(parent)}})
    with pytest.raises(EvidenceError, match='window-or-draft-changed'):
        journey.check_settings('independent-switch-parent', {'ui': {'window': {**parent, 'pid': 43}}})


def test_review_fragments_reject_unregistered_profiles_and_invalid_invocations():
    from feedback_composition import privacy_review
    from window_switch import window_switch_entry
    for prefix in ('bad prefix', 'missing-dash', None):
        with pytest.raises(EvidenceError):
            privacy_review(prefix=prefix)
        with pytest.raises(EvidenceError):
            window_switch_entry(prefix)
    with pytest.raises(EvidenceError, match='privacy-profile'):
        privacy_review(profile='unknown')
    assert list(privacy_review(profile='formatted-file').values()) == [
        'ui:draft-feedback-privacy-open', 'ui:draft-feedback-privacy-returned']


@pytest.mark.parametrize('flow', ['draft', 'attachments'])
def test_draft_actual_worker_sequence_and_every_refusal(monkeypatch, flow):
    from tests.support.perl import run_perl
    from tests.support.perl import ALLOWANCE_WORKER
    from parent_feedback_draft import PLAN as DRAFT_PLAN
    from parent_feedback_attachments import PLAN as FILE_PLAN
    PLAN = DRAFT_PLAN if flow == 'draft' else FILE_PLAN
    from ui_observations import OPERATION_LABELS
    script = ALLOWANCE_WORKER.replace('onpc_set_allowance', 'onpc_feedback_privacy')
    script = script.replace('::run($exchange)', "::run($exchange, '" + flow + "')")
    script = script.replace('sub record_info { }',
                            "sub record_info { }\nsub type_string { push @main::events, ['text', @_]; }")
    monkeypatch.setenv('ONPC_TEST_REFUSE', '')
    success = json.loads(run_perl(script).stdout)
    assert success['ok'], success['error']
    stages = list(PLAN.screen_tags)
    assert [event[1] for event in success['events'] if event[0] == 'stage'] == stages
    assert all(tag.removeprefix('ui:') in OPERATION_LABELS for tag in PLAN.screen_tags.values())
    assert sum(event[:2] == ['key', 'alt-f4'] for event in success['events']) == (4 if flow == 'draft' else 0)
    assert sum(event[:2] == ['key', 'alt-tab'] for event in success['events']) == (3 if flow == 'draft' else 0)
    assert not any('send' in operation for operation in PLAN.screen_tags.values())
    for stage in stages:
        monkeypatch.setenv('ONPC_TEST_REFUSE', stage)
        result = json.loads(run_perl(script).stdout)
        assert not result['ok'] and 'fixture:refused' in result['error']
        boundary = success['events'].index(['stage', stage])
        assert result['events'] == success['events'][:boundary + 1]


@pytest.mark.parametrize('flow', ['draft', 'attachments'])
def test_draft_recorder_reaches_real_controller_and_retains_owned_actions(tmp_path, flow):
    import parent_feedback_draft
    import parent_feedback_attachments
    from feedback_composition import FeedbackDraftJourney
    from attachment_composition import AttachmentJourney
    module = parent_feedback_draft if flow == 'draft' else parent_feedback_attachments
    execute, PLAN, ACTIONS = module.execute, module.PLAN, module.ACTIONS
    recorder = MagicMock(assertion=Mock())
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
                              verified=SimpleNamespace(inputs={}), guestfs=Mock(),
                              commands=Mock(), recorder=recorder)
    def worker(**options):
        controller = options['guarded_observe'].__self__
        assert type(controller) is (FeedbackDraftJourney if flow == 'draft' else AttachmentJourney)
        assert controller.plan is PLAN and controller.actions == ACTIONS
        assert options['validate'].__self__ is controller
        raise EvidenceError('synthetic-worker-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        execute(recorder, context)
    context.run_worker.assert_called_once()
    recorder.assertion.assert_not_called()


@pytest.mark.parametrize('operation', sorted(accessible_ui.FILE_REVIEW_OPERATIONS))
def test_file_review_decoder_and_preservation(operation):
    from attachment_composition import AttachmentJourney, compare_file_draft
    from installed_journey import JourneyPlan
    PLAN = JourneyPlan(prefix='file-library', worker_mode='fixture', phases={}, screen_tags={
        stage: 'ui:files-' + stage for stage in ('feedback-draft', 'feedback-draft-reopen')})
    from ui_observations import UiObservations
    draft = {'draft': 'attachment-file', 'attachments': ['Synthetic note.txt'],
        'collection': 'ready', 'validation': 'none', 'controls': 'ready',
        'items': [['Synthetic note.txt', '34 bytes']], 'include_logs': False}
    compare_file_draft(draft)
    value = ({'window': {'binding': 'feedback', 'pid': 42, 'endpoint': [':1.42', '/window'],
                        'active': True, 'feedback': draft}} if 'switch-' in operation else
             {} if operation.endswith('privacy-open') else {'file_draft': draft})
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', **value}
    transport = Mock()
    observer = UiObservations(transport)
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert observer.observe(operation) == result
    journey = AttachmentJourney(SimpleNamespace(), Mock(), PLAN)
    journey.check_settings('feedback-draft', {'ui': {'file_draft': draft}})
    journey.check_settings('feedback-draft-reopen', {'ui': {'file_draft': dict(draft)}})
    draft['items'] = [['Synthetic note.txt', '26 bytes']]
    if value:
        observer.call = Mock(return_value=(json.dumps(result).encode(), []))
        with pytest.raises(EvidenceError):
            observer.observe(operation)
    with pytest.raises(EvidenceError, match='preserved-draft'):
        journey.check_settings('feedback-draft-reopen', {'ui': {'file_draft': draft}})


def test_source_snapshot_and_readd_compare_independent_public_results():
    from attachment_composition import AttachmentJourney
    from installed_journey import JourneyPlan
    plan = JourneyPlan(prefix='source-library', worker_mode='fixture', phases={}, screen_tags={
        stage: 'ui:' + stage for stage in accessible_ui.BOUNDARY_OPERATIONS})
    journey = AttachmentJourney(SimpleNamespace(), Mock(), plan)
    def observation(operation):
        return {'ui': {'boundary': accessible_ui.boundary_expected(operation)}}
    for stage in ('boundary-single-before', 'boundary-single-preserved',
                  'boundary-source-unchanged', 'boundary-changed-before', 'boundary-changed-preserved'):
        journey.check_settings(stage, observation(stage))
    changed = observation('boundary-source-unchanged')
    changed['ui']['boundary']['items'][0][1] = '34 bytes'
    with pytest.raises(EvidenceError, match='source-result'):
        journey.check_settings('boundary-source-unchanged', changed)
    stale = observation('boundary-changed-preserved')
    stale['ui']['boundary']['items'][0][1] = '26 bytes'
    with pytest.raises(EvidenceError, match='source-result'):
        journey.check_settings('boundary-changed-preserved', stale)


@pytest.mark.parametrize('fault', ['', 'text', 'file', 'size', 'logs', 'status'])
def test_changed_file_draft_public_snapshot_requires_exact_result(fault):
    ui, dialog, rows = boundary_ui('changed')
    controls = {node.identity: node for node in dialog.children}
    for binding in ('body-first', 'reply-first'):
        identity, value = accessible_ui.TEXT_VALUES[binding]
        controls[identity].text.value = value
        controls[identity].text.count = len(value)
    ui.api.Text.get_text = Mock(side_effect=lambda text, start, end: text.value[start:end])
    if fault == 'text': controls['feedback-reply-email'].text.value = 'wrong'
    if fault == 'file': dialog.children.remove(rows[0])
    if fault == 'size': rows[0].children[0].name = '26 bytes'
    if fault == 'logs': controls['feedback-logs-row'].name = 'diagnostic-logs.zip'
    if fault == 'status': controls['feedback-status'].name = 'Reading attachments…'
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.feedback_snapshot('attachment-file')
    else:
        from attachment_composition import compare_file_draft
        value = ui.feedback_snapshot('attachment-file')
        value.pop('status')
        compare_file_draft(value)


@pytest.mark.parametrize('batch', ['name180', 'name181', 'hidden', 'mixed', 'single', 'changed'])
def test_new_boundary_handoff_keeps_exact_entry_and_source_profile(monkeypatch, batch):
    ui, _, _ = boundary_ui(accessible_ui.BOUNDARY_BATCHES[batch][0])
    operation = Mock(return_value={'checked': 'chooser-open', 'provider': {'fixture': True}})
    monkeypatch.setattr(ui, 'chooser_operation', operation)
    assert ui.boundary_operation('boundary-' + batch + '-open') == {
        'checked': 'boundary-' + batch + '-open', 'provider': {'fixture': True}}
    operation.assert_called_once_with('chooser-open',
        profile='single' if batch == 'changed' else batch, boundary=batch)
    ui, _, _ = boundary_ui(accessible_ui.BOUNDARY_BATCHES[batch][0])
    ui.activate_id = Mock(side_effect=RuntimeError('input reached'))
    ui.chooser_snapshot = Mock(return_value=True)
    with pytest.raises(RuntimeError, match='input reached'):
        ui.chooser_operation('chooser-open', profile='single' if batch == 'changed' else batch,
                             boundary=batch)
    ui.activate_id.assert_called_once_with('feedback-add-files')
    ui, _, _ = boundary_ui('empty')
    ui.activate_id = Mock()
    with pytest.raises(accessible_ui.UiError):
        ui.chooser_operation('chooser-open', profile='single' if batch == 'changed' else batch,
                             boundary=batch)
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('reset', [False, True])
@pytest.mark.parametrize('fault', ['', 'file', 'format', 'reply', 'extra'])
def test_formatted_draft_decoder_and_independent_prior_comparison(tmp_path, reset, fault):
    from attachment_composition import formatted_draft_expected
    from feedback_composition import FeedbackDraftJourney
    from parent_feedback_draft import PLAN, ACTIONS
    from ui_observations import UiObservations
    operation = 'draft-feedback-reopen' if reset else 'draft-feedback-draft-reopen'
    value = formatted_draft_expected(reset=reset)
    if fault == 'file': value['items'] = [['Other.txt', '26 bytes']]
    if fault == 'format': value['formats']['link'] = 'https://example.com/wrong'
    if fault == 'reply': value['draft'] = 'states-no-reply'
    if fault == 'extra': value['private'] = 'refuse'
    reply = {'operation': operation, 'interface': 'AT-SPI', 'outcome': 'passed', 'draft_state': value}
    reader = UiObservations(Mock())
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    if fault:
        with pytest.raises(EvidenceError, match='formatted-draft'):
            reader.observe(operation)
        return
    assert reader.observe(operation) == reply
    journey = FeedbackDraftJourney(SimpleNamespace(directory=tmp_path), lambda *_: None, PLAN, actions=ACTIONS)
    stage = 'feedback-reopen' if reset else 'feedback-draft-reopen'
    with pytest.raises(EvidenceError, match='missing-prior-draft'):
        journey.check_settings(stage, {'ui': reply})
    journey.check_settings('feedback-draft', {'ui': {'draft_state': formatted_draft_expected()}})
    journey.check_settings(stage, {'ui': reply})


@pytest.mark.parametrize('fault', ['', 'file', 'text', 'format', 'status'])
def test_formatted_file_public_snapshot_requires_exact_fields_metadata_and_formats(monkeypatch, fault):
    ui, dialog, rows = attachment_ui()
    dialog.children.remove(rows[0])
    controls = {node.identity: node for node in dialog.children}
    for binding in ('body-smoke', 'reply-first'):
        identity, value = accessible_ui.TEXT_VALUES[binding]
        controls[identity].text.value = value
        controls[identity].text.count = len(value)
    ui.api.Text.get_text = Mock(side_effect=lambda text, start, end: text.value[start:end])
    controls['feedback-status'].name = '1 file attachment ready.'
    from attachment_composition import formatted_draft_expected
    expected = formatted_draft_expected()['formats']
    read = Mock(return_value=expected)
    monkeypatch.setattr(ui, 'basic_feedback_formatting', read)
    if fault == 'text': controls['feedback-reply-email'].text.value = 'wrong'
    if fault == 'status': controls['feedback-status'].name = 'Attach at most 5 files.'
    if fault == 'format': read.side_effect = accessible_ui.UiError('ui:formats-result')
    if fault == 'file': dialog.children.append(Node(identity='feedback-attachment-unknown'))
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.feedback_snapshot('formatted-file')
    else:
        value = ui.feedback_snapshot('formatted-file')
        assert value['items'] == [['Synthetic note.txt', '26 bytes']]
        assert value['formats'] == expected


def test_formatted_window_decoder_preserves_endpoint_and_complete_draft(tmp_path):
    import copy
    from attachment_composition import formatted_draft_expected
    from feedback_composition import FeedbackDraftJourney
    from parent_feedback_draft import PLAN, ACTIONS
    from ui_observations import UiObservations
    value = {'binding': 'feedback', 'pid': 123, 'endpoint': [':1.123', '/org/a11y/atspi/accessible/42'],
             'active': True, 'feedback': formatted_draft_expected()}
    reply = {'operation': 'draft-switch-feedback', 'outcome': 'passed', 'interface': 'AT-SPI', 'window': value}
    reader = UiObservations(Mock())
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    assert reader.observe('draft-switch-feedback') == reply
    journey = FeedbackDraftJourney(SimpleNamespace(directory=tmp_path), Mock(), PLAN, actions=ACTIONS)
    journey.check_settings('switch-draft-before', {'ui': copy.deepcopy(reply)})
    journey.check_settings('switch-feedback', {'ui': reply})
    value['endpoint'][1] += '1'
    with pytest.raises(EvidenceError, match='window-or-draft-changed'):
        journey.check_settings('switch-feedback', {'ui': reply})
    value['feedback']['items'] = []
    reader.call.return_value = (json.dumps(reply).encode(), [])
    with pytest.raises(EvidenceError, match='formatted-draft'):
        reader.observe('draft-switch-feedback')


@pytest.mark.parametrize('fault', ['', 'blocks', 'link', 'attributes', 'body'])
def test_empty_draft_reset_observes_formatting_before_any_input(monkeypatch, fault):
    ui, _, _, controls = feedback_ui()
    root = controls['feedback-editor-input']
    root.text.get_attribute_run = Mock(return_value=({'weight': '700' if fault == 'attributes' else '400',
        'style': 'normal', 'underline': 'none', 'strikethrough': 'false'}, 0, 1))
    monkeypatch.setattr(accessible_ui.block_semantics, 'read_blocks', Mock(return_value=['heading'] if fault == 'blocks' else []))
    monkeypatch.setattr(accessible_ui.feedback_formats, 'read_links', Mock(return_value='link' if fault == 'link' else None))
    if fault == 'body': root.text.count = 12
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.feedback_draft_operation('draft-feedback-reread')
    else:
        assert ui.feedback_draft_operation('draft-feedback-reread')['draft_state']['items'] == []
    for node in controls.values():
        node.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'uri', 'text', 'duplicate', 'missing-interface',
                                  'invalid', 'incomplete', 'cycle', 'extent'])
def test_formats_link_reader_requires_exact_text_and_public_destination(fault):
    import feedback_formats as formats
    link = Mock()
    link.get_role_name.return_value = 'link'
    link.get_text_iface.return_value = Mock(get_character_count=Mock(return_value=5),
                                          get_text=Mock(return_value='Plain'))
    link.get_hyperlink.return_value = Mock(get_n_anchors=Mock(return_value=1),
        is_valid=Mock(return_value=True), get_uri=Mock(return_value=formats.LINK),
        get_start_index=Mock(return_value=0), get_end_index=Mock(return_value=1))
    link.get_child_count.return_value = 0
    children = [link]
    root = Mock(get_role_name=Mock(return_value='section'))
    if fault == 'uri':
        link.get_hyperlink.return_value.get_uri.return_value = 'https://example.com/wrong'
    elif fault == 'text':
        link.get_text_iface.return_value.get_text.return_value = 'Other'
    elif fault == 'duplicate':
        children.append(link)
    elif fault == 'missing-interface':
        link.get_hyperlink.return_value = None
    elif fault == 'invalid':
        link.get_hyperlink.return_value.is_valid.return_value = False
    elif fault == 'extent':
        link.get_hyperlink.return_value.get_end_index.return_value = 5
    elif fault == 'incomplete':
        children.append(None)
    elif fault == 'cycle':
        children.append(root)
    root.get_child_count.return_value = len(children)
    root.get_child_at_index.side_effect = lambda index: children[index]
    if fault:
        with pytest.raises(accessible_ui.UiError):
            formats.read_links(root, accessible_ui.require)
    else:
        assert formats.read_links(root, accessible_ui.require) == formats.LINK


@pytest.mark.parametrize('fault', ['', 'strike', 'normal', 'range', 'partial', 'link-text'])
def test_linked_attributes_use_independent_link_text_and_embedded_width(fault):
    import feedback_formats as formats
    normal = {'weight': '400', 'style': 'normal', 'underline': 'none', 'strikethrough': 'false'}
    styled = {'weight': '700', 'style': 'italic', 'underline': 'single', 'strikethrough': 'true'}
    def run(offset, defaults):
        if offset < formats.START:
            return normal, 0, formats.START
        return ({**normal, 'weight': '700'} if fault == 'normal' else normal,
                formats.START + 1, len(formats.blocks.BODY) - 4)
    text = Mock(get_character_count=Mock(return_value=len(formats.blocks.BODY)),
                get_attribute_run=Mock(side_effect=run))
    link_text = Mock(get_character_count=Mock(return_value=5),
                     get_text=Mock(return_value='Other' if fault == 'link-text' else 'Plain'),
                     get_attribute_run=Mock(return_value=(
                         {**styled, 'strikethrough': 'false'} if fault == 'strike' else styled,
                         1 if fault == 'partial' else 0, 4 if fault == 'range' else 5)))
    link = Mock(get_role_name=Mock(return_value='link'),
                get_attributes=Mock(return_value={}), get_text_iface=Mock(return_value=link_text),
                get_child_count=Mock(return_value=0))
    link.get_hyperlink.return_value = Mock(get_n_anchors=Mock(return_value=1),
        is_valid=Mock(return_value=True), get_uri=Mock(return_value=formats.LINK),
        get_start_index=Mock(return_value=0), get_end_index=Mock(return_value=1))
    root = Mock(get_role_name=Mock(return_value='entry'), get_attributes=Mock(return_value={}),
                get_text_iface=Mock(return_value=text), get_child_count=Mock(return_value=1),
                get_child_at_index=Mock(return_value=link))
    text.get_text.return_value = formats.blocks.BODY
    ui = Mock(text_recipient=Mock(return_value=root))
    if fault:
        with pytest.raises(accessible_ui.UiError):
            formats.read(ui, accessible_ui.require, 'linked-kept-reopen')
    else:
        assert formats.read(ui, accessible_ui.require, 'linked-kept-reopen') == formats.expected('linked-kept-reopen')
        link_text.get_attribute_run.assert_called_once_with(2, True)
        # The suffix query uses the public embedded width, not flattened 94.
        assert text.get_attribute_run.call_args_list[0].args == (90, True)
        ui.api.Text.get_n_selections.return_value = 1
        ui.api.Text.get_selection.return_value = SimpleNamespace(start_offset=0, end_offset=94)
        formats.operate(ui, 'formats-clear-selected', accessible_ui.require, accessible_ui.UiError)
        ui.activate_id.assert_called_once_with('feedback-format-clear')
        ui.activate_id.reset_mock()
        ui.api.Text.get_selection.return_value.end_offset = 98
        with pytest.raises(accessible_ui.UiError, match='ui:formats-selection'):
            formats.operate(ui, 'formats-clear-selected', accessible_ui.require, accessible_ui.UiError)
        ui.activate_id.assert_not_called()


@pytest.mark.parametrize('linked', [False, True])
@pytest.mark.parametrize('fault', ['', 'formats-bold-home', 'formats-link-target',
                                  'formats-link-save', 'formats-link-read',
                                  'formats-kept-wrong-entry', 'formats-clear-selected',
                                  'formats-cleared-reopen'])
def test_complete_format_worker_uses_shared_sequence_and_stops_on_refusal(fault, linked):
    from feedback_formats import STAGES, LINK_STAGES, START, END, LINK, blocks
    if linked:
        fault = fault.replace('formats-', 'linked-')
        if fault and fault not in LINK_STAGES:
            fault = 'linked-kept-reopen'
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV; my $linked = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type:' . $_[0]; }
package main;
require onpc_format;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    my $worker = $linked ? \&onpc_format::run_links : \&onpc_format::run_formats;
    $worker->(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault, '1' if linked else '0').stdout)
    stages = ['parent-selected', *(LINK_STAGES if linked else STAGES)]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')
    if not fault:
        events = [event.replace('linked-', 'formats-') for event in result['events']]
        for kind in ('bold', 'italic', 'underline', 'strike', 'link', *(() if linked else ('clear',))):
            keys = events[events.index(f'formats-{kind}-home') + 1:
                          events.index(f'formats-{kind}-selected')]
            assert keys == (['ctrl-shift-end'] if kind == 'clear' else
                            ['ctrl-end'] + ['left'] * (len(blocks.BODY) - START)
                            + ['shift-right'] * (END - START))
        assert events[events.index('formats-link-target') + 1] == 'type:' + LINK


@pytest.mark.parametrize('linked', [False, True])
def test_formats_decoder_independent_recorder_and_shipped_imports(tmp_path, linked):
    import feedback_formats as formats
    from feedback_formats_qualification import PLAN, FeedbackFormatsJourney
    if linked:
        from feedback_formats_qualification import LINK_PLAN as PLAN, FeedbackLinkJourney as FeedbackFormatsJourney
    prefix = 'linked' if linked else 'formats'
    from installed_journey import record_installed_journey
    from ui_observations import UiObservations
    reader = UiObservations(Mock())
    reply = {'operation': prefix + '-kept-reopen', 'outcome': 'passed', 'interface': 'AT-SPI',
             'formats': formats.expected(prefix + '-kept-reopen')}
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    assert reader.observe(prefix + '-kept-reopen') == reply
    import subprocess
    import sys
    subprocess.run([sys.executable, '-I', '-c',
                    "import sys; ns={'__name__':'observer'}; "
                    "exec(compile(sys.stdin.read(), 'observer.py', 'exec'), ns); "
                    "assert 'formats-cleared-reopen' in ns['OPERATIONS']"],
                   input=reader.call.call_args.kwargs['input'], check=True,
                   capture_output=True, timeout=20)
    journey = FeedbackFormatsJourney(SimpleNamespace(directory=tmp_path), Mock())
    with pytest.raises(EvidenceError, match='formats:independent-entry'):
        journey.check_settings(prefix + '-kept-reopen', {'ui': reply})
    journey.check_settings(prefix + '-link-read', {'ui': reply})
    journey.check_settings(prefix + '-kept-reopen', {'ui': reply})
    reply['formats']['link'] = None
    reader.call.return_value = (json.dumps(reply).encode(), [])
    with pytest.raises(EvidenceError, match='ui:formats-response'):
        reader.observe(prefix + '-kept-reopen')
    recorder = MagicMock(assertion=Mock())
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
                              verified=SimpleNamespace(inputs={}), guestfs=Mock(),
                              commands=Mock(), recorder=recorder)
    def worker(**options):
        controller = options['guarded_observe'].__self__
        assert type(controller) is FeedbackFormatsJourney
        assert controller.plan is PLAN and controller.actions == {}
        raise EvidenceError('synthetic-worker-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        record_installed_journey(recorder, context, PLAN, actions={},
                                 journey_type=FeedbackFormatsJourney)
    context.run_worker.assert_called_once()
    recorder.assertion.assert_not_called()


def test_formats_selector_preserves_guarded_envelope(monkeypatch):
    import check_e2e_feedback_formats as check_formats
    run = Mock(return_value=0)
    monkeypatch.setattr(check_formats, 'smoke', run)
    assert check_formats.main() == 0
    assert run.call_args.kwargs['feedback_formats'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_formats=True)
    with pytest.raises(CommandError, match='formats-prerequisites'):
        smoke.main(feedback_formats=True, feedback_block_semantics=True)


def test_link_selector_preserves_guarded_envelope(monkeypatch):
    import check_e2e_feedback_link_semantics as check_links
    run = Mock(return_value=0)
    monkeypatch.setattr(check_links, 'smoke', run)
    assert check_links.main() == 0
    assert run.call_args.kwargs['feedback_link_semantics'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_link_semantics=True)
    with pytest.raises(CommandError, match='linked-prerequisites'):
        smoke.main(feedback_link_semantics=True, feedback_formats=True)


@pytest.mark.parametrize('fault', ['', 'unfocused', 'wrong-text', 'selection', 'uncertain',
                                  'missing', 'duplicate', 'wrong-owner'])
def test_formats_selection_refuses_before_toolbar_input(fault):
    import feedback_formats as formats
    ui, parent, dialog, controls = feedback_ui()
    editor = controls['feedback-editor-input']
    editor.states.add('focused')
    editor.text.count = len(formats.blocks.BODY)
    ui.api.Text.get_text = Mock(return_value=formats.blocks.BODY)
    ui.api.Text.get_n_selections = Mock(return_value=1)
    ui.api.Text.get_selection = Mock(return_value=SimpleNamespace(
        start_offset=formats.START, end_offset=formats.END))
    ui.activate_id = Mock()
    if fault == 'unfocused':
        editor.states.remove('focused')
    elif fault == 'wrong-text':
        ui.api.Text.get_text.return_value = 'x' * editor.text.count
    elif fault == 'selection':
        ui.api.Text.get_selection.return_value.end_offset += 1
    elif fault == 'uncertain':
        ui.input_uncertain = True
    elif fault == 'missing':
        dialog.children.remove(editor)
    elif fault == 'duplicate':
        dialog.children.append(Node(identity='feedback-editor-input'))
    elif fault == 'wrong-owner':
        parent.parent.identity = 'unrelated-application'
    if fault:
        with pytest.raises(accessible_ui.UiError):
            formats.operate(ui, 'formats-link-selected', accessible_ui.require, accessible_ui.UiError)
        ui.activate_id.assert_not_called()
    else:
        formats.operate(ui, 'formats-link-selected', accessible_ui.require, accessible_ui.UiError)
        ui.activate_id.assert_called_once_with('feedback-format-link')


@pytest.mark.parametrize('fault', ['', 'text', 'selection', 'unfocused'])
def test_link_entry_requires_selected_synthetic_prefill(fault):
    import feedback_formats as formats
    ui, _, dialog, controls = feedback_ui()
    editor = controls['feedback-editor-input']
    editor.text.count = len(formats.blocks.BODY)
    target = Node(identity='feedback-link-target', role='text',
                  states=('showing', 'visible', 'sensitive', 'editable', 'focused'))
    target.text = SimpleNamespace(count=5)
    target.get_text_iface = lambda: target.text
    dialog.children.append(target)
    target.parent = dialog
    ui.api.Text.get_text = Mock(side_effect=lambda text, *_:
        formats.blocks.BODY if text is editor.text else 'Other' if fault == 'text' else 'Plain')
    ui.api.Text.get_n_selections = Mock(return_value=1)
    ui.api.Text.get_selection = Mock(return_value=SimpleNamespace(
        start_offset=0, end_offset=4 if fault == 'selection' else 5))
    ui.activate_id = Mock()
    if fault == 'unfocused':
        target.states.remove('focused')
    if fault:
        with pytest.raises(accessible_ui.UiError):
            formats.operate(ui, 'formats-link-target', accessible_ui.require, accessible_ui.UiError)
    else:
        formats.operate(ui, 'formats-link-target', accessible_ui.require, accessible_ui.UiError)
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'duplicate', 'wrong-text', 'normal-in-container',
                                  'missing-level', 'list-kind', 'incomplete'])
def test_block_reader_associates_exact_text_and_refuses_ambiguous_trees(fault):
    from block_semantics import FORMATS, LINES, projection, read_blocks

    def node(role='paragraph', attrs=None, value=None, children=()):
        item = Mock()
        item.get_role_name.return_value = role
        item.get_attributes.return_value = attrs or {}
        item.get_text_iface.return_value = None if value is None else Mock(
            get_text=Mock(return_value=value), get_character_count=Mock(return_value=len(value)))
        item.get_child_count.return_value = len(children)
        item.get_child_at_index.side_effect = lambda index: children[index]
        return item

    nodes = [node('heading', {'level': '1'}, LINES[0]),
             node('heading', {'level': '2'}, LINES[1]),
             node('list item', {'roledescription': 'numbered list item'}, LINES[2]),
             node('list item', {'roledescription': 'bulleted list item'}, LINES[3]),
             node(attrs={'xml-roles': 'blockquote'}, value=LINES[4]),
             node(attrs={'xml-roles': 'code'}, children=[node(value=LINES[5])])]
    if fault == 'duplicate':
        nodes.append(nodes[0])
    elif fault == 'wrong-text':
        nodes[0].get_text_iface.return_value.get_text.return_value = LINES[-1]
    elif fault == 'normal-in-container':
        nodes[-1] = node(attrs={'xml-roles': 'code'}, children=[
            node(value=LINES[5]), node(value=LINES[-1])])
    elif fault == 'missing-level':
        nodes[0].get_attributes.return_value = {}
    elif fault == 'list-kind':
        nodes[2].get_attributes.return_value = {}
    elif fault == 'incomplete':
        nodes.append(None)
    root = node(children=nodes)
    if fault:
        with pytest.raises(accessible_ui.UiError):
            read_blocks(root, accessible_ui.require)
    else:
        assert read_blocks(root, accessible_ui.require) == projection(FORMATS)


def test_block_decoder_and_independent_recorder(tmp_path):
    from feedback_block_semantics import BlockSemanticsJourney
    from block_semantics import FORMATS, projection
    from ui_observations import UiObservations
    value = projection(FORMATS)
    reader = UiObservations(Mock())
    reply = {'operation': 'block-reopen', 'outcome': 'passed', 'interface': 'AT-SPI',
             'blocks': value}
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    assert reader.observe('block-reopen') == reply
    # Execute the exact shipped program without __main__, in isolated Python:
    # guest imports cannot depend on the host checkout or pytest's sys.path.
    import subprocess
    import sys
    program = reader.call.call_args.kwargs['input']
    subprocess.run([sys.executable, '-I', '-c',
                    "import sys; namespace={'__name__':'observer'}; "
                    "exec(compile(sys.stdin.read(), 'observer.py', 'exec'), namespace); "
                    "assert 'block-reopen' in namespace['OPERATIONS']"],
                   input=program, check=True, capture_output=True, timeout=20)
    journey = BlockSemanticsJourney(SimpleNamespace(directory=tmp_path), Mock())
    with pytest.raises(EvidenceError, match='blocks:independent-entry'):
        journey.check_settings('block-reopen', {'ui': reply})
    journey.check_settings('block-code-read', {'ui': reply})
    journey.check_settings('block-reopen', {'ui': reply})
    reply['blocks'] = value[:-1]
    reader.call.return_value = (json.dumps(reply).encode(), [])
    with pytest.raises(EvidenceError, match='ui:block-response'):
        reader.observe('block-reopen')


@pytest.mark.parametrize('fault', ['', 'block-heading-1-home', 'block-ordered-selected',
                                  'block-code-read', 'block-wrong-entry', 'block-reopen'])
def test_block_worker_stops_on_refusal(fault):
    from feedback_block_semantics import STAGES
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
    onpc_format::run_blocks(sub {
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


def test_block_recorder_reaches_real_custom_controller(tmp_path):
    from feedback_block_semantics import PLAN, BlockSemanticsJourney
    from installed_journey import record_installed_journey
    recorder = MagicMock(assertion=Mock())
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
                              verified=SimpleNamespace(inputs={}), guestfs=Mock(),
                              commands=Mock(), recorder=recorder)

    def worker(**options):
        controller = options['guarded_observe'].__self__
        assert type(controller) is BlockSemanticsJourney
        assert controller.plan is PLAN and controller.actions == {} and controller.formatted is None
        raise EvidenceError('synthetic-worker-stop')

    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        record_installed_journey(recorder, context, PLAN, actions={},
                                 journey_type=BlockSemanticsJourney)
    context.run_worker.assert_called_once()
    recorder.assertion.assert_not_called()


def test_block_selector_preserves_guarded_envelope(monkeypatch):
    import check_e2e_feedback_block_semantics as check_blocks
    run = Mock(return_value=0)
    monkeypatch.setattr(check_blocks, 'smoke', run)
    assert check_blocks.main() == 0
    assert run.call_args.kwargs['feedback_block_semantics'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_block_semantics=True)
    with pytest.raises(CommandError, match='block-prerequisites'):
        smoke.main(feedback_block_semantics=True, format_qualification=True)


@pytest.mark.parametrize('block,family,fault', [
    ('edits', '', ''), ('edits', '', 'feedback-state-no-reply'),
    ('length', 'ascii', ''), ('length', 'mixed', ''),
    ('length', 'ascii', 'length-ascii-refusal'),
    ('length', 'mixed', 'text-scalar-body-mixed-5001-caret'),
    ('length', 'unsupported', ''),
])
def test_feedback_fragments_accept_supplied_journey_and_stop_before_later_input(block, family, fault):
    from feedback_length import length_boundary
    from feedback_states import edit_states
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages);
my ($block, $family, $fault) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type'; }
package main;
require onpc_feedback_states;
my $journey = onpc_journey->new(prefix => 'independent-fragment', review => 0,
    exchange => sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    });
my $ok = eval {
    if ($block eq 'edits') { onpc_feedback_states::edit_states($journey); }
    else { onpc_feedback_states::length_boundary($journey, $family); }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', block, family, fault).stdout)
    if family == 'unsupported':
        assert result == dict(ok=0, events=[], stages=[])
        with pytest.raises(EvidenceError, match='length:family'):
            length_boundary(family)
        return
    fragment = edit_states() if block == 'edits' else length_boundary(family)
    stages = list(fragment)
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert len(result['stages']) == len(set(result['stages']))
    assert result['events'][-1] == (fault or stages[-1])
    assert [stage for stage in stages if stage.endswith('-send')] == (
        [] if block == 'edits' else [f'rejection-{family}-send'])
    fragment.clear()
    assert list(edit_states() if block == 'edits' else length_boundary(family)) == stages


def attachment_ui():
    import hashlib
    ui, parent, dialog, controls = feedback_ui()
    ui.api.RelationType.DESCRIBED_BY = 'described-by'
    rows = []
    for name, data in accessible_ui.ATTACHMENT_INPUTS:
        key = hashlib.sha256(name.encode() + b'\0' + data).hexdigest()[:16]
        remove = Node(identity='feedback-remove-attachment-' + key)
        subtitle = Node(f'{len(data)} bytes', role='label')
        row = Node(name, identity='feedback-attachment-' + key, children=[remove, subtitle])
        row.action.get_action_name = lambda _: 'row.activate'
        label_actions = sorted(accessible_ui.ATTACHMENT_LABEL_ACTIONS)
        subtitle.action.get_n_actions = lambda: len(label_actions)
        subtitle.action.get_action_name = lambda index: label_actions[index]
        availability = Node('Preview is not available', identity='feedback-preview-availability-' + key)
        availability.action = None
        availability.parent = row
        row.children.append(availability)
        row.relations = [SimpleNamespace(
            get_relation_type=lambda: 'described-by', get_n_targets=lambda: 1,
            get_target=lambda _, subtitle=subtitle: subtitle)]
        remove.action.do_action.side_effect = lambda _, row=row: (dialog.children.remove(row) or True)
        row.parent = dialog
        dialog.children.append(row)
        rows.append(row)
    dialog.children.append(Node('2 file attachments ready.', identity='feedback-status'))
    return ui, dialog, rows


@pytest.mark.parametrize('fault', ['', 'name', 'size', 'order', 'duplicate', 'stale', 'missing',
                                  'inactive', 'no-size', 'ambiguous-size', 'foreign-size', 'hidden-size'])
def test_attachment_items_public_metadata_and_refusals(fault):
    ui, dialog, rows = attachment_ui()
    if fault == 'name': rows[0].name = 'Unexpected.txt'
    if fault == 'size': rows[0].children[1].name = '999 bytes'
    if fault == 'no-size': rows[0].relations = []
    if fault == 'ambiguous-size': rows[0].relations *= 2
    if fault == 'foreign-size': rows[0].relations = rows[1].relations
    if fault == 'hidden-size': rows[0].children[1].states.remove('visible')
    if fault == 'order': dialog.children[-3:-1] = reversed(rows)
    if fault == 'duplicate': dialog.children.append(Node(identity=rows[0].identity))
    if fault == 'stale': rows[0].states.add('defunct')
    if fault == 'missing': dialog.children.remove(rows[0])
    if fault == 'inactive': dialog.states.remove('active')
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.attachment_operation('attachment-remove')
        rows[0].children[0].action.do_action.assert_not_called()
    else:
        assert ui.attachment_operation('attachment-details')['items'] == [
            ['Second note.txt', '33 bytes'], ['Synthetic note.txt', '26 bytes']]
        assert ui.attachment_operation('attachment-remove')['items'] == [['Synthetic note.txt', '26 bytes']]
        assert ui.attachment_operation('attachment-remaining')['items'] == [['Synthetic note.txt', '26 bytes']]


def test_attachment_removal_refuses_stale_list_and_wrong_item_without_replay():
    for wrong in (False, True):
        ui, dialog, rows = attachment_ui()
        action = rows[0].children[0].action.do_action
        action.side_effect = (lambda _: (dialog.children.remove(rows[1]) or True)) if wrong else None
        with pytest.raises(accessible_ui.UiError):
            ui.attachment_operation('attachment-remove')
        assert ui.input_uncertain
        with pytest.raises(accessible_ui.UiError):
            ui.attachment_operation('attachment-remove')
        assert action.call_count == 1


def test_attachment_removal_waits_for_queued_action_without_replay(monkeypatch):
    ui, dialog, rows = attachment_ui()
    ui.timeout = 1
    action = rows[0].children[0].action.do_action
    action.side_effect = None
    dispatch = Mock(side_effect=lambda _: dialog.children.remove(rows[0]))
    monkeypatch.setattr(accessible_ui.time, 'sleep', dispatch)
    assert ui.attachment_operation('attachment-remove')['items'] == [['Synthetic note.txt', '26 bytes']]
    assert action.call_count == 1
    assert dispatch.call_count == 1


def test_attachment_wrong_entry_is_publicly_checked():
    ui, _, _, _ = feedback_ui()
    assert ui.attachment_operation('attachment-wrong-entry') == {'checked': 'attachment-wrong-entry'}


@pytest.mark.parametrize('operation', sorted(accessible_ui.ATTACHMENT_OPERATIONS))
def test_attachment_controller_decodes_exact_metadata_and_refuses_corruption(operation):
    from ui_observations import UiObservations
    ui, _, _ = attachment_ui()
    if operation == 'attachment-wrong-entry':
        ui, _, _, _ = feedback_ui()
    if operation == 'attachment-remaining':
        ui.attachment_operation('attachment-remove')
    value = ui.attachment_operation(operation)
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', 'attachment': value}
    controller = UiObservations(Mock())
    controller.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert controller.observe(operation)['attachment'] == value
    value['items'] = [['Unexpected.txt', '0 bytes']]
    controller.call.return_value = (json.dumps(result).encode(), [])
    with pytest.raises(EvidenceError, match='attachment-response'):
        controller.observe(operation)


def chooser_ui(*, portal=False, profile='standard'):
    ui, parent, caller, controls = feedback_ui()
    ui.api.StateType.MULTISELECTABLE = 'multiselectable'
    names = accessible_ui.CHOOSER_FILES if profile == 'standard' else [name for name, _ in accessible_ui.BOUNDARY_FILES[profile]]
    items = [Node(name + ('. File' if portal else ''), role='list item') for name in names]
    selected = []
    selection = SimpleNamespace()
    view = Node(role='list', children=items,
                states=('visible', 'showing', 'sensitive', 'multiselectable'))
    view.get_selection_iface = lambda: selection
    ui.api.Selection = SimpleNamespace(
        get_n_selected_children=lambda _: len(selected),
        get_selected_child=lambda _, index: selected[index],
        select_all=Mock(side_effect=lambda _: selected.__setitem__(slice(None), items) or True))
    accept = Node('Open', role='push button')
    cancel = Node('Cancel', role='push button')
    window = Node(role='file chooser', children=[view, accept, cancel],
                  states=('visible', 'showing', 'active', 'modal', 'sensitive'))
    window.relations = [SimpleNamespace(get_relation_type=lambda: 'controlled-by',
        get_n_targets=lambda: 1, get_target=lambda _: caller)]
    parent.children.append(window)
    window.parent = parent
    ui.prompt_enabled = True
    ui.prompt_session = 'desktop'
    if portal:
        window.relations = []  # Imported Wayland parents have no GTK relation.
        # Nautilus cancels through its window close control, not a Cancel button.
        cancel.name = 'Close'
        ui.chooser_portal_owner = Mock(side_effect=lambda caller, provider:
            accessible_ui.validate_chooser_portal_owner(portal_query(), caller, provider))
        parent.children.remove(window)
        accept.identity = 'accept_button'
        window.identity = 'NautilusFileChooser'
        window.role = 'dialog'
        application = Node('org.gnome.Nautilus', role='application', children=[window])
        for node in (application, window, view, *items, accept, window.children[-1]):
            node.get_process_id = lambda: 200
        window.get_application = lambda: application
        desktop = Node(role='desktop', children=[ui.root(), application])
        ui.api.get_desktop = lambda _: desktop
    return ui, window, view, items, selected, accept, caller


# Save adds bounded in-memory provider doubles and waited private Perl children;
# the existing compatible unit classification and isolation remain applicable.
def save_ui():
    ui, window, _, _, _, accept, caller = chooser_ui(portal=True)
    accept.name = 'Save'
    field = Node(role='text', identity='filename_entry', states=(
        'visible', 'showing', 'sensitive', 'editable', 'focused'))
    field.get_process_id = lambda: 200
    field.value = 'diagnostic-logs.zip'
    field.get_text_iface = lambda: field
    field.get_editable_text_iface = lambda: field
    ui.api.Text = SimpleNamespace(get_character_count=lambda f: len(f.value),
                                 get_text=lambda f, a, b: f.value[a:b])
    ui.api.EditableText = SimpleNamespace(set_text_contents=Mock(
        side_effect=lambda f, value: setattr(f, 'value', value) or True))
    window.children.append(field)
    return ui, window, field, accept, caller


def collapse_save_name(ui, window, field):
    # Nautilus removes the transient editor from AT-SPI on focus loss.
    window.children.remove(field)
    label = Node(field.value, role='label', identity='filename_label')
    edit = Node(field.value, role='button', children=[label])
    reset = Node('Reset File Name', role='button', identity='filename_undo_button')
    for node in (label, edit, reset):
        node.get_process_id = lambda: 200
    ui.api.RelationType.LABELLED_BY = 'labelled-by'
    edit.relations = [SimpleNamespace(get_relation_type=lambda: 'labelled-by',
        get_n_targets=lambda: 1, get_target=lambda _: label)]
    window.children.extend([edit, reset])

    def reveal(_):
        window.children.remove(edit)
        window.children.append(field)
        field.states.add('focused')
        return True
    edit.action.do_action.side_effect = reveal
    return edit, label, reset


@pytest.mark.parametrize('fault', ['', 'wrong-mode', 'wrong-owner', 'ambiguous',
    'hidden', 'disabled', 'no-focus', 'timeout', 'refused', 'readback', 'unknown-modal'])
def test_save_filename_guard_and_uncertain_input(fault):
    ui, window, field, accept, caller = save_ui()
    setter = ui.api.EditableText.set_text_contents
    if fault == 'wrong-mode':
        accept.name = 'Open'
    elif fault == 'wrong-owner':
        field.get_process_id = lambda: 999
    elif fault == 'ambiguous':
        window.children.append(Node(role='text', identity='filename_entry'))
    elif fault in ('hidden', 'disabled', 'no-focus'):
        field.states.remove({'hidden': 'visible', 'disabled': 'sensitive', 'no-focus': 'focused'}[fault])
    elif fault == 'timeout':
        setter.side_effect = TimeoutError
    elif fault in ('refused', 'readback'):
        setter.side_effect = None
        setter.return_value = fault != 'refused'
    elif fault == 'unknown-modal':
        window.children.append(Node(role='dialog', states=('visible', 'showing', 'modal', 'active')))
    if fault:
        with pytest.raises((accessible_ui.UiError, TimeoutError)):
            ui.save_chooser_operation('save-chooser-name')
        if fault in ('timeout', 'refused', 'readback'):
            with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
                ui.save_chooser_operation('save-chooser-name')
            setter.assert_called_once()
        else:
            setter.assert_not_called()
    else:
        ui.save_chooser_operation('save-chooser-name')
        assert field.value == accessible_ui.SAVE_NAMES[0]
        setter.assert_called_once()
        with pytest.raises(accessible_ui.UiError, match='chooser-mode'):
            ui.chooser_snapshot(mode='open')
    accept.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'directory', 'input-echo', 'name', 'uncertain'])
def test_save_checks_destination_then_restored_name_before_single_accept(fault):
    assert accessible_ui.SAVE_DIRECTORY == '/home/onpc-parent-jamie/Downloads'
    ui, window, field, accept, _ = save_ui()
    field.value = accessible_ui.SAVE_NAMES[0]
    edit, _, reset = collapse_save_name(ui, window, field)
    location = Node(role='text', identity='location_entry', states=(
        'visible', 'showing', 'sensitive', 'editable', 'focused'))
    location.get_process_id = lambda: 200
    location.get_text_iface = lambda: location
    location.value = accessible_ui.SAVE_DIRECTORY
    window.children.append(location)
    accept.action.do_action.side_effect = lambda _: window.states.clear() or True
    if fault == 'directory':
        location.value += '-wrong'
    elif fault == 'input-echo':
        location.value += '/'
    if fault in ('directory', 'input-echo'):
        with pytest.raises((accessible_ui.UiError, TimeoutError)):
            ui.save_chooser_operation('save-chooser-destination')
        accept.action.do_action.assert_not_called()
        return
    ui.save_chooser_operation('save-chooser-destination')
    location.states.remove('showing')
    if fault == 'name':
        field.value = 'Wrong.zip'
    elif fault == 'uncertain':
        accept.action.do_action.side_effect = TimeoutError
    if fault == 'name':
        with pytest.raises(accessible_ui.UiError):
            ui.save_chooser_operation('save-chooser-restored')
        accept.action.do_action.assert_not_called()
    else:
        ui.save_chooser_operation('save-chooser-restored')
        if fault == 'uncertain':
            with pytest.raises(TimeoutError):
                ui.save_chooser_operation('save-chooser-accept')
            with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
                ui.save_chooser_operation('save-chooser-accept')
        else:
            ui.save_chooser_operation('save-chooser-accept')
        accept.action.do_action.assert_called_once()
        if not fault:
            assert ui.chooser_snapshot(mode='save', absent=True)
        edit.action.do_action.assert_called_once()
    reset.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'delayed', 'missing-editor', 'wrong-name',
    'duplicate-label', 'duplicate-button', 'hidden-duplicate', 'wrong-owner',
    'wrong-mode', 'hidden', 'disabled', 'unknown-modal', 'location-open',
    'duplicate-location', 'refused', 'timeout', 'editor-unfocused'])
def test_save_restores_collapsed_filename_once_with_guards(monkeypatch, fault):
    ui, window, field, accept, _ = save_ui()
    field.value = accessible_ui.SAVE_NAMES[0]
    edit, label, reset = collapse_save_name(ui, window, field)
    reveal = edit.action.do_action.side_effect
    if fault == 'duplicate-label':
        window.children.append(Node(label.name, role='label', identity='filename_label'))
    elif fault in ('duplicate-button', 'hidden-duplicate'):
        duplicate = Node(edit.name, role='button', states=() if fault == 'hidden-duplicate'
                         else ('visible', 'showing', 'sensitive'))
        duplicate.relations = edit.relations
        window.children.append(duplicate)
    elif fault == 'wrong-owner':
        edit.get_process_id = lambda: 999
    elif fault == 'wrong-mode':
        accept.name = 'Open'
    elif fault in ('hidden', 'disabled'):
        edit.states.remove('visible' if fault == 'hidden' else 'sensitive')
    elif fault == 'unknown-modal':
        window.children.append(Node(role='dialog', states=('visible', 'showing', 'modal', 'active')))
    elif fault in ('location-open', 'duplicate-location'):
        window.children.append(Node(role='text', identity='location_entry'))
        if fault == 'duplicate-location':
            window.children[-1].states.clear()
            window.children.append(Node(role='text', identity='location_entry', states=()))
    elif fault == 'refused':
        edit.action.do_action.side_effect = lambda _: False
    elif fault == 'timeout':
        edit.action.do_action.side_effect = TimeoutError
    elif fault in ('missing-editor', 'delayed'):
        edit.action.do_action.side_effect = lambda _: True
    elif fault == 'wrong-name':
        field.value = 'Changed.zip'
    elif fault == 'editor-unfocused':
        def unfocused(index):
            reveal(index)
            field.states.remove('focused')
            return True
        edit.action.do_action.side_effect = unfocused
    sleep = Mock(side_effect=lambda _: reveal(0))
    monkeypatch.setattr(accessible_ui.time, 'sleep', sleep)
    ui.timeout = 1 if fault == 'delayed' else 0
    after_input = {'missing-editor', 'wrong-name', 'refused', 'timeout', 'editor-unfocused'}
    if fault in ('', 'delayed'):
        ui.save_chooser_operation('save-chooser-restored')
        edit.action.do_action.assert_called_once()
        assert (sleep.call_count == 1) == (fault == 'delayed')
    else:
        with pytest.raises((accessible_ui.UiError, TimeoutError)):
            ui.save_chooser_operation('save-chooser-restored')
        if fault in after_input:
            assert ui.input_uncertain
            with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
                ui.save_chooser_operation('save-chooser-restored')
            edit.action.do_action.assert_called_once()
        else:
            edit.action.do_action.assert_not_called()
        sleep.assert_not_called()
    accept.action.do_action.assert_not_called()
    reset.action.do_action.assert_not_called()
    ui.api.EditableText.set_text_contents.assert_not_called()


@pytest.mark.parametrize('appears', [True, False])
def test_save_destination_waits_for_projection_without_replaying_input(monkeypatch, appears):
    # The editor can disappear before slot navigation and its next projection.
    # Private in-memory trees and a mocked clock retain this module's bucket.
    ui, window, field, accept, _ = save_ui()
    location = Node(role='text', identity='location_entry', states=(
        'visible', 'showing', 'sensitive', 'editable', 'focused'))
    location.get_process_id = lambda: 200
    location.get_text_iface = lambda: location
    location.value = accessible_ui.SAVE_DIRECTORY
    ui.timeout = 1 if appears else 0
    sleep = Mock(side_effect=lambda _: window.children.append(location))
    monkeypatch.setattr(accessible_ui.time, 'sleep', sleep)
    if appears:
        assert ui.save_chooser_operation('save-chooser-destination') == {
            'checked': 'save-chooser-destination'}
        sleep.assert_called_once()
    else:
        with pytest.raises(accessible_ui.UiError, match='ui:timeout:save-chooser-destination'):
            ui.save_chooser_operation('save-chooser-destination')
        sleep.assert_not_called()
    ui.api.EditableText.set_text_contents.assert_not_called()
    accept.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['duplicate', 'hidden-duplicate', 'wrong-role',
    'wrong-owner', 'wrong-mode', 'hidden', 'disabled', 'unfocused', 'stale', 'unknown-modal'])
def test_save_destination_readiness_refuses_unsafe_projection(monkeypatch, fault):
    ui, window, field, accept, _ = save_ui()
    location = Node(role='text', identity='location_entry', states=(
        'visible', 'showing', 'sensitive', 'editable', 'focused'))
    location.get_process_id = lambda: 200
    location.get_text_iface = lambda: location
    location.value = accessible_ui.SAVE_DIRECTORY
    window.children.append(location)
    if fault in ('duplicate', 'hidden-duplicate'):
        window.children.append(Node(role='text', identity='location_entry',
            states=('visible', 'showing') if fault == 'duplicate' else ()))
    elif fault == 'wrong-role':
        location.role = 'label'
    elif fault == 'wrong-owner':
        location.get_process_id = lambda: 999
    elif fault == 'wrong-mode':
        accept.name = 'Open'
    elif fault in ('hidden', 'disabled', 'unfocused'):
        location.states.remove({'hidden': 'showing', 'disabled': 'sensitive',
                                'unfocused': 'focused'}[fault])
    elif fault == 'stale':
        location.states.add('defunct')
    elif fault == 'unknown-modal':
        window.children.append(Node(role='dialog', states=('visible', 'showing', 'modal', 'active')))
    sleep = Mock()
    monkeypatch.setattr(accessible_ui.time, 'sleep', sleep)
    with pytest.raises(accessible_ui.UiError):
        ui.save_chooser_operation('save-chooser-destination')
    sleep.assert_not_called()
    ui.api.EditableText.set_text_contents.assert_not_called()
    accept.action.do_action.assert_not_called()


def test_save_refuses_accept_while_location_editor_is_showing():
    ui, window, field, accept, _ = save_ui()
    field.value = accessible_ui.SAVE_NAMES[0]
    field.states.remove('focused')
    location = Node(role='text', identity='location_entry', states=(
        'visible', 'showing', 'sensitive', 'editable', 'focused'))
    location.get_process_id = lambda: 200
    window.children.append(location)
    with pytest.raises(accessible_ui.UiError, match='save-location-still-open'):
        ui.save_chooser_operation('save-chooser-accept')
    accept.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', sorted(accessible_ui.SAVE_OPERATIONS))
def test_save_controller_requires_exact_mode_caller_and_result(operation):
    from ui_observations import UiObservations
    value = {'checked': operation}
    if operation.removeprefix('denied-').removeprefix('export-') in ('save-chooser-open', 'save-chooser-reopen'):
        value['provider'] = {'route': 'nautilus-portal', 'version': '50.2.2-1',
            'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']],
            'mode': 'save', 'caller': 'parent-feedback'}
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', 'chooser': value}
    controller = UiObservations(Mock())
    controller.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert controller.observe(operation)['chooser'] == value
    if 'provider' in value:
        value['provider']['mode'] = 'open'
    else:
        value['unexpected'] = True
    controller.call.return_value = (json.dumps(result).encode(), [])
    with pytest.raises(EvidenceError):
        controller.observe(operation)


@pytest.mark.parametrize('export', [False, True, 'case'])
def test_save_worker_matches_plan_and_refuses_before_later_input(export):
    if export == 'case':
        from parent_diagnostic_export import PLAN
    elif export:
        from diagnostic_export import PLAN
    else:
        from save_chooser import PLAN
    from tests.support.perl import run_perl
    stages = list(PLAN.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    script = r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); my ($fault, $export) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, $_[0]; }
sub type_string { push @main::events, 'typed'; }
package main;
require onpc_feedback_read;
require onpc_feedback_privacy;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $exchange = sub {
    push @events, $_[0]; push @stages, $_[0];
    die 'failed proof' if $_[0] eq $fault;
    return {observed => $_[0]};
};
my $ok = eval {
    if ($export eq 'case') { onpc_feedback_privacy::run($exchange, 'export'); }
    elsif ($export) { onpc_feedback_read::run_diagnostic_export($exchange); }
    else { onpc_feedback_read::run_save_chooser($exchange); }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
'''
    for fault in ('', *stages):
        result = json.loads(run_perl(script, fault, 'case' if export == 'case' else str(int(export))).stdout)
        assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
        assert result['ok'] == (not fault)
        assert result['events'][-1] == (fault or 'finish')
        if not fault:
            assert [event for event in result['events'] if event in ('ctrl-l', 'ret', 'esc')] == [
                'ctrl-l', 'ret', 'ctrl-l', 'esc'] * 2


def test_save_selector_and_prepare_registration(monkeypatch):
    import check_e2e_save_chooser as selector
    run = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', run)
    assert selector.main() == 0
    assert run.call_args.kwargs['save_chooser'] is True
    with pytest.raises(CommandError, match='save-chooser-prerequisites'):
        smoke.main(save_chooser=True, file_chooser=True)


def test_export_selector_and_constructor_registration(tmp_path, monkeypatch):
    import check_e2e_diagnostic_export as selector
    from parent_setup_qualification import DiagnosticExportQualification
    from diagnostic_export import PLAN
    from tests.support.e2e_composition import composition_errors, CASE_MODULES
    from tests.support.paths import ROOT
    run = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', run)
    assert selector.main() == 0 and run.call_args.kwargs['diagnostic_export'] is True
    with pytest.raises(CommandError, match='diagnostic-export-prerequisites'):
        smoke.main(diagnostic_export=True, save_chooser=True)
    journey = DiagnosticExportQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan is PLAN
    assert set(journey.actions) == {'save-prepare', 'save-read', 'diagnostic-inspect', 'save-cleanup'}
    assert composition_errors((ROOT / 'tests/e2e/diagnostic_export.py').read_text(), CASE_MODULES) == []


def test_export_comparison_runs_through_recorder_and_refuses_before_reply(tmp_path, monkeypatch):
    from copy import deepcopy
    from diagnostic_export import PLAN, journey as factory
    import installed_journey
    window = {'binding': 'feedback', 'pid': 42, 'endpoint': [':1.42', '/feedback'],
              'active': True, 'feedback': {'draft': 'synthetic-first',
                'attachments': ['diagnostic-logs.zip'], 'collection': 'ready',
                'validation': 'none', 'controls': 'ready'}}
    for fault in ('', 'pid', 'endpoint', 'feedback', 'capture'):
        directory = tmp_path / (fault or 'success')
        directory.mkdir()
        recorder = factory(SimpleNamespace(directory=directory), Mock())
        if fault != 'capture': recorder.check_settings('first-capture', {'ui': {'window': window}})
        actual = deepcopy(window)
        if fault == 'pid': actual['pid'] += 1
        if fault == 'endpoint': actual['endpoint'][1] = '/replaced'
        if fault == 'feedback': actual['feedback']['attachments'] = []
        stage = 'first-return'
        stages = list(PLAN.stages)
        recorder.steps = [{'stage': name} for name in stages[:stages.index(stage)]]
        recorder.ui = SimpleNamespace(boot_guard='', boot_proof='a' * 64,
            observe=Mock(return_value={'window': actual}))
        recorder.transport = Mock()
        monkeypatch.setattr(installed_journey.session_control, 'observe', Mock(return_value={}))
        (directory / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
        if fault:
            with pytest.raises(EvidenceError, match='window-or-draft-changed'): recorder.step(Mock())
            assert not (directory / (stage + '.reply.json')).exists()
        else:
            recorder.step(Mock())
            assert (directory / (stage + '.reply.json')).exists()
            # Independent reentry may capture again only after consuming comparison.
            recorder.check_settings('second-capture', {'ui': {'window': window}})


def test_export_shared_fragment_works_with_renamed_independent_consumer():
    from attachment_composition import diagnostic_export
    from tests.support.perl import run_perl
    stages = list(diagnostic_export('another-consumer'))
    script = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, $_[0]; }
package main;
require onpc_feedback_read;
my $fault = shift @ARGV;
my $journey = onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {
    push @events, $_[0]; die 'refused' if $_[0] eq $fault;
    return {observed => $_[0]};
});
my $ok = eval { onpc_feedback_read::diagnostic_export($journey, 'another-consumer'); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''
    expected = []
    for stage in stages:
        expected.append(stage)
        if stage.endswith(('-name', '-navigated')): expected.append('ctrl-l')
        if stage.endswith('-location'): expected.append('ret')
        if stage.endswith('-destination'): expected.append('esc')
    for fault in ('', *stages):
        value = json.loads(run_perl(script, fault).stdout)
        assert value == {'ok': int(not fault), 'events': (
            expected[:expected.index(fault) + 1] if fault else expected)}


@pytest.mark.parametrize('fragment', ['save_handoff', 'save_cancellation'])
def test_save_fragment_reuses_independent_invocation_and_refuses_before_input(fragment):
    from attachment_composition import save_handoff, save_cancellation
    from tests.support.perl import run_perl
    # An arbitrary consumer binding must work without a qualification import or
    # adding its name to the implementation. Save does not force a Cancel.
    factory = {'save_handoff': save_handoff, 'save_cancellation': save_cancellation}[fragment]
    stages = list(factory('consumer-export'))
    script = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, $_[0]; }
package main;
require onpc_feedback_read;
my ($fragment, $entry, $fault) = @ARGV;
my $journey = onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {
    push @events, $_[0]; die 'refused' if $_[0] eq $fault;
    return {observed => $_[0]};
});
my $ok = eval {
    if ($fragment eq 'save_handoff') { onpc_feedback_read::save_handoff($journey, $entry); }
    else { onpc_feedback_read::save_cancellation($journey, $entry); }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''
    expected = []
    for stage in stages:
        expected.append(stage)
        if stage.endswith(('-name', '-navigated')) and not stage.endswith('cancel-name'):
            expected.append('ctrl-l')
        if stage.endswith('-location'):
            expected.append('ret')
        if stage.endswith('-destination'):
            expected.append('esc')
    for fault in ('', *stages):
        result = json.loads(run_perl(script, fragment, 'consumer-export', fault).stdout)
        assert result == {'ok': int(not fault), 'events': (
            expected[:expected.index(fault) + 1] if fault else expected)}
    for invalid in ('bad prefix', '../escape', '', None):
        with pytest.raises(EvidenceError, match='save:invocation'):
            factory(invalid)
        if invalid is not None:
            assert json.loads(run_perl(script, fragment, invalid, '').stdout) == {'ok': 0, 'events': []}


def test_shared_draft_comparisons_do_not_alias_nested_observations():
    from attachment_composition import (compare_file_draft, compare_formatted_draft,
                                        formatted_draft_expected)
    formatted = formatted_draft_expected()
    captured = compare_formatted_draft(formatted)
    formatted['formats']['inline'].clear()
    formatted['items'][0][0] = 'Changed.txt'
    assert captured == formatted_draft_expected()
    file_draft = {'draft': 'attachment-file', 'attachments': ['Synthetic note.txt'],
        'collection': 'ready', 'validation': 'none', 'controls': 'ready',
        'items': [['Synthetic note.txt', '34 bytes']], 'include_logs': False}
    captured = compare_file_draft(file_draft)
    file_draft['attachments'].clear()
    file_draft['items'][0][0] = 'Changed.txt'
    assert captured['attachments'] == ['Synthetic note.txt']
    assert captured['items'] == [['Synthetic note.txt', '34 bytes']]


def test_window_history_copies_capture_before_independent_comparison():
    from copy import deepcopy
    from installed_journey import JourneyPlan
    from window_switch import WindowSwitchJourney
    plan = JourneyPlan(prefix='consumer', worker_mode='consumer', phases={}, screen_tags={
        'capture': 'ui:switch-draft-before', 'return': 'ui:switch-feedback'})
    journey = WindowSwitchJourney(SimpleNamespace(), Mock(), plan)
    window = {'binding': 'feedback', 'pid': 42, 'endpoint': [':1.42', '/window'],
              'active': True, 'feedback': {'items': [['Synthetic note.txt', '26 bytes']]}}
    original = deepcopy(window)
    journey.check_settings('capture', {'ui': {'window': window}})
    window['endpoint'][1] = '/changed'
    window['feedback']['items'][0][0] = 'Changed.txt'
    journey.check_settings('return', {'ui': {'window': original}})
    with pytest.raises(EvidenceError, match='window-or-draft-changed'):
        journey.check_settings('return', {'ui': {'window': window}})


def test_save_cancel_checks_fresh_filename_and_closure_without_save():
    ui, window, field, accept, _ = save_ui()
    field.value = accessible_ui.SAVE_NAMES[1]
    cancel = next(node for node in window.children if node.name == 'Close')
    cancel.action.do_action.side_effect = lambda _: window.states.clear() or True
    ui.save_chooser_operation('save-chooser-cancel')
    cancel.action.do_action.assert_called_once()
    accept.action.do_action.assert_not_called()


@pytest.mark.parametrize('step', ['location', 'destination'])
def test_denied_save_supplies_and_independently_checks_only_fixed_destination(step):
    ui, window, field, _, _ = save_ui()
    field.identity = 'location_entry'
    field.value = accessible_ui.SAVE_DIRECTORY + '/Unwritable'
    if step == 'location': field.value = 'previous'
    ui.save_chooser_operation('denied-export-save-chooser-' + step)
    assert field.value == accessible_ui.SAVE_DIRECTORY + '/Unwritable' + (
        '/' if step == 'location' else '')
    if step == 'destination':
        field.value = accessible_ui.SAVE_DIRECTORY
        with pytest.raises(accessible_ui.UiError, match='save-field-readback'):
            ui.save_chooser_operation('denied-export-save-chooser-destination')


@pytest.mark.parametrize('fault', ['', 'delayed', 'timeout', 'owner', 'ambiguous', 'chooser'])
def test_save_error_requires_exact_app_subtitle_and_refuses_unsafe_result(fault):
    ui, _, _, controls = feedback_ui()
    expected = 'Could not save logs. Try another location.'
    subtitle = Node(expected, role='label')
    row = controls['feedback-logs-row']
    row.children.append(subtitle)
    subtitle.parent = row
    ui.api.RelationType.DESCRIBED_BY = 'described-by'
    row.relations = [SimpleNamespace(get_relation_type=lambda: 'described-by',
        get_n_targets=lambda: 2 if fault == 'ambiguous' else 1,
        get_target=lambda _: subtitle)]
    ui.chooser_snapshot = Mock(return_value=fault != 'chooser')
    if fault == 'owner': row.get_process_id = lambda: 999
    if fault == 'timeout': subtitle.name = 'Could not choose a download location. Try again.'
    if fault == 'delayed':
        subtitle.name = 'Latest 3 log dates · ZIP archive'
        original_wait = ui.wait
        def delayed(predicate, label, **kwargs):
            if label == 'save-app-result':
                assert predicate() is False
                subtitle.name = expected
            return original_wait(predicate, label, **kwargs)
        ui.wait = delayed
    if fault in ('timeout', 'owner', 'ambiguous', 'chooser'):
        with pytest.raises(accessible_ui.UiError): ui.save_app_result(expected)
    else:
        ui.save_app_result(expected)
    for node in controls.values(): node.action.do_action.assert_not_called()


def test_synthetic_cancel_and_failed_save_preserve_draft_before_recovery():
    from attachment_composition import save_handoff, save_cancellation
    assert set(save_handoff('independent', draft='synthetic-first', destination='unwritable').values()) <= {
        'ui:' + operation for operation in accessible_ui.SAVE_OPERATIONS}
    with pytest.raises(EvidenceError, match='save:destination'):
        save_handoff('independent', draft='synthetic-first', destination='../other')
    ui, window, field, accept, _ = save_ui()
    cancel = next(node for node in window.children if node.name == 'Close')
    cancel.action.do_action.side_effect = lambda _: window.states.clear() or True
    ui.save_chooser_operation('export-save-chooser-cancel-name')
    ui.save_chooser_operation('export-save-chooser-cancel')
    ui.wait_feedback_collection = Mock()
    ui.feedback_snapshot = Mock()
    ui.save_chooser_operation('export-save-chooser-preserved')
    ui.feedback_snapshot.assert_called_once_with('synthetic-first')
    accept.action.do_action.assert_not_called()
    assert all(value.startswith('ui:export-save-chooser-')
               for value in save_cancellation('independent', draft='synthetic-first').values())


def test_case155_recorder_constructs_shared_journey_and_registered_actions(tmp_path):
    from parent_diagnostic_export import PLAN, execute
    from attachment_composition import DiagnosticExportJourney
    recorder = MagicMock(assertion=Mock())
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
        verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock(), recorder=recorder)
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert type(journey) is DiagnosticExportJourney and journey.plan is PLAN
        assert set(journey.actions) == set(PLAN.stage_actions.values())
        assert options['validate'].__self__ is journey
        raise EvidenceError('synthetic-worker-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'): execute(recorder, context)
    context.run_worker.assert_called_once()
    recorder.assertion.assert_not_called()


@pytest.mark.parametrize('phase', ['cancel', 'denied', 'export', 'privacy'])
@pytest.mark.parametrize('fault', ['', 'pid', 'endpoint', 'draft', 'capture'])
def test_case155_independent_comparison_refuses_before_durable_reply(tmp_path, monkeypatch, phase, fault):
    from copy import deepcopy
    from parent_diagnostic_export import PLAN
    from attachment_composition import DiagnosticExportJourney
    from synthetic_files import diagnostic_export_actions
    import installed_journey
    window = {'binding': 'feedback', 'pid': 42, 'endpoint': [':1.42', '/feedback'],
              'active': True, 'feedback': {'draft': 'synthetic-first',
                'attachments': ['diagnostic-logs.zip'], 'collection': 'ready',
                'validation': 'none', 'controls': 'ready'}}
    journey = DiagnosticExportJourney(SimpleNamespace(directory=tmp_path), Mock(), PLAN,
                                      actions=diagnostic_export_actions(preservation=True))
    if fault != 'capture': journey.check_settings(phase + '-capture', {'ui': {'window': window}})
    actual = deepcopy(window)
    if fault == 'pid': actual['pid'] += 1
    if fault == 'endpoint': actual['endpoint'][1] = '/replaced'
    if fault == 'draft': actual['feedback']['attachments'] = []
    stage = phase + '-return'
    stages = list(PLAN.stages)
    journey.steps = [{'stage': name} for name in stages[:stages.index(stage)]]
    journey.ui = SimpleNamespace(boot_guard='', boot_proof='a' * 64,
        observe=Mock(return_value={'window': actual}))
    journey.transport = Mock()
    monkeypatch.setattr(installed_journey.session_control, 'observe', Mock(return_value={}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError, match='window-or-draft-changed'): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        assert 'feedback' not in journey.windows


def portal_query():
    """Public introspection for one live delegated request, no host bus."""
    def query(bus, path, interface, method, signature, args):
        if method == 'GetNameOwner':
            return ':1.20'
        if method == 'GetConnectionUnixProcessID':
            return 200 if args == (':1.20',) else Node().get_process_id()
        if path.endswith('/request'):
            return '<node><node name="1_10"/></node>'
        if path.endswith('/1_10'):
            return '<node><node name="gtk123"/></node>'
        prefix = 'org.freedesktop.portal' if bus == 'org.freedesktop.portal.Desktop' else 'org.freedesktop.impl.portal'
        return '<node><interface name="' + prefix + '.Request"/></node>'
    return query


@pytest.mark.parametrize('fault', ['none', 'wrong-provider', 'wrong-caller', 'no-request',
    'other-request', 'two-tokens', 'path-injection', 'missing-frontend', 'missing-backend',
    'malformed', 'oversize', 'replaced'])
def test_portal_request_proves_live_provider_and_caller_or_refuses(fault):
    baseline = portal_query()
    calls = []
    def query(bus, path, interface, method, signature, args):
        calls.append((bus, path, method, args))
        if method == 'GetConnectionUnixProcessID':
            if fault == 'wrong-provider' and args == (':1.20',):
                return 999
            if fault == 'wrong-caller' and args == (':1.10',):
                return 999
        if method == 'GetNameOwner' and fault == 'replaced' and len(calls) > 1:
            return ':1.21'
        if method == 'Introspect':
            if fault == 'malformed':
                return '<node'
            if fault == 'oversize':
                return 'x' * 65537
            if path.endswith('/request'):
                if fault == 'no-request':
                    return '<node/>'
                if fault == 'other-request':
                    return '<node><node name="1_10"/><node name="1_11"/></node>'
            if path.endswith('/1_10'):
                if fault == 'two-tokens':
                    return '<node><node name="a"/><node name="b"/></node>'
                if fault == 'path-injection':
                    return '<node><node name="../other"/></node>'
            if path.endswith('/gtk123') and (
                    fault == 'missing-frontend' and bus == 'org.freedesktop.portal.Desktop'
                    or fault == 'missing-backend' and bus == ':1.20'):
                return '<node/>'
        return baseline(bus, path, interface, method, signature, args)
    if fault == 'none':
        accessible_ui.validate_chooser_portal_owner(query, Node().get_process_id(), 200)
        assert len(calls) == 9
    else:
        with pytest.raises(accessible_ui.UiError, match='chooser-'):
            accessible_ui.validate_chooser_portal_owner(query, Node().get_process_id(), 200)
    assert {call[2] for call in calls} <= {'GetNameOwner', 'GetConnectionUnixProcessID', 'Introspect'}


@pytest.mark.parametrize('portal', [False, True])
def test_chooser_selects_prepared_files_in_one_api_call(portal):
    ui, _, _, items, selected, accept, _ = chooser_ui(portal=portal)
    ui.chooser_operation('chooser-files')
    assert selected == items
    accept.action.do_action.assert_not_called()
    assert ui.chooser_selection(accessible_ui.CHOOSER_FILES)[2] == list(accessible_ui.CHOOSER_FILES)
    ui.api.Selection.select_all.assert_called_once()


@pytest.mark.parametrize('profile', sorted(accessible_ui.BOUNDARY_FILES))
@pytest.mark.parametrize('fault', ['', 'extra-file', 'wrong-file', 'partial', 'wrong-owner'])
def test_boundary_chooser_exact_batch_before_select_all(profile, fault):
    ui, _, view, items, selected, accept, _ = chooser_ui(portal=True, profile=profile)
    view.name = 'Content View'
    view.states.remove('multiselectable')
    if fault == 'extra-file': view.children.append(Node('Unknown.File', role='list item'))
    if fault == 'wrong-file': items[0].name = 'Unknown.File'
    if fault == 'partial':
        ui.api.Selection.select_all.side_effect = lambda _: selected.extend(items[:-1]) or True
    if fault == 'wrong-owner':
        ui.chooser_portal_owner.side_effect = accessible_ui.UiError('ui:chooser-request-caller')
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.chooser_select_files(profile=profile)
        if fault != 'partial': ui.api.Selection.select_all.assert_not_called()
    else:
        ui.chooser_select_files(profile=profile)
        assert selected == items
        ui.api.Selection.select_all.assert_called_once()
    accept.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'single-selection', 'ambiguous', 'missing-interface'])
def test_nautilus_custom_selection_model_without_multiselectable_hint(fault):
    ui, window, view, items, selected, accept, _ = chooser_ui(portal=True)
    view.name = 'Content View'
    view.states.remove('multiselectable')
    if fault == 'single-selection':
        ui.api.Selection.select_all.side_effect = lambda _: selected.append(items[0]) or True
    elif fault == 'ambiguous':
        duplicate = Node('Content View', role='list')
        duplicate.get_selection_iface = view.get_selection_iface
        window.children.append(duplicate)
    elif fault == 'missing-interface':
        view.get_selection_iface = lambda: None
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.chooser_select_files()
        accept.action.do_action.assert_not_called()
        if fault != 'single-selection':
            ui.api.Selection.select_all.assert_not_called()
    else:
        ui.chooser_select_files()
        assert selected == items


@pytest.mark.parametrize('suffix', ['', '. Folder', '. File. Starred', '. File extra'])
def test_nautilus_file_labels_require_exact_registered_file_role(suffix):
    ui, _, _, items, _, accept, _ = chooser_ui(portal=True)
    items[0].name = accessible_ui.CHOOSER_FILES[0] + suffix
    with pytest.raises(accessible_ui.UiError, match='file-set'):
        ui.chooser_select_files()
    ui.api.Selection.select_all.assert_not_called()
    accept.action.do_action.assert_not_called()


def location_ui(*, portal=False):
    ui, window, *_ = chooser_ui(portal=portal)
    field = Node(role='text', identity='entry', states=(
        'visible', 'showing', 'sensitive', 'editable', 'focused'))
    field.get_process_id = window.get_process_id
    field.value = 'old location'
    field.get_text_iface = field.get_editable_text_iface = lambda: field
    window.children.append(field)
    field.parent = window
    ui.api.Text = SimpleNamespace(get_character_count=lambda node: len(node.value),
                                 get_text=lambda node, start, end: node.value[start:end])
    ui.api.EditableText = SimpleNamespace(set_text_contents=Mock(
        side_effect=lambda node, value: setattr(node, 'value', value) or True))
    return ui, window, field


@pytest.mark.parametrize('portal', [False, True])
def test_chooser_location_uses_editable_api_and_fresh_readback(portal):
    ui, _, field = location_ui(portal=portal)
    snapshot = ui.chooser_snapshot
    ui.chooser_snapshot = Mock(side_effect=snapshot)
    ui.chooser_operation('chooser-location')
    ui.api.EditableText.set_text_contents.assert_called_once_with(
        field, accessible_ui.CHOOSER_DIRECTORY + '/')
    assert ui.chooser_snapshot.call_count == 2
    assert not ui.input_uncertain


@pytest.mark.parametrize('fault', ['wrong-owner', 'wrong-id', 'no-focus', 'hidden',
    'disabled', 'ambiguous', 'no-api', 'refused', 'timeout', 'wrong-text', 'lost-focus'])
def test_chooser_location_refuses_unsafe_target_and_uncertain_input(fault):
    ui, window, field = location_ui(portal=True)
    setter = ui.api.EditableText.set_text_contents
    after_input = fault in ('refused', 'timeout', 'wrong-text', 'lost-focus')
    if fault == 'wrong-owner':
        field.get_process_id = lambda: 999
    elif fault == 'wrong-id':
        field.identity = 'search_entry'
    elif fault in ('no-focus', 'hidden', 'disabled'):
        field.states.remove({'no-focus': 'focused', 'hidden': 'visible', 'disabled': 'sensitive'}[fault])
    elif fault == 'ambiguous':
        window.children.append(Node(role='text', identity='entry', states=field.states))
    elif fault == 'no-api':
        field.get_editable_text_iface = lambda: None
    elif fault == 'timeout':
        setter.side_effect = TimeoutError
    elif fault in ('refused', 'wrong-text'):
        setter.side_effect = None
        setter.return_value = fault != 'refused'
    else:
        setter.side_effect = lambda *_: field.states.remove('focused') or True
    with pytest.raises((accessible_ui.UiError, TimeoutError)):
        ui.chooser_operation('chooser-location')
    if after_input:
        with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
            ui.chooser_operation('chooser-location')
        setter.assert_called_once()
    else:
        setter.assert_not_called()


def test_portal_is_expected_only_inside_fresh_chooser_validation():
    ui, window, _, _, _, _, _ = chooser_ui(portal=True)
    assert ui.system_prompt_kind() == 'unknown'
    assert ui.chooser_snapshot()[-1] == 'nautilus-portal'
    assert ui.chooser_snapshot(absent=True) is False
    # A successful chooser read must not exempt this provider in later work.
    with pytest.raises(accessible_ui.UiError, match='system-prompt-refused'):
        ui.handle_system_prompt()
    window.states.clear()
    assert ui.chooser_snapshot(absent=True) is True


@pytest.mark.parametrize('portal', [False, True])
@pytest.mark.parametrize('button_role', ['push button', 'button'])
def test_chooser_cancel_invokes_provider_control_once_and_observes_closure(portal, button_role):
    ui, window, _, items, selected, accept, _ = chooser_ui(portal=portal)
    # Cancel does not require browsing to or selecting a candidate file.
    cancel = window.children[-1]
    accept.role = cancel.role = button_role
    cancel.action.do_action.side_effect = lambda _: window.states.clear() or True
    ui.chooser_operation('chooser-cancel')
    cancel.action.do_action.assert_called_once()
    accept.action.do_action.assert_not_called()
    assert ui.chooser_snapshot(absent=True) is True


@pytest.mark.parametrize('fault', ['missing', 'ambiguous', 'wrong-owner', 'hidden', 'disabled', 'uncertain'])
@pytest.mark.parametrize('button_role', ['push button', 'button'])
def test_portal_cancel_refuses_invalid_control_and_never_replays(fault, button_role):
    ui, window, _, items, selected, accept, _ = chooser_ui(portal=True)
    selected.append(items[0])
    cancel = window.children[-1]
    accept.role = cancel.role = button_role
    if fault == 'missing':
        cancel.name = 'Cancel'
    elif fault == 'ambiguous':
        window.children.append(Node('Close', role=button_role))
    elif fault == 'wrong-owner':
        cancel.get_process_id = lambda: 999
    elif fault in ('hidden', 'disabled'):
        cancel.states.remove('visible' if fault == 'hidden' else 'sensitive')
    else:
        cancel.action.do_action.side_effect = TimeoutError
    with pytest.raises((accessible_ui.UiError, TimeoutError)):
        ui.chooser_operation('chooser-cancel')
    accept.action.do_action.assert_not_called()
    if fault == 'uncertain':
        with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
            ui.chooser_operation('chooser-cancel')
        cancel.action.do_action.assert_called_once()
    else:
        cancel.action.do_action.assert_not_called()


@pytest.mark.parametrize('failed', [False, True])
def test_portal_owner_reads_current_session_without_activation_and_closes(monkeypatch, failed):
    from gi.repository import Gio
    connection = Mock()
    baseline = portal_query()
    def reply(bus, path, interface, method, parameters, result_type, flags, timeout, cancellable):
        assert flags == Gio.DBusCallFlags.NO_AUTO_START
        assert timeout == 2000
        if failed:
            raise accessible_ui.UiError('ui:chooser-request-interface')
        args = parameters.unpack() if parameters is not None else ()
        return SimpleNamespace(unpack=lambda: (baseline(bus, path, interface, method, '', args),))
    connection.call_sync.side_effect = reply
    connect = Mock(return_value=connection)
    monkeypatch.setattr(Gio.DBusConnection, 'new_for_address_sync', connect)
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/private-test-bus')
    ui, *_ = chooser_ui()
    if failed:
        with pytest.raises(accessible_ui.UiError, match='request-interface'):
            ui.chooser_portal_owner(Node().get_process_id(), 200)
    else:
        ui.chooser_portal_owner(Node().get_process_id(), 200)
    assert connect.call_args.args[0] == 'unix:path=/private-test-bus'
    connection.set_exit_on_close.assert_called_once_with(False)
    connection.close_sync.assert_called_once_with(None)


def test_portal_request_failure_prevents_selection_and_open():
    ui, _, _, _, _, accept, _ = chooser_ui(portal=True)
    ui.chooser_portal_owner.side_effect = accessible_ui.UiError('ui:chooser-request-caller')
    with pytest.raises(accessible_ui.UiError, match='request-caller'):
        ui.chooser_select_files()
    ui.api.Selection.select_all.assert_not_called()
    accept.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['wrong-caller', 'wrong-owner', 'secret',
                                  'authentication-title', 'other-modal', 'nested-modal'])
def test_portal_guard_rejects_unproven_or_additional_prompts(fault):
    ui, window, _, _, _, accept, _ = chooser_ui(portal=True)
    if fault == 'wrong-caller':
        window.relations = [SimpleNamespace(get_relation_type=lambda: 'controlled-by',
            get_n_targets=lambda: 1, get_target=lambda _: Node())]
    elif fault == 'wrong-owner':
        window.get_application().name = 'Unrelated application'
    elif fault == 'secret':
        window.children.append(Node(role='password text'))
    elif fault == 'authentication-title':
        window.name = 'Authentication Required'
    else:
        owner = window if fault == 'nested-modal' else window.get_application()
        owner.children.append(Node(role='dialog'))
    with pytest.raises(accessible_ui.UiError):
        ui.chooser_select_files()
    ui.api.Selection.select_all.assert_not_called()
    accept.action.do_action.assert_not_called()


def test_portal_open_wait_validates_chooser_before_generic_prompt_refusal():
    ui, window, _, _, _, _, _ = chooser_ui(portal=True)
    states = window.states.copy()
    window.states.clear()
    ui.activate_id = Mock(side_effect=lambda _: window.states.update(states))
    ui.chooser_metadata = Mock(return_value={'route': 'nautilus-portal'})
    assert ui.chooser_operation('chooser-open')['provider']['route'] == 'nautilus-portal'
    ui.activate_id.assert_called_once_with('feedback-add-files')


@pytest.mark.parametrize('fault', ['wrong-caller', 'mode', 'inactive', 'not-modal',
    'ambiguous', 'wrong-file', 'single-mode', 'incomplete', 'disabled', 'uncertain'])
def test_chooser_refuses_before_selection_or_open(fault):
    ui, window, view, items, selected, accept, caller = chooser_ui()
    if fault == 'wrong-caller':
        window.relations[0].get_target = lambda _: Node()
    elif fault == 'mode':
        accept.name = 'Save'
    elif fault == 'inactive':
        window.states.remove('active')
    elif fault == 'not-modal':
        window.states.remove('modal')
    elif fault == 'ambiguous':
        window.parent.children.append(Node(role='file chooser', children=[Node('Open', role='push button')]))
    elif fault == 'wrong-file':
        items[0].name = 'Unregistered.txt'
    elif fault == 'single-mode':
        view.states.remove('multiselectable')
    elif fault == 'incomplete':
        window.get_child_count = Mock(side_effect=LookupError())
    elif fault == 'disabled':
        view.states.remove('sensitive')
    elif fault == 'uncertain':
        ui.input_uncertain = True
    with pytest.raises((accessible_ui.UiError, LookupError)):
        ui.chooser_select_files()
    ui.api.Selection.select_all.assert_not_called()
    accept.action.do_action.assert_not_called()


def test_chooser_uncertain_selection_cannot_replay_or_open():
    ui, _, _, _, _, accept, _ = chooser_ui()
    ui.api.Selection.select_all.side_effect = TimeoutError
    with pytest.raises(TimeoutError):
        ui.chooser_select_files()
    with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
        ui.chooser_operation('chooser-accept')
    assert ui.api.Selection.select_all.call_count == 1
    accept.action.do_action.assert_not_called()


def test_chooser_refuses_partial_selection_without_opening_or_replaying():
    ui, _, _, items, selected, accept, _ = chooser_ui()
    def replace(_):
        selected[:] = [items[0]]
        return True
    ui.api.Selection.select_all.side_effect = replace
    with pytest.raises(accessible_ui.UiError, match='partial-selection'):
        ui.chooser_select_files()
    with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
        ui.chooser_select_files()
    assert ui.api.Selection.select_all.call_count == 1
    accept.action.do_action.assert_not_called()


def test_chooser_open_refuses_partial_selection_even_without_selection_action():
    ui, _, _, items, selected, accept, _ = chooser_ui()
    selected.append(items[0])
    with pytest.raises(accessible_ui.UiError, match='partial-selection'):
        ui.chooser_operation('chooser-accept')
    accept.action.do_action.assert_not_called()


def test_chooser_attachment_readback_uses_exact_ids_names_and_status():
    import hashlib
    from synthetic_files_guest import FILES
    ui, _, dialog, _ = feedback_ui()
    assert sorted(FILES) == list(accessible_ui.CHOOSER_FILES)
    for name, data in FILES.items():
        key = hashlib.sha256(name.encode() + b'\0' + data).hexdigest()[:16]
        dialog.children.append(Node(name, identity='feedback-attachment-' + key))
    dialog.children.append(Node('2 file attachments ready.', identity='feedback-status'))
    ui.feedback_snapshot(attachments=True)
    with pytest.raises(accessible_ui.UiError, match='attachment-set'):
        ui.feedback_snapshot()
    dialog.children[-2].name = 'Unexpected.txt'
    with pytest.raises(accessible_ui.UiError, match='attachment-name'):
        ui.feedback_snapshot(attachments=True)


@pytest.mark.parametrize('items', [0, 1, 2, 3])
@pytest.mark.parametrize('fault', ['', 'chooser-open', 'chooser-location',
    'chooser-files', 'chooser-accept', 'chooser-cancel', 'chooser-preserved'])
def test_chooser_worker_matches_plan_and_stops_at_failed_proof(fault, items):
    from file_chooser import PLAN as chooser_plan
    if items == 1:
        from attachment_items import PLAN as chooser_plan
    if items == 2:
        from attachment_preview import PLAN as chooser_plan
    if items == 3:
        from attachment_boundaries import PLAN as chooser_plan
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV; our $items = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, $_[0]; }
sub type_string { push @main::events, 'type'; }
package main;
require onpc_feedback_read;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval { onpc_feedback_read::run_file_chooser(sub {
    push @events, $_[0]; push @stages, $_[0];
    die 'failed proof' if $_[0] eq $fault;
    return {observed => $_[0]};
}, ($items ? ($items) : ())); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault, str(int(items))).stdout)
    stages = list(chooser_plan.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert result['ok'] == (not fault)
    assert result['events'][-1] == (fault or 'finish')
    if not fault:
        assert [event for event in result['events'] if event in ('ctrl-l', 'ctrl-a', 'ret', 'type')] == ['ctrl-l', 'ret'] * (7 if items == 3 else 1)


@pytest.mark.parametrize('prefix', ['chooser', 'boundary-sixth', 'unregistered'])
@pytest.mark.parametrize('fault', ['', 'open', 'location', 'files', 'accept'])
def test_shared_file_handoff_accepts_independent_entry_and_stops_before_later_input(prefix, fault):
    from attachment_composition import file_handoff
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our @events; my ($prefix, $fault) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, 'key:' . $_[0]; }
package main;
use onpc_journey;
use onpc_feedback_read;
my $journey = onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {
    push @events, $_[0];
    die 'failed proof' if $_[0] eq "$prefix-$fault";
    return {observed => $_[0]};
});
my $ok = eval { onpc_feedback_read::supply_files($journey, $prefix); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', prefix, fault).stdout)
    if prefix == 'unregistered':
        assert result == {'ok': 0, 'events': []}
        return
    stages = list(file_handoff(prefix))
    expected = [stages[0], 'key:ctrl-l', stages[1], 'key:ret', *stages[2:]]
    if fault:
        expected = expected[:expected.index(prefix + '-' + fault) + 1]
    assert result == {'ok': int(not fault), 'events': expected}


@pytest.mark.parametrize('fragment', ['chooser_preservation', 'attachment_removal'])
@pytest.mark.parametrize('prefix', ['', 'independent-'])
def test_attachment_fragments_share_protocol_and_stop_at_every_refusal(fragment, prefix):
    import attachment_composition
    from tests.support.perl import run_perl
    declaration = getattr(attachment_composition, fragment)
    stages = declaration(prefix)
    assert list(stages.values()) == list(declaration().values())
    changed = declaration(prefix)
    changed.clear()
    assert declaration(prefix) == stages
    for invalid in ('bad prefix', 'missing-dash', None):
        with pytest.raises(EvidenceError):
            declaration(invalid)
    script = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { die 'unexpected input'; }
package main;
require onpc_feedback_read;
my ($fragment, $prefix, $fault, @stages) = @ARGV;
my $journey = onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {
    push @events, $_[0];
    die 'proof refused' if $_[0] eq $fault;
    return {observed => $_[0]};
});
$journey->declare_invocations(\@stages) if length $prefix;
my $ok = eval {
    if ($fragment eq 'chooser_preservation') {
        onpc_feedback_read::chooser_preservation($journey, $prefix);
    } else { onpc_feedback_read::attachment_removal($journey, $prefix); }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''
    for fault in ('', *stages):
        result = json.loads(run_perl(script, fragment, prefix, fault, *stages).stdout)
        expected = list(stages)
        if fault:
            expected = expected[:expected.index(fault) + 1]
        assert result == {'ok': int(not fault), 'events': expected}
    result = json.loads(run_perl(script, fragment, 'bad prefix', '', *stages).stdout)
    assert result == {'ok': 0, 'events': []}


@pytest.mark.parametrize('fault', sorted(
    set(__import__('attachment_boundaries').PLAN.screen_tags) & accessible_ui.BOUNDARY_OPERATIONS))
def test_boundary_worker_stops_at_each_failed_proof(fault):
    test_chooser_worker_matches_plan_and_stops_at_failed_proof(fault, 3)


def test_boundary_selector_registration_and_prerequisites(monkeypatch):
    import check_e2e_attachments
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_attachments, 'smoke', run)
    assert check_e2e_attachments.main() == 0
    assert run.call_args.kwargs['attachment_boundaries'] is True
    with pytest.raises(CommandError, match='attachment-boundaries-prerequisites'):
        smoke.main(attachment_boundaries=True, attachment_preview=True)


@pytest.mark.parametrize('operation', sorted(accessible_ui.BOUNDARY_OPERATIONS))
def test_boundary_controller_decodes_exact_results_and_rejects_altered_evidence(operation):
    from ui_observations import UiObservations
    value = accessible_ui.boundary_expected(operation)
    if operation.endswith('-open'):
        value['provider'] = {'route': 'nautilus-portal', 'version': '50.2.2-1',
                             'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', 'boundary': value}
    controller = UiObservations(Mock())
    controller.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert controller.observe(operation)['boundary'] == value
    value['unexpected'] = True
    controller.call = Mock(return_value=(json.dumps(result).encode(), []))
    with pytest.raises(EvidenceError, match='boundary-response'):
        controller.observe(operation)


def test_boundary_comparison_preserves_independent_prior_list():
    from attachment_composition import AttachmentJourney
    from installed_journey import JourneyPlan
    plan = JourneyPlan(prefix='boundary-library', worker_mode='fixture', phases={}, screen_tags={
        stage: 'ui:' + stage for stage in accessible_ui.BOUNDARY_OPERATIONS})
    controller = AttachmentJourney(SimpleNamespace(), Mock(), plan)
    for batch in ('sixth', 'oversized', 'overflow', 'name181', 'hidden', 'mixed'):
        def observation(step):
            return {'ui': {'boundary': accessible_ui.boundary_expected(f'boundary-{batch}-{step}')}}
        controller.check_settings(f'boundary-{batch}-before', observation('before'))
        controller.check_settings(f'boundary-{batch}-result', observation('result'))
        value = observation('preserved')
        value['ui']['boundary']['items'].pop()
        with pytest.raises(EvidenceError, match='rejection-list-changed'):
            controller.check_settings(f'boundary-{batch}-preserved', value)


def boundary_ui(state_name):
    import hashlib
    ui, _, dialog, controls = feedback_ui()
    ui.api.RelationType.DESCRIBED_BY = 'described-by'
    inputs, status, logs = accessible_ui.BOUNDARY_STATES[state_name]
    rows = []
    for name, data in inputs:
        key = hashlib.sha256(name.encode() + b'\0' + data).hexdigest()[:16]
        subtitle = Node(accessible_ui.attachment_size(data), role='label')
        remove = Node(identity='feedback-remove-attachment-' + key)
        row = Node(name, identity='feedback-attachment-' + key, children=[subtitle, remove])
        row.relations = [SimpleNamespace(get_relation_type=lambda: 'described-by',
            get_n_targets=lambda: 1, get_target=lambda _, subtitle=subtitle: subtitle)]
        remove.action.do_action.side_effect = lambda _, row=row: (dialog.children.remove(row) or True)
        row.parent = dialog
        rows.append(row)
        dialog.children.append(row)
    dialog.children.append(Node(status, identity='feedback-status'))
    if not logs:
        next(node for node in dialog.children if node.identity == 'feedback-logs-row').name = 'No logs attached'
        controls['feedback-download-logs'].states.remove('visible')
    return ui, dialog, rows


@pytest.mark.parametrize('fault', ['', 'persistent', 'attachment'])
def test_exclude_logs_retries_transition_without_rereading_the_old_state(monkeypatch, fault):
    ui, dialog, _ = boundary_ui('cleared')
    logs = next(node for node in dialog.children if node.identity == 'feedback-logs-row')
    download = next(node for node in dialog.children if node.identity == 'feedback-download-logs')
    snapshot = ui.feedback_snapshot
    def read(*args, **kwargs):
        try:
            return snapshot(*args, **kwargs)
        finally:
            if not kwargs['attachment_state'][2] and fault != 'persistent':
                logs.name = 'No logs attached'
    reads = Mock(side_effect=read)
    monkeypatch.setattr(ui, 'feedback_snapshot', reads)

    def activate(identity):
        assert identity == 'feedback-toggle-logs'
        download.states.remove('visible')
        if fault == 'attachment':
            dialog.children.append(Node('Unknown', identity='feedback-attachment-unknown'))
    clicked = Mock(side_effect=activate)
    monkeypatch.setattr(ui, 'activate_id', clicked)

    def wait(predicate, code, **kwargs):
        assert code == 'boundary-exclude-logs'
        assert predicate() is None  # Old name, new download visibility.
        if fault == 'persistent':
            raise accessible_ui.UiError('ui:timeout:' + code)
        return predicate()
    monkeypatch.setattr(ui, 'wait', wait)
    if fault:
        with pytest.raises(accessible_ui.UiError, match='timeout|attachment-set'):
            ui.boundary_operation('boundary-exclude-logs')
        assert ui.input_uncertain
    else:
        assert ui.boundary_operation('boundary-exclude-logs') == accessible_ui.boundary_expected(
            'boundary-exclude-logs')
        assert [call.kwargs['attachment_state'] for call in reads.call_args_list] == [
            accessible_ui.BOUNDARY_STATES[state] for state in ('cleared', 'no-logs', 'no-logs')]
    clicked.assert_called_once_with('feedback-toggle-logs')


@pytest.mark.parametrize('name', ['No logs attached', 'private-name@example.invalid'])
def test_feedback_logs_diagnostics_include_only_closed_public_names(name):
    ui, dialog, _ = boundary_ui('cleared')
    next(node for node in dialog.children if node.identity == 'feedback-logs-row').name = name
    with pytest.raises(accessible_ui.UiError, match='ui:feedback-logs') as raised:
        ui.feedback_snapshot(attachment_state=accessible_ui.BOUNDARY_STATES['cleared'])
    notes = '\n'.join(raised.value.__notes__)
    assert 'diagnostic-logs.zip' in notes
    assert (name in notes) == (name == 'No logs attached')


@pytest.mark.parametrize('fault', ['', 'not-delivered', 'callback', 'result', 'preserved'])
def test_component_chooser_waits_for_new_delivery_before_identical_rejection(tmp_path, fault):
    from tests.support.feedback import install_component_chooser, add_component_attachments

    manifest = tmp_path / 'chooser-inputs.json'
    manifest.write_text(json.dumps([['long-name.txt'], ['hidden-name.txt']]), encoding='utf-8')
    delivery = manifest.with_suffix('.delivered')
    pending, received, operations, clicks = [], [], [], []
    gtk = SimpleNamespace()
    gio = SimpleNamespace(File=SimpleNamespace(new_for_path=lambda path: path))
    glib = SimpleNamespace(idle_add=lambda callback: pending.append(callback), SOURCE_REMOVE=False)
    install_component_chooser(manifest, gtk, gio, glib)

    def selected(chooser, _result):
        # The acknowledgement must follow the application callback, including
        # its failure; chooser dispatch alone never establishes a handoff.
        assert not delivery.exists() or delivery.read_text(encoding='ascii') == '1'
        if len(clicks) == 2 and fault == 'callback':
            raise RuntimeError('selection callback failed')
        files = chooser.open_multiple_finish(None)
        received.append(files.get_item(0))

    def activate(identity):
        assert identity == 'feedback-add-files'
        clicks.append(identity)
        chooser = gtk.FileDialog(title='Add feedback attachments')
        chooser.open_multiple(None, None, selected)

    def wait(predicate, code):
        assert code == 'component-chooser-delivered'
        # The first selection has no marker; the second has a stale marker.
        # Neither may be mistaken for delivery of the new selection.
        assert not predicate()
        if len(clicks) == 2 and fault == 'not-delivered':
            raise AssertionError('chooser delivery timed out')
        assert pending.pop(0)() is glib.SOURCE_REMOVE
        assert predicate()
        return True

    def boundary(operation):
        operations.append(operation)
        if not operation.endswith('-before'):
            assert len(received) == len(clicks), 'previous rejection accepted before new delivery'
        if operation == f'boundary-hidden-{fault}':
            raise accessible_ui.UiError('ui:feedback-control')
        # Both rejections deliberately have exactly the same public result.
        return accessible_ui.boundary_expected('boundary-hidden-result')

    ui = SimpleNamespace(boundary_operation=boundary, activate_id=activate,
                         wait=wait, input_uncertain=False)
    first = add_component_attachments(ui, 'name181', manifest)
    if fault:
        with pytest.raises((AssertionError, RuntimeError, accessible_ui.UiError)):
            add_component_attachments(ui, 'hidden', manifest)
    else:
        assert add_component_attachments(ui, 'hidden', manifest) == first
    assert len(clicks) == 2  # Delivery/read failures never replay input.
    if fault in ('not-delivered', 'callback'):
        assert delivery.read_text(encoding='ascii') == '1'
        assert operations[-1] == 'boundary-hidden-before'
        assert ui.input_uncertain
    else:
        assert delivery.read_text(encoding='ascii') == '2'
        assert received == ['long-name.txt', 'hidden-name.txt']
        assert operations[-1] == f'boundary-hidden-{fault or "preserved"}'


@pytest.mark.parametrize('state', sorted(accessible_ui.BOUNDARY_STATES))
@pytest.mark.parametrize('fault', ['', 'status', 'logs', 'extra', 'size', 'order'])
def test_boundary_public_observations_require_exact_state(state, fault):
    ui, dialog, rows = boundary_ui(state)
    if fault == 'status': dialog.children[-1].name = 'Reading attachments…'
    if fault == 'logs':
        next(node for node in dialog.children if node.identity == 'feedback-logs-row').name = 'Unexpected'
    if fault == 'extra': dialog.children.append(Node('Unknown', identity='feedback-attachment-unknown'))
    if fault == 'size':
        if not rows: return
        rows[0].children[0].name = '0 bytes'
    if fault == 'order':
        if len(rows) < 2: return
        first, second = dialog.children.index(rows[0]), dialog.children.index(rows[1])
        dialog.children[first], dialog.children[second] = rows[1], rows[0]
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.feedback_snapshot(attachment_state=accessible_ui.BOUNDARY_STATES[state])
    else:
        value = ui.feedback_snapshot(attachment_state=accessible_ui.BOUNDARY_STATES[state])
        assert value['include_logs'] == accessible_ui.BOUNDARY_STATES[state][2]
        assert value['status'] == accessible_ui.BOUNDARY_STATES[state][1]


@pytest.mark.parametrize('operation,state,result', [
    ('boundary-clear-count', 'count-rejected', 'cleared'),
    ('boundary-remove-total', 'total', 'maximum-again'),
    *[(key, *value) for key, value in accessible_ui.BOUNDARY_REMOVALS.items()]])
def test_boundary_removal_uses_owned_ids_and_independent_readback(operation, state, result):
    ui, _, _ = boundary_ui(state)
    assert ui.boundary_operation(operation) == accessible_ui.boundary_expected(operation)
    ui.feedback_snapshot(attachment_state=accessible_ui.BOUNDARY_STATES[result])


def test_chooser_selector_registration_and_prerequisites(monkeypatch):
    import check_e2e_file_chooser
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_file_chooser, 'smoke', run)
    assert check_e2e_file_chooser.main() == 0
    assert run.call_args.kwargs['file_chooser'] is True
    with pytest.raises(CommandError):
        smoke.main(file_chooser=True)
    with pytest.raises(CommandError, match='file-chooser-prerequisites'):
        smoke.main(file_chooser=True, feedback_read=True)


@pytest.mark.parametrize('fault', ['attachment-wrong-entry', 'attachment-details',
                                  'attachment-remove', 'attachment-remaining'])
def test_attachment_worker_stops_at_each_failed_proof(fault):
    test_chooser_worker_matches_plan_and_stops_at_failed_proof(fault, True)


def test_attachment_selector_registration_and_prerequisites(monkeypatch):
    import check_e2e_attachment_items
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_attachment_items, 'smoke', run)
    assert check_e2e_attachment_items.main() == 0
    assert run.call_args.kwargs['attachment_items'] is True
    with pytest.raises(CommandError, match='attachment-items-prerequisites'):
        smoke.main(attachment_items=True, file_chooser=True)


@pytest.mark.parametrize('fault', ['attachment-wrong-entry', 'attachment-details',
                                  'attachment-preview', 'attachment-preview-return'])
def test_preview_worker_stops_at_each_failed_proof(fault):
    test_chooser_worker_matches_plan_and_stops_at_failed_proof(fault, 2)


def test_preview_selector_registration_and_prerequisites(monkeypatch):
    import check_e2e_attachment_preview
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_attachment_preview, 'smoke', run)
    assert check_e2e_attachment_preview.main() == 0
    assert run.call_args.kwargs['attachment_preview'] is True
    with pytest.raises(CommandError, match='attachment-preview-prerequisites'):
        smoke.main(attachment_preview=True, attachment_items=True)


@pytest.mark.parametrize('fault', ['', 'offered', 'extra-action', 'label-action', 'foreign-remove', 'wrong-item', 'availability',
                                  'wrong-owner', 'stale', 'duplicate', 'missing'])
def test_preview_public_applicability_refuses_unbound_actions_and_wrong_rows(fault):
    ui, dialog, rows = attachment_ui()
    if fault == 'offered': rows[0].action = Node().action
    if fault == 'availability': rows[0].children[2].name = ''
    if fault == 'extra-action': rows[0].children.append(Node('Preview'))
    if fault == 'label-action': rows[0].children[1].action.get_action_name = lambda _: 'preview'
    if fault == 'foreign-remove':
        dialog.children.append(rows[0].children.pop(0))
    if fault == 'wrong-item': rows[0].name = 'Wrong.txt'
    if fault == 'wrong-owner': rows[0].get_process_id = lambda: 999
    if fault == 'stale': rows[0].states.add('defunct')
    if fault == 'duplicate': dialog.children.append(Node(identity=rows[0].identity))
    if fault == 'missing': dialog.children.remove(rows[0])
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.attachment_operation('attachment-preview')
    else:
        result = ui.attachment_operation('attachment-preview')
        assert result['preview'] == 'not-offered'
        assert ui.attachment_operation('attachment-preview-return')['items'] == result['items']
    for row in rows:
        for child in row.children:
            if child.action:
                child.action.do_action.assert_not_called()


def test_preview_comparison_uses_captured_immutable_list():
    from attachment_preview import journey
    controller = journey(SimpleNamespace(), Mock())
    value = {'ui': {'attachment': {'items': [['Second note.txt', '33 bytes'],
                                           ['Synthetic note.txt', '26 bytes']]}}}
    controller.check_settings('attachment-details', value)
    controller.check_settings('attachment-preview', value)
    controller.check_settings('attachment-preview-return', value)
    value['ui']['attachment']['items'].reverse()
    with pytest.raises(EvidenceError, match='preview-list-changed'):
        controller.check_settings('attachment-preview-return', value)


def test_attachment_comparison_uses_operations_with_distinct_invocation_names():
    from attachment_composition import AttachmentJourney
    from installed_journey import JourneyPlan
    plan = JourneyPlan(prefix='consumer', worker_mode='consumer', phases={}, screen_tags={
        'draft-files': 'ui:attachment-details', 'draft-preview': 'ui:attachment-preview',
        'rejected-before': 'ui:boundary-sixth-before', 'rejected-after': 'ui:boundary-sixth-preserved'})
    controller = AttachmentJourney(SimpleNamespace(), Mock(), plan)
    value = {'ui': {'attachment': {'items': [['Example.txt', '26 bytes']]}}}
    with pytest.raises(EvidenceError, match='preview-list-changed'):
        controller.check_settings('draft-preview', value)
    controller.check_settings('draft-files', value)
    controller.check_settings('draft-preview', value)
    with pytest.raises(EvidenceError, match='preview-replay'):
        controller.check_settings('draft-files', value)
    value = {'ui': {'boundary': {'items': [['Example.txt', '26 bytes']], 'include_logs': False}}}
    with pytest.raises(EvidenceError, match='rejection-list-changed'):
        controller.check_settings('rejected-after', value)
    controller.check_settings('rejected-before', value)
    controller.check_settings('rejected-after', value)
    value['ui']['boundary']['include_logs'] = True
    with pytest.raises(EvidenceError, match='rejection-list-changed'):
        controller.check_settings('rejected-after', value)


@pytest.mark.parametrize('fault', ['', 'guard-stage', 'stage', 'guard-cleanup', 'cleanup'])
def test_shared_attachment_fixtures_keep_identity_and_stop_on_failure(monkeypatch, fault):
    import synthetic_files
    events, controllers = [], []
    def create(transport, profile):
        controller = SimpleNamespace(profile=profile)
        def call(operation):
            events.append((profile, operation))
            if profile == 'sixth' and operation == fault:
                raise EvidenceError('synthetic-stop')
            return {'absent': True} if operation == 'cleanup' else {'profile': profile}
        controller.call = call
        controllers.append(controller)
        return controller
    monkeypatch.setattr(synthetic_files, 'SyntheticFiles', create)
    actions = synthetic_files.fixture_actions(('standard', 'sixth', 'total'))
    journey = SimpleNamespace(transport=object())
    phase, guarded = 'stage', []
    def guard():
        guarded.append(phase)
        if fault == 'guard-' + phase and guarded.count(phase) == 2:
            raise EvidenceError('synthetic-stop')
    if fault in ('guard-stage', 'stage'):
        with pytest.raises(EvidenceError, match='synthetic-stop'):
            actions['chooser-fixtures'](journey, guard)
        assert events == [('standard', 'stage')] + ([('sixth', 'stage')] if fault == 'stage' else [])
        assert journey.attachment_files == controllers
        with pytest.raises(EvidenceError, match='fixture-replay'):
            actions['chooser-fixtures'](journey, guard)
        return
    receipts = actions['chooser-fixtures'](journey, guard)
    assert list(receipts) == ['standard', 'sixth', 'total']
    assert journey.attachment_files == controllers
    phase = 'cleanup'
    if fault:
        with pytest.raises(EvidenceError, match='synthetic-stop'):
            actions['chooser-cleanup'](journey, guard)
        assert events[3:] == [('standard', 'cleanup')] + ([('sixth', 'cleanup')] if fault == 'cleanup' else [])
    else:
        assert actions['chooser-cleanup'](journey, guard) == {'owned_cleanup': True}
        assert events[3:] == [(profile, 'cleanup') for profile in receipts]


def test_shared_attachment_fixtures_refuse_invalid_sets_and_unprepared_cleanup():
    from synthetic_files import fixture_actions
    for profiles in ((), ('standard', 'standard'), ('unknown',), ['standard']):
        with pytest.raises(EvidenceError, match='files:profiles'):
            fixture_actions(profiles)
    with pytest.raises(EvidenceError, match='files:fixture-entry'):
        fixture_actions(('standard',))['chooser-cleanup'](SimpleNamespace(), Mock())


@pytest.mark.parametrize('boundaries', [False, True])
def test_preview_recorder_reaches_worker_with_plan_and_owned_actions(tmp_path, boundaries):
    from attachment_preview import PLAN, AttachmentPreviewJourney
    from file_chooser import stage_files, cleanup_files
    if boundaries:
        from attachment_boundaries import PLAN, AttachmentBoundariesJourney as AttachmentPreviewJourney
        from attachment_boundaries import stage_boundaries as stage_files, cleanup_boundaries as cleanup_files
    from installed_journey import record_installed_journey
    recorder = MagicMock(assertion=Mock())
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
                              verified=SimpleNamespace(inputs={}), guestfs=Mock(),
                              commands=Mock(), recorder=recorder)
    actions = ({'attachment-fixtures': stage_files, 'attachment-cleanup': cleanup_files} if boundaries else
               {'chooser-fixtures': stage_files, 'chooser-cleanup': cleanup_files})

    def worker(**options):
        controller = options['guarded_observe'].__self__
        assert type(controller) is AttachmentPreviewJourney
        assert controller.plan is PLAN and controller.actions == actions
        assert controller.before_preview is None
        assert options['validate'].__self__ is controller
        raise EvidenceError('synthetic-worker-stop')

    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        record_installed_journey(recorder, context, PLAN, actions=actions,
                                 journey_type=AttachmentPreviewJourney)
    context.run_worker.assert_called_once()
    assert recorder.step.return_value.__exit__.call_args.args[0] is EvidenceError
    recorder.assertion.assert_not_called()


@pytest.mark.parametrize('operation', sorted(accessible_ui.CHOOSER_OPERATIONS))
def test_chooser_real_controller_decodes_closed_evidence(operation):
    from ui_observations import UiObservations
    value = {'checked': operation}
    if operation in ('chooser-open', 'chooser-reopen'):
        value['provider'] = {'route': 'nautilus-portal', 'version': '50.1-1',
                             'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}
    if operation in ('chooser-attachments', 'chooser-preserved'):
        value['attachments'] = ['diagnostic-logs.zip', *accessible_ui.CHOOSER_FILES]
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', 'chooser': value}
    controller = UiObservations(Mock())
    controller.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert controller.observe(operation)['chooser'] == value
    assert controller.call.call_count == 1


def test_chooser_controller_rejects_partial_attachment_evidence():
    from ui_observations import UiObservations
    controller = UiObservations(Mock())
    result = {'operation': 'chooser-preserved', 'outcome': 'passed', 'interface': 'AT-SPI',
              'chooser': {'checked': 'chooser-preserved', 'attachments': ['diagnostic-logs.zip']}}
    controller.call = Mock(return_value=(json.dumps(result).encode(), []))
    with pytest.raises(EvidenceError, match='chooser-response'):
        controller.observe('chooser-preserved')


def test_validation_entry_reaches_worker_and_closes_recorder_on_failure(tmp_path):
    from parent_feedback_validation import PLAN, ValidationJourney, execute

    recorder = MagicMock(assertion=Mock())
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
                              verified=SimpleNamespace(inputs={}), guestfs=Mock(),
                              commands=Mock(), recorder=recorder)

    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert type(journey) is ValidationJourney
        assert journey.context is context and journey.plan is PLAN
        assert options['validate'].__self__ is journey
        assert options['authenticate'] is True and options['timeout'] == 1800
        assert journey.actions == {} and not journey.steps and not journey.states
        raise EvidenceError('synthetic-worker-stop')

    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        execute(recorder, context)
    context.credentials.provision.assert_called_once_with(
        context.lease, context.verified, tmp_path, context.guestfs, context.commands)
    context.run_worker.assert_called_once()
    recorder.step.assert_called_once_with('setup')
    assert recorder.step.return_value.__exit__.call_args.args[0] is EvidenceError
    recorder.assertion.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'feedback-state-empty', 'rejection-empty-send',
                                  'rejection-empty-read', 'text-body-first-selected',
                                  'text-reply-first-read', 'recovery-reopen',
                                  'review-valid', 'feedback-state-close'])
def test_complete_validation_worker_matches_plan_and_stops_at_failed_proof(fault):
    from parent_feedback_validation import PLAN
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type:' . $_[0]; }
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
    }, 'validation'); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    stages = list(PLAN.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    assert len(stages) == len(set(stages))
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')
    if not fault:
        assert not set(result['events']) & {'ctrl-shift-v', 'alt-tab', 'ctrl-shift-u', 'alt-f4'}
        operations = [PLAN.screen_tags[stage] for stage in stages]
        assert {operation for operation in operations if operation.endswith('-send')} == {
            'ui:rejection-empty-send'}
        assert operations.index('ui:rejection-empty-read') < operations.index('ui:feedback-state-reopen')


@pytest.mark.parametrize('stage,projection,validation', [
    ('feedback-state-whitespace', 'states-whitespace', 'none'),
    ('feedback-state-no-reply', 'states-no-reply', 'none'),
    ('feedback-state-malformed', 'states-malformed', 'none'),
    ('length-ascii-valid', 'length-ascii-5000', 'none'),
    ('length-mixed-valid', 'length-mixed-5000', 'none'),
    ('rejection-ascii-read', 'length-ascii-5001', 'length-invalid'),
    ('rejection-mixed-read', 'length-mixed-5001', 'length-invalid'),
    ('rejection-empty-read', 'initial-empty', 'body-required'),
    ('rejection-malformed-read', 'states-malformed', 'reply-invalid'),
    ('rejection-hidden-read', 'rejection-hidden', 'hidden-invalid'),
    ('rejection-complex-read', 'rejection-complex', 'format-invalid'),
    ('review-valid', 'synthetic-first', 'none'),
])
@pytest.mark.parametrize('fault', ['', 'projection', 'explanation', 'disabled'])
def test_validation_matrix_requires_each_public_result(tmp_path, stage, projection, validation, fault):
    from feedback_composition import FeedbackValidationJourney
    from installed_journey import JourneyPlan
    plan = JourneyPlan(prefix='validation-library', worker_mode='fixture', phases={}, screen_tags={
        stage: 'ui:' + ('feedback-state-valid' if stage == 'review-valid' else stage)})
    journey = FeedbackValidationJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    value = dict(draft=projection, validation=validation, send_enabled=True,
                 attachments=['diagnostic-logs.zip'], collection='ready', controls='ready')
    if fault == 'projection':
        value['draft'] = 'synthetic-first' if projection != 'synthetic-first' else 'initial-empty'
    elif fault == 'explanation':
        value['validation'] = 'none' if validation != 'none' else 'body-required'
    elif fault == 'disabled':
        value['send_enabled'] = False
    if fault:
        with pytest.raises(EvidenceError, match='matrix-result'):
            journey.check_settings(stage, {'ui': {'feedback_state': value}})
    else:
        journey.check_settings(stage, {'ui': {'feedback_state': value}})
        with pytest.raises(EvidenceError, match='matrix-replay'):
            journey.check_settings(stage, {'ui': {'feedback_state': value}})


def test_validation_preservation_requires_earlier_evidence(tmp_path):
    from feedback_composition import FeedbackValidationJourney
    from installed_journey import JourneyPlan
    plan = JourneyPlan(prefix='validation-library', worker_mode='fixture', phases={}, screen_tags={
        stage: 'ui:' + stage for stage in (
            'rejection-complex-read', 'rejection-reopen', 'rejection-reopened-read',
            'feedback-draft', 'feedback-privacy-returned', 'feedback-draft-reread', 'feedback-draft-reopen')})
    journey = FeedbackValidationJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    for stage in ('ready', 'setup-detached'):
        journey.check_settings(stage, {})
    assert not journey.states and not journey.windows and journey.draft is None
    value = dict(draft='rejection-complex', validation='none', send_enabled=True,
                 attachments=['diagnostic-logs.zip'], collection='ready', controls='ready')
    with pytest.raises(EvidenceError, match='matrix-preservation'):
        journey.check_settings('rejection-reopen', {'ui': {'feedback_state': value}})
    rejected = dict(value, validation='format-invalid')
    journey.check_settings('rejection-complex-read', {'ui': {'feedback_state': rejected}})
    journey.check_settings('rejection-reopen', {'ui': {'feedback_state': value}})
    journey.check_settings('rejection-reopened-read', {'ui': {'feedback_state': rejected}})
    draft = dict(draft='synthetic-first', validation='none', attachments=['diagnostic-logs.zip'],
                 collection='ready', controls='ready')
    with pytest.raises(EvidenceError, match='preserved-draft'):
        journey.check_settings('feedback-draft-reopen', {'ui': {'feedback': draft}})
    journey.check_settings('feedback-draft', {'ui': {'feedback': draft}})
    for stage in ('feedback-privacy-returned', 'feedback-draft-reread', 'feedback-draft-reopen'):
        journey.check_settings(stage, {'ui': {'feedback': draft}})


def rejection_ui(case):
    ui, parent, dialog, controls = feedback_ui()
    projection, _ = accessible_ui.REJECTION_CASES[case]
    for binding in accessible_ui.FEEDBACK_PROJECTIONS[projection]:
        identity, value = accessible_ui.TEXT_VALUES[binding]
        controls[identity].text.count = len(value)
        controls[identity].text.value = value
    ui.api.Text.get_text = Mock(side_effect=lambda text, start, end: text.value[start:end])
    ui.api.Text.get_character_at_offset = Mock(side_effect=lambda text, offset: ord(text.value[offset]))
    ui.api.Text.get_attribute_run = Mock(side_effect=lambda text, offset, defaults: (
        ({'weight': '400', 'style': 'normal', 'underline': 'none', 'strikethrough': 'false'}
         if projection.startswith('length-') else
         {'weight': '700', 'style': 'italic', 'underline': 'single', 'strikethrough': 'true'}),
        offset, offset + 1))
    ui.activate_id = Mock()
    return ui, parent, dialog, controls


@pytest.mark.parametrize('case', accessible_ui.REJECTION_CASES)
@pytest.mark.parametrize('fault', ['', 'body', 'reply', 'duplicate', 'owner', 'stale',
                                  'disabled', 'uncertain', 'wrong-entry'])
def test_invalid_only_send_requires_exact_fresh_owned_invalid_fixture(case, fault):
    ui, parent, dialog, controls = rejection_ui(case)
    if fault == 'body':
        controls['feedback-editor-input'].text.count += 10
    elif fault == 'reply':
        controls['feedback-reply-email'].text.count += 1
    elif fault == 'duplicate':
        dialog.children.append(Node(identity='feedback-send'))
    elif fault == 'owner':
        ui.api.get_desktop(0).identity = 'other.app'
    elif fault == 'stale':
        controls['feedback-editor-input'].states.add('defunct')
    elif fault == 'disabled':
        controls['feedback-send'].states.discard('sensitive')
    elif fault == 'uncertain':
        ui.input_uncertain = True
    elif fault == 'wrong-entry':
        parent.children.clear()
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.reject_invalid_feedback(case)
        ui.activate_id.assert_not_called()
    else:
        ui.reject_invalid_feedback(case)
        ui.activate_id.assert_called_once_with('feedback-send')


def test_rejection_refuses_valid_input_and_missing_format_at_last_line():
    ui, _, _, controls = rejection_ui('complex')
    with pytest.raises(accessible_ui.UiError, match='valid-refused'):
        ui.reject_invalid_feedback('valid')
    ui.api.Text.get_attribute_run.side_effect = lambda text, offset, defaults: (
        {'weight': '700', 'style': 'italic', 'underline': 'single',
         'strikethrough': 'false' if offset == len(accessible_ui.COMPLEX_BODY) - 1 else 'true'},
        offset, offset + 1)
    with pytest.raises(accessible_ui.UiError, match='format-proof'):
        ui.reject_invalid_feedback('complex')
    ui.activate_id.assert_not_called()
    ui, _, _, controls = rejection_ui('hidden')
    controls['feedback-editor-input'].text.value = 'a b'
    with pytest.raises(accessible_ui.UiError, match='nonempty-draft'):
        ui.reject_invalid_feedback('hidden')
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('attribute', ['weight', 'style', 'underline', 'strikethrough'])
@pytest.mark.parametrize('offset', [0, 1200, 2398])
def test_rejection_reports_missing_format_without_exposing_text(attribute, offset):
    ui, _, _, _ = rejection_ui('complex')
    read = ui.api.Text.get_attribute_run.side_effect
    def missing(text, position, defaults):
        attributes, first, last = read(text, position, defaults)
        if position == offset:
            attributes.pop(attribute)
        return attributes, first, last
    ui.api.Text.get_attribute_run.side_effect = missing
    with pytest.raises(accessible_ui.UiError) as error:
        ui.reject_invalid_feedback('complex')
    assert str(error.value) == f'ui:rejection-format-proof:{attribute}:{offset}'
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('boundary', [1, 2, 1200, 2398, 2399])
def test_rejection_covers_public_runs_without_skipping_unproven_characters(boundary):
    ui, _, _, _ = rejection_ui('complex')
    read = ui.api.Text.get_attribute_run.side_effect
    def ranges(text, offset, defaults):
        attributes, _, _ = read(text, offset, defaults)
        if offset < boundary:
            return attributes, 0, boundary
        attributes['strikethrough'] = 'false'
        return attributes, boundary, len(accessible_ui.COMPLEX_BODY)
    ui.api.Text.get_attribute_run.side_effect = ranges
    if boundary == len(accessible_ui.COMPLEX_BODY):
        ui.reject_invalid_feedback('complex')
        ui.api.Text.get_attribute_run.assert_called_once()
        ui.activate_id.assert_called_once_with('feedback-send')
    else:
        with pytest.raises(accessible_ui.UiError, match='format-proof:strikethrough'):
            ui.reject_invalid_feedback('complex')
        assert ui.api.Text.get_attribute_run.call_args.args[1] == boundary + boundary % 2
        ui.activate_id.assert_not_called()


def test_rejection_values_stay_invalid_under_maintained_transport_limits():
    from common.oh_no_parent_control_ui import feedback_transport as transport
    assert accessible_ui.TEXT_VALUES['body-hidden'][1] == 'a\x01b'
    assert (transport.MAX_MESSAGE_UTF16, transport.MAX_HTML_UTF16) == (5000, 50000)
    html = '<p><strong><em><u><s>x</s></u></em></strong></p>' * accessible_ui.COMPLEX_LINES
    assert len(html) == 48 * accessible_ui.COMPLEX_LINES > transport.MAX_HTML_UTF16
    for case, (projection, explanation) in accessible_ui.REJECTION_CASES.items():
        body, reply = [accessible_ui.TEXT_VALUES[binding][1]
                       for binding in accessible_ui.FEEDBACK_PROJECTIONS[projection]]
        units = len(body.encode('utf-16-le')) // 2
        if explanation == 'length-invalid':
            assert units == transport.MAX_MESSAGE_UTF16 + 1
        else:
            assert units <= transport.MAX_MESSAGE_UTF16
        error = transport.validation_error(body, reply, '1.2', html if projection == 'rejection-complex' else '')
        assert accessible_ui.FEEDBACK_VALIDATION[error] == explanation


def test_rejection_waits_for_the_independent_public_result_without_replaying_send():
    ui, _, _, _ = rejection_ui('empty')
    initial = ui.feedback_snapshot('initial-empty', states=True)
    rejected = {**initial, 'validation': 'body-required'}
    ui.feedback_snapshot = Mock(side_effect=[initial, rejected])
    ui.timeout = 1
    assert ui.rejection_operation('rejection-empty-read') == rejected
    assert ui.feedback_snapshot.call_count == 2
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('case', accessible_ui.REJECTION_CASES)
def test_rejection_requires_independent_explanation_and_decodes_closed_result(case):
    from ui_observations import UiObservations
    ui, _, dialog, _ = rejection_ui(case)
    with pytest.raises(accessible_ui.UiError, match='explanation'):
        ui.rejection_operation(f'rejection-{case}-read')
    projection, explanation = accessible_ui.REJECTION_CASES[case]
    label = next(text for text, name in accessible_ui.FEEDBACK_VALIDATION.items() if name == explanation)
    dialog.children.append(Node(label, identity='feedback-status'))
    state = ui.rejection_operation(f'rejection-{case}-read')
    reader = UiObservations(Mock())
    response = {'operation': f'rejection-{case}-read', 'outcome': 'passed', 'interface': 'AT-SPI',
                'feedback_state': state}
    reader.call = Mock(return_value=(json.dumps(response).encode(), []))
    assert reader.observe(response['operation']) == response
    state['validation'] = 'none'
    reader.call.return_value = (json.dumps(response).encode(), [])
    with pytest.raises(EvidenceError, match='rejection-response'):
        reader.observe(response['operation'])
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'rejection-empty-read', 'rejection-hidden-input-read',
                                  'text-duplicate-body-complex-150-select',
                                  'text-duplicate-body-complex-selected',
                                  'text-duplicate-body-complex-read',
                                  'rejection-format-strike-apply', 'rejection-complex-read'])
def test_rejection_worker_stops_without_replay_or_followup_input(fault):
    from feedback_rejection import PLAN, STAGES
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type:' . $_[0]; }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_states::run_rejection(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    assert len(result['stages']) == len(set(result['stages']))
    assert set(result['stages']) <= set(PLAN.screen_tags)
    stages = ['parent-selected', *STAGES]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')
    if not fault:
        caret = result['events'].index('rejection-hidden-caret')
        assert result['events'][caret + 1:caret + 5] == [
            'ctrl-shift-u', 'type:0001', 'ret', 'rejection-hidden-input-read']
        assert result['events'].count('ctrl-shift-v') == 4
        assert result['events'].count('ctrl-c') == 4
        assert 'type:' + accessible_ui.COMPLEX_BODY not in result['events']
        for binding in (value for value in accessible_ui.TEXT_DUPLICATIONS
                        if value.startswith('body-complex')):
            selected = result['events'].index('text-duplicate-' + binding + '-selected')
            assert result['events'][selected + 1:selected + 6] == [
                'ctrl-c', 'ctrl-end', 'ret', 'ctrl-shift-v', 'text-duplicate-' + binding + '-read']


@pytest.mark.parametrize('fault', ['', 'unfocused', 'wrong-source', 'selection', 'refused', 'uncertain'])
@pytest.mark.parametrize('binding', ['body-complex-150', 'body-ascii-5000-double-1'])
def test_duplicate_source_and_exact_selection_guard_copy(fault, binding):
    ui, _, _, controls = feedback_ui()
    node = controls['feedback-editor-input']
    value = accessible_ui.TEXT_VALUES[accessible_ui.TEXT_DUPLICATIONS[binding]][1]
    prefix = 'text-duplicate-' + binding
    node.text.count = len(value) + 1
    node.states.add('focused')
    ui.api.Text.get_text = Mock(return_value=value + '\n')
    ui.api.Text.get_n_selections = Mock(return_value=1)
    ui.api.Text.set_selection = Mock(return_value=True)
    ui.api.Text.get_selection = Mock(return_value=SimpleNamespace(start_offset=0, end_offset=len(value)))
    if fault == 'unfocused':
        node.states.remove('focused')
    elif fault == 'wrong-source':
        ui.api.Text.get_text.return_value = 'y' * len(value) + '\n'
    elif fault == 'selection':
        ui.api.Text.get_n_selections.return_value = 0
    elif fault == 'refused':
        ui.api.Text.set_selection.return_value = False
    elif fault == 'uncertain':
        ui.input_uncertain = True
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.duplicate_text_operation(prefix + '-select')
        assert ui.api.Text.set_selection.call_count == (1 if fault == 'refused' else 0)
    else:
        ui.duplicate_text_operation(prefix + '-select')
        ui.api.Text.set_selection.assert_called_once_with(node.text, 0, 0, len(value))
        ui.duplicate_text_operation(prefix + '-selected')
        ui.api.Text.get_selection.return_value.end_offset += 1
        with pytest.raises(accessible_ui.UiError, match='duplicate-selection'):
            ui.duplicate_text_operation(prefix + '-selected')


def test_rejection_selector_preserves_guarded_envelope(monkeypatch):
    import check_e2e_feedback_rejection
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_feedback_rejection, 'smoke', run)
    assert check_e2e_feedback_rejection.main() == 0
    assert run.call_args.kwargs['feedback_rejection'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_rejection=True)
    with pytest.raises(CommandError, match='feedback-rejection-prerequisites'):
        smoke.main(feedback_rejection=True, feedback_states=True)


@pytest.mark.parametrize('family', ['ascii', 'mixed'])
def test_length_valid_boundary_cannot_reach_send_even_with_invalid_case_name(family):
    ui, _, _, controls = rejection_ui(family)
    value = accessible_ui.TEXT_VALUES[f'body-{family}-5000'][1]
    body = controls['feedback-editor-input'].text
    body.value, body.count = value, len(value)
    assert len(value.encode('utf-16-le')) // 2 == 5000
    ui.length_operation(f'length-{family}-refusal')
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('family', ['ascii', 'mixed'])
def test_length_wrong_entry_operation_refuses_without_input(family):
    ui, parent, _, _ = rejection_ui(family)
    parent.children.clear()
    assert ui.length_operation(f'length-{family}-wrong-entry') is None
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('family,fault', [
    (family, fault) for family in ('ascii', 'mixed')
    for fault in ('same-length', 'newline', 'formatted',
                  *(('utf16-offset',) if family == 'mixed' else ()))])
def test_length_invalid_guard_proves_all_scalars_and_normal_attributes(family, fault):
    ui, _, _, controls = rejection_ui(family)
    body = controls['feedback-editor-input'].text
    if fault == 'same-length':
        body.value = 'y' + body.value[1:]
    elif fault == 'newline':
        body.value += '\n\n'
        body.count += 2
    elif fault == 'utf16-offset':
        # Public offsets count Unicode scalars, never surrogate code units.
        body.count = len(body.value.encode('utf-16-le')) // 2 + 1
        body.value += '\nx'
    else:
        ui.api.Text.get_attribute_run.side_effect = lambda text, offset, defaults: (
            {'weight': '700', 'style': 'normal', 'underline': 'none', 'strikethrough': 'false'},
            0, body.count)
    with pytest.raises(accessible_ui.UiError):
        ui.reject_invalid_feedback(family)
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('family', ['ascii', 'mixed'])
def test_length_reopen_decoder_and_journey_require_independent_prior_result(tmp_path, family):
    from feedback_length import FeedbackLengthJourney
    from ui_observations import UiObservations
    ui, _, _, _ = rejection_ui(family)
    state = ui.feedback_snapshot(f'length-{family}-5001', states=True)
    response = {'operation': f'length-{family}-reopen', 'outcome': 'passed',
                'interface': 'AT-SPI', 'feedback_state': state}
    reader = UiObservations(Mock())
    reader.call = Mock(return_value=(json.dumps(response).encode(), []))
    assert reader.observe(response['operation']) == response
    frozen = FeedbackStateObservation.from_value(state)
    with pytest.raises(FrozenInstanceError):
        frozen.draft = 'other'
    journey = FeedbackLengthJourney(SimpleNamespace(directory=tmp_path), Mock())
    with pytest.raises(EvidenceError, match='independent-entry'):
        journey.check_settings(response['operation'], {'ui': response})
    rejected = {**response, 'feedback_state': {**state, 'validation': 'length-invalid'}}
    journey.check_settings(f'rejection-{family}-read', {'ui': rejected})
    journey.check_settings(response['operation'], {'ui': response})
    journey.check_settings(f'rejection-{family}-reopened-read', {'ui': rejected})
    state['send_enabled'] = False
    reader.call.return_value = (json.dumps(response).encode(), [])
    with pytest.raises(EvidenceError, match='length-response'):
        reader.observe(response['operation'])


@pytest.mark.parametrize('fault', ['', 'source', 'focus', 'caret', 'uncertain'])
@pytest.mark.parametrize('kind', ['scalar', 'suffix'])
def test_scalar_append_requires_exact_source_and_public_character_caret(fault, kind):
    ui, _, _, controls = rejection_ui('mixed')
    node = controls['feedback-editor-input']
    binding = 'body-mixed-5001' if kind == 'scalar' else 'body-mixed-5001-base'
    sources = accessible_ui.TEXT_SCALARS if kind == 'scalar' else accessible_ui.TEXT_SUFFIXES
    value = accessible_ui.TEXT_VALUES[sources[binding][0]][1]
    operation = getattr(ui, kind + '_text_operation')
    node.text.value, node.text.count = value, len(value)
    node.states.add('focused')
    ui.api.Text.get_caret_offset = Mock(return_value=len(value))
    if fault == 'source':
        node.text.value = 'y' * len(value)
    elif fault == 'focus':
        node.states.remove('focused')
    elif fault == 'caret':
        ui.api.Text.get_caret_offset.return_value -= 1
    elif fault == 'uncertain':
        ui.input_uncertain = True
    if fault:
        with pytest.raises(accessible_ui.UiError):
            operation(f'text-{kind}-{binding}-caret')
    else:
        operation(f'text-{kind}-{binding}-caret')
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'text-body-ascii-5000-seed-read',
    *(f'text-duplicate-body-ascii-5000-double-{step}-{action}'
      for step in range(1, 5) for action in ('select', 'selected', 'read')),
    'text-suffix-body-ascii-5000-caret', 'text-suffix-body-ascii-5000-read', 'length-ascii-refusal',
    'rejection-ascii-read', 'length-ascii-reopen', 'text-scalar-body-mixed-5000-caret',
    'text-scalar-body-mixed-5001-read', 'rejection-mixed-reopened-read'])
def test_length_worker_matches_controller_and_stops_at_failed_proof(fault):
    from feedback_length import STAGES, PLAN
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type:' . $_[0]; }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_states::run_length(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    stages = ['parent-selected', *STAGES]
    assert len(stages) == len(set(stages))
    assert set(stages) <= set(PLAN.screen_tags)
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')
    if not fault:
        assert result['events'].count('ctrl-c') == 16
        assert result['events'].count('ctrl-shift-v') == 16
        typed = [event.removeprefix('type:') for event in result['events'] if event.startswith('type:')]
        assert sum(value.count('x') for value in typed) == 1278
        assert max(map(len, typed)) == 312
        for binding, (seed, *copies) in accessible_ui.TEXT_REPETITIONS.items():
            assert 'type:' + accessible_ui.TEXT_VALUES[seed][1] in result['events']
            assert 'type:' + accessible_ui.TEXT_VALUES[binding][1] not in result['events']
            for target in copies:
                prefix = 'text-duplicate-' + target
                selected = result['events'].index(prefix + '-selected')
                assert result['events'][selected + 1:selected + 5] == [
                    'ctrl-c', 'ctrl-end', 'ctrl-shift-v', prefix + '-read']
            caret = result['events'].index(f'text-suffix-{binding}-caret')
            assert result['events'][caret + 1:caret + 3] == [
                'type:' + accessible_ui.TEXT_SUFFIXES[binding][1], f'text-suffix-{binding}-read']
        for units in (5000, 5001):
            caret = result['events'].index(f'text-scalar-body-mixed-{units}-caret')
            assert result['events'][caret + 1:caret + 5] == [
                'ctrl-shift-u', 'type:1f600', 'ret', f'text-scalar-body-mixed-{units}-read']


def test_length_selector_preserves_guarded_envelope(monkeypatch):
    import check_e2e_feedback_length
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_feedback_length, 'smoke', run)
    assert check_e2e_feedback_length.main() == 0
    assert run.call_args.kwargs['feedback_length'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_length=True)
    with pytest.raises(CommandError, match='feedback-length-prerequisites'):
        smoke.main(feedback_length=True, feedback_rejection=True)


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


@pytest.mark.parametrize('boundary', ['entry', 'proof', 'metadata'])
@pytest.mark.parametrize('failure', ['transient', 'incomplete', 'wrong-owner'])
def test_window_viewer_launch_retries_only_complete_reads(monkeypatch, boundary, failure):
    ui = ui_for(Node())
    ui.timeout = 1 if failure == 'transient' else 0
    ui.handle_system_prompt = Mock()
    ui.existing_window_active = Mock(return_value=Node())
    ui.license_viewer_snapshot = Mock(return_value=(None, None, None))
    proof = {'binding': 'viewer', 'pid': 123, 'endpoint': [':1.2', '/viewer'], 'active': True}
    metadata = {'version': '50.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}
    ui.window_switch_proof = Mock(return_value=proof)
    ui.license_provider_metadata = Mock(return_value=metadata)
    ui.license_content = Mock(return_value=True)
    observer, value = {
        'entry': (ui.license_viewer_snapshot, (None, None, None)),
        'proof': (ui.window_switch_proof, proof),
        'metadata': (ui.license_provider_metadata, metadata),
    }[boundary]
    error = accessible_ui.UiError('ui:document-owner' if failure == 'wrong-owner'
                                  else 'ui:incomplete-tree')
    observer.side_effect = [error, value] if failure == 'transient' else error
    launch = Mock()
    monkeypatch.setattr(accessible_ui.subprocess, 'run', launch)
    monkeypatch.setattr(accessible_ui.time, 'sleep', Mock())
    if failure == 'transient':
        result = ui.run('switch-viewer-launch', '1.1')
        assert result['window'] == proof and result['provider'] == metadata
        assert observer.call_count == 2
        assert ui.incomplete_observations
    else:
        with pytest.raises(accessible_ui.UiError, match=(
                'document-owner' if failure == 'wrong-owner' else 'timeout:')):
            ui.run('switch-viewer-launch', '1.1')
        assert observer.call_count == 1
    assert launch.call_count == (0 if boundary == 'entry' and failure != 'transient' else 1)
    if launch.called:
        assert launch.call_args.args[0] == [
            '/usr/bin/systemd-run', '--user', '--quiet', '--collect',
            '--service-type=exec', '/usr/bin/gnome-text-editor', '--new-window',
            '/usr/share/oh-no-parent-control/LICENSE']
    if boundary == 'proof' and failure != 'transient':
        assert ui.input_uncertain
        with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
            ui.run('switch-viewer-launch', '1.1')
        assert launch.call_count == 1


@pytest.mark.parametrize('boundary', ['source', 'target', 'proof'])
@pytest.mark.parametrize('failure', ['transient', 'incomplete', 'wrong-owner'])
def test_window_switch_readiness_retries_only_complete_reads(monkeypatch, boundary, failure):
    ui = ui_for(Node())
    ui.timeout = 1 if failure == 'transient' else 0
    proof = {'binding': 'viewer', 'pid': 123, 'endpoint': [':1.2', '/viewer'], 'active': False}
    source = Node()
    reads = []
    error = accessible_ui.UiError('ui:document-owner' if failure == 'wrong-owner'
                                  else 'ui:incomplete-tree')
    failed = False

    def read(stage, value):
        nonlocal failed
        reads.append(stage)
        if stage == boundary and (not failed or failure != 'transient'):
            failed = True
            raise error
        return value

    ui.existing_window_active = lambda binding: read(
        'source' if binding == 'feedback' else 'target', source if binding == 'feedback' else None)
    ui.window_switch_proof = lambda binding, **kwargs: read('proof', proof)
    launch = Mock()
    monkeypatch.setattr(accessible_ui.subprocess, 'run', launch)
    monkeypatch.setattr(accessible_ui.time, 'sleep', Mock())
    if failure == 'transient':
        assert ui.window_switch_operation('switch-viewer-ready') == proof
        assert reads[-3:] == ['source', 'target', 'proof']
        assert reads.count('source') == 2
        assert ui.incomplete_observations
    else:
        with pytest.raises(accessible_ui.UiError, match=(
                'document-owner' if failure == 'wrong-owner' else 'timeout:')):
            ui.window_switch_operation('switch-viewer-ready')
        assert reads.count('source') == 1
    launch.assert_not_called()
    assert not ui.input_uncertain


def test_window_viewer_launch_failure_never_replays_command(monkeypatch):
    ui = ui_for(Node())
    ui.existing_window_active = Mock(return_value=Node())
    ui.license_viewer_snapshot = Mock(return_value=(None, None, None))
    ui.license_content = Mock()
    launch = Mock(side_effect=accessible_ui.subprocess.TimeoutExpired('viewer', 15))
    monkeypatch.setattr(accessible_ui.subprocess, 'run', launch)
    with pytest.raises(accessible_ui.subprocess.TimeoutExpired):
        ui.window_switch_operation('switch-viewer-launch')
    with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
        ui.window_switch_operation('switch-viewer-launch')
    launch.assert_called_once()
    ui.license_content.assert_not_called()


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
    from common.oh_no_parent_control_ui import messages
    suffix = getattr(messages, method.body[0].value.right.attr).source
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


def test_reset_selector_owned_envelope_and_explicit_empty_expectation(tmp_path, monkeypatch):
    import check_e2e_feedback_reset as check
    from feedback_reset import PLAN, FeedbackResetJourney, EMPTY_DRAFT
    from parent_setup_qualification import FeedbackResetQualification, KioskEntryQualification
    run = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == 0
    assert run.call_args.kwargs['feedback_reset'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_reset=True)
    for conflict in ('feedback_privacy', 'feedback_read', 'app_restart', 'attachment_items'):
        with pytest.raises(CommandError, match='feedback-reset-prerequisites'):
            smoke.main(feedback_reset=True, **{conflict: True})
    context = SimpleNamespace(directory=tmp_path)
    journey = FeedbackResetQualification.journey(context, Mock())
    assert type(journey) is FeedbackResetJourney and journey.plan is PLAN
    from app_snapshot import snapshot_name
    version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
    assert context.installed_snapshot == snapshot_name(version)
    assert FeedbackResetQualification.finalize is KioskEntryQualification.finalize
    assert FeedbackResetQualification.prepare_context is KioskEntryQualification.prepare_context
    ui, _, _, _ = synthetic_feedback_ui()
    nonempty = {'ui': {'feedback': ui.feedback_snapshot('synthetic-first')}}
    empty = {'ui': {'feedback': dict(draft='initial-empty', attachments=['diagnostic-logs.zip'],
                                    collection='ready', validation='none', controls='ready')}}
    with pytest.raises(EvidenceError, match='missing-entry'):
        journey.check_settings('feedback-reopen', empty)
    journey.check_settings('feedback-draft', nonempty)
    journey.check_settings('feedback-draft-reread', nonempty)
    with pytest.raises(EvidenceError, match='empty-draft'):
        journey.check_settings('feedback-reopen', nonempty)
    journey.check_settings('feedback-reopen', empty)
    journey.check_settings('feedback-reread', empty)
    assert FeedbackObservation.from_value(empty['ui']['feedback']) == EMPTY_DRAFT
    empty['ui']['feedback']['attachments'].append('stale.txt')
    with pytest.raises(EvidenceError, match='feedback-response'):
        journey.check_settings('feedback-reread', empty)


def test_reset_actual_worker_sequence_and_every_refusal(monkeypatch):
    from tests.support.perl import run_perl
    from tests.support.perl import ALLOWANCE_WORKER
    from feedback_reset import PLAN
    from ui_observations import OPERATION_LABELS
    script = ALLOWANCE_WORKER.replace('onpc_set_allowance', 'onpc_feedback_privacy')
    script = script.replace('onpc_feedback_privacy::run(', 'onpc_feedback_privacy::run_reset(')
    script = script.replace('sub record_info { }',
                            "sub record_info { }\nsub type_string { push @main::events, ['text', @_]; }")
    monkeypatch.setenv('ONPC_TEST_REFUSE', '')
    success = json.loads(run_perl(script).stdout)
    assert success['ok'], success['error']
    stages = list(PLAN.screen_tags)
    assert [event[1] for event in success['events'] if event[0] == 'stage'] == stages
    assert all(tag.removeprefix('ui:') in OPERATION_LABELS for tag in PLAN.screen_tags.values())
    assert sum(event[:2] == ['key', 'alt-f4'] for event in success['events']) == 2
    assert sum(event[0] == 'text' for event in success['events']) == 2
    for stage in stages:
        monkeypatch.setenv('ONPC_TEST_REFUSE', stage)
        result = json.loads(run_perl(script).stdout)
        assert not result['ok'] and 'fixture:refused' in result['error']
        boundary = success['events'].index(['stage', stage])
        assert result['events'] == success['events'][:boundary + 1]


def test_reset_recorder_reaches_real_custom_controller(tmp_path):
    from feedback_reset import PLAN, FeedbackResetJourney
    from installed_journey import record_installed_journey
    recorder = MagicMock(assertion=Mock())
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
                              verified=SimpleNamespace(inputs={}), guestfs=Mock(),
                              commands=Mock(), recorder=recorder)

    def worker(**options):
        controller = options['guarded_observe'].__self__
        assert type(controller) is FeedbackResetJourney
        assert controller.plan is PLAN and controller.actions == {} and controller.draft is None
        assert options['validate'].__self__ is controller
        raise EvidenceError('synthetic-worker-stop')

    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        record_installed_journey(recorder, context, PLAN, actions={},
                                 journey_type=FeedbackResetJourney)
    context.run_worker.assert_called_once()
    assert recorder.step.return_value.__exit__.call_args.args[0] is EvidenceError
    recorder.assertion.assert_not_called()


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


@pytest.mark.parametrize('fault', [None, 'absent', 'wrong-owner', 'duplicate',
                                 'disabled', 'no-action', 'ambiguous-action', 'private-draft'])
def test_parent_report_reads_exact_automatic_draft_and_action_availability_without_input(fault):
    ui, parent, dialog, controls = feedback_ui()
    privacy = Node(identity='feedback-privacy-link')
    dialog.children.append(privacy); privacy.parent = dialog
    body = accessible_ui.TEXT_VALUES['body-rule-error'][1]
    editor = controls['feedback-editor-input']
    editor.text.count = len(body)
    ui.api.Text.get_text = Mock(return_value='private' if fault == 'private-draft' else body)
    if fault == 'absent': parent.children.clear()
    elif fault == 'wrong-owner': ui.api.get_desktop(0).identity = 'foreign.application'
    elif fault == 'duplicate': dialog.children.append(Node(identity='feedback-privacy-link'))
    elif fault == 'disabled': privacy.states.remove('sensitive')
    elif fault == 'no-action': privacy.get_action_iface = lambda: None
    elif fault == 'ambiguous-action': privacy.action.get_n_actions = lambda: 2
    if fault:
        with pytest.raises(accessible_ui.UiError): ui.parent_report_operation('parent-report-read')
    else:
        assert ui.parent_report_operation('parent-report-read')['draft'] == 'parent-rule-error'
    for node in (*controls.values(), privacy):
        node.action.do_action.assert_not_called()


def test_parent_report_wrong_entry_refuses_close_and_never_opens_feedback():
    ui, parent, dialog, controls = feedback_ui()
    parent.children.clear(); parent.states.add('active')
    assert ui.parent_report_operation('parent-report-refused') == {'refusal': 'absent'}
    for node in controls.values(): node.action.do_action.assert_not_called()


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
    ui.api.Text.get_character_at_offset = Mock(side_effect=lambda text, offset: ord(value[offset]))
    assert ui.read_synthetic_text(binding) == {
        'binding': binding, 'exact': True, 'length': len(value)}
    if binding == 'body-hidden':
        ui.api.Text.get_text.assert_not_called()
        assert ui.api.Text.get_character_at_offset.call_count == len(value)
    elif value:
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


@pytest.mark.parametrize('anchor', [False, True])
@pytest.mark.parametrize('fault', ['query', 'incomplete', 'persistent', 'disabled'])
def test_text_focus_preflight_retries_reads_without_replaying_input(anchor, fault):
    ui, _, _, controls = feedback_ui()
    ui.timeout = .2
    ui.query_errors = (LookupError,)
    read = ui.text_recipient
    calls = []
    def recipient(identity, **kwargs):
        calls.append(identity)
        if len(calls) == 1 or fault == 'persistent':
            if fault == 'disabled': raise accessible_ui.UiError('ui:text-disabled')
            if fault == 'incomplete': raise accessible_ui.UiError('ui:incomplete-tree')
            raise LookupError('transient public object')
        return read(identity, **kwargs)
    ui.text_recipient = recipient
    operation = (lambda: ui.text_operation('text-reply-first-anchor')) if anchor else (
        lambda: ui.focus_text('feedback-editor-input'))
    focus = controls['feedback-editor-input'].component.grab_focus
    if fault in ('persistent', 'disabled'):
        with pytest.raises(accessible_ui.UiError, match='timeout:text-|text-disabled'):
            operation()
        focus.assert_not_called()
    else:
        operation()
        focus.assert_called_once()
    controls['feedback-reply-email'].component.grab_focus.assert_not_called()


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
