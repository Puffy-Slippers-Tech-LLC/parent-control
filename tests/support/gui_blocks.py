"""Run the installed worker's finite GUI blocks on the private host display.

Only the input transport differs: the existing Perl composites supply their
ordered public observations and keyboard batches; AccessibleUI and the guarded
host keyboard execute them. This is not a VM runner or a selector language.
"""

import json
from itertools import groupby

from tests.support.perl import run_perl
from tests.support import keyboard


_TRACE = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, ['key', $_[0]]; }
sub type_string { my ($text, %options) = @_; push @events, ['text', $text, $options{max_interval} // 0]; }
package main;
require onpc_text;
require onpc_format;
require onpc_feedback_states;
require onpc_app_rows;
require onpc_feedback_privacy;
my ($block, @arguments) = @ARGV;
my $journey = onpc_journey->new(prefix => 'host-gui', review => 0, exchange => sub {
    push @events, ['observe', $_[0]];
    return {observed => $_[0]};
});
if ($block eq 'replace') { onpc_text::replace_text($journey, @arguments); }
elsif ($block eq 'filter') { onpc_app_rows::filter($journey, @arguments); }
elsif ($block eq 'match-editor') { onpc_app_rows::match_editor($journey, @arguments); }
elsif ($block eq 'match-response') { onpc_app_rows::match_response($journey, @arguments); }
elsif ($block eq 'report-review') { onpc_feedback_privacy::review_parent_report($journey, @arguments); }
elsif ($block eq 'report-close') { onpc_feedback_privacy::close_parent_report($journey, @arguments); }
elsif ($block eq 'access-choice') { onpc_app_rows::access_choice($journey, @arguments); }
elsif ($block eq 'edit-policy') {
    $arguments[-1] = decode_json($arguments[-1]);
    onpc_app_rows::edit_policy($journey, @arguments);
}
elsif ($block eq 'scalar') { onpc_text::append_scalar($journey, @arguments); }
elsif ($block eq 'bold') { onpc_format::apply_bold($journey, @arguments); }
elsif ($block eq 'block') { onpc_format::apply_block($journey, @arguments); }
elsif ($block eq 'inline') { onpc_format::apply_inline($journey, @arguments); }
elsif ($block eq 'formats') { onpc_format::apply_all($journey, @arguments); }
elsif ($block eq 'states') { onpc_feedback_states::edit_states($journey, @arguments); }
elsif ($block eq 'length') { onpc_feedback_states::length_boundary($journey, @arguments); }
elsif ($block eq 'hidden') { onpc_feedback_states::input_hidden($journey, @arguments); }
elsif ($block eq 'complex') { onpc_feedback_states::input_complex($journey, @arguments); }
else { die 'host-gui:block'; }
print encode_json(\@events);
'''

_KEYS = {
    'ctrl-a': '<Control>a', 'ctrl-home': '<Control>Home',
    'ctrl-end': '<Control>End', 'ctrl-tab': '<Control>Tab',
    'ctrl-shift-end': '<Control><Shift>End', 'ctrl-shift-u': '<Control><Shift>u',
    'ctrl-c': '<Control>c', 'ctrl-shift-v': '<Control><Shift>v',
    'right': 'Right', 'left': 'Left', 'shift-right': '<Shift>Right',
    'backspace': 'BackSpace', 'ret': 'Return', 'esc': 'Escape',
    'alt-f4': '<Alt>F4',
}


def run_block(ui, block, *arguments, child=None, operations=None, child_bindings=None):
    """Execute once, stopping at the first failed observation or input.

    The short, waited Perl process only expands a named finite composite into
    memory. It reads shared modules without opening a display or socket. Real input still
    reacquires its public recipient; no precomputed observation is evidence.
    """
    from tests.e2e.accessible_ui import TEXT_OPERATIONS, TEXT_VALUES, FILTER_OPERATIONS

    events = json.loads(run_perl(_TRACE, block, *arguments).stdout)
    if not isinstance(events, list) or not 0 < len(events) <= 4096:
        raise ValueError('Invalid GUI block')
    observations = {}
    identity = 'feedback-editor-input'
    for event, group in groupby(events):
        if event[0] == 'key' and event[1] in ('right', 'left', 'shift-right'):
            # Same ordered keys and subsequent exact selection proof as the VM;
            # reuse host pacing for cursor-only batches that cannot change focus.
            keyboard.repeat_cursor(ui, identity, _KEYS[event[1]], sum(1 for _ in group))
            continue
        for event in group:
            if event[0] == 'observe':
                stage = event[1]
                operation = operations[stage].removeprefix('ui:') if operations is not None else stage
                if operation in TEXT_OPERATIONS:
                    binding, action = TEXT_OPERATIONS[operation]
                    identity = ('feedback-editor-input' if action == 'anchor'
                                else TEXT_VALUES[binding][0])
                elif operation.endswith('-link-target'):
                    identity = 'feedback-link-target'
                elif operation.endswith('-focus'):
                    identity = 'feedback-editor-input'
                elif operation in FILTER_OPERATIONS:
                    identity = 'parent-window'
                elif operation == 'feedback-privacy-open':
                    identity = 'feedback-privacy-dialog'
                elif operation in ('feedback-draft-reread', 'parent-report-read'):
                    identity = 'feedback-dialog'
                bound_child = child_bindings.get(stage) if child_bindings is not None else child
                observations[stage] = ui.run(operation, '', **({'child': bound_child} if bound_child else {}))
            elif event[0] == 'key':
                keyboard.key_combo(ui, identity, _KEYS[event[1]],
                    state=ui.api.StateType.ACTIVE if event[1] in ('esc', 'alt-f4') else ui.api.StateType.FOCUSED)
            elif event[0] == 'text':
                keyboard.type_text(ui, identity, event[1], interval=event[2] / 1000)
            else:
                raise ValueError('Invalid GUI block event')
    return observations
