"""Command documentation uses bounded SSH stdout and leaves the desktop clear."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import HELP_BINDINGS, UiError
from command_documentation import BINDINGS, command, observe, validate
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.perl import run_perl

PROMPT = 'onpc-parent-jamie@fixture:~$ '
def terminal(value):
    field = Node(role='terminal',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    window = Node(children=[field],
                  states=('showing', 'visible', 'active'))
    application = Node('Ptyxis', 'application', children=[window],
                       identity='org.gnome.Ptyxis')
    root = Node(role='desktop frame', children=[application])
    ui = ui_for(root)
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


def test_station_manual_purpose_survives_man_line_hyphenation():
    value = ('OH-NO-PARENT-CONTROL(1)\nNAME\n'
             'oh-no-parent-control - run the parent-con‐\n'
             '       trol request interface\nSYNOPSIS\n'
             'oh-no-parent-control [options]\nDESCRIPTION\n')
    ui, _, _ = terminal(value)
    assert ui.help_content('station-manual')
    ui, _, _ = terminal(value.replace('request interface', 'unrelated purpose'))
    assert not ui.help_content('station-manual')


def test_projection_is_bounded_and_raw_terminal_text_never_leaves_adapter():
    ui, _, _ = terminal('private-prefix' * 1000 + '\n' + PROMPT)
    assert ui.run('help-shell-ready', '1') == {
        'operation': 'help-shell-ready', 'outcome': 'passed', 'interface': 'AT-SPI'}
    assert all(call.args[2] - call.args[1] <= 8192 for call in ui.api.Text.get_text.call_args_list)
    ui, _, _ = terminal('x' * 65537)
    with pytest.raises(UiError, match='text-bound'): ui.help_terminal_text()
    ui.api.Text.get_text.assert_not_called()


def test_fixed_stream_commands_run_as_parent_without_shell_or_terminal():
    for binding, (name, kind, _) in BINDINGS.items():
        argv = command(binding)
        assert argv[:5] == ['/usr/sbin/runuser', '--user', 'onpc-parent-jamie',
                            '--', '/usr/bin/env']
        assert argv[-2:] == (['/usr/bin/' + name, '--help'] if kind == 'help'
                             else ['cat', name])
    with pytest.raises(EvidenceError, match='help:binding'):
        command('arbitrary; command')


@pytest.mark.parametrize('binding', BINDINGS)
def test_stream_content_requires_command_identity_and_sections(binding):
    name, kind, identity = BINDINGS[binding]
    raw = (f'usage: {name} [-h]\n{identity}\noptions:\n'
           ' -h, --help  show this help message and exit\n' if kind == 'help'
           else f'{name.upper()}(1)\nNAME\n{name} - {identity}\nSYNOPSIS\n'
                f'{name} [options]\nDESCRIPTION\n{identity}\n').encode()
    assert validate(binding, raw)['interface'] == 'SSH stdout'
    with pytest.raises(EvidenceError, match='help:content'):
        validate(binding, raw.replace(identity.encode(), b'unrelated documentation'))
    with pytest.raises(EvidenceError, match='help:output-bound'):
        validate(binding, b'x' * 65537)


def test_observer_checks_captured_stdout_and_bounds_stream_chunks():
    name, _, identity = BINDINGS['parent-help']
    raw = (f'usage: {name} [-h]\n{identity}\n'
           '-h, --help show this help message and exit\n').encode()

    class Transport:
        def __init__(self, output):
            self.output = output
            self.argv = None

        def call(self, argv, *, timeout, on_output):
            self.argv = argv
            assert timeout == 45
            for chunk in (self.output[:10], self.output[10:]):
                on_output(chunk)
            return self.output

    transport = Transport(raw)
    assert observe(transport, 'parent-help') == {
        'operation': 'parent-help', 'outcome': 'passed', 'interface': 'SSH stdout'}
    assert transport.argv == command('parent-help')
    with pytest.raises(EvidenceError, match='help:output-bound'):
        observe(Transport(b'x' * 65537), 'parent-help')


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


def test_complete_worker_matches_ordered_plan_without_terminal_input():
    from command_help import PLAN
    result = json.loads(run_perl(RUN_PROBE).stdout)
    assert result['ok']
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == list(PLAN.screen_tags)
    assert result['events'].count(['key', 'q']) == 0
    assert result['events'].count(['key', 'ctrl-alt-t']) == 0
    assert result['events'][-1] == ['power', 'off']
