package onpc_install;
use strict;
use warnings;
use testapi ();
use onpc_password ();

my $attempted = 0;

# The audited sudo-rs wraps the custom prompt, then appends the PAM message.
# Supply our OWN newline inside that wrapper. Bash receives literal escapes,
# so command echo cannot contain this delimiter. Require the complete fixed
# suffix; accepting the bare marker could authorize input before a fragmented
# private/unknown PAM suffix arrives. Match raw bytes before CRLF normalization.
my $marker = 'ONPC-INSTALL-PASSWORD: ';
my $suffix = '] Password: ';
my $password_prompt = qr/\n\Q$marker$suffix\E\z/;

# A failed serial match retains its ring buffer. The documented negative-match
# mode returns that buffer without recording it; never publish terminal bytes,
# lengths, arbitrary errors or identifiers. These flags diagnose only fixed
# protocol tokens. A diagnostic observation can never authorize password input.
sub _prompt_diagnostic {
    my $buffer = testapi::wait_serial(qr/(?!)/, timeout => 1,
        expect_not_found => 1, quiet => 1, record_output => 0, buffer_size => 4096);
    my $state = !defined($buffer) ? 'unavailable' : !length($buffer) ? 'empty' : 'present';
    $buffer = '' unless defined($buffer);
    # Remove only the literal echoed Bash prompt argument, not arbitrary lines.
    # Keep an incomplete marker/suffix distinct from absence in this buffer;
    # none of these observations establish what sudo emitted outside it.
    my $output = $buffer;
    my $echo_argument = q{$'\nONPC-INSTALL-PASSWORD: '};
    $output =~ s/\Q$echo_argument\E//g;
    my $delivery = 'marker-absent';
    if ($output =~ $password_prompt) {
        $delivery = 'supported';
    } elsif ($output =~ /\n\Q$marker\E(.*)\z/s) {
        my $tail = $1;
        $delivery = length($tail) < length($suffix) && index($suffix, $tail) == 0
            ? 'partial-suffix' : 'unsupported-suffix';
    } elsif (index($output, $marker) >= 0) {
        $delivery = 'unsupported-framing';
    } elsif ($output =~ /\n([^\n]*)\z/s && length($1)
            && length($1) < length($marker) && index($marker, $1) == 0) {
        $delivery = 'partial-marker';
    }
    $delivery = $state if $state ne 'present';
    my $tail = qr/printf 'ONPC-INSTALL-%s\\n' 'OK'/;
    testapi::record_info('install-prompt-diagnostic', 'buffer=' . $state
        . ' delivery=' . $delivery
        . ' command-echo=' . ($buffer =~ m{/usr/bin/sudo -k -p } ? 1 : 0)
        . ' command-tail=' . ($buffer =~ $tail ? 1 : 0)
        . ' command-enter=' . ($buffer =~ /${tail}\r{0,2}\n/ ? 1 : 0)
        . ' readline-paste-off=' . ($buffer =~ /\e\[\?2004l/ ? 1 : 0)
        . ' output-marker=' . (index($output, $marker) >= 0 ? 1 : 0)
        . ' prompt-line=' . ($output =~ /\n\Q$marker\E/ ? 1 : 0)
        . ' prompt-supported=' . ($buffer =~ $password_prompt ? 1 : 0)
        . ' sudo-error=' . ($buffer =~ /(?:\A|\n)(?:sudo|sudo-rs):/ ? 1 : 0)
        . ' unsupported-option=' . ($buffer =~ /(?:unrecognized|unexpected|invalid) (?:option|argument)/ ? 1 : 0)
        . ' shell-prompt=' . ($buffer =~ /\$ \z/ ? 1 : 0)
        . ' completion=' . ($buffer =~ /ONPC-INSTALL-OK\r?\n/ ? 1 : 0));
}

sub _command_diagnostic {
    my $buffer = testapi::wait_serial(qr/(?!)/, timeout => 1,
        expect_not_found => 1, quiet => 1, record_output => 0, buffer_size => 4096);
    testapi::record_info('install-command-diagnostic',
        'buffer=' . (!defined($buffer) ? 'unavailable' : !length($buffer) ? 'empty' : 'present')
        . ' authentication-denial=' . (defined($buffer) && $buffer =~ /Sorry, try again\./ ? 1 : 0)
        . ' apt-output=' . (defined($buffer) && $buffer =~ /Reading package lists\.\.\./ ? 1 : 0)
        . ' password-reprompt=' . (defined($buffer) && $buffer =~ $password_prompt ? 1 : 0));
}

# Called only from the authenticated serial shell. The controller owns phase,
# boot and VerifiedInputs checks; acknowledgements precede irreversible input.
# No caller command, asset path, password value or capture option is accepted.
sub run {
    my ($exchange) = @_;
    die "install:already-attempted\n" if $attempted++;
    onpc_password::seal_capture();
    my $stage = 'precondition';
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
        $stage = 'command-input';
        testapi::type_string("/usr/bin/sudo -k -p \$'\\nONPC-INSTALL-PASSWORD: ' -- /usr/bin/apt-get install -y /var/lib/onpc-e2e-assets/package.deb && printf 'ONPC-INSTALL-%s\\n' 'OK'\n");
        $stage = 'password-prompt';
        my $matched_prompt = testapi::wait_serial($password_prompt,
            timeout => 30, quiet => 1, record_output => 0);
        unless ($matched_prompt) {
            eval { _prompt_diagnostic(); };
            # Reuse the exact read-only recipient proof to distinguish a live
            # sudo password boundary from command delivery/line-editing state.
            # This consumes the normal proof phase but NEVER authorizes input:
            # the prompt failure below remains terminal even if proof succeeds.
            my $safe_recipient = eval {
                my $proof = $exchange->('install-password', undef);
                $proof->{sudo_install_process_verified} && $proof->{terminal_echo_disabled};
            };
            testapi::record_info('install-recipient-diagnostic',
                $safe_recipient ? 'exact-sudo-no-echo=verified' : 'exact-sudo-no-echo=unverified');
            die 'install:password-prompt';
        }
        testapi::record_info('install-prompt-verified', 'explicit-newline-and-fixed-pam-suffix=verified');
        $stage = 'password-proof';
        my $proof = $exchange->('install-password', undef);
        die 'install:password-boundary' unless $proof->{sudo_install_process_verified}
            && $proof->{terminal_echo_disabled};
        my $password = testapi::get_required_var('_SECRET_ONPC_PARENT_PASSWORD');
        die 'install:password-value' unless defined($password) && !ref($password)
            && $password =~ /\A[\x20-\x7e]{1,256}\z/;
        $stage = 'password-input';
        testapi::type_password($password);
        testapi::type_string("\n");
        testapi::record_info('install-password-submitted', 'Single password and Enter submitted after independent proof.');
        $stage = 'command-output';
        unless (testapi::wait_serial(qr/ONPC-INSTALL-OK\r{0,2}\n/,
                timeout => 300, quiet => 1, record_output => 0)) {
            eval { _command_diagnostic(); };
            die 'install:command-output';
        }
        $stage = 'result-proof';
        my $after = $exchange->('install-complete', undef);
        die 'install:result' unless $after->{installed_identity_verified}
            && $after->{verified_package_digest} && $after->{product_reboot_required};
        $stage = 'shell-prompt';
        die 'install:shell-prompt' unless testapi::wait_serial(qr/\$ \z/,
            timeout => 30, quiet => 1, record_output => 0);
        testapi::record_info('install-complete', 'Authenticated fixed package command and independent package result verified.');
        1;
    };
    unless ($ok) {
        # The outer serial wrapper intentionally suppresses nested exceptions.
        # Preserve only our fixed stage, including when diagnostic collection fails.
        eval { testapi::record_info('install-failed-stage', $stage); };
        die "install:boundary-failed\n";
    }
    return 1;
}

1;
