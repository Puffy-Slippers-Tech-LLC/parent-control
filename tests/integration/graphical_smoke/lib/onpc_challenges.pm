package onpc_challenges;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_journey ();
use onpc_gdm ();
use onpc_desktop_session ();
use onpc_parent ();
use onpc_request_flow ();
use onpc_app_rows ();

sub shell_panel {
    onpc_progress::operation('Qualifying direct and normal panel overlay entry');
    my ($exchange, $declared, $challenges) = @_;
    my @stages = qw(installed-greeter parent-focused recipient-qualified recipient-rechecked desktop
        fresh-installed-greeter fresh-child-focused fresh-child-recipient-qualified
        fresh-child-recipient-rechecked fresh-desktop direct-launch direct-form direct-cancel
        independent-desktop independent-launch independent-form independent-cancel
        panel-desktop panel-panel panel-launch panel-form singleton-reveal singleton-panel singleton-launch
        singleton-overview singleton-form panel-cancel closed-desktop);
    die 'shell-panel:plan' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 2
        && ref($challenges->{'parent-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'parent-login'}}) eq 'parent/recipient-qualified/recipient-rechecked'
        && ref($challenges->{'child-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'child-login'}}) eq
            'child/fresh-child-recipient-qualified/fresh-child-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'shell-panel', review => 0);
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
    $journey->seen('wrong-account-refused');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    onpc_request_flow::overlay_entry($journey, 'direct', 'command');
    $journey->invoke('direct-cancel');
    $journey->invoke('independent-desktop');
    onpc_request_flow::overlay_entry($journey, 'independent', 'command');
    $journey->invoke('independent-cancel');
    $journey->invoke('panel-desktop');
    onpc_request_flow::overlay_entry($journey, 'panel', 'panel');
    onpc_request_flow::overlay_entry($journey, 'singleton', 'panel-reopen');
    $journey->invoke('panel-cancel');
    $journey->invoke('closed-desktop');
    $journey->finish();
}

sub countdown {
    onpc_progress::operation('Qualifying the child desktop countdown');
    my $present = shift;
    return _countdown($present, 0, @_);
}

sub countdown_animation {
    onpc_progress::operation('Qualifying the child countdown animation preference');
    return _countdown(1, 1, @_);
}

sub countdown_session {
    onpc_progress::operation('Checking the child countdown across lock and retained sign-in');
    return _countdown(1, 0, @_, 1);
}

sub _countdown {
    onpc_progress::operation('Qualifying the child desktop countdown');
    my ($present, $animation, $exchange, $declared, $challenges, $session) = @_;
    $session //= 0;
    my @stages = qw(installed-greeter parent-focused recipient-qualified recipient-rechecked desktop
        fresh-installed-greeter fresh-child-focused fresh-child-recipient-qualified
        fresh-child-recipient-rechecked fresh-desktop countdown independent-countdown);
    @stages = map { $_ eq 'countdown' ? 'animation-set' :
        $_ eq 'independent-countdown' ? 'animation-read' : $_ } @stages if $animation;
    if ($session) {
        splice @stages, -1, 1, qw(panel-bound locked-countdown greeter-countdown
            retained-list retained-focused retained-recipient-qualified retained-recipient-rechecked
            unlock-desktop panel-restored independent-countdown);
    }
    die 'countdown:plan' unless (@_ == 5 || @_ == 6 && $session == 1 && $present && !$animation)
        && ($present eq '0' || $present eq '1')
        && ($animation eq '0' || $animation eq '1') && (!$animation || $present)
        && ref($exchange) eq 'CODE' && ref($declared) eq 'ARRAY'
        && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == ($session ? 3 : 2)
        && (!$session || ref($challenges->{'retained-login'}) eq 'ARRAY'
            && join('/', @{$challenges->{'retained-login'}}) eq
                'child/retained-recipient-qualified/retained-recipient-rechecked')
        && ref($challenges->{'parent-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'parent-login'}}) eq 'parent/recipient-qualified/recipient-rechecked'
        && ref($challenges->{'child-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'child-login'}}) eq
            'child/fresh-child-recipient-qualified/fresh-child-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $session ? 'countdown-session' : $animation ? 'countdown-animation' : $present ? 'countdown-enabled' : 'countdown-off', review => 0);
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
    $journey->seen('limits-disabled') unless $present;
    $journey->seen('wrong-account-refused') unless $session;
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    $journey->invoke($animation ? 'animation-set' : 'countdown');
    if ($session) {
        $journey->invoke('panel-bound');
        $journey->seen('lock');
        $journey->invoke('locked-countdown');
        $journey->seen('return-greeter');
        $journey->seen('retained-greeter');
        $journey->invoke('greeter-countdown');
        onpc_desktop_session::retained_gdm_unlock($journey);
        $journey->invoke('panel-restored');
    }
    $journey->invoke($animation ? 'animation-read' : 'independent-countdown');
    $journey->finish();
}

# TIME02 consumes an independently supplied child desktop. Countdown reads/waits
# stay in the shared controller, with no input or minute-edge sleep in the worker.
sub countdown_minutes {
    onpc_progress::operation('Qualifying displayed minute countdown progression');
    die 'countdown:minute-plan' unless @_ == 3;
    return _countdown_progression('countdown-minutes', 4,
        [qw(minute-progression independent-minute-progression)], @_);
}

sub countdown_ticks {
    onpc_progress::operation('Qualifying displayed final-second countdown progression');
    die 'countdown:tick-plan' unless @_ == 3;
    return _countdown_progression('countdown-ticks', 4,
        [qw(final-second-transition second-progression independent-second-progression)], @_);
}

sub _countdown_progression {
    my ($prefix, $minutes, $progressions, $exchange, $declared, $challenges) = @_;
    my @stages = qw(installed-greeter parent-focused recipient-qualified recipient-rechecked desktop
        wrong-account-refused fresh-installed-greeter fresh-child-focused
        fresh-child-recipient-qualified fresh-child-recipient-rechecked fresh-desktop);
    push @stages, @$progressions;
    die 'countdown:progress-plan' unless @_ == 6 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 2
        && ref($challenges->{'parent-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'parent-login'}}) eq 'parent/recipient-qualified/recipient-rechecked'
        && ref($challenges->{'child-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'child-login'}}) eq
            'child/fresh-child-recipient-qualified/fresh-child-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => $prefix, review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    $journey->invoke('wrong-account-refused');
    onpc_parent::daily_time_profile($journey, 'desktop', 'parent', 'same-user', 'new', 'child', 0, $minutes);
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    $journey->invoke($_) for @$progressions;
    $journey->finish();
}

# TIME04 prepares only public daily time, then the controller observes normal
# fixture activity until the owned lock. This worker never requests Lock.
sub natural_expiry {
    onpc_progress::operation('Using the native app until natural screen-time exhaustion');
    my ($exchange, $declared, $challenges) = @_;
    my @stages = qw(installed-greeter parent-focused recipient-qualified recipient-rechecked desktop
        wrong-account-refused fresh-installed-greeter fresh-child-focused fresh-child-recipient-qualified
        fresh-child-recipient-rechecked fresh-desktop natural-expiry lock-input-ready lock-result);
    die 'natural-expiry:plan' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 2
        && ref($challenges->{'parent-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'parent-login'}}) eq 'parent/recipient-qualified/recipient-rechecked'
        && ref($challenges->{'child-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'child-login'}}) eq
            'child/fresh-child-recipient-qualified/fresh-child-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'natural-expiry', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    $journey->invoke('wrong-account-refused');
    onpc_parent::daily_time_profile($journey, 'desktop', 'parent', 'same-user', 'new', 'child', 0, 4);
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    onpc_app_rows::native_activity_entry($journey, 'activity', 'command', 'child');
    $journey->invoke('natural-expiry');
    onpc_desktop_session::verify_locked_input($journey, 'lock-input-ready', 'lock-result');
    $journey->finish();
}

sub suspend_active_grant {
    my ($exchange, $declared, $challenges, $request) = @_;
    die 'suspend-active-grant:plan' unless (@_ == 3 || @_ == 4) && ref($exchange) eq 'CODE'
        && (!defined($request) || ref($request) eq 'ARRAY'
            && join('/', @$request) eq 'child/parent/600/1');
    my $expired = defined($request);
    onpc_progress::operation($expired ? 'Checking that time expiring during sleep blocks the child desktop'
        : 'Waking and unlocking the same child work before extra time expires');
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $expired ? 'suspend-expired-grant' : 'suspend-active-grant', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_parent::grant_only_time_profile($journey, 'gdm', 'fresh', 'new', 0, 0,
        $expired ? 600 : 1200, 'default', 1);
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    onpc_app_rows::native_activity_entry($journey, 'activity', 'command', 'child');
    $journey->seen('initial-countdown');
    $journey->seen($_) for $expired ? qw(expiry-wait suspend-countdown) : ();
    $journey->seen($_) for qw(suspend wake-session);
    if ($expired) {
        # Expiry during sleep exposes the native restriction directly. Pin it
        # before an independent denial read; no reveal or credential input.
        $journey->consume_observation('denial-ready', $journey->seen('denial-ready'));
        $journey->seen('time-denied');
        $journey->seen($_) for qw(return-greeter denied-returned retained-after);
        $journey->finish();
        return;
    }
    onpc_desktop_session::observe_lock($journey, 'challenge');
    onpc_desktop_session::unlock_success($journey);
    $journey->seen($_) for qw(returned-session returned-countdown);
    onpc_app_rows::native_activity_resume($journey, 'resume');
    $journey->seen('usable-activity');
    $journey->finish();
}

sub countdown_daily {
    onpc_progress::operation('Following daily time and original child work through unlock and natural lock');
    my ($exchange, $declared, $challenges) = @_;
    die 'countdown-daily:plan' unless @_ == 3 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'countdown-daily', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::daily_time_profile($journey, 'desktop', 'parent', 'same-user', 'new', 'child', 0, 6);
    countdown_activity($journey, 1);
}

sub countdown_grant {
    onpc_progress::operation('Following approved extra time and original child work through unlock and natural lock');
    my ($exchange, $declared, $challenges) = @_;
    die 'countdown-grant:plan' unless @_ == 3 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'countdown-grant', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_parent::grant_only_time_profile($journey, 'gdm', 'fresh', 'new', 0, 0, 600, 'default', 0);
    # Read the retained Parent window through its public API while GDM stays
    # active. An extra Parent login would spend the child's wall-clock grant.
    $journey->seen('profile-balance');
    countdown_activity($journey, 1, 0);
}

sub countdown_combined {
    onpc_progress::operation('Following daily and approved time with original child work through unlock and natural lock');
    my ($exchange, $declared, $challenges) = @_;
    die 'countdown-combined:plan' unless @_ == 3 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'countdown-combined', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_parent::grant_only_time_profile($journey, 'gdm', 'fresh', 'new', 0, 0, 240, 'default', 0, 4);
    $journey->seen('profile-balance');
    countdown_activity($journey, 1, 0);
}

sub countdown_activity {
    my ($journey, $minute_edges, $desktop_observation) = @_;
    $desktop_observation = 1 if @_ == 2;
    die 'countdown:activity-binding' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey'
        && defined($minute_edges) && $minute_edges =~ /\A[01]\z/
        && defined($desktop_observation) && $desktop_observation =~ /\A[01]\z/;
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused',
        $desktop_observation ? 'fresh-desktop' : 'initial-countdown');
    $journey->invoke('initial-countdown') if $desktop_observation;
    onpc_app_rows::native_activity_entry($journey, 'activity', 'command', 'child', $desktop_observation);
    onpc_desktop_session::lock($journey, $journey->seen('lock-ready'), 'lock-ready');
    onpc_desktop_session::unlock_success($journey);
    $journey->invoke('returned-countdown');
    onpc_app_rows::native_read_activity($journey, 'returned-activity');
    onpc_app_rows::native_activity_resume($journey, 'resume');
    onpc_app_rows::native_read_activity($journey, 'usable-activity');
    $journey->invoke('minute-progression') if $minute_edges;
    $journey->invoke($_) for qw(final-second-transition second-progression
        independent-second-progression natural-expiry);
    onpc_desktop_session::verify_locked_input($journey, 'lock-input-ready', 'lock-result');
    $journey->finish();
}

sub grant_work_recovery {
    onpc_progress::operation('Returning to the child work after time runs out with the parent soft-app choice');
    my ($exchange, $declared, $challenges, $binding) = @_;
    die 'grant-recovery:plan' unless @_ == 4 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ref($binding) eq 'ARRAY' && join(',', @$binding) =~ /\Achild,parent,1200,[01]\z/;
    my $allow_soft = $binding->[3];
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'grant-work-recovery', review => 0);
    $journey->{kiosk_request} = $binding;
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_app_rows::named_app_set($journey, 'gdm', 'fresh', 'new', 'child', [
        ['A', 'match-precise', 'allowed'], ['H', 'match-hard-precise', 'permanent'],
        ['S', 'match-soft-wildcard', 'conditional']], 'rules');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'setup-return');
    onpc_parent::grant_only_time_profile($journey, 'desktop', 'same-user', 'retained', 0, 0, 600, 'default', 0);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'fresh');
    onpc_app_rows::native_activity_entry($journey, 'activity', 'command', 'child');
    my $soft = $journey->scope('soft');
    onpc_app_rows::native_usable_app($soft, 'command', $soft->seen('desktop'), 'child', 'S');
    onpc_app_rows::native_read_activity($journey, 'soft-capture');
    $journey->invoke('natural-expiry');
    onpc_desktop_session::verify_locked_input($journey, 'lock-input-ready', 'lock-result');
    onpc_desktop_session::enter_desktop($journey, 'locked', 'child', 'lock', 'time-denied', 'denial');
    $journey->seen($_) for qw(return-greeter denied-returned retained-before);
    onpc_request_flow::obtain_time($journey, 'observed',
        'fixture-child', 'fixture-parent', 1200, $allow_soft, 'automatic');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'retained', 'success', 'retained');
    $journey->seen($_) for qw(countdown recovery-identity);
    onpc_app_rows::native_activity_resume($journey, 'resume');
    if ($allow_soft) {
        onpc_app_rows::native_read_activity($journey, 'soft-retained');
        $journey->seen($_) for qw(soft-close soft-closed hard-launch);
        my $relaunch = $journey->scope('soft-relaunch');
        onpc_app_rows::native_usable_app($relaunch, 'command', $relaunch->seen('desktop'), 'child', 'S');
    } else {
        $journey->seen($_) for qw(soft-closed hard-launch soft-launch);
    }
    onpc_app_rows::native_read_activity($journey, 'allowed-work');
    $journey->finish();
}

sub natural_access {
    onpc_progress::operation('Checking child access after animated exhaustion, approval and revocation');
    my ($exchange, $declared, $challenges) = @_;
    die 'natural-access:plan' unless @_ == 3 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'natural-access', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    my $selected = onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'new', 'child');
    $journey->consume_observation('same-parent-selected', $selected);
    $journey->consume_observation($_, $journey->seen($_))
        for qw(profile-before profile-configured profile-settings policy-before);
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'fresh');
    $journey->invoke($_) for qw(before-animation animation-set animation-read);
    onpc_app_rows::native_activity_entry($journey, 'activity', 'command', 'child');
    $journey->invoke('natural-expiry');
    onpc_desktop_session::verify_locked_input($journey, 'lock-input-ready', 'lock-result');
    my $denied = onpc_desktop_session::reveal_lock($journey, 'time-denied');
    $journey->consume_observation('time-denied', $denied);
    $journey->seen($_) for qw(return-greeter denied-returned retained-before);
    onpc_request_flow::obtain_time($journey, 'default', 'fixture-child', 'fixture-parent', 600, 1, 'automatic');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'retained', 'success', 'recovery');
    $journey->seen('recovery-identity');
    onpc_app_rows::native_read_activity($journey, 'recovery-activity');
    onpc_app_rows::native_activity_resume($journey, 'resume');
    onpc_app_rows::native_read_activity($journey, 'usable-activity');
    # Logout is a guarded shared system operation; its independent GDM result
    # is kept in this case's declared stages.
    $journey->consume_observation('logout-ready', $journey->seen('logout-ready'));
    $journey->seen($_) for qw(logout gdm-logged-out);
    onpc_gdm::sign_in_challenge($journey, 'return',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
    $journey->consume_observation('supplied-parent-retained',
        onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'child', 'supplied'));
    $journey->seen($_) for qw(before-revoke confirm-open confirm-warning confirmed after-revoke);
    $journey->consume_observation('parent-leave-ready', $journey->seen('parent-leave-ready'));
    $journey->seen($_) for qw(parent-leave final-greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'time-denied', 'denied');
    $journey->finish();
}

sub jordan_daily_access {
    onpc_progress::operation('Checking daily access for [Child user] across fresh sign-ins');
    my ($exchange, $declared, $challenges) = @_;
    die 'jordan-daily-access:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'jordan-daily-access', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'initial',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    $journey->consume_observation('parent-selected', onpc_parent::select_child($journey, 'existing',
        $journey->seen('child-picker-opened'), 'child-picker-opened', 'child-choice-highlighted', 'parent-selected'));
    $journey->seen($_) for qw(allowance-configured before session-before);
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'fresh', 'success', 'positive');
    $journey->seen('countdown');
    my $logout = $journey->scope('logout');
    onpc_desktop_session::log_out($logout, $logout->seen('desktop'));
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'return');
    onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'existing', 'supplied', 0);
    $journey->seen($_) for qw(session-returned zero-configured zero-before);
    $journey->consume_observation('zero-desktop', $journey->seen('zero-desktop'));
    $journey->seen($_) for qw(zero-switch zero-greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'fresh', 'time-denied', 'denied');
    onpc_gdm::return_from_time_denial($journey,
        'first-denied-return-ready', 'first-denied-return-state', 'first-denied-returned');
    $journey->consume_observation('independent-entry-guard', $journey->seen('independent-entry-guard'));
    onpc_gdm::sign_in_challenge($journey, 'independent',
        'independent-installed-greeter', 'independent-standard-focused', 'independent-denied');
    onpc_gdm::return_from_time_denial($journey,
        'second-denied-return-ready', 'second-denied-return-state', 'second-denied-returned');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'off-return');
    onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'existing', 'off-supplied', 0);
    $journey->seen($_) for qw(limits-disabled disabled-settings);
    $journey->consume_observation('off-parent-desktop', $journey->seen('off-parent-desktop'));
    $journey->seen($_) for qw(off-switch off-greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'fresh', 'success', 'off');
    $journey->seen('absent-countdown');
    $journey->finish();
}

sub fresh_child_allowed {
    onpc_progress::operation('Qualifying fresh child login with saved daily time');
    my $ok = eval { _fresh_child_allowed(@_); 1 };
    die "fresh-child:failed\n" unless $ok;
}

sub _fresh_child_allowed {
    return _fresh_child_entry('success', @_);
}

sub fresh_child_denied {
    onpc_progress::operation('Qualifying fresh child time denial and normal return');
    my $ok = eval { _fresh_child_entry('time-denied', @_); 1 };
    die "fresh-child:failed\n" unless $ok;
}

sub _fresh_child_entry {
    onpc_progress::operation('Qualifying fresh child login with saved daily time');
    my ($expected, $exchange, $declared, $challenges) = @_;
    die 'fresh-child:result' unless $expected eq 'success' || $expected eq 'time-denied';
    my $result_stage = $expected eq 'success' ? 'fresh-desktop' : 'fresh-denied';
    my @stages = qw(installed-greeter parent-focused recipient-qualified recipient-rechecked desktop
        wrong-list wrong-focused wrong-refused wrong-returned
        fresh-installed-greeter fresh-child-focused fresh-child-recipient-qualified
        fresh-child-recipient-rechecked);
    push @stages, $result_stage;
    push @stages, qw(denied-return-ready denied-return-state denied-returned) if $expected eq 'time-denied';
    die 'fresh-child:plan' unless @_ == 4 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 2
        && ref($challenges->{'parent-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'parent-login'}}) eq 'parent/recipient-qualified/recipient-rechecked'
        && ref($challenges->{'child-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'child-login'}}) eq
            'child/fresh-child-recipient-qualified/fresh-child-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $expected eq 'success' ? 'fresh-child-allowed' : 'fresh-child-denied', review => 0);
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
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    my $list = $journey->invoke('wrong-list');
    my $focus = $journey->highlight_choice($list, 'wrong-list', 'wrong-focused');
    $journey->consume_observation('wrong-focused', $focus);
    testapi::send_key('ret');
    my $refused = $journey->invoke('wrong-refused');
    $journey->consume_observation('wrong-refused', $refused);
    testapi::send_key('esc');
    $journey->invoke('wrong-returned');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', $result_stage);
    onpc_gdm::return_from_time_denial($journey, 'denied-return-ready', 'denied-return-state', 'denied-returned')
        if $expected eq 'time-denied';
    $journey->finish();
}

sub run {
    onpc_progress::operation('Qualifying distinct graphical authentication challenges');
    my ($exchange, $declared, $challenges) = @_;
    my @stages = qw(wrong-list wrong-focused wrong-refused wrong-returned
        installed-greeter parent-focused recipient-qualified recipient-rechecked desktop
        second-installed-greeter second-parent-focused second-recipient-qualified
        second-recipient-rechecked second-desktop);
    die 'challenges:plan' unless ref($declared) eq 'ARRAY'
        && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 2;
    for my $id ('first-login', 'second-login') {
        my $prefix = $id eq 'first-login' ? '' : 'second-';
        die 'challenges:plan' unless ref($challenges->{$id}) eq 'ARRAY'
            && join('/', @{$challenges->{$id}}) eq
                "parent/${prefix}recipient-qualified/${prefix}recipient-rechecked";
    }
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'challenges', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $list = $journey->invoke('wrong-list');
    my $focus = $journey->highlight_choice($list, 'wrong-list', 'wrong-focused');
    $journey->consume_observation('wrong-focused', $focus);
    testapi::send_key('ret');
    my $refusal = $journey->invoke('wrong-refused');
    $journey->consume_observation('wrong-refused', $refusal);
    testapi::send_key('esc');
    $journey->invoke('wrong-returned');
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'first-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_desktop_session::log_out($journey, $desktop);
    onpc_gdm::sign_in_challenge($journey, 'second-login',
        'second-installed-greeter', 'second-parent-focused', 'second-desktop');
    $journey->finish();
}

1;
