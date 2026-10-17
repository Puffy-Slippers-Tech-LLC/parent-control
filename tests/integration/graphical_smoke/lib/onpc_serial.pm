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
            # OS lifecycle input belongs to the controller's pinned SSH
            # transport. The worker submits no shell command or reboot secret.
            $reboot_stage = 'ssh-request';
            my $requested = $exchange->('reboot-requested', undef);
            die 'serial:reboot-request-unverified' unless $requested->{reboot_requested};
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
