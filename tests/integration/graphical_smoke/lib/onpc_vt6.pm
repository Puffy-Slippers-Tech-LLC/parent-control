package onpc_vt6;
use strict;
use warnings;
use onpc_progress ();
use onpc_password ();
use onpc_harness ();
use testapi ();
use JSON::PP ();

my $attempted = 0;

# A VT console can prove its process and serial lineage to the controller, but
# it exposes no public automation identity for the graphical input recipient.
# Keep both retained entry points bounded and single-use, and refuse before
# console selection, image acquisition, credential access or input. The serial
# authentication route remains separate in onpc_serial.
sub authenticate {
    onpc_progress::operation('Authenticating at the fixture terminal');
    die "vt6:already-attempted\n" if $attempted++;
    onpc_password::seal_capture();
    die "vt6:public-recipient-id-required\n";
}

# A distinct external-provider route; the retired image entry points above and
# below remain unavailable. Every receipt is one-use, same-boot and exact-schema.
sub _text_receipt {
    my ($exchange, $stage, $boot, @checks) = @_;
    my $reply = $exchange->($stage, undef);
    die 'vt6:receipt' unless ref($reply) eq 'HASH'
        && keys(%$reply) == 2 + scalar(@checks)
        && ($reply->{stage} // '') eq $stage
        && defined($reply->{boot_sha256}) && !ref($reply->{boot_sha256})
        && $reply->{boot_sha256} =~ /\A[0-9a-f]{64}\z/
        && (!defined($$boot) || $$boot eq $reply->{boot_sha256});
    for my $key (@checks) {
        if ($key eq 'command_challenge') {
            die 'vt6:receipt' unless defined($reply->{$key}) && !ref($reply->{$key})
                && $reply->{$key} =~ /\A[0-9a-f]{64}\z/;
        } else {
            die 'vt6:receipt' unless JSON::PP::is_bool($reply->{$key}) && $reply->{$key};
        }
    }
    $$boot = $reply->{boot_sha256};
    return $reply;
}

sub _console_policy {
    die 'vt6:console' unless testapi::current_console() eq 'sut';
    die 'vt6:video-policy' unless testapi::get_var('NOVIDEO', 0) eq '1';
}

# The boot-time VNC connection can stop delivering keys across the guest's
# graphics initialization. Rebind it after controller readiness, before any
# console selection input or recipient proof. This is not an input retry.
sub select_boot_console {
    die 'vt6:video-policy' unless testapi::get_var('NOVIDEO', 0) eq '1';
    my $current = testapi::current_console();
    die 'vt6:console' unless !defined($current) || $current eq '' || $current eq 'sut';
    testapi::console('sut')->disable();
    testapi::reset_consoles();
    onpc_harness::select_console('initial', 'sut');
    _console_policy();
}

sub authenticate_text {
    onpc_progress::operation('Authenticating at the observed terminal login prompt');
    die "vt6:already-attempted\n" if $attempted++;
    onpc_password::seal_capture();
    my ($exchange) = @_;
    my $ok = eval {
        die 'vt6:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
        die 'vt6:video-policy' unless testapi::get_var('NOVIDEO', 0) eq '1';
        select_boot_console();
        testapi::send_key('ctrl-alt-f6');
        $exchange->('vt6-provider-inspected', undef);
        my $boot;
        _text_receipt($exchange, 'vt6-login-ready', \$boot,
            qw(vt6_getty_verified active_vt6_verified vt6_prompt_text_verified));
        _console_policy();
        testapi::type_string('onpc-parent-jamie');
        _console_policy();
        testapi::send_key('ret');
        my @password_checks = qw(vt6_login_process_verified terminal_echo_disabled
            active_vt6_verified vt6_recipient_continuity_verified vt6_prompt_text_verified);
        _text_receipt($exchange, 'vt6-password-ready', \$boot, @password_checks);
        my $proof = _text_receipt($exchange, 'vt6-password-text', \$boot,
            @password_checks, 'vt6_password_input_authorized');
        onpc_password::enter_vt6_password($proof, $boot);
        _console_policy();
        testapi::send_key('ret');
        my $shell = _text_receipt($exchange, 'vt6-shell', \$boot,
            qw(active_local_vt6_session active_vt6_verified vt6_login_continuity_verified
               vt6_command_input_authorized command_challenge));
        my $challenge = $shell->{command_challenge};
        # Same closed grammar as vt6_command.keyboard_command; never accept a
        # controller-supplied command or path. The marker proves real execution.
        my $command = "(umask 077; set -C; builtin printf '%s\\n' '$challenge'"
            . " \"\$\$\" > /tmp/onpc-vt6-command-$challenge)";
        _console_policy();
        testapi::type_string($command);
        _console_policy();
        testapi::send_key('ret');
        _text_receipt($exchange, 'vt6-authenticated', \$boot,
            qw(active_local_vt6_session active_vt6_verified vt6_shell_ready_verified
               vt6_login_continuity_verified));
        1;
    };
    unless ($ok) {
        onpc_password::seal_capture();
        die "vt6:text-authentication-failed\n";
    }
    return 1;
}

sub inspect_prompt {
    onpc_progress::operation('Inspecting the terminal login prompt');
    die "vt6:already-attempted\n" if $attempted++;
    onpc_password::seal_capture();
    die "vt6:public-recipient-id-required\n";
}

# Bounded feasibility experiment, separate from both retired input routes.
# Consume the shared attempt before selecting the console; an uncertain key
# delivery must never be retried. No image, account or credential is accessed.
sub diagnose_provider {
    onpc_progress::operation('Inspecting the selected terminal without entering an account or password');
    die "vt6:already-attempted\n" if $attempted++;
    onpc_password::seal_capture();
    my ($exchange) = @_;
    my $ok = eval {
        die 'vt6:diagnostic-arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
        die 'vt6:video-policy' unless testapi::get_var('NOVIDEO', 0) eq '1';
        onpc_harness::select_console('initial', 'sut');
        onpc_progress::operation('Selecting the terminal once to inspect its login prompt');
        testapi::send_key('ctrl-alt-f6');
        $exchange->('vt6-provider-inspected', undef);
        1;
    };
    die "vt6:provider-diagnostic-failed\n" unless $ok;
    # A recorded prompt is not a qualified credential recipient. Authentication
    # and the independently verified command are still required for a pass.
    die "vt6:provider-diagnostic-only\n";
}

1;
