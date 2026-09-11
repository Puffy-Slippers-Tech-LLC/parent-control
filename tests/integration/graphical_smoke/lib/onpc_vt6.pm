package onpc_vt6;
use strict;
use warnings;
use JSON::PP ();
use testapi ();
use onpc_password ();

my $attempted = 0;

# Authentication uses a distinct, exact controller protocol. The credential-free
# collector's booleans cannot authorize input. The controller must bind these
# receipts to this worker, its fresh capture, boot and observed process lineage.
sub _receipt {
    my ($reply, $stage, $boot, @proofs) = @_;
    die 'vt6:receipt' unless ref($reply) eq 'HASH'
        && keys(%$reply) == 2 + @proofs
        && defined($reply->{stage}) && !ref($reply->{stage}) && $reply->{stage} eq $stage
        && defined($reply->{boot_sha256}) && !ref($reply->{boot_sha256})
        && $reply->{boot_sha256} =~ /\A[0-9a-f]{64}\z/
        && (!defined($boot) || $reply->{boot_sha256} eq $boot);
    for my $name (@proofs) {
        die 'vt6:proof' unless JSON::PP::is_bool($reply->{$name}) && $reply->{$name};
    }
    return $reply->{boot_sha256};
}

sub _input_console {
    die 'vt6:video-policy' unless testapi::get_var('NOVIDEO', 0) eq '1';
    die 'vt6:console' unless testapi::current_console() eq 'sut';
}

# Selected only by the guarded authentication qualification controller.
# No installation command, logout or retry is implicit in login.
sub authenticate {
    die "vt6:already-attempted\n" if $attempted++;
    my ($exchange) = @_;
    my $ok = eval {
        die 'vt6:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
        die 'vt6:video-policy' unless testapi::get_var('NOVIDEO', 0) eq '1';
        testapi::select_console('sut');
        _input_console();
        testapi::send_key('ctrl-alt-f6');
        testapi::wait_still_screen(1, 10);
        my $boot = _receipt($exchange->('vt6-login-ready', undef), 'vt6-login-ready', undef,
            qw(vt6_getty_verified active_vt6_verified));
        die 'vt6:prompt-false-positive' if testapi::check_screen('onpc-vt6-parent-password', 1);
        _input_console();
        testapi::type_string('onpc-parent-jamie', secret => 1);
        testapi::send_key('ret');
        testapi::wait_still_screen(1, 10);
        _receipt($exchange->('vt6-password-ready', undef), 'vt6-password-ready', $boot,
            qw(vt6_login_process_verified terminal_echo_disabled active_vt6_verified
               vt6_recipient_continuity_verified));
        # Both screen gates are mandatory. assert_screen's similarity alone
        # accepts sparse extra output; the controller must compare this capture
        # exactly with the provenance-bound reference and recheck the recipient.
        testapi::assert_screen('onpc-vt6-parent-password', 30) or die 'vt6:prompt';
        my $capture = onpc_password::capture_before_authentication();
        onpc_password::seal_capture();
        _receipt($exchange->('vt6-password-screen', $capture->{screenshot}),
            'vt6-password-screen', $boot,
            qw(vt6_login_process_verified terminal_echo_disabled active_vt6_verified
               vt6_recipient_continuity_verified vt6_prompt_pixels_verified
               vt6_password_input_authorized));
        _input_console();
        my $password = testapi::get_required_var('_SECRET_ONPC_PARENT_PASSWORD');
        die 'vt6:password-value' unless defined($password) && !ref($password)
            && $password =~ /\A[\x20-\x7e]{1,256}\z/;
        _input_console();
        testapi::type_password($password);
        # A failed or partially delivered password must never submit or retry.
        _input_console();
        testapi::send_key('ret');
        my $command = $exchange->('vt6-shell', undef);
        die 'vt6:command-receipt' unless ref($command) eq 'HASH';
        my %proof = %$command;
        my $challenge = delete $proof{command_challenge};
        die 'vt6:command-challenge' unless defined($challenge) && !ref($challenge)
            && $challenge =~ /\A[0-9a-f]{64}\z/;
        _receipt(\%proof, 'vt6-shell', $boot,
            qw(active_local_vt6_session active_vt6_verified vt6_login_continuity_verified
               vt6_command_input_authorized));
        # The fresh nonce is nonsecret. Only this grammar is accepted: no
        # controller-supplied command, output capture or input retry is possible.
        my $line = "(umask 077; set -C; builtin printf '%s\\n' '$challenge' "
            . '"$$" > /tmp/onpc-vt6-command-' . $challenge . ')';
        _input_console();
        testapi::type_string($line, secret => 1);
        _input_console();
        testapi::send_key('ret');
        _receipt($exchange->('vt6-authenticated', undef), 'vt6-authenticated', $boot,
            qw(active_local_vt6_session active_vt6_verified vt6_shell_ready_verified
               vt6_login_continuity_verified));
        1;
    };
    onpc_password::seal_capture();
    die "vt6:authentication-failed\n" unless $ok;
    return 1;
}

# Collect the missing reviewed fixture/challenge pixels without provisioning,
# reading or submitting a password. This is not an authentication fallback.
sub inspect_prompt {
    die "vt6:already-attempted\n" if $attempted++;
    my ($exchange) = @_;
    my $ok = eval {
        die 'vt6:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
        die 'vt6:video-policy' unless testapi::get_var('NOVIDEO', 0) eq '1';
        testapi::select_console('sut');
        die 'vt6:console' unless testapi::current_console() eq 'sut';
        testapi::send_key('ctrl-alt-f6');
        testapi::wait_still_screen(1, 10);
        my $getty = $exchange->('vt6-ready', undef);
        die 'vt6:getty' unless $getty->{vt6_getty_verified} && $getty->{active_vt6_verified};
        my $login = onpc_password::capture_before_authentication();
        $exchange->('vt6-login-screen', $login->{screenshot});
        # The fixed fixture selection is private in raw capture, never a secret
        # or customer command. This route has no password capability at all.
        testapi::type_string('onpc-parent-jamie', secret => 1);
        testapi::send_key('ret');
        testapi::wait_still_screen(1, 10);
        my $proof = $exchange->('vt6-prompt-ready', undef);
        die 'vt6:recipient' unless $proof->{vt6_login_process_verified}
            && $proof->{terminal_echo_disabled} && $proof->{active_vt6_verified};
        my $prompt = onpc_password::capture_before_authentication();
        $exchange->('vt6-prompt-screen', $prompt->{screenshot});
        1;
    };
    onpc_password::seal_capture();
    die "vt6:prompt-inspection-failed\n" unless $ok;
    return 1;
}

1;
