"""Execute fixed Perl installation input with public testapi test doubles."""

import json
from pathlib import Path
import subprocess

import pytest

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
our @diagnostics;
our $waits = 0;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub get_var { return $main::mode eq 'video' ? 0 : 1; }
sub current_console { return $main::mode eq 'console' ? 'sut' : 'onpc-serial'; }
sub get_required_var { return $main::mode eq 'control' ? "unsafe\n" : 'private-canary'; }
sub type_string {
    my ($input) = @_;
    die 'fixed input only' unless $input eq "\n" || $input eq
        "/usr/bin/sudo -k -p \$'\\nONPC-INSTALL-PASSWORD: ' -- /usr/bin/apt-get install -y /var/lib/onpc-e2e-assets/package.deb && printf 'ONPC-INSTALL-%s\\n' 'OK'\n";
    push @main::events, $input eq "\n" ? 'enter' : 'command';
}
sub wait_serial {
    my ($regex, %options) = @_;
    die 'output policy' unless $options{quiet} && !$options{record_output};
    if ($main::screen && ($main::waits == 0 || $options{expect_not_found})) {
        $main::waits++ unless $options{expect_not_found};
        my $ret = $main::screen->read_until($regex, 1,
            buffer_size => 4096, record_output => 0);
        $ret->{string} =~ s/\r\n/\n/g;
        return $ret->{string} if $options{expect_not_found} ? !$ret->{matched} : $ret->{matched};
        return undef;
    }
    if ($options{expect_not_found}) {
        die 'bounded diagnostic' unless $options{timeout} == 1 && $options{buffer_size} == 4096;
        die 'private-canary' if $main::mode eq 'diagnostic-error';
        my %buffers = (
            denial => 'private-canary Sorry, try again.',
            echo => 'private-canary Reading package lists...',
            prompt => '',
            'diagnostic-error-output' => "private-canary\nsudo: unrecognized option\nprivate-canary\$ ",
            'diagnostic-echo' => q{/usr/bin/sudo -k -p $'\nONPC-INSTALL-PASSWORD: ' -- private-canary},
            'diagnostic-crlf' => "private-canary\nONPC-INSTALL-PASSWORD: \r\n",
            'diagnostic-control' => "private-canary\nONPC-INSTALL-PASSWORD: \e[0m",
            'diagnostic-end' => "private-canary\nONPC-INSTALL-PASSWORD: ] Password: ",
            'diagnostic-rs' => "private-canary[sudo: \nONPC-INSTALL-PASSWORD: ] Password: ",
            'diagnostic-rs-name' => "private-canary[sudo-rs: \nONPC-INSTALL-PASSWORD: ] private-canary: ",
            'diagnostic-rs-echo' => "private-canary '[sudo: ONPC-INSTALL-PASSWORD: ] Password: '",
            'diagnostic-tail' => "private-canary " . q{printf 'ONPC-INSTALL-%s\n' 'OK'},
            'diagnostic-enter' => "private-canary " . q{printf 'ONPC-INSTALL-%s\n' 'OK'} . "\r\r\n\e[?2004l",
        );
        my $buffer = $buffers{$main::mode};
        die 'negative match must be impossible' if defined($buffer) && $buffer =~ $regex;
        return $buffer;
    }
    $main::waits++;
    my $sample = $main::waits == 1 ? "\nONPC-INSTALL-PASSWORD: ] Password: "
        : $main::waits == 2 ? "ONPC-INSTALL-OK\r\n" : 'fixture$ ';
    $sample = $main::prompt_sample if $main::waits == 1 && defined($main::prompt_sample);
    return undef if ($main::mode eq 'prompt' || $main::mode =~ /^diagnostic-/) && $main::waits == 1;
    return undef if $main::mode eq 'shell' && $main::waits == 3;
    if ($main::waits == 2) {
        $sample = q{printf 'ONPC-INSTALL-%s\n' 'OK'} if $main::mode eq 'echo';
        $sample = 'Sorry, try again.' if $main::mode eq 'denial';
    }
    return $sample =~ $regex ? $sample : undef;
}
sub type_password {
    die 'secret options' unless @_ == 1 && $_[0] eq 'private-canary';
    die 'premature fragmented input' if $main::screen && @{$main::screen->{fragments}};
    push @main::events, 'password';
    die 'private-canary' if $main::mode eq 'typing';
}
sub record_info {
    push @main::diagnostics, [@_];
    push @main::events, 'record' if $_[0] eq 'install-complete';
}
sub save_screenshot { die 'capture must stay sealed'; }
package main;
if (defined($fragments)) {
    require lib;
    lib->import('/usr/lib/os-autoinst');
    require consoles::serial_screen;
    # Use the installed parser AND its real pipe read path. Each read receives
    # exactly one scheduled fragment without timing-dependent writer processes.
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
require onpc_install;
my $exchange = sub {
    my ($stage, $capture) = @_;
    die 'capture' if defined($capture);
    push @events, $stage;
    die 'private-canary' if $mode eq 'diagnostic-proof-error' && $stage eq 'install-password';
    die 'private-canary' if $mode eq 'phase' && $stage eq 'install-ready';
    return {installation_authorized => $mode ne 'unauthorized',
        product_package_absent => $mode ne 'present', verified_assets => $mode ne 'assets',
        active_local_serial_session => $mode ne 'session',
        sudo_install_process_verified => $mode ne 'process' && $mode ne 'diagnostic-wrong-process',
        terminal_echo_disabled => $mode ne 'echo-enabled' && $mode ne 'diagnostic-echo-enabled',
        installed_identity_verified => $mode ne 'package', verified_package_digest => $mode ne 'digest',
        product_reboot_required => $mode ne 'marker'};
};
my $ok = eval { onpc_install::run($exchange, ($mode eq 'arguments' ? ('extra') : ())); 1; };
my $error = $@;
my $retry = eval { onpc_install::run($exchange); 1; };
my $capture = eval { onpc_password::capture_before_authentication(); 1; };
print encode_json({ok => $ok ? 1 : 0, error => $error, retry => $retry ? 1 : 0,
                   capture => $capture ? 1 : 0, events => \@events, diagnostics => \@diagnostics});
'''


@pytest.mark.parametrize('mode', ['ok', 'arguments', 'video', 'console', 'phase',
    'unauthorized', 'present', 'assets', 'session', 'prompt', 'process', 'echo-enabled',
    'control', 'typing', 'echo', 'denial', 'package', 'digest', 'marker', 'shell'])
def test_fixed_install_input_requires_phase_and_independent_password_proof(mode):
    result = subprocess.run(['/usr/bin/perl', '-I', str(LIB), '-e', PROBE, mode],
                            capture_output=True, text=True, timeout=10, check=True)
    data = json.loads(result.stdout)
    assert 'private-canary' not in result.stdout + result.stderr
    assert data['ok'] == (mode == 'ok')
    assert not data['retry'] and not data['capture']
    events = data['events']
    if mode in ('arguments', 'video', 'console', 'phase', 'unauthorized', 'present', 'assets', 'session'):
        assert 'command' not in events
    if mode in ('ok', 'typing', 'echo', 'denial', 'package', 'digest', 'marker', 'shell'):
        assert events.index('install-ready') < events.index('command') < events.index('install-password') < events.index('password')
    else:
        assert 'password' not in events
    if mode in ('echo', 'denial', 'typing'):
        assert 'install-complete' not in events
    if mode in ('echo', 'denial'):
        title, flags = data['diagnostics'][-2]
        assert title == 'install-command-diagnostic'
        assert ('authentication-denial=' + str(int(mode == 'denial'))) in flags.split()
        assert ('apt-output=' + str(int(mode == 'echo'))) in flags.split()
        assert events.count('password') == 1
    if mode == 'ok':
        assert events[-2:] == ['install-complete', 'record']


@pytest.mark.parametrize(('mode', 'expected'), [
    ('prompt', ('buffer=empty', 'delivery=empty')),
    ('diagnostic-error-output', ('sudo-error=1', 'unsupported-option=1', 'shell-prompt=1')),
    ('diagnostic-echo', ('command-echo=1', 'output-marker=0', 'delivery=marker-absent')),
    ('diagnostic-crlf', ('prompt-line=1', 'delivery=unsupported-suffix')),
    ('diagnostic-control', ('prompt-line=1', 'delivery=unsupported-suffix')),
    ('diagnostic-end', ('prompt-line=1', 'delivery=supported')),
    ('diagnostic-rs', ('prompt-line=1', 'delivery=supported')),
    ('diagnostic-rs-name', ('prompt-line=1', 'delivery=unsupported-suffix')),
    ('diagnostic-rs-echo', ('prompt-line=0', 'delivery=unsupported-framing')),
    ('diagnostic-unavailable', ('buffer=unavailable',)),
    ('diagnostic-error', ()),
    ('diagnostic-tail', ('command-tail=1', 'command-enter=0', 'readline-paste-off=0')),
    ('diagnostic-enter', ('command-tail=1', 'command-enter=1', 'readline-paste-off=1')),
    ('diagnostic-proof-error', ('buffer=unavailable',)),
    ('diagnostic-wrong-process', ('buffer=unavailable',)),
    ('diagnostic-echo-enabled', ('buffer=unavailable',)),
])
def test_prompt_diagnostics_report_only_fixed_flags_and_never_authorize_input(mode, expected):
    result = subprocess.run(['/usr/bin/perl', '-I', str(LIB), '-e', PROBE, mode],
                            capture_output=True, text=True, timeout=10, check=True)
    assert 'private-canary' not in result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert not data['ok'] and not data['retry'] and not data['capture']
    assert 'password' not in data['events'] and 'install-complete' not in data['events']
    assert data['events'].count('install-password') == 1
    verified = mode not in ('diagnostic-proof-error', 'diagnostic-wrong-process', 'diagnostic-echo-enabled')
    assert data['diagnostics'][-2] == ['install-recipient-diagnostic',
        'exact-sudo-no-echo=' + ('verified' if verified else 'unverified')]
    assert data['diagnostics'][-1] == ['install-failed-stage', 'password-prompt']
    if expected:
        title, flags = data['diagnostics'][0]
        assert title == 'install-prompt-diagnostic'
        assert all(flag in flags.split() for flag in expected)
    else:
        assert len(data['diagnostics']) == 2


@pytest.mark.parametrize('prompt', [
    '\nONPC-INSTALL-PASSWORD: ] Password: ',
    '[sudo: \r\nONPC-INSTALL-PASSWORD: ] Password: ',
    '[sudo-rs: \nONPC-INSTALL-PASSWORD: ] Password: ',
])
@pytest.mark.parametrize('prefix', ['', 'command\r\n', 'command\r\r\n\x1b[?2004l\r'])
def test_supported_prompt_and_readline_controls_keep_independent_input_gates(prompt, prefix):
    for mode in ('ok', 'process', 'echo-enabled'):
        result = subprocess.run(['/usr/bin/perl', '-I', str(LIB), '-e', PROBE, mode, prefix + prompt],
                                capture_output=True, text=True, timeout=10, check=True)
        data = json.loads(result.stdout)
        assert data['ok'] == (mode == 'ok')
        assert ('password' in data['events']) == (mode == 'ok')
        assert not data['retry'] and not data['capture']
        assert 'private-canary' not in result.stdout + result.stderr


@pytest.mark.parametrize('prompt', [
    "/usr/bin/sudo -k -p 'ONPC-INSTALL-PASSWORD: ",
    "private-canary '[sudo: ONPC-INSTALL-PASSWORD: ] Password: ",
    '[sudo: ONPC-INSTALL-PASSWORD: ] private-canary: ',
    '[sudo: ONPC-INSTALL-PASSWORD: ] Password:',
    '[sudo: ONPC-INSTALL-PASSWORD: ] ',
    '[sudo: ONPC-INSTALL-PASSWORD: ] Password: \n',
    '[sudo: ONPC-INSTALL-PASSWORD: ] Password: \x1b[0m',
    '\x1b[0m[sudo: ONPC-INSTALL-PASSWORD: ] Password: ',
    '\x1b[?2004l[sudo: ONPC-INSTALL-PASSWORD: ] Password: ',
    '\x1b[?2004l\r\r[sudo: ONPC-INSTALL-PASSWORD: ] Password: ',
    'private-canary\r[sudo: ONPC-INSTALL-PASSWORD: ] Password: ',
    '\x1b]0;[sudo: ONPC-INSTALL-PASSWORD: ] Password: ',
    '\nONPC-INSTALL-PASSWORD: ',
    '\nONPC-INSTALL-PASSWORD: ] private-canary: ',
    '\nONPC-INSTALL-PASSWORD: ] Password:',
    '\nONPC-INSTALL-PASSWORD: ] Password: \x1b[0m',
    '\nONPC-INSTALL-PASSWORD: ] Password: \n',
])
def test_unrelated_private_incomplete_or_control_modified_prompts_refuse_input(prompt):
    result = subprocess.run(['/usr/bin/perl', '-I', str(LIB), '-e', PROBE, 'ok', prompt],
                            capture_output=True, text=True, timeout=10, check=True)
    data = json.loads(result.stdout)
    assert not data['ok'] and not data['retry'] and not data['capture']
    assert 'password' not in data['events']
    assert data['diagnostics'][-1] == ['install-failed-stage', 'password-prompt']
    assert 'private-canary' not in result.stdout + result.stderr


ECHO = ("/usr/bin/sudo -k -p $'\\nONPC-INSTALL-PASSWORD: ' -- "
        "/usr/bin/apt-get install -y /var/lib/onpc-e2e-assets/package.deb && "
        "printf 'ONPC-INSTALL-%s\\n' 'OK'\r\n\x1b[?2004l\r")
PROMPT = '[sudo: \r\nONPC-INSTALL-PASSWORD: ] Password: '


def serial_probe(chunks, mode='ok'):
    result = subprocess.run(['/usr/bin/perl', '-I', str(LIB), '-e', PROBE,
                             mode, '', json.dumps(chunks)],
                            capture_output=True, text=True, timeout=10, check=True)
    assert 'private-canary' not in result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert not data['retry'] and not data['capture']
    return data


@pytest.mark.parametrize('split', range(1, len(PROMPT)))
def test_installed_serial_parser_reassembles_every_prompt_boundary(split):
    data = serial_probe([ECHO, PROMPT[:split], PROMPT[split:]])
    assert data['ok'] and data['events'].count('password') == 1


@pytest.mark.parametrize(('ending', 'delivery'), [
    ('', 'marker-absent'),
    ('[sudo: \r', 'marker-absent'),
    ('[sudo: \r\nONPC-INSTALL-PASS', 'partial-marker'),
    ('[sudo: \r\nONPC-INSTALL-PASSWORD: ', 'partial-suffix'),
    ('[sudo: \r\nONPC-INSTALL-PASSWORD: ] Pass', 'partial-suffix'),
    ('[sudo: \r\nONPC-INSTALL-PASSWORD: ] private-canary: ', 'unsupported-suffix'),
    ('[sudo: \r\nONPC-INSTALL-PASSWORD: ] Password: private-canary', 'unsupported-suffix'),
    ('[sudo: \rONPC-INSTALL-PASSWORD: ] Password: ', 'unsupported-framing'),
])
def test_installed_serial_parser_timeout_preserves_safe_discriminating_diagnostics(ending, delivery):
    # One-byte echo delivery must never count as a prompt. Suffix fragments
    # deliberately stop before any complete supported prompt exists.
    # A private suffix fragmented before the fixed suffix is complete must
    # refuse too. A stream cannot predict bytes sent after a complete prompt;
    # test trailing bytes in the same read separately from partial delivery.
    chunks = [ending] if ending.endswith('Password: private-canary') else list(ending)
    data = serial_probe(list(ECHO) + chunks)
    assert not data['ok'] and 'password' not in data['events']
    assert data['events'].count('install-password') == 1  # diagnostic proof only
    title, flags = data['diagnostics'][0]
    assert title == 'install-prompt-diagnostic'
    assert 'delivery=' + delivery in flags.split()


@pytest.mark.parametrize('mode', ['process', 'echo-enabled'])
def test_fragmented_valid_prompt_still_requires_independent_recipient_proof(mode):
    data = serial_probe([ECHO] + list(PROMPT), mode)
    assert not data['ok'] and 'password' not in data['events']
