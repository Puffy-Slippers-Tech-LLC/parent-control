"""Execute the actual Perl serial flow against stubbed public testapi calls."""

import json
from pathlib import Path
import os
import termios

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
our $selected = '';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub get_var { return $main::mode eq 'video' ? 0 : 1; }
sub get_required_var { return $main::mode eq 'control' ? "unsafe\n" : 'private-canary'; }
sub select_console { $main::selected = $_[0]; push @main::events, 'console:' . $_[0]; }
sub current_console { return $main::mode eq 'console' ? 'sut' : $main::selected; }
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
            my $sample = defined($main::prompt_sample) ? $main::prompt_sample
                : "[sudo: \r\nONPC-REBOOT-PASSWORD: ] Password: ";
            return $sample =~ $regex ? $sample : undef;
        }
        return ' login: ' =~ $regex if $main::mode eq 'install-refusal';
        my $sample = $main::mode eq 'echo' ? q{printf 'ONPC-SERIAL-%s\n' 'OK'}
            : $main::mode eq 'ansi-output' ? "\e[?2004l\rONPC-SERIAL-OK\r\r\n"
            : "\r\nONPC-SERIAL-OK\r\n";
        return $sample =~ $regex;
    }
    if ($main::waits == 5 && $main::mode =~ /^install/ && $main::mode ne 'install-refusal') {
        my $sample = $main::mode =~ /^install-command-failed/ ? "private-canary\nCall to Reboot failed: Interactive authentication required.\nONPC-REBOOT-RESULT:1\r\n"
            : $main::mode eq 'install-command-unknown' ? 'private-canary'
            : $main::mode eq 'install-password-denied' ? "\nONPC-REBOOT-PASSWORD: ] Password: "
            : "ONPC-REBOOT-RESULT:0\r\r\n";
        return $sample =~ $regex ? $sample : undef;
    }
    return undef if $main::mode eq 'install-login-missing' && $main::waits == 6;
    return 1;
}
sub type_string {
    if ($_[0] =~ m{^/usr/bin/sudo }) {
        die 'fixed reboot only' unless $_[0] eq
            "/usr/bin/sudo -k -p \$'\\nONPC-REBOOT-PASSWORD: ' -- /usr/bin/systemctl --no-ask-password reboot; printf 'ONPC-REBOOT-%s:%s\\n' 'RESULT' \"\$?\"\n";
    }
    push @main::events, $_[0] eq "exit\n" ? 'logout'
        : $_[0] =~ m{^/usr/bin/sudo } ? 'reboot-input'
        : $_[0] =~ /^printf/ ? 'command' : 'input';
}
sub type_password {
    die 'options' unless @_ == 1 && $_[0] eq 'private-canary';
    push @main::events, 'password';
    die 'private-canary' if $main::mode eq 'typing';
    if ($main::waits == 4) {
        die 'private-canary' if $main::mode eq 'install-password-input-error';
        if ($main::screen) {
            die 'premature password' if @{$main::screen->{fragments}};
            push @{$main::screen->{fragments}},
                ($main::mode eq 'install-stream-missing-result' ? '' : "ONPC-REBOOT-RESULT:0\r\n"),
                'fixture login: ';
        }
    }
}
sub record_info {
    if ($_[0] eq 'reboot-command-diagnostic') {
        die 'private-canary' if $main::mode eq 'install-command-failed-diagnostic-error';
        push @main::events, 'diagnostic:' . $_[1];
        return;
    }
    push @main::events, $_[0] eq 'reboot-command-result' ? 'command-result:' . $_[1] : 'record';
}
sub save_screenshot { die 'capture must remain sealed'; }
package main;
require onpc_serial;
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
    die 'private-canary' if $mode eq 'install-password-proof-error' && $stage eq 'reboot-password';
    return {serial_login_process_verified => ($mode ne 'process'),
            customer_reboot_authorized => ($mode ne 'install-unauthorized'),
            active_local_serial_session => ($mode ne 'install-session'),
            sudo_reboot_process_verified => ($mode ne 'install-recipient'),
            boot_changed => ($mode ne 'install-unchanged'),
            terminal_echo_disabled => ($mode ne 'echo-enabled' &&
                !($mode eq 'install-reboot-echo' && $stage eq 'reboot-password'))};
};
my $ok = eval {
    $mode eq 'install-refusal' ? onpc_serial::run_install_refusal($exchange)
        : $mode =~ /^install/ ? onpc_serial::run_install($exchange)
        : onpc_serial::run($exchange);
    1;
};
my $error = $@;
my $retry = eval { onpc_serial::run($exchange); 1; };
my $capture = eval { onpc_password::capture_before_authentication(); 1; };
print encode_json({ok => $ok ? 1 : 0, error => $error, retry => $retry ? 1 : 0,
                   capture => $capture ? 1 : 0, events => \@events});
