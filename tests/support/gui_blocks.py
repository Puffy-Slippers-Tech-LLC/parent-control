"""Run installed Application UI composites on the private host display.

The Perl composites declare the same finite operation sequence for both suites.
The shared reader owns every API input and its independent public observation.
"""

import json

from tests.support.perl import run_perl


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
require onpc_allowance_selection;
my ($block, @arguments) = @ARGV;
my $journey = onpc_journey->new(prefix => 'host-gui', review => 0, exchange => sub {
    push @events, ['observe', $_[0]];
    return {observed => $_[0]};
});
if ($block eq 'replace') { onpc_text::replace_text($journey, @arguments); }
elsif ($block eq 'allowance') {
    $arguments[1] = decode_json($arguments[1]);
    onpc_allowance_selection::select($journey, @arguments);
}
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

def select_allowance(ui, values, *, child=None):
    """Run the installed allowance block on the host's private display."""
    from tests.e2e.journey_blocks import allowance_selection
    from tests.e2e.accessible_ui import NAMED_CUSTOM_CHILDREN, CHILD, EXISTING_CHILD
    if hasattr(ui, 'reader'):
        ui = ui.reader
        if ui.fixture_uids is None:
            ui.fixture_uids = {CHILD: 1001, EXISTING_CHILD: 1002}
    child = next((alias for alias, label in NAMED_CUSTOM_CHILDREN.items() if label == child), child)
    operations = allowance_selection('choice', values)
    return run_block(ui, 'allowance', 'choice', json.dumps(values), 'confirm',
                     child=child, operations=operations)


def run_block(ui, block, *arguments, child=None, operations=None, child_bindings=None):
    """Execute once, stopping at the first failed observation or input.

    The short, waited Perl process only expands a named finite composite into
    memory. It reads shared modules without opening a display or socket. Each
    live operation resolves its public API recipient; the trace is not evidence.
    """
    events = json.loads(run_perl(_TRACE, block, *arguments).stdout)
    if not isinstance(events, list) or not 0 < len(events) <= 4096:
        raise ValueError('Invalid GUI block')
    observations = {}
    for event in events:
        if not isinstance(event, list) or len(event) != 2 or event[0] != 'observe':
            raise ValueError('Product composites require Application UI operations')
        stage = event[1]
        operation = operations[stage].removeprefix('ui:') if operations is not None else stage
        bound_child = child_bindings.get(stage) if child_bindings is not None else child
        binding = {'child': bound_child} if bound_child else {}
        observations[stage] = ui.run(operation, '', **binding)
    return observations
