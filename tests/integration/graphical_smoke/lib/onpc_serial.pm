package onpc_serial;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_password ();
use onpc_gdm ();
use onpc_install ();
use onpc_harness ();

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
    onpc_progress::operation('Running serial console checks');
    return _run($_[0], 0, scalar @_);
}

sub run_functional {
    onpc_progress::operation('Running functional serial console checks');
    require onpc_flow00;
    return onpc_flow00::serial(@_);
}

sub run_install {
    onpc_progress::operation('Installing through the serial console');
    return _run($_[0], 1, scalar @_);
}

sub run_install_refusal {
    onpc_progress::operation('Checking installation refusal through the serial console');
    return _run($_[0], 2, scalar @_);
}

# The original single-attempt and capture boundary surrounds all compositions,
# including legacy installation/refusal consumers. It is never reset.
sub attempt {
    onpc_progress::operation('Starting the declared serial action');
    my ($exchange, $body) = @_;
    die "serial:already-attempted\n" if $attempted++;
    onpc_password::seal_capture();
    my $state = {exchange => $exchange, phase => 'new'};
    my $ok = eval {
        die 'serial:arguments' unless @_ == 2 && ref($exchange) eq 'CODE' && ref($body) eq 'CODE';
        die 'serial:video-policy' unless testapi::get_var('NOVIDEO', 0) eq '1';
        $body->($state);
        1;
    };
    $state->{phase} = 'closed';
    die "serial:qualification-failed\n" unless $ok;
    return 1;
}

