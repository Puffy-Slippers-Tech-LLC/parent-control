"""Terminal input must qualify the actual foreground public input surface."""

import pytest
import json
from types import SimpleNamespace
from unittest.mock import Mock

from accessible_ui import UiError
from tests.support.accessible_ui import Node, ui_for
from tests.support.perl import run_perl


@pytest.mark.parametrize('fault', [None, 'background', 'overview', 'hidden',
                                   'disabled', 'unfocused', 'password', 'duplicate'])
def test_terminal_input_independent_entry_and_wrong_surface_refusal(fault):
    field = Node(role='password text' if fault == 'password' else 'terminal',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    window = Node(children=[field], states=('showing', 'visible', 'active'))
    root = Node(children=[window])
    if fault == 'background': window.states.remove('active')
    if fault == 'overview': root.children.append(Node('Overview', 'panel'))
    if fault == 'hidden': field.states.remove('showing')
    if fault == 'disabled': field.states.remove('sensitive')
    if fault == 'unfocused': field.states.remove('focused')
    if fault == 'duplicate': window.children.append(Node(role='terminal'))
    ui = ui_for(root)
    if fault == 'duplicate':
        with pytest.raises(UiError, match='ambiguous-terminal'):
            ui.terminal_input(focused=True)
    else:
        assert ui.terminal_input(focused=True) is (None if fault else field)


def test_terminal_focus_target_does_not_claim_focus():
    field = Node(role='terminal')
    ui = ui_for(Node(children=[Node(children=[field],
        states=('showing', 'visible', 'active'))]))
    assert ui.terminal_input() is field
    assert ui.terminal_input(focused=True) is None


@pytest.mark.parametrize('fault', [None, 'already-focused', 'background', 'refused', 'unobserved'])
def test_terminal_focus_uses_component_once_and_requires_fresh_focus(fault):
    field = Node(role='terminal')
    if fault == 'already-focused':
        field.states.add('focused')
    window = Node(children=[field], states=('showing', 'visible', 'active'))
    if fault == 'background':
        window.states.remove('active')
    def focus():
        if fault is None:
            field.states.add('focused')
        return fault != 'refused'
    component = SimpleNamespace(grab_focus=Mock(side_effect=focus))
    field.get_component_iface = lambda: component
    ui = ui_for(Node(children=[window]))
    if fault not in (None, 'already-focused'):
        with pytest.raises(UiError):
            ui.focus_terminal()
    else:
        ui.focus_terminal()
        assert ui.terminal_input(focused=True) is field
    assert component.grab_focus.call_count == (0 if fault in ('background', 'already-focused') else 1)


@pytest.mark.parametrize('fault', [None, 'generic', 'echo', 'management', 'stale', 'inactive'])
def test_denial_requires_specific_visible_gui_and_complete_management_exclusion(fault):
    label = Node('Only an administrator can manage parental controls. '
                 'Sign in with an administrator account to open the Parent App.', 'label',
                 identity='parent-access-denied-message')
    window = Node('Administrator access required', children=[label,
                  Node('Close', 'push button', identity='parent-access-denied-close')],
                  states=('showing', 'visible', 'active'), identity='parent-access-denied-window')
    root = Node(children=[window])
    if fault == 'generic': label.name = 'Something went wrong'
    if fault == 'echo': label.role = 'terminal'
    if fault == 'management': root.children.append(Node('Oh No! Parent Control', identity='parent-window'))
    if fault == 'stale': root.children.append(Node(states=('defunct',)))
    if fault == 'inactive': window.states.remove('active')
    ui = ui_for(root)
    if fault:
        with pytest.raises(UiError): ui.management_denied()
    else:
        ui.management_denied()


SUBMIT_PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $fault = shift;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub type_string {
    push @main::events, ['type', @_];
    die 'uncertain' if $main::fault eq 'uncertain';
}
sub send_key { push @main::events, ['key', @_]; }
package main;
require onpc_terminal;
require onpc_journey;
my $journey = onpc_journey->new(prefix => 'unit', review => 0,
    exchange => sub { return {}; });
my $proof = $journey->seen($fault eq 'wrong' ? 'other' : 'terminal-focused');
my $ok = eval { onpc_terminal::submit_parent($journey, $proof); 1; };
my $replay = eval { onpc_terminal::submit_parent($journey, $proof); 1; };
print encode_json({ok => $ok ? 1 : 0, replay => $replay ? 1 : 0, events => \@events});
package testapi;
sub record_info { }
'''


OPEN_PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $fault = shift;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub send_key { push @main::events, ['key', @_]; }
sub record_info { }
package main;
require onpc_terminal;
require onpc_journey;
my $journey = onpc_journey->new(prefix => 'unit', review => 0,
    exchange => sub {
        my ($stage) = @_;
        push @events, ['seen', $stage];
        die 'not-ready' if $stage eq $fault;
        return {};
    });
my $proof = $journey->seen($fault eq 'wrong' ? 'other' : 'desktop');
@events = ();
my $ok = eval { onpc_terminal::open($journey, $proof); 1; };
my $replay = eval { onpc_terminal::open($journey, $proof); 1; };
print encode_json({ok => $ok ? 1 : 0, replay => $replay ? 1 : 0, events => \@events});
'''


FOCUS_PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $fault = shift;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub mouse_set { die 'unexpected pointer input'; }
package main;
require onpc_terminal;
require onpc_journey;
my $journey = onpc_journey->new(prefix => 'unit', review => 0,
    exchange => sub {
        my ($stage) = @_;
        push @events, $stage;
        die 'focus-failed' if $fault eq 'failed' && $stage eq 'terminal-focused';
        return {};
    });
my $proof = $journey->seen($fault eq 'wrong' ? 'other' : 'terminal-input');
@events = ();
my $ok = eval { onpc_terminal::focus($journey, $proof, 'input'); 1; };
my $replay = eval { onpc_terminal::focus($journey, $proof, 'input'); 1; };
print encode_json({ok => $ok ? 1 : 0, replay => $replay ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('fault', ['', 'wrong', 'failed'])
def test_focus_consumes_input_once_without_framebuffer_click(fault):
    result = json.loads(run_perl(FOCUS_PROBE, fault).stdout)
    assert result['ok'] == (fault == '')
    assert not result['replay']
    assert result['events'] == ([] if fault == 'wrong' else ['terminal-focused'])


@pytest.mark.parametrize('fault', ['', 'wrong', 'system-prompt',
                                   'terminal-wrong-surface', 'terminal-opened'])
def test_open_shortcut_requires_desktop_and_observed_readiness_without_replay(fault):
    result = json.loads(run_perl(OPEN_PROBE, fault).stdout)
    assert result['ok'] == (fault == '')
    assert not result['replay']
    expected = [
        ['seen', 'system-prompt'], ['seen', 'terminal-wrong-surface'],
        ['key', 'ctrl-alt-t'], ['seen', 'terminal-opened'],
    ]
    if fault == 'wrong':
        expected = []
    elif fault:
        expected = expected[:expected.index(['seen', fault]) + 1]
    assert result['events'] == expected


@pytest.mark.parametrize('fault', ['', 'wrong', 'uncertain'])
def test_submit_fixed_command_once_after_fresh_focus_without_wait_or_replay(fault):
    result = json.loads(run_perl(SUBMIT_PROBE, fault).stdout)
    assert result['ok'] == (fault == '')
    assert not result['replay']
    assert result['events'] == ([] if fault == 'wrong' else
        [['type', '/usr/bin/oh-no-parent-control-parent']] +
        ([['key', 'ret']] if not fault else []))
