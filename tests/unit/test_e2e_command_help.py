"""Command documentation needs real content, return input and no product UI."""

import json
import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import HELP_BINDINGS, UiError
from tests.support.accessible_ui import Node, TEST_PROMPT_CONTRACTS, ui_for
from tests.support.perl import run_perl

PROMPT = 'onpc-parent-jamie@fixture:~$ '
TERMINAL_CONTRACTS = copy.deepcopy(TEST_PROMPT_CONTRACTS)
TERMINAL_CONTRACTS['terminal'] = {
    'application_id': 'test-terminal-application',
    'surfaces': {'terminal': ('test-terminal-window', {
        'input-output': 'test-terminal-input-output'})},
    'blocked_consumers': (),
}


def terminal(value):
    field = Node(role='terminal', identity='test-terminal-input-output',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    window = Node(identity='test-terminal-window', children=[field],
                  states=('showing', 'visible', 'active'))
    application = Node(identity='test-terminal-application', children=[window])
    root = Node(children=[application])
    ui = ui_for(root, provider_contracts=TERMINAL_CONTRACTS)
    text = object()
    field.get_text_iface = lambda: text
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: len(value),
        get_text=Mock(side_effect=lambda _, start, end: value[start:end]))
    return ui, root, field


@pytest.mark.parametrize('binding', HELP_BINDINGS)
@pytest.mark.parametrize('fault', [None, 'echo', 'wrong-content', 'background', 'product',
                                   'request', 'stale', 'wrong-return'])
def test_content_requires_identifying_output_and_right_terminal_state(binding, fault):
    command, kind, identity = HELP_BINDINGS[binding]
    value = (f'usage: {command} [-h]\n{identity}\noptions:\n'
             ' -h, --help  show this help message and exit\n' + PROMPT if kind == 'help'
             else f'{command.upper()}(1)\nNAME\n{command} - {identity}\nSYNOPSIS\n'
                  f'{command} [options]\nDESCRIPTION\n{identity}\n:')
    if fault == 'echo': value = PROMPT + command + ' --help\n' + PROMPT
    if fault == 'wrong-content': value = value.replace(identity, 'unrelated documentation')
    if fault == 'wrong-return':
        value = value.removesuffix(PROMPT) + (':' if kind == 'help' else '\n' + PROMPT)
    ui, root, field = terminal(value)
    if fault == 'background': field.parent.states.remove('active')
    if fault == 'product':
        root.children.append(Node('Oh No! Parent Control', identity='parent-access-denied-window'))
    if fault == 'request':
        root.children.append(Node('Request', 'push button', identity='kiosk-request-window'))
    if fault == 'stale': root.children.append(Node(states=('defunct',)))
    if fault in ('product', 'request', 'stale'):
        with pytest.raises(UiError): ui.help_content(binding)
    else:
        assert ui.help_content(binding) is (fault is None)


def test_projection_is_bounded_and_raw_terminal_text_never_leaves_adapter():
    ui, _, _ = terminal('private-prefix' * 1000 + '\n' + PROMPT)
    assert ui.run('help-shell-ready', '1') == {
        'operation': 'help-shell-ready', 'outcome': 'passed', 'interface': 'AT-SPI'}
    assert all(call.args[2] - call.args[1] <= 8192 for call in ui.api.Text.get_text.call_args_list)
    ui, _, _ = terminal('x' * 65537)
    with pytest.raises(UiError, match='text-bound'): ui.help_terminal_text()
    ui.api.Text.get_text.assert_not_called()


PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our ($binding, $fault) = @ARGV;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub type_string {
    push @main::events, ['type', @_];
    die 'uncertain' if $main::fault eq 'uncertain';
}
sub send_key { push @main::events, ['key', @_]; }
package main;
require onpc_command_help;
my $journey = onpc_journey->new(prefix => 'unit', review => 0, exchange => sub {
    push @events, ['seen', $_[0]];
    die 'missing-content' if $fault eq 'content' && $_[0] =~ /-content$/;
    return {};
});
my $entry = $journey->seen($fault eq 'wrong' ? 'desktop' : $binding . '-entry');
@events = ();
my $ok = eval { onpc_command_help::read_installed($journey, $binding, $entry); 1; };
my $replay = eval { onpc_command_help::read_installed($journey, $binding, $entry); 1; };
print encode_json({ok => $ok ? 1 : 0, replay => $replay ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('binding', [*HELP_BINDINGS, 'arbitrary; command'])
@pytest.mark.parametrize('fault', ['', 'wrong', 'uncertain', 'content'])
def test_only_registered_commands_follow_fresh_proofs_without_replay(binding, fault):
    result = json.loads(run_perl(PROBE, binding, fault).stdout)
    assert result['ok'] == (not fault and binding in HELP_BINDINGS)
    assert not result['replay']
    if binding not in HELP_BINDINGS or fault == 'wrong':
        assert not result['events']
        return
    command, kind, _ = HELP_BINDINGS[binding]
    expected = [['type', '/usr/bin/' + command + ' --help' if kind == 'help' else 'man ' + command]]
    if fault != 'uncertain':
        expected += [['key', 'ret'], ['seen', binding + '-content']]
    if not fault:
        if kind == 'manual': expected += [['key', 'q']]
        expected += [['seen', binding + '-returned']]
    assert result['events'] == expected


RUN_PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { }
sub select_console { }
sub get_var { $_[0] eq 'NOVIDEO' ? '1' : $_[1] }
sub get_required_var { 'unit-fixture-value' }
sub type_password { push @main::events, ['secret']; }
sub type_string { push @main::events, ['text', $_[0]]; }
sub send_key { push @main::events, ['key', $_[0]]; }
sub save_screenshot { die 'explicit capture forbidden'; }
sub record_info { }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]]; }
sub check_shutdown { 1 }
package Console;
sub disable { }
package main;
require onpc_command_help;
my $ok = eval {
    onpc_command_help::run(sub {
        push @events, ['stage', $_[0]];
        return {observed => $_[0]} if $_[0] =~ /recipient-(?:qualified|rechecked)\z/;
        return {ui_focused => 1} if $_[0] =~ /(?:greeter|list)$/;
        return {observed => $_[0]};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


def test_complete_worker_matches_ordered_plan_and_exits_each_manual_normally():
    from command_help import PLAN
    result = json.loads(run_perl(RUN_PROBE).stdout)
    assert result['ok']
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == list(PLAN.screen_tags)
    assert result['events'].count(['key', 'q']) == 2
    assert result['events'].count(['key', 'ctrl-alt-t']) == 4
    assert result['events'][-1] == ['power', 'off']
