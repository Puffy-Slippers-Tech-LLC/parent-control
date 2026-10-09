package onpc_desktop_session;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();
use onpc_password ();
use onpc_app_rows ();

# DESK03: shared system lock/switch command, then independent GDM observation.
sub switch_user {
    onpc_progress::operation('Switching to the greeter');
    my ($journey, $desktop, $stage) = @_;
    $stage //= 'desktop';
    die 'desk:switch-binding' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey'
        && ($stage eq 'desktop' || $stage eq 'repeat-desktop');
    $journey->consume_observation($stage, $desktop);
    $journey->seen('switch-user');
    return $journey->seen('gdm-switched');
}

# DESK04: direct session logout, then independent GDM observation.
sub log_out {
    onpc_progress::operation('Logging out the fixture desktop');
    my ($journey, $desktop) = @_;
    die 'desk:logout-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('desktop', $desktop);
    $journey->seen('logout');
    return $journey->seen('gdm-logged-out');
}

# DESK06: no secret or empty submission. A fresh curtain proof guards one Space.
sub observe_lock {
    onpc_progress::operation('Revealing the bound lock challenge');
    my ($journey, $entry) = @_;
    $entry //= 'curtain';
    die 'desk:lock-binding' unless (@_ == 1 || @_ == 2) && ref($journey) eq 'onpc_journey'
        && ($entry eq 'curtain' || $entry eq 'challenge');
    return $journey->seen('challenge') if $entry eq 'challenge';
    return reveal_lock($journey, 'challenge');
}

# A fresh curtain proof guards one Space; callers own the resulting surface.
sub reveal_lock {
    onpc_progress::operation('Revealing the bound locked surface');
    my ($journey, $result) = @_;
    die 'desk:lock-reveal-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && ($result eq 'challenge' || $result eq 'time-denied');
    $journey->consume_observation('curtain', $journey->seen('curtain'));
    $journey->consume_observation('reveal-ready', $journey->seen('reveal-ready'));
    testapi::send_key('spc');
    return $journey->seen($result);
}

# DESK05: one public session command; callers independently observe DESK06.
sub lock {
    onpc_progress::operation('Locking the fixture desktop');
    my ($journey, $desktop, $stage) = @_;
    $stage //= 'desktop';
    die 'desk:lock-binding' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey'
        && ($stage eq 'desktop' || $stage eq 'lock-ready');
    $journey->consume_observation($stage, $desktop);
    $journey->seen('lock');
    return observe_lock($journey);
}

sub qualify_lock {
    onpc_progress::operation('Qualifying the desktop lock surface');
    my ($exchange, $supplied) = @_;
    die 'desk:lock-qualification-binding' unless @_ == 2 && ref($exchange) eq 'CODE'
        && ($supplied == 0 || $supplied == 1);
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $supplied ? 'lock-supplied' : 'lock-command', review => 0);
    my $desktop = onpc_parent::login_functional($journey);
    $journey->seen('unlocked-refused');
    if ($supplied) {
        # Independent normal desktop shortcut supplies entry to the observer.
        $journey->consume_observation('lock-ready', $journey->seen('lock-ready'));
        testapi::send_key('super-l');
        observe_lock($journey);
    } else {
        lock($journey, $journey->seen('lock-ready'), 'lock-ready');
    }
    $journey->seen('lock-refusals');
    $journey->seen('independent-challenge');
    $journey->finish();
}

