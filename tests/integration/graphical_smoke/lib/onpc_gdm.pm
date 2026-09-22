package onpc_gdm;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_pointer ();
use onpc_journey ();

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

# GDM01/02 ordinary-account qualification. Each list reply is consumed once,
# and each Escape follows its own fresh nonsecret prompt observation. The
# second cycle must start from a separately acquired complete list.
sub navigation_qualification_with_prefix {
    onpc_progress::operation('Checking the declared greeter navigation sequence');
    my ($exchange, $prefix) = @_;
    die 'gdm:arguments' unless @_ == 2 && ref($exchange) eq 'CODE'
        && ($prefix eq 'gdm-navigation' || $prefix eq 'gdm-product-free');
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => $prefix, review => 0);
    reattach_functional();

    for my $cycle ('initial', 'repeated') {
        my $list_stage = "$cycle-list";
        my $focused_stage = "$cycle-focused";
        my $list = $journey->seen($list_stage);
        my $focused = $journey->highlight_choice(
            $list, $list_stage, $focused_stage);
        $journey->consume_observation($focused_stage, $focused);
        testapi::send_key('ret');
        my $prompt = $journey->seen("$cycle-prompt");
        $journey->consume_observation("$cycle-prompt", $prompt);
        testapi::send_key('esc');
        $journey->seen("$cycle-returned");
    }
    $journey->finish();
}

sub navigation_qualification {
    onpc_progress::operation('Qualifying ordinary greeter account navigation');
    my ($exchange) = @_;
    die 'gdm:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    navigation_qualification_with_prefix($exchange, 'gdm-navigation');
}

sub product_free_qualification {
    onpc_progress::operation('Qualifying product-free greeter account navigation');
    my ($exchange) = @_;
    die 'gdm:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    navigation_qualification_with_prefix($exchange, 'gdm-product-free');
}

# GDM01/02/03/04/08/09 qualification. The worker never receives or submits a
# credential. Every prompt proof is consumed before Escape, and the two empty
# intended-recipient checks are separate controller observations of one prompt.
sub recipient_qualification {
    onpc_progress::operation('Qualifying the greeter password recipient');
    my ($exchange) = @_;
    die 'gdm:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'gdm-recipient', review => 0);
    reattach_functional();

    my $wrong = $journey->seen('wrong-list');
    my $wrong_focused = $journey->highlight_choice(
        $wrong, 'wrong-list', 'wrong-focused');
    $journey->consume_observation('wrong-focused', $wrong_focused);
    testapi::send_key('ret');
    my $refusal = $journey->seen('wrong-recipient-refused');
    die 'gdm:wrong-recipient-proof' unless ref($refusal) eq 'HASH'
        && keys(%$refusal) == 1
        && ($refusal->{observed} // '') eq 'wrong-recipient-refused';
    $journey->consume_observation('wrong-recipient-refused', $refusal);
    testapi::send_key('esc');

    $journey->seen('wrong-returned');
    my $intended = $journey->seen('intended-list');
    my $intended_focused = $journey->highlight_choice(
        $intended, 'intended-list', 'intended-focused');
    $journey->consume_observation('intended-focused', $intended_focused);
    testapi::send_key('ret');

    my $proof;
    for my $stage ('recipient-qualified', 'recipient-rechecked') {
        $proof = $journey->seen($stage);
        die 'gdm:recipient-proof' unless ref($proof) eq 'HASH'
            && keys(%$proof) == 1 && ($proof->{observed} // '') eq $stage;
    }
    $journey->consume_observation('recipient-rechecked', $proof);
    my $prompt = $journey->seen('intended-prompt');
    die 'gdm:prompt-proof' unless ref($prompt) eq 'HASH'
        && keys(%$prompt) == 1 && ($prompt->{observed} // '') eq 'intended-prompt';
    $journey->consume_observation('intended-prompt', $prompt);
    testapi::send_key('esc');
    $journey->seen('intended-returned');
    $journey->finish();
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
    return _dismiss_observed_prompt($journey, $prompt, 'gdm-select-parent', scalar @_);
}

sub dismiss_product_free_prompt {
    onpc_progress::operation('Dismissing the product-free password prompt');
    my ($journey, $prompt) = @_;
    return _dismiss_observed_prompt(
        $journey, $prompt, 'gdm-product-free-select-parent', scalar @_);
}

sub _dismiss_observed_prompt {
    my ($journey, $prompt, $operation, $count) = @_;
    die 'gdm:arguments' unless $count == 2 && @_ == 4
        && ref($journey) eq 'onpc_journey';
    die 'gdm:prompt-observation' unless ref($prompt) eq 'HASH'
        && ref($prompt->{ui}) eq 'HASH'
        && ($prompt->{ui}->{operation} // '') eq $operation
        && ($prompt->{ui}->{outcome} // '') eq 'passed'
        && ($prompt->{ui}->{interface} // '') eq 'AT-SPI';
    die 'gdm:console' unless testapi::current_console() eq 'sut';
    $journey->consume_observation('selected', $prompt);
    testapi::send_key('esc');
    return $journey->seen('dismissed');
}

# Retained legacy entry points refuse until the installed provider exposes the
# complete public-ID contract used by the functional GDM route above.
sub wait_list {
    onpc_progress::operation('Waiting for the greeter account list');
    die "gdm:provider-id-required\n";
}

sub select_parent {
    onpc_progress::operation('Selecting [Parent user] in the greeter');
    die "gdm:provider-id-required\n";
}

sub dismiss_prompt {
    onpc_progress::operation('Dismissing the password prompt');
    die "gdm:provider-id-required\n";
}

sub return_from_serial {
    onpc_progress::operation('Returning to graphics after serial logout');
    die "gdm:provider-id-required\n";
}

sub return_after_reboot {
    onpc_progress::operation('Waiting for the greeter after reboot');
    die "gdm:provider-id-required\n";
}

sub reattach_after_setup {
    onpc_progress::operation('Reconnecting graphics after setup');
    die "gdm:provider-id-required\n";
}

sub reattach_functional {
    onpc_progress::operation('Reconnecting the graphical console');
    die "gdm:arguments\n" if @_;
    my $current = testapi::current_console();
    die "gdm:console\n" if defined($current) && $current ne 'sut';
    # disable closes VNC but leaves the console activated. The documented
    # reboot reset makes select_console activate it again and obtain fresh pixels.
    testapi::reset_consoles();
    testapi::select_console('sut');
    die "gdm:reconnect\n" unless (testapi::current_console() // '') eq 'sut';
}

# Installed input has a separate reviewed tag; the observation-only tag stays
# unable to authorize clicks. This acquisition route never submits a secret.
sub inspect_installed_parent {
    onpc_progress::operation('Checking the Parent sign-in prompt');
    die "gdm:provider-id-required\n";
}

# Select the fixed visible child-role fixture without submitting its password.
# The separate prompt acquisition is still pre-authentication and cannot
# authorize later secret input by itself.
sub inspect_installed_standard {
    onpc_progress::operation('Checking the standard-account sign-in prompt');
    die "gdm:provider-id-required\n";
}

sub _return_from_serial {
    die "gdm:provider-id-required\n";
}

1;