sub _block {
    my ($state, $before, $after, $body) = @_;
    my $valid = ref($state) eq 'HASH'
        && ref($state->{exchange}) eq 'CODE' && ($state->{phase} // '') eq $before;
    # Consume before input: an uncertain operation cannot be retried even if a
    # caller catches its exception. Successful blocks return explicit evidence.
    $state->{phase} = 'failed' if ref($state) eq 'HASH';
    die 'serial:block-order' unless $valid;
    my $result = $body->();
    $state->{phase} = $after;
    return $result;
}

# HAR02: closed projections, fixed deadlines and private terminal output.
sub observe_text {
    onpc_progress::operation('Checking expected terminal text');
    my ($projection) = @_;
    die 'serial:text-arguments' unless @_ == 1 && defined($projection);
    die 'serial:console' unless testapi::current_console() eq 'onpc-serial';
    my %profiles = (
        login => [qr/ login: \z/, 30, 'login-prompt'],
        password => [qr/Password: \z/, 15, 'password-prompt'],
        shell => [qr/\$ \z/, 30, 'shell-prompt'],
        command => [qr/ONPC-SERIAL-OK\r{0,2}\n/, 15, 'command-output'],
        logout => [qr/ login: \z/, 30, 'logout'],
    );
    die 'serial:text-projection' unless exists $profiles{$projection};
    my ($regex, $timeout, $error) = @{$profiles{$projection}};
    my $value = testapi::wait_serial($regex, timeout => $timeout, quiet => 1, record_output => 0);
    if ($projection eq 'password') {
        die 'serial:password-prompt' unless defined($value) && length($value) <= 256;
        # wait_serial normalizes one CRLF layer of agetty's CRCRLF output.
        my $cr_count = () = $value =~ /\r/g;
        my $lf_count = () = $value =~ /\n/g;
        testapi::record_info('serial-prompt', 'fixture-echo=' . ($value =~ /\Aonpc-parent-jamie/ ? 1 : 0)
            . ' cr=' . $cr_count . ' lf=' . $lf_count);
        die 'serial:fixture-echo' unless $value =~ /\Aonpc-parent-jamie\r?\nPassword: \z/;
    } else {
        die 'serial:' . $error unless $value;
    }
    return {projection => $projection, matched => 1};
}

# UI19, serial-only binding: no submission, no new authentication capability.
sub type_fixture_secret {
    onpc_progress::operation('Entering the protected fixture credential');
    my ($state, $reference, $proof) = @_;
    return _block($state, 'password', 'secret-typed', sub {
        die 'serial:secret-reference' unless $reference eq 'parent-serial';
        die 'serial:console' unless testapi::current_console() eq 'onpc-serial';
        die 'serial:password-boundary' unless ref($proof) eq 'HASH'
            && $proof == $state->{password_proof}
            && $proof->{serial_login_process_verified} && $proof->{terminal_echo_disabled};
        my $password = testapi::get_required_var('_SECRET_ONPC_PARENT_PASSWORD');
        die 'serial:password-value' unless defined($password) && !ref($password)
            && $password =~ /\A[\x20-\x7e]{1,256}\z/;
        testapi::type_password($password);
        return {secret_typed => 1};
    });
}

# HAR05: login/session readiness is separate from command execution.
sub login {
    onpc_progress::operation('Signing in through the serial console');
    my ($state) = @_;
    return _block($state, 'new', 'authenticated', sub {
        onpc_password::seal_capture();
        onpc_harness::select_console('sut', 'onpc-serial');
        observe_text('login');
        testapi::type_string("onpc-parent-jamie\n");
        observe_text('password');
        my $proof = $state->{exchange}->('serial-password', undef);
        $state->{password_proof} = $proof;
        $state->{phase} = 'password';
        type_fixture_secret($state, 'parent-serial', $proof);
        $state->{phase} = 'failed';
        testapi::type_string("\n");
        my $session = $state->{exchange}->('serial-authenticated', undef);
        observe_text('shell');
        return $session;
    });
}

# HAR06: split marker keeps command echo from satisfying actual stdout.
sub command {
    onpc_progress::operation('Running the declared terminal command');
    my ($state) = @_;
    return _block($state, 'authenticated', 'command-observed', sub {
        die 'serial:console' unless testapi::current_console() eq 'onpc-serial';
        testapi::type_string("printf 'ONPC-SERIAL-%s\\n' 'OK'\n");
        observe_text('command');
        return $state->{exchange}->('serial-command', undef);
    });
}

# HAR07: the returned acknowledgement is single-use evidence for HAR08.
sub logout {
    onpc_progress::operation('Logging out of the serial console');
    my ($state) = @_;
    return _block($state, 'command-observed', 'logged-out', sub {
        die 'serial:console' unless testapi::current_console() eq 'onpc-serial';
        testapi::type_string("exit\n");
        observe_text('logout');
        my $proof = $state->{exchange}->('serial-logout', undef);
        die 'serial:logout-proof' unless ref($proof) eq 'HASH'
            && $proof->{active_graphical_greeter}
            && exists($proof->{unexpected_user_session}) && !$proof->{unexpected_user_session};
        $state->{logout_proof} = $proof;
        testapi::record_info('serial-logout', 'Real serial logout independently acknowledged before graphical return.');
        return $proof;
    });
}

# HAR08: the exchange combines fresh HAR03(greeter) and GDM01 observations.
sub return_graphics {
    onpc_progress::operation('Returning to the graphical console');
    my ($state, $logout) = @_;
    return _block($state, 'logged-out', 'returned', sub {
        die 'serial:logout-proof' unless ref($logout) eq 'HASH'
            && $logout == $state->{logout_proof};
        onpc_harness::select_console('onpc-serial', 'sut');
        return $state->{exchange}->('gdm-return', undef);
    });
}

sub _run {
    my ($exchange, $install, $count) = @_;
    return attempt($exchange, sub {
    my ($state) = @_;
    my $reboot_stage;
    my $ok = eval {
        die 'serial:arguments' unless $count == 1 && ref($exchange) eq 'CODE';
        login($state);
        if ($install) {
            $install == 2 ? onpc_install::run_refusal($exchange) : onpc_install::run($exchange);
        } else {
            command($state);
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
            # The extracted serial blocks return only semantic observations.
            # Keep this legacy second challenge's secret local to its input.
            my $password = testapi::get_required_var('_SECRET_ONPC_PARENT_PASSWORD');
            die 'serial:password-value' unless defined($password) && !ref($password)
                && $password =~ /\A[\x20-\x7e]{1,256}\z/;
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
            $state->{phase} = 'command-observed' if $install == 2;
            logout($state);
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
    });
}

1;
