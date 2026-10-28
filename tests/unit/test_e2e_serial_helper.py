"""Execute the actual Perl serial flow against stubbed public testapi calls."""

import json
from pathlib import Path

import pytest
from tests.support.perl import run_perl

LIB = Path(__file__).resolve().parents[1] / 'integration/graphical_smoke/lib'
PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $mode = shift;
our $prompt_sample = shift;
our $fragments = shift;
our $screen;
our @events;
our $waits = 0;
our $selected = 'sut';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub get_var { return $main::mode eq 'video' ? 0 : 1; }
sub get_required_var { return $main::mode eq 'control' ? "unsafe\n" : 'private-canary'; }
sub select_console { $main::selected = $_[0]; push @main::events, 'console:' . $_[0]; }
sub current_console { return $main::mode eq 'console' ? 'sut' : $main::selected; }
sub send_key { push @main::events, 'key:' . $_[0]; }
sub assert_screen {
    my $tag = $main::mode =~ /^install/ && $main::mode ne 'install-refusal'
        ? 'onpc-gdm-parent-installed-account' : 'onpc-gdm-parent-account';
    die 'wrong graphical match' unless $_[0] eq $tag && $_[1] == 30;
    push @main::events, 'gdm-match';
    die 'private-canary' if $main::mode eq 'return-missing' || $main::mode eq 'install-return-missing';
    return 1;
}
sub wait_serial {
    my ($regex, %opts) = @_;
    die 'unsafe output' unless $opts{quiet} && !$opts{record_output};
    $main::waits++;
    push @main::events, 'wait:' . $main::waits;
    if ($main::screen && $main::waits >= 4) {
        my $ret = $main::screen->read_until($regex, 1, buffer_size => 4096, record_output => 0);
        $ret->{string} =~ s/\r\n/\n/g;
        return $ret->{matched} ? $ret->{string} : undef;
    }
    return 0 if $main::mode eq 'prompt' && $main::waits == 2;
    if ($main::waits == 2) {
        my $sample = $main::mode eq 'wrong-echo' ? "other-parent\r\nPassword: "
            : $main::mode eq 'double-cr' ? "onpc-parent-jamie\r\r\nPassword: "
            : "onpc-parent-jamie\r\nPassword: ";
        return undef unless $sample =~ $regex;
        $sample =~ s/\r\n/\n/g; # Public testapi's documented return normalization.
        return $sample;
    }
    if ($main::waits == 3) {
        return undef if $main::mode eq 'shell-not-ready';
        push @main::events, 'shell-ready';
        my $sample = 'fixture-shell$ ';
        return $sample =~ $regex ? $sample : undef;
    }
    if ($main::waits == 4) {
        if ($main::mode =~ /^install/ && $main::mode ne 'install-refusal') {
            return undef if $main::mode eq 'install-login-missing';
            return 'fixture login: ' =~ $regex;
        }
        return ' login: ' =~ $regex if $main::mode eq 'install-refusal';
        my $sample = $main::mode eq 'echo' ? q{printf 'ONPC-SERIAL-%s\n' 'OK'}
            : $main::mode eq 'ansi-output' ? "\e[?2004l\rONPC-SERIAL-OK\r\r\n"
            : "\r\nONPC-SERIAL-OK\r\n";
        return $sample =~ $regex;
    }
    return 1;
}
sub type_string {
    die 'OS commands must use SSH' if $_[0] =~ /(?:sudo|systemctl|reboot|poweroff)/;
    push @main::events, $_[0] eq "exit\n" ? 'logout'
        : $_[0] =~ /^printf/ ? 'command' : 'input';
}
sub type_password {
    die 'options' unless @_ == 1 && $_[0] eq 'private-canary';
    push @main::events, 'password';
    die 'private-canary' if $main::mode eq 'typing';

}
sub record_info { push @main::events, 'record'; }
sub save_screenshot { die 'capture must remain sealed'; }
package main;
require onpc_serial;
# The legacy wrapper's graphical return is independently provider-blocked.
# Stub only that terminal observation so these cases continue to exercise the
# supported serial proof, secret and command boundaries.
{
    no warnings 'redefine';
    *onpc_gdm::return_from_serial = sub {
        die 'provider return missing' if $mode eq 'return-missing';
        1;
    };
    *onpc_gdm::return_after_reboot = sub {
        die 'provider return missing' if $mode eq 'install-return-missing';
        1;
    };
}
if (defined($fragments)) {
    require lib;
    lib->import('/usr/lib/os-autoinst');
    require consoles::serial_screen;
    *bmwqemu::log_call = sub {};
    *bmwqemu::fctinfo = sub {};
    @FragmentScreen::ISA = ('consoles::serial_screen');
    *FragmentScreen::do_read = sub {
        my $self = $_[0];
        if (@{$self->{fragments}}) {
            my $chunk = shift @{$self->{fragments}};
            syswrite($self->{writer}, $chunk) == length($chunk) or die 'fixture write';
        }
        goto &consoles::serial_screen::do_read;
    };
    pipe(my $reader, my $writer) or die 'fixture pipe';
    $screen = consoles::serial_screen->new($reader);
    bless $screen, 'FragmentScreen';
    $screen->{writer} = $writer;
    $screen->{fragments} = decode_json($fragments);
}
if ($mode =~ /^install/) {
    no warnings 'redefine';
    *onpc_install::run = sub {
        die 'install callback' unless @_ == 1 && ref($_[0]) eq 'CODE';
        push @events, 'installation';
        return 1;
    };
    *onpc_install::run_refusal = sub {
        die 'install callback' unless @_ == 1 && ref($_[0]) eq 'CODE';
        push @events, 'installation-refusal';
        return 1;
    };
}
my $exchange = sub {
    my ($stage, $shot) = @_;
    die 'unexpected capture' if defined($shot);
    push @events, $stage;
    die 'private-canary' if $mode eq 'probe-error' && $stage eq 'serial-password';
    die 'private-canary' if $mode eq 'install-reboot-error' && $stage eq 'reboot-observed';
    die 'private-canary' if $mode eq 'install-request-error' && $stage eq 'reboot-requested';
    return {serial_login_process_verified => ($mode ne 'process'),
            active_graphical_greeter => 1, unexpected_user_session => 0,
            ui_focused => 1,
            ui => {operation => $mode eq 'flow00' ? 'gdm-product-free-select-parent'
                                                  : 'gdm-select-parent',
                   outcome => 'passed', interface => 'ApplicationUI+external-provider'},
            customer_reboot_authorized => ($mode ne 'install-unauthorized'),
            active_local_serial_session => ($mode ne 'install-session'),
            reboot_requested => ($mode ne 'install-request-unverified'),
            boot_changed => ($mode ne 'install-unchanged'),
            terminal_echo_disabled => ($mode ne 'echo-enabled')};
};
my $ok = eval {
    if ($mode eq 'flow00') {
        require onpc_flow00;
        require onpc_journey;
        $selected = '';
        my $journey = onpc_journey->new(prefix => 'smokeui', review => 0, exchange => $exchange);
        onpc_flow00::run($journey, $exchange);
    } else {
    $mode eq 'install-refusal' ? onpc_serial::run_install_refusal($exchange)
        : $mode =~ /^install/ ? onpc_serial::run_install($exchange)
        : $mode eq 'functional' ? onpc_serial::run_functional($exchange)
        : onpc_serial::run($exchange);
    }
    1;
};
my $error = $@;
my $retry = eval { onpc_serial::run($exchange); 1; };
my $capture = eval { onpc_password::capture_before_authentication(); 1; };
print encode_json({ok => $ok ? 1 : 0, error => $error, retry => $retry ? 1 : 0,
                   capture => $capture ? 1 : 0, events => \@events});
