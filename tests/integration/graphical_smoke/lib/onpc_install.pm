package onpc_install;
use strict;
use warnings;
use testapi ();
use onpc_password ();

my $attempted = 0;

# Called only from the authenticated serial shell. The controller owns phase,
# boot and VerifiedInputs checks; acknowledgements precede irreversible input.
# No caller command, asset path, password value or capture option is accepted.
sub run {
    my ($exchange) = @_;
    die "install:already-attempted\n" if $attempted++;
    onpc_password::seal_capture();
    my $ok = eval {
        die 'install:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
        die 'install:video-policy' unless testapi::get_var('NOVIDEO', 0) eq '1';
        die 'install:console' unless testapi::current_console() eq 'onpc-serial';
        my $before = $exchange->('install-ready', undef);
        die 'install:precondition' unless $before->{installation_authorized}
            && $before->{product_package_absent} && $before->{verified_assets}
            && $before->{active_local_serial_session};
        # -k forces fresh authentication for this command. The marker is split
        # so command echo cannot prove successful apt completion.
        testapi::type_string("/usr/bin/sudo -k -p 'ONPC-INSTALL-PASSWORD: ' -- /usr/bin/apt-get install -y /var/lib/onpc-e2e-assets/package.deb && printf 'ONPC-INSTALL-%s\\n' 'OK'\n");
        die 'install:password-prompt' unless testapi::wait_serial(qr/ONPC-INSTALL-PASSWORD: \z/,
            timeout => 30, quiet => 1, record_output => 0);
        my $proof = $exchange->('install-password', undef);
        die 'install:password-boundary' unless $proof->{sudo_install_process_verified}
            && $proof->{terminal_echo_disabled};
        my $password = testapi::get_required_var('_SECRET_ONPC_PARENT_PASSWORD');
        die 'install:password-value' unless defined($password) && !ref($password)
            && $password =~ /\A[\x20-\x7e]{1,256}\z/;
        testapi::type_password($password);
        testapi::type_string("\n");
        die 'install:command-output' unless testapi::wait_serial(qr/ONPC-INSTALL-OK\r{0,2}\n/,
            timeout => 300, quiet => 1, record_output => 0);
        my $after = $exchange->('install-complete', undef);
        die 'install:result' unless $after->{installed_identity_verified}
            && $after->{verified_package_digest} && $after->{product_reboot_required};
        die 'install:shell-prompt' unless testapi::wait_serial(qr/\$ \z/,
            timeout => 30, quiet => 1, record_output => 0);
        testapi::record_info('install-complete', 'Authenticated fixed package command and independent package result verified.');
        1;
    };
    die "install:boundary-failed\n" unless $ok;
    return 1;
}

1;
