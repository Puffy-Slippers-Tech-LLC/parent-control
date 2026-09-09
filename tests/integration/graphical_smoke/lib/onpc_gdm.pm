package onpc_gdm;
use strict;
use warnings;
use testapi ();

# Small reviewed fixture regions, never clocks, whole-screen stillness or a
# coordinate fallback. assert_screen retains the actual match and screenshot
# in the private worker result; a timeout must stop the next input.
sub wait_list {
    my ($timeout) = @_;
    die "gdm:deadline\n" unless @_ == 1 && defined($timeout)
        && $timeout =~ /\A[0-9]+\z/ && $timeout >= 1 && $timeout <= 90;
    die "gdm:console\n" unless testapi::current_console() eq 'sut';
    my $match = testapi::assert_screen('onpc-gdm-parent-account', $timeout)
        or die "gdm:list-not-matched\n";
    return $match;
}

sub select_parent {
    die "gdm:arguments\n" if @_;
    wait_list(30);
    testapi::assert_and_click('onpc-gdm-parent-account', timeout => 30, mousehide => 1);
    testapi::assert_screen('onpc-gdm-parent-masked-password', 30)
        or die "gdm:prompt-not-matched\n";
    # A deliberate negative match also guards reuse of the list needle for
    # readiness: the selected account prompt must not satisfy it.
    die "gdm:list-false-positive\n"
        if testapi::check_screen('onpc-gdm-parent-account', 1);
    testapi::record_info('gdm-prompt', 'Reviewed empty fixture prompt matched; account-list needle refused.');
}

sub dismiss_prompt {
    die "gdm:arguments\n" if @_;
    testapi::send_key('esc');
    wait_list(30);
}

sub return_from_serial {
    die "gdm:arguments\n" if @_;
    return _return_from_serial('onpc-gdm-parent-account');
}

sub return_after_reboot {
    die "gdm:arguments\n" if @_;
    # The installed greeter's fixture-label pixels differ from the baseline.
    # Require the separately reviewed rendering at
    # the same 100% threshold. This tag never authorizes account/password input.
    return _return_from_serial('onpc-gdm-parent-installed-account');
}

sub _return_from_serial {
    my ($tag) = @_;
    die "gdm:serial-console\n" unless testapi::current_console() eq 'onpc-serial';
    testapi::select_console('sut');
    die "gdm:console\n" unless testapi::current_console() eq 'sut';
    testapi::assert_screen($tag, 30) or die "gdm:list-not-matched\n";
    testapi::record_info('gdm-return', 'Account list matched after serial flow and graphical-console selection.');
    # Do not reopen explicit capture after authentication. The public match's
    # automatic screenshot remains private under the existing worker policy.
}

1;