'''


def test_functional_return_keeps_secret_boundary_command_and_logout_without_pixels():
    result = run_perl(PROBE, 'functional')
    data = json.loads(result.stdout)
    assert data['ok'] and not data['retry'] and not data['capture']
    events = data['events']
    assert events.index('serial-password') < events.index('password') < events.index('serial-command')
    assert events.index('serial-command') < events.index('logout') < events.index('serial-logout')
    assert events.index('serial-logout') < events.index('console:sut') < events.index('gdm-return')
    assert 'gdm-match' not in events
    assert 'private-canary' not in result.stdout + result.stderr


@pytest.mark.parametrize('arguments', ['none', 'extra', 'wrong-callback'])
def test_invalid_functional_arguments_still_seal_capture_and_consume_attempt(arguments):
    probe = r'''
use JSON::PP;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub get_var { 1 }
sub select_console { die 'input forbidden'; }
sub save_screenshot { die 'capture forbidden'; }
package main;
require onpc_serial;
my $mode = shift;
my $ok = eval {
    $mode eq 'none' ? onpc_serial::run_functional()
        : $mode eq 'extra' ? onpc_serial::run_functional(sub {}, 'extra')
        : onpc_serial::run_functional('invalid');
    1;
};
my $retry = eval { onpc_serial::run_functional(sub {}); 1; };
my $error = $@;
my $capture = eval { onpc_password::capture_before_authentication(); 1; };
print encode_json({ok => $ok ? 1 : 0, retry => $retry ? 1 : 0,
    refused => $error =~ /already-attempted/ ? 1 : 0, capture => $capture ? 1 : 0});
