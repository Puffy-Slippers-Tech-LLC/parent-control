"""Command documentation uses bounded SSH stdout and leaves the desktop clear."""

import json

import pytest

from command_documentation import BINDINGS, command, observe, validate
from private_artifacts import EvidenceError
from tests.support.perl import run_perl

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