# DESK07: GDM acknowledgements carry no lock authority. Keep the two fresh
# controller proofs on the same lock challenge; input/submission are separate.
sub lock_recipient {
    onpc_progress::operation('Qualifying the intended lock-screen recipient');
    my ($journey, $prefix, $role) = @_;
    $prefix //= '';
    $role //= 'parent';
    die 'desk:lock-recipient-binding' unless (@_ == 1 || @_ == 2 || @_ == 3)
        && ($role eq 'parent' || $role eq 'child')
        && $prefix =~ /\A(?:[a-z][a-z0-9-]*-)?\z/ && ref($journey) eq 'onpc_journey'
        && !$journey->{review} && !$journey->{lock_recipient_failed};
    my ($identity, $reply);
    my $ok = eval {
        for my $check ('qualified', 'rechecked') {
            my $stage = $prefix . 'lock-recipient-' . $check;
            $reply = $journey->seen($stage);
            die 'desk:lock-recipient-proof' unless ref($reply) eq 'HASH' && keys(%$reply) == 2;
            my $proof = $reply->{lock_recipient};
            die 'desk:lock-recipient-proof' unless ($reply->{observed} // '') eq $stage && ref($proof) eq 'HASH'
                && keys(%$proof) == 3 && ($proof->{surface} // '') eq 'lock'
                && ($proof->{role} // '') eq $role
                && ($proof->{challenge_id} // '') =~ /\A[0-9a-f]{64}\z/;
            die 'desk:lock-recipient-replaced' if defined($identity) && $identity ne $proof->{challenge_id};
            $identity = $proof->{challenge_id};
        }
        1;
    };
    unless ($ok) {
        $journey->{lock_recipient_failed} = 1;
        delete $journey->{last_observation};
        die $@;
    }
    return $reply;
}

sub qualify_lock_recipient {
    onpc_progress::operation('Qualifying the lock-screen password boundary');
    my ($exchange) = @_;
    die 'desk:lock-recipient-binding' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'lock-recipient', review => 0);
    my $desktop = onpc_parent::login_functional($journey);
    $journey->seen('unlocked-refused');
    # The negative observation is not the desktop proof consumed by Lock.
    $desktop = $journey->seen('lock-ready');
    lock($journey, $desktop, 'lock-ready');
    $journey->seen('lock-recipient-refusals');
    $journey->seen('independent-challenge');
    lock_recipient($journey);
    $journey->seen('final-challenge');
    $journey->finish();
}

# GDM reauthenticates a retained session on the greeter before activating it.
# Reuse the GDM proof/input path, never treat it as child lock-screen authority.
sub retained_gdm_unlock {
    onpc_progress::operation('Authenticating the retained child through the greeter');
    my ($journey) = @_;
    die 'desk:retained-entry' unless @_ == 1 && ref($journey) eq 'onpc_journey'
        && !$journey->{review} && testapi::current_console() eq 'sut';
    return onpc_gdm::sign_in_challenge($journey, 'retained-login',
        'retained-list', 'retained-focused', 'unlock-desktop');
}

# DESK08 success: the sealed helper owns both fresh lock proofs; Enter and
# the independently observed unlocked desktop are separate from secret input.
sub unlock_success {
    onpc_progress::operation('Unlocking the intended child desktop');
    my ($journey) = @_;
    die 'desk:unlock-binding' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_password::enter_lock_password($journey, 'child');
    testapi::send_key('ret');
    return $journey->seen('unlock-desktop');
}

sub qualify_retained_parent {
    onpc_progress::operation('Returning to the same Parent desktop and existing window');
    my ($exchange, $declared, $challenges) = @_;
    die 'desk:retained-parent-plan' unless @_ == 3 && ref($exchange) eq 'CODE';
    require onpc_feedback_read;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'retained-parent', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'initial',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for qw(allowance-configured before session-before);
    switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'away',
        'away-installed-greeter', 'away-standard-focused', 'away-desktop');
    $journey->consume_observation('return-parent-retained',
        onpc_parent::open_for_child($journey, 'desktop', 'retained', 'retained', 'child', 'return'));
    $journey->seen('session-returned');
    onpc_feedback_read::prepare_window_switch($journey, 'focus-');
    $journey->seen('second-before');
    $journey->consume_observation('second-desktop', $journey->seen('second-desktop'));
    $journey->seen($_) for qw(second-switch second-greeter);
    onpc_gdm::sign_in_challenge($journey, 'again',
        'again-installed-greeter', 'again-standard-focused', 'again-desktop');
    $journey->consume_observation('independent-source', $journey->seen('independent-source'));
    $journey->seen($_) for qw(independent-switch independent-greeter);
    onpc_gdm::sign_in_challenge($journey, 'independent',
        'independent-installed-greeter', 'independent-parent-focused', 'independent-desktop');
    $journey->consume_observation('supplied-parent-retained',
        onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'child', 'supplied'));
    $journey->seen($_) for qw(session-supplied close absent-refused);
    $journey->finish();
}

sub qualify_retained_unlock {
    onpc_progress::operation('Qualifying child unlock and preservation of original activity');
    my ($exchange, $retained, $declared, $challenges) = @_;
    die 'desk:unlock-plan' unless @_ == 4 && ref($exchange) eq 'CODE'
        && ($retained == 0 || $retained == 1);
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $retained ? 'retained-unlock' : 'child-unlock', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen('allowance-configured');
    switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    onpc_app_rows::native_activity_entry($journey, 'activity', 'command');
    $journey->seen('unlocked-refused');
    lock($journey, $journey->seen('lock-ready'), 'lock-ready');
    $journey->seen('lock-recipient-refusals');
    my $challenge = $journey->seen('independent-challenge');
    if ($retained) {
        $journey->consume_observation('independent-challenge', $challenge);
        $journey->seen('return-greeter');
        $journey->seen('retained-greeter');
        retained_gdm_unlock($journey);
    } else {
        unlock_success($journey);
    }
    onpc_app_rows::native_read_activity($journey, 'returned-activity');
    onpc_app_rows::native_activity_resume($journey, 'resume');
    onpc_app_rows::native_read_activity($journey, 'usable-activity');
    $journey->finish();
}

# Configured-zero qualification uses a fresh Parent session to change time,
# then observes native lock restriction or authenticates GDM once. These are
# distinct results; the zero-time Shell shield has no password recipient.
sub qualify_retained_denial {
    onpc_progress::operation('Qualifying retained-child time denial and return');
    my ($exchange, $retained, $declared, $challenges) = @_;
    die 'desk:denial-plan' unless @_ == 4 && ref($exchange) eq 'CODE'
        && ($retained == 0 || $retained == 1);
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $retained ? 'retained-denial' : 'lock-denial', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen('allowance-configured');
    $journey->consume_observation('logout-ready', $journey->seen('logout-ready'));
    $journey->seen('logout');
    $journey->seen('gdm-logged-out');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    $journey->consume_observation('child-switch-ready', $journey->seen('child-switch-ready'));
    $journey->seen('child-switch');
    $journey->seen('child-greeter');
    $journey->seen('retained-before');
    $desktop = onpc_gdm::sign_in_challenge($journey, 'renewed-login',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
    onpc_parent::launch($journey, $desktop, 'management', 'return-desktop');
    $selected = onpc_parent::select_child($journey, 'child', $journey->seen('return-child-picker-opened'),
        'return-child-picker-opened', 'return-child-choice-highlighted', 'return-parent-selected');
    $journey->consume_observation('return-parent-selected', $selected);
    $journey->seen('zero-configured');
    switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    if ($retained) {
        onpc_gdm::sign_in_challenge($journey, 'retained-login',
            'retained-list', 'retained-focused', 'time-denied');
        onpc_gdm::return_from_time_denial($journey,
            'denied-return-ready', 'denied-return-state', 'denied-returned');
    } else {
        $journey->seen('enter-locked');
        my $denied = reveal_lock($journey, 'time-denied');
        $journey->consume_observation('time-denied', $denied);
        $journey->seen('return-greeter');
        $journey->seen('denied-returned');
    }
    $journey->seen('retained-after');
    $journey->finish();
}

sub run {
    onpc_progress::operation('Checking shared desktop session commands');
    my ($exchange, $action) = @_;
    die 'desk:action-binding' unless @_ == 2
        && ($action eq 'logout' || $action eq 'switch-user');
    my $prefix = $action eq 'logout' ? 'desktop-logout' : 'desktop-switch';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => $prefix, review => 0);
    my $desktop = onpc_parent::login_functional($journey);
    $action eq 'logout' ? log_out($journey, $desktop) : switch_user($journey, $desktop);
    $journey->finish();
}

1;