'''
    assert json.loads(run_perl(probe, arguments).stdout) == {
        'ok': 0, 'retry': 0, 'refused': 1, 'capture': 0}


@pytest.mark.parametrize('fault', ['echo', 'wrong-echo', 'echo-enabled', 'process', 'typing',
                                 'shell-not-ready', 'probe-error', 'control', 'video', 'console'])
def test_extracted_functional_composition_keeps_authentication_and_output_refusals(fault):
    result = run_perl(PROBE.replace("$mode eq 'functional' ?", "1 ?"), fault)
    data = json.loads(result.stdout)
    assert not data['ok'] and not data['retry'] and not data['capture']
    assert 'serial-command' not in data['events'] and 'gdm-return' not in data['events']
    assert 'private-canary' not in result.stdout + result.stderr


@pytest.mark.parametrize('block', ['command', 'logout', 'return'])
@pytest.mark.parametrize('fault', ['', 'wrong-state', 'wrong-console', 'observation', 'missing-output',
                                 'stale-proof'])
def test_serial_blocks_accept_independent_entry_and_never_replay(block, fault):
    probe = r'''
use strict;
use warnings;
use JSON::PP;
our ($block, $fault) = @ARGV;
our @events;
our $console = $fault eq 'wrong-console' ? 'sut' : 'onpc-serial';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { $main::console }
sub select_console { $main::console = $_[0]; push @main::events, 'select'; }
sub type_string { push @main::events, $_[0] =~ /^printf/ ? 'command' : 'exit'; }
sub wait_serial {
    my ($regex, %options) = @_;
    die 'private output' unless $options{quiet} == 1 && $options{record_output} == 0;
    return undef if $main::fault eq 'missing-output';
    my $value = $main::block eq 'command' ? "ONPC-SERIAL-OK\r\n" : 'fixture login: ';
    return $value =~ $regex;
}
sub record_info { push @main::events, $_[0]; }
sub type_password { die 'no authentication in these blocks'; }
package main;
require onpc_serial;
my $logout = {active_graphical_greeter => 1, unexpected_user_session => 0};
my $state = {phase => $fault eq 'wrong-state' ? 'new'
    : $block eq 'command' ? 'authenticated' : $block eq 'logout' ? 'command-observed' : 'logged-out',
    logout_proof => $logout, exchange => sub {
        push @events, $_[0];
        die 'unavailable' if $fault eq 'observation';
        return {active_graphical_greeter => 1, unexpected_user_session => 0};
    }};