'''


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
            assert events.index(action) < events.index('reboot-ready') < events.index('reboot-input')
            assert events.index('reboot-input') < events.index('reboot-observed') < events.index('gdm-return')
            assert events.index('reboot-input') < events.index('reboot-password') < events.index('reboot-observed')
            assert events.count('password') == 2  # Login and reboot; installation is stubbed here.
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
        assert events[-5:] == ['console:sut', 'gdm-match', 'record', 'gdm-return', 'record']
        assert events.index('serial-logout') < events.index('gdm-return')
    elif mode == 'return-missing':
        assert 'serial-logout' in events and events[-1] == 'gdm-match'
    elif mode in ('typing', 'echo', 'shell-not-ready'):
        assert 'password' in events and 'serial-command' not in events
        if mode == 'shell-not-ready':
            assert 'command' not in events
    else:
        assert 'password' not in events


@pytest.mark.parametrize('mode', ['install-unauthorized', 'install-session',
    'install-unchanged', 'install-reboot-error', 'install-login-missing', 'install-command-failed',
    'install-command-failed-diagnostic-error', 'install-recipient', 'install-reboot-echo',
    'install-password-proof-error', 'install-password-input-error', 'install-password-denied',
    'install-return-missing'])
def test_reboot_refusal_stops_input_or_graphical_return_without_retry(mode):
    result = run_perl(PROBE, mode)
    data = json.loads(result.stdout)
    assert 'private-canary' not in result.stdout + result.stderr
    assert not data['ok'] and not data['retry'] and not data['capture']
    events = data['events']
    assert 'gdm-return' not in events and 'logout' not in events
    assert events.count('reboot-input') == (0 if mode in (
        'install-unauthorized', 'install-session') else 1)
    if mode.startswith('install-command-failed'):
        assert 'command-result:returned-nonzero' in events
        assert 'reboot-observed' not in events
        if mode == 'install-command-failed':
            assert any(event.startswith('diagnostic:authentication-required=1 ') for event in events)
    if mode in ('install-recipient', 'install-reboot-echo', 'install-password-proof-error'):
        assert events.count('password') == 1
        assert 'reboot-observed' not in events
    if mode == 'install-password-denied':
        assert events.count('password') == 2
        assert 'reboot-observed' not in events


REBOOT_PROMPT = '[sudo: \r\nONPC-REBOOT-PASSWORD: ] Password: '
REBOOT_ECHO = "/usr/bin/sudo -k -p $'\\nONPC-REBOOT-PASSWORD: ' -- /usr/bin/systemctl --no-ask-password reboot\r\n"


@pytest.mark.parametrize('split', range(1, len(REBOOT_PROMPT)))
def test_reboot_prompt_fragments_through_installed_serial_parser(split):
    result = run_perl(PROBE, 'install-stream', '', json.dumps([
        REBOOT_ECHO, REBOOT_PROMPT[:split], REBOOT_PROMPT[split:]]))
    data = json.loads(result.stdout)
    assert data['ok'] and not data['retry'] and not data['capture']
    assert data['events'].count('password') == 2
    assert 'private-canary' not in result.stdout + result.stderr


@pytest.mark.parametrize('prompt', [REBOOT_ECHO, '\nONPC-REBOOT-PASSWORD: ',
    '\nONPC-REBOOT-PASSWORD: ] Pass', '\nONPC-REBOOT-PASSWORD: ] private-canary: ',
    '\nONPC-INSTALL-PASSWORD: ] Password: ', REBOOT_PROMPT + 'private-canary'])
def test_invalid_reboot_prompt_never_submits_second_password(prompt):
    result = run_perl(PROBE, 'install-invalid-prompt', prompt)
    data = json.loads(result.stdout)
    assert not data['ok'] and not data['retry'] and not data['capture']
    assert data['events'].count('password') == 1
    assert 'reboot-password' not in data['events'] and 'reboot-observed' not in data['events']
    assert 'private-canary' not in result.stdout + result.stderr


def test_missing_reboot_marker_preserves_new_login_in_real_serial_buffer():
    result = run_perl(PROBE, 'install-stream-missing-result', '', json.dumps([REBOOT_PROMPT]))
    data = json.loads(result.stdout)
    assert data['ok'] and not data['retry'] and not data['capture']
    assert 'command-result:unobserved' in data['events']
    assert data['events'].index('reboot-observed') < data['events'].index('gdm-return')


def test_missing_reboot_command_result_stays_unknown_and_requires_boot_proof():
    data = json.loads(run_perl(PROBE, 'install-command-unknown').stdout)
    assert data['ok'] and not data['retry'] and not data['capture']
    assert 'command-result:unobserved' in data['events']
    assert data['events'].count('reboot-input') == 1
    assert data['events'].index('reboot-observed') < data['events'].index('gdm-return')
    assert not any(event.startswith('diagnostic:') for event in data['events'])


@pytest.mark.parametrize(('output', 'observed'), [
    ('Call to Reboot failed: Interactive authentication required.', {'authentication-required'}),
    ('Call to Reboot failed: Access denied as the requested operation requires interactive authentication. '
     'However, interactive authentication has not been enabled by the calling program.',
     {'authentication-required', 'access-denied'}),
    ('Call to Reboot failed: Access denied', {'access-denied'}),
    ('Operation inhibited by "private-canary" (PID 123, user private-canary).\n'
     'Please retry operation after closing inhibitors and logging out other users.',
     {'inhibitor', 'session-or-inhibitor-refusal'}),
    ('User private-canary is logged in on private-canary.\r\n'
     'Please retry operation after closing inhibitors and logging out other users.',
     {'other-session', 'session-or-inhibitor-refusal'}),
    ('bash: /usr/bin/systemctl: Permission denied', {'shell-permission-denied'}),
    ('bash: /usr/bin/systemctl: No such file or directory', {'shell-not-found'}),
    ('private-canary\nONPC-REBOOT-RESULT:1\n', set()),
    ("/usr/bin/systemctl --no-ask-password reboot; printf 'ONPC-REBOOT-%s:%s\\n' 'RESULT' \"$?\"",
     set()),
    ('', set()),
])
def test_reboot_diagnostics_export_only_fixed_flags(output, observed):
    probe = r'''
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info {
    die 'wrong record' unless $_[0] eq 'reboot-command-diagnostic';
    print $_[1];
}
package main;
require onpc_serial;
onpc_serial::_reboot_failure_diagnostic(shift);
'''
    result = run_perl(probe, output)
    assert result.returncode == 0 and not result.stderr
    assert 'private-canary' not in result.stdout
    flags = dict(field.split('=') for field in result.stdout.split())
    assert set(flags) == {'authentication-required', 'access-denied', 'inhibitor',
                          'other-session', 'session-or-inhibitor-refusal',
                          'shell-permission-denied', 'shell-not-found'}
    assert all(value in {'0', '1'} for value in flags.values())
    assert {key for key, value in flags.items() if value == '1'} == observed


def test_real_terminal_onlcr_produces_getty_double_carriage_return():
    master, slave = os.openpty()
    try:
        attrs = termios.tcgetattr(slave)
        attrs[1] |= termios.OPOST | termios.ONLCR
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        os.write(slave, b'onpc-parent-jamie\r\nPassword: ')
        import select
        assert select.select([master], [], [], 1)[0]
        assert os.read(master, 128) == b'onpc-parent-jamie\r\r\nPassword: '
    finally:
        os.close(slave)
        os.close(master)
