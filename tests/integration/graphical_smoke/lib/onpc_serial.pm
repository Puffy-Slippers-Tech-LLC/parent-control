package onpc_serial;
use strict;
use warnings;
use testapi ();
use onpc_password ();
use onpc_gdm ();
use onpc_install ();

my $attempted = 0;

# Inspect only the private command-result tail already returned by wait_serial.
# These fixed token observations distinguish systemctl's local inhibitor/session
# check, logind authorization and shell execution errors. They never authorize
# a retry or export user/session names, inhibitor reasons or arbitrary stderr.
sub _reboot_failure_diagnostic {
    my ($output) = @_;
    testapi::record_info('reboot-command-diagnostic',
        'authentication-required=' . ($output =~ /(?:Interactive authentication required|requires interactive authentication)/ ? 1 : 0)
        . ' access-denied=' . (index($output, 'Access denied') >= 0 ? 1 : 0)
        . ' inhibitor=' . (index($output, 'Operation inhibited by ') >= 0 ? 1 : 0)
        . ' other-session=' . ($output =~ /(?:\A|\n)User [^\n]* is logged in on [^\n]*\./ ? 1 : 0)
        . ' session-or-inhibitor-refusal=' . (index($output,
            'Please retry operation after closing inhibitors and logging out other users.') >= 0 ? 1 : 0)
        . ' shell-permission-denied=' . (index($output, '/usr/bin/systemctl: Permission denied') >= 0 ? 1 : 0)
        . ' shell-not-found=' . (index($output, '/usr/bin/systemctl: No such file or directory') >= 0 ? 1 : 0));
}

sub run {
    return _run($_[0], 0, scalar @_);
}

sub run_install {
    return _run($_[0], 1, scalar @_);
}

sub run_install_refusal {
    return _run($_[0], 2, scalar @_);
}

sub _run {
    my ($exchange, $install, $count) = @_;
    die "serial:already-attempted\n" if $attempted++;
    onpc_password::seal_capture();
    my $reboot_stage;
    my $ok = eval {
        die 'serial:arguments' unless $count == 1 && ref($exchange) eq 'CODE';
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
        if ($install) {
            $install == 2 ? onpc_install::run_refusal($exchange) : onpc_install::run($exchange);
        } else {
            # Split the marker: terminal echo cannot pass the complete output
            # assertion. Readline may emit controls immediately before stdout;
            # a preceding LF is unnecessary and rejects valid terminals.
            testapi::type_string("printf 'ONPC-SERIAL-%s\\n' 'OK'\n");
            die 'serial:command-output' unless testapi::wait_serial(qr/ONPC-SERIAL-OK\r{0,2}\n/,
                timeout => 15, quiet => 1, record_output => 0);
            $exchange->('serial-command', undef);
        }
        if ($install == 1) {
            $reboot_stage = 'ready';
            my $before = $exchange->('reboot-ready', undef);
            die 'serial:reboot-boundary' unless $before->{customer_reboot_authorized}
                && $before->{active_local_serial_session};
            # Fresh administrator authentication for this exact customer
            # command. The earlier apt authentication is not reboot authority.
            # Keep normal inhibitor policy and the existing changed-boot proof.
            # Split the marker so command echo cannot prove execution. A
            # disappearing shell may never print it; absence stays unknown.
            $reboot_stage = 'command-input';
            testapi::type_string("/usr/bin/sudo -k -p \$'\\nONPC-REBOOT-PASSWORD: ' -- /usr/bin/systemctl --no-ask-password reboot; printf 'ONPC-REBOOT-%s:%s\\n' 'RESULT' \"\$?\"\n");
            testapi::record_info('reboot-input', 'Fixed customer reboot command submitted once.');
            # Reuse the qualified explicit newline and complete sudo-rs PAM
            # suffix. Neither command echo nor a partial prompt can authorize
            # input. The independent observer verifies the reboot argv, live
            # getty/shell/sudo lineage, foreground tty and disabled character echo.
            $reboot_stage = 'password-prompt';
            die 'serial:reboot-password-prompt' unless testapi::wait_serial(
                qr/\nONPC-REBOOT-PASSWORD: \] Password: \z/,
                timeout => 30, quiet => 1, record_output => 0);
            testapi::record_info('reboot-password-prompt', 'Complete fixed sudo challenge recognized.');
            $reboot_stage = 'password-proof';
            my $proof = $exchange->('reboot-password', undef);
            die 'serial:reboot-password-boundary' unless $proof->{sudo_reboot_process_verified}
                && $proof->{terminal_echo_disabled};
            $reboot_stage = 'password-input';
            testapi::type_password($password);
            testapi::type_string("\n");
            testapi::record_info('reboot-password-submitted', 'One password submitted after independent reboot recipient proof.');
            $reboot_stage = 'command-result';
            my $output = testapi::wait_serial(
                qr/(?:ONPC-REBOOT-RESULT:[0-9]{1,3}\r{0,2}\n|\nONPC-REBOOT-PASSWORD: \] Password: \z)/,
                timeout => 15, quiet => 1, record_output => 0);
            if (defined($output) && $output =~ /\nONPC-REBOOT-PASSWORD: \] Password: \z/) {
                $reboot_stage = 'password-refused';
                die 'serial:reboot-password-refused';
            }
            my $status = defined($output) && $output =~ /ONPC-REBOOT-RESULT:([0-9]{1,3})\r{0,2}\n/
                ? 0 + $1 : undef;
            testapi::record_info('reboot-command-result', !defined($status) ? 'unobserved'
                : $status == 0 ? 'returned-zero' : 'returned-nonzero');
            if (defined($status) && $status != 0) {
                eval { _reboot_failure_diagnostic($output); };
                die 'serial:reboot-command-failed';
            }
            $reboot_stage = 'boot-observation';
            my $after = $exchange->('reboot-observed', undef);
            die 'serial:reboot-unverified' unless $after->{boot_changed};
            $reboot_stage = 'login-prompt';
            die 'serial:reboot-login-prompt' unless testapi::wait_serial(qr/ login: \z/,
                timeout => 90, quiet => 1, record_output => 0);
            testapi::record_info('reboot-serial-return',
                'Fresh login prompt received on the held serial stream after changed boot acknowledgement.');
        } else {
            testapi::type_string("exit\n");
            die 'serial:logout' unless testapi::wait_serial(qr/ login: \z/,
                timeout => 30, quiet => 1, record_output => 0);
            $exchange->('serial-logout', undef);
            testapi::record_info('serial-logout', 'Real serial logout independently acknowledged before graphical return.');
        }
        $reboot_stage = 'gdm-return' if $install == 1;
        if ($install == 1) {
            onpc_gdm::return_after_reboot();
        } else {
            onpc_gdm::return_from_serial();
        }
        $exchange->('gdm-return', undef);
        testapi::record_info('serial-command', $install == 1
            ? 'Real installation, customer reboot, serial continuity and graphical return verified.'
            : 'Real fixture serial login, fixed command output, logout and graphical return verified.');
        1;
    };
    unless ($ok) {
        eval { testapi::record_info('reboot-failed-stage', $reboot_stage); } if defined($reboot_stage);
        die "serial:qualification-failed\n";
    }
    return 1;
}

1;