$logout = {%$logout} if $fault eq 'stale-proof';
my $invoke = sub {
    return $block eq 'command' ? onpc_serial::command($state)
        : $block eq 'logout' ? onpc_serial::logout($state)
        : onpc_serial::return_graphics($state, $logout);
};
my $ok = eval { $invoke->(); 1; };
my $before_retry = scalar @events;
my $retry = eval { $invoke->(); 1; };
print encode_json({ok => $ok ? 1 : 0, retry => $retry ? 1 : 0,
    before_retry => $before_retry, events => \@events});
'''
    data = json.loads(run_perl(probe, block, fault).stdout)
    succeeds = fault == '' or (fault == 'stale-proof' and block != 'return') or (
        fault == 'missing-output' and block == 'return')
    assert data['ok'] == succeeds, data
    assert not data['retry'] and data['before_retry'] == len(data['events'])
    if fault in ('wrong-state', 'wrong-console') or (fault == 'stale-proof' and block == 'return'):
        assert not data['events']
    if fault == 'missing-output' and block != 'return':
        assert 'serial-command' not in data['events'] and 'serial-logout' not in data['events']


@pytest.mark.parametrize('mode', ['ok', 'install', 'install-refusal', 'double-cr', 'ansi-output', 'shell-not-ready', 'video', 'console', 'prompt', 'wrong-echo', 'process',
                                 'echo-enabled', 'probe-error', 'control', 'typing', 'echo', 'return-missing'])
def test_serial_secret_boundary_and_command_output(mode):
    result = run_perl(PROBE, mode)
    data = json.loads(result.stdout)
    assert 'private-canary' not in result.stdout + result.stderr
    assert data['ok'] == (mode in ('ok', 'install', 'install-refusal', 'double-cr', 'ansi-output'))
    assert not data['retry'] and not data['capture']
    events = data['events']
    if mode in ('install', 'install-refusal'):
        action = 'installation-refusal' if mode == 'install-refusal' else 'installation'
        assert events.index('serial-authenticated') < events.index('shell-ready') < events.index(action)
        if mode == 'install':
            assert events.index(action) < events.index('reboot-ready') < events.index('reboot-requested')
            assert events.index('reboot-requested') < events.index('reboot-observed') < events.index('gdm-return')
            assert events.count('password') == 1  # Login only; installation is stubbed here.
            assert 'reboot-input' not in events
            assert 'logout' not in events and 'serial-logout' not in events
        else:
            assert events.index(action) < events.index('logout') < events.index('gdm-return')
            assert 'reboot-input' not in events
        assert 'command' not in events and 'serial-command' not in events
    elif mode in ('ok', 'double-cr', 'ansi-output'):
        assert events.index('serial-password') < events.index('password')
        assert events.index('serial-authenticated') < events.index('serial-command')
        assert events.index('serial-authenticated') < events.index('shell-ready') < events.index('command')
        assert events.index('serial-command') < events.index('logout') < events.index('serial-logout')
        assert events[-2:] == ['gdm-return', 'record']
        assert events.index('serial-logout') < events.index('gdm-return')
    elif mode == 'return-missing':
        assert 'serial-logout' in events and 'gdm-return' not in events
    elif mode in ('typing', 'echo', 'shell-not-ready'):
        assert 'password' in events and 'serial-command' not in events
        if mode == 'shell-not-ready':
            assert 'command' not in events
    else:
        assert 'password' not in events


@pytest.mark.parametrize('mode', ['install-unauthorized', 'install-session',
    'install-unchanged', 'install-reboot-error', 'install-login-missing',
    'install-request-error', 'install-request-unverified', 'install-return-missing'])
def test_reboot_refusal_stops_input_or_graphical_return_without_retry(mode):
    result = run_perl(PROBE, mode)
    data = json.loads(result.stdout)
    assert 'private-canary' not in result.stdout + result.stderr
    assert not data['ok'] and not data['retry'] and not data['capture']
    events = data['events']
    assert 'gdm-return' not in events and 'logout' not in events
    assert 'reboot-input' not in events
    assert events.count('password') == 1
    assert events.count('reboot-requested') == (0 if mode in (
        'install-unauthorized', 'install-session') else 1)
    if mode in ('install-request-error', 'install-request-unverified'):
        assert 'reboot-observed' not in events
