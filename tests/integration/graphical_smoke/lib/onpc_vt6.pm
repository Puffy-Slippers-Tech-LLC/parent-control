package onpc_vt6;
use strict;
use warnings;
use testapi ();
use onpc_password ();

my $attempted = 0;

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
