package onpc_gdm;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_pointer ();

# GDM02's functional credential binding. Prompt qualification is the caller's
# immediately following GDM03 checkpoint; account focus alone authorizes no secret.
sub choose_account {
    onpc_progress::operation('Selecting the intended greeter account');
    my ($journey, $account, $list, $list_stage, $focused_stage) = @_;
    my %bindings = (
        parent => 'parent-list/parent-focused',
        'other-parent' => 'installed-greeter/other-parent-focused',
        'other-child' => 'standard-list/standard-focused',
    );
    die 'gdm:selection-binding' unless @_ == 5 && ref($journey) eq 'onpc_journey'
        && exists($bindings{$account}) && join('/', $list_stage, $focused_stage) eq $bindings{$account};
    die 'gdm:console' unless testapi::current_console() eq 'sut';
    my $focused = $journey->highlight_choice($list, $list_stage, $focused_stage);
    $journey->consume_observation($focused_stage, $focused);
    testapi::send_key('ret');
}

# GDM04: positive wrong-account prompt and negative intended-recipient proof,
# then a single dismissal and a fresh account-list observation.
sub refuse_wrong_recipient {
    onpc_progress::operation('Rejecting the wrong-account password prompt');
    my ($journey, $wrong, $intended) = @_;
    die 'gdm:recipient-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $wrong eq 'other-parent' && ($intended eq 'parent' || $intended eq 'other-child');
    choose_account($journey, $wrong, $journey->seen('installed-greeter'),
                   'installed-greeter', 'other-parent-focused');
    my $proof = $journey->seen('wrong-recipient-refused');
    $journey->consume_observation('wrong-recipient-refused', $proof);
    testapi::send_key('esc');
    return $journey->seen($intended eq 'parent' ? 'parent-list' : 'standard-list');
}

sub functional_selection {
    onpc_progress::operation('Checking greeter account selection');
    my ($journey) = @_;
    die 'gdm:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    my $prompt = select_prompt($journey, 'parent', 'prompt');
    dismiss_observed_prompt($journey, $prompt);
}

# GDM02, fixed Parent/prompt binding. No secret recipient is authorized here.
sub select_prompt {
    onpc_progress::operation('Opening the intended account prompt');
    my ($journey, $account, $destination) = @_;
    die 'gdm:arguments' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $account eq 'parent' && $destination eq 'prompt';
    die 'gdm:console' unless testapi::current_console() eq 'sut';
    my $focused = $journey->highlight_choice($journey->seen('gdm'), 'gdm', 'focused');
    $journey->consume_observation('focused', $focused);
    testapi::send_key('ret');
    return $journey->seen('selected');
}

# GDM09 accepts the explicitly supplied, freshly acknowledged prompt. The
# controller owns ordering/freshness; this block has no prior-test dependency.
sub dismiss_observed_prompt {
    onpc_progress::operation('Dismissing the observed password prompt');
    my ($journey, $prompt) = @_;
    die 'gdm:arguments' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    die 'gdm:prompt-observation' unless ref($prompt) eq 'HASH'
        && ref($prompt->{ui}) eq 'HASH'
        && ($prompt->{ui}->{operation} // '') eq 'gdm-select-parent'
        && ($prompt->{ui}->{outcome} // '') eq 'passed'
        && ($prompt->{ui}->{interface} // '') eq 'AT-SPI';
    die 'gdm:console' unless testapi::current_console() eq 'sut';
    $journey->consume_observation('selected', $prompt);
    testapi::send_key('esc');
    return $journey->seen('dismissed');
}

# Small reviewed fixture regions, never clocks, whole-screen stillness or a
# coordinate fallback. assert_screen retains the actual match and screenshot
# in the private worker result; a timeout must stop the next input.
sub wait_list {
    onpc_progress::operation('Waiting for the greeter account list');
    my ($timeout) = @_;
    die "gdm:deadline\n" unless @_ == 1 && defined($timeout)
        && $timeout =~ /\A[0-9]+\z/ && $timeout >= 1 && $timeout <= 90;
    die "gdm:console\n" unless testapi::current_console() eq 'sut';
    my $match = testapi::assert_screen('onpc-gdm-parent-account', $timeout)
        or die "gdm:list-not-matched\n";
    return $match;
}

sub select_parent {
    onpc_progress::operation('Selecting [Parent user] in the greeter');
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
    onpc_progress::operation('Dismissing the password prompt');
    die "gdm:arguments\n" if @_;
    testapi::send_key('esc');
    wait_list(30);
}

sub return_from_serial {
    onpc_progress::operation('Returning to graphics after serial logout');
    die "gdm:arguments\n" if @_;
    return _return_from_serial('onpc-gdm-parent-account');
}

sub return_after_reboot {
    onpc_progress::operation('Waiting for the greeter after reboot');
    die "gdm:arguments\n" if @_;
    # The installed greeter's fixture-label pixels differ from the baseline.
    # Require the separately reviewed rendering at
    # the same 100% threshold. This tag never authorizes account/password input.
    return _return_from_serial('onpc-gdm-parent-installed-account');
}

sub reattach_after_setup {
    onpc_progress::operation('Reconnecting graphics after setup');
    die "gdm:arguments\n" if @_;
    reattach_functional();
    testapi::assert_screen('onpc-gdm-parent-installed-account', 90)
        or die "gdm:list-not-matched\n";
}

sub reattach_functional {
    onpc_progress::operation('Reconnecting the graphical console');
    die "gdm:arguments\n" if @_;
    die "gdm:console\n" unless testapi::current_console() eq 'sut';
    # disable closes VNC but leaves the console activated. The documented
    # reboot reset makes select_console activate it again and obtain fresh pixels.
    testapi::reset_consoles();
    testapi::select_console('sut');
}

# Installed input has a separate reviewed tag; the observation-only tag stays
# unable to authorize clicks. This acquisition route never submits a secret.
sub inspect_installed_parent {
    onpc_progress::operation('Checking the Parent sign-in prompt');
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
    onpc_progress::operation('Checking the standard-account sign-in prompt');
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
