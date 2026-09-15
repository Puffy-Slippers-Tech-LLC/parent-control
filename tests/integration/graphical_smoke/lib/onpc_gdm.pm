package onpc_gdm;
use strict;
use warnings;
use testapi ();
use onpc_pointer ();

sub functional_selection {
    my ($journey) = @_;
    die 'gdm:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    die 'gdm:console' unless testapi::current_console() eq 'sut';
    $journey->navigate_choice($journey->seen('gdm'));
    $journey->seen('focused');
    testapi::send_key('ret');
    $journey->seen('selected');
    testapi::send_key('esc');
    $journey->seen('dismissed');
}

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

sub reattach_after_setup {
    die "gdm:arguments\n" if @_;
    die "gdm:console\n" unless testapi::current_console() eq 'sut';
    # disable closes VNC but leaves the console activated. The documented
    # reboot reset makes select_console activate it again and obtain fresh pixels.
    testapi::reset_consoles();
    testapi::select_console('sut');
    testapi::assert_screen('onpc-gdm-parent-installed-account', 90)
        or die "gdm:list-not-matched\n";
}

# Installed input has a separate reviewed tag; the observation-only tag stays
# unable to authorize clicks. This acquisition route never submits a secret.
sub inspect_installed_parent {
    die "gdm:arguments\n" if @_;
    die "gdm:console\n" unless testapi::current_console() eq 'sut';
    testapi::assert_and_click('onpc-gdm-parent-installed-input-account', timeout => 30, mousehide => 1);
    testapi::wait_still_screen(1, 10);
    die "gdm:list-still-visible\n"
        if testapi::check_screen('onpc-gdm-parent-installed-account', 1);
}

# Select the fixed visible child-role fixture without submitting its password.
# The separate prompt acquisition is still pre-authentication and cannot
# authorize later secret input by itself.
sub inspect_installed_standard {
    my ($verify_parent) = @_;
    die "gdm:arguments\n" if @_ > 1 || (defined($verify_parent) && ref($verify_parent) ne 'CODE');
    die "gdm:console\n" unless testapi::current_console() eq 'sut';
    # GDM scrolls its list while changing focus. Establish the Parent prompt,
    # return to the list, start at Home, and reach the fixed baseline fixture.
    # Escape resets focus to the top, not the account whose prompt was open.
    # A positive focused-row match guards Enter; the caller independently
    # requires the role-specific empty prompt before any password input.
    onpc_pointer::click('onpc-gdm-parent-installed-input-account', 30);
    testapi::assert_screen('onpc-gdm-parent-masked-password', 30);
    $verify_parent->() if defined($verify_parent);
    testapi::send_key('esc');
    testapi::assert_screen('onpc-gdm-parent-installed-account', 30);
    testapi::send_key('home');
    testapi::send_key('down') for 1 .. 4;
    testapi::assert_screen('onpc-gdm-standard-selected-account', 30);
    testapi::send_key('ret');
    testapi::wait_still_screen(1, 10);
    die "gdm:list-still-visible\n"
        if testapi::check_screen('onpc-gdm-parent-installed-account', 1);
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
