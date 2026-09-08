package onpc_serial;
use strict;
use warnings;
use testapi ();
use onpc_password ();

my $attempted = 0;

sub run {
    my ($exchange) = @_;
    die "serial:already-attempted\n" if $attempted++;
    onpc_password::seal_capture();
    my $ok = eval {
        die 'serial:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
        die 'serial:video-policy' unless testapi::get_var('NOVIDEO', 0) eq '1';
        testapi::select_console('onpc-serial');
        die 'serial:console' unless testapi::current_console() eq 'onpc-serial';
        # A banner/command echo cannot satisfy a fresh password prompt. Do not
        # log terminal output; it contains private guest/fixture identifiers.
        die 'serial:login-prompt' unless testapi::wait_serial(qr/ login: \z/,
            timeout => 30, quiet => 1, record_output => 0);
        testapi::type_string("onpc-parent-jamie\n");
        # login wipes argv's username for privacy. Require the exact real echo
        # of our selected fixture and the subsequent password prompt together.
        my $prompt = testapi::wait_serial(qr/Password: \z/,
            timeout => 15, quiet => 1, record_output => 0);
        die 'serial:password-prompt' unless defined($prompt) && length($prompt) <= 256;
        # agetty writes CRLF with ONLCR enabled, producing CRCRLF. Public
        # wait_serial normalizes one CRLF layer in its returned string. Match
        # only the resulting LF/CRLF forms and the exact selected fixture.
        my $cr_count = () = $prompt =~ /\r/g;
        my $lf_count = () = $prompt =~ /\n/g;
        testapi::record_info('serial-prompt', 'fixture-echo=' . ($prompt =~ /\Aonpc-parent-jamie/ ? 1 : 0)
            . ' cr=' . $cr_count . ' lf=' . $lf_count);
        die 'serial:fixture-echo' unless $prompt =~ /\Aonpc-parent-jamie\r?\nPassword: \z/;
        my $proof = $exchange->('serial-password', undef);
        die 'serial:password-boundary' unless $proof->{serial_login_process_verified}
            && $proof->{terminal_echo_disabled};
        my $password = testapi::get_required_var('_SECRET_ONPC_PARENT_PASSWORD');
        die 'serial:password-value' unless defined($password) && !ref($password)
            && $password =~ /\A[\x20-\x7e]{1,256}\z/;
        # Public secret-safe API, fixed options, no root-password shortcut.
        testapi::type_password($password);
        testapi::type_string("\n");
        $exchange->('serial-authenticated', undef);
        # logind activation precedes the interactive shell. Wait for its real
        # prompt before typing; login/PAM may still be initializing the tty.
        die 'serial:shell-prompt' unless testapi::wait_serial(qr/\$ \z/,
            timeout => 30, quiet => 1, record_output => 0);
        # Split the marker in the typed command: terminal echo cannot pass the
        # complete output assertion. This changes no guest file.
        testapi::type_string("printf 'ONPC-SERIAL-%s\\n' 'OK'\n");
        # Readline may emit bracketed-paste/CR controls immediately before
        # stdout. The complete marker cannot occur in the split command echo,
        # so a preceding LF is unnecessary and would reject valid terminals.
        die 'serial:command-output' unless testapi::wait_serial(qr/ONPC-SERIAL-OK\r{0,2}\n/,
            timeout => 15, quiet => 1, record_output => 0);
        $exchange->('serial-command', undef);
        testapi::type_string("exit\n");
        die 'serial:logout' unless testapi::wait_serial(qr/ login: \z/,
            timeout => 30, quiet => 1, record_output => 0);
        $exchange->('serial-logout', undef);
        testapi::select_console('sut');
        testapi::record_info('serial-command', 'Real fixture serial login, fixed command output, logout and graphical return verified.');
        1;
    };
    die "serial:qualification-failed\n" unless $ok;
    return 1;
}

1;
