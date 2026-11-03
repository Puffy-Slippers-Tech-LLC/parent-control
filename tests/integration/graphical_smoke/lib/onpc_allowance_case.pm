package onpc_allowance_case;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_lifecycle ();
use onpc_allowance_boundaries ();
use onpc_allowance_selection ();
use onpc_feedback_states ();
use onpc_desktop_session ();
use onpc_app_rows ();
use Digest::SHA ();

sub daily_only_new {
    return daily_only(@_, 0);
}

sub daily_only_retained {
    return daily_only(@_, 1);
}

sub grant_only_new {
    onpc_progress::operation('Checking extra time across fresh child sign-ins and allowance changes');
    my ($exchange, $declared, $challenges, $request) = @_;
    die 'grant-access:arguments' unless @_ == 4 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ref($request) eq 'ARRAY' && join(',', @$request) eq 'other-child,parent,1200,1';
    require onpc_request_flow;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'grant-access-case', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'initial',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    $journey->consume_observation('parent-selected', onpc_parent::select_child($journey, 'existing',
        $journey->seen('child-picker-opened'), 'child-picker-opened', 'child-choice-highlighted', 'parent-selected'));
    $journey->seen($_) for qw(initial-balance setup-enable);
    onpc_allowance_selection::select($journey, 'setup-zero', [0], 'confirm');
    $journey->seen($_) for qw(setup-settings apps-page);
    for my $edit (['A', 'match-precise', 'allowed', 'allowed'],
                  ['H', 'match-hard-precise', 'permanent', 'hard']) {
        my ($role, $draft, $access, $prefix) = @$edit;
        my $app = 'parent-app-' . substr(Digest::SHA::sha256_hex(
            'com.puffyslippers.ONPCTest.' . $role . '.desktop'), 0, 16);
        onpc_app_rows::edit_policy($journey, $app, $draft, $access, $prefix, []);
    }
    $journey->seen($_) for qw(policy-screen setup-disable setup-off-settings setup-off-balance);
    for my $name (qw(enabled grant positive zero off reenabled)) {
        if ($name eq 'grant') {
            my $leave = $journey->scope('approval-leave');
            onpc_desktop_session::switch_user($leave, $leave->seen('desktop'));
            my $approval = $journey->scope('request');
            $approval->{kiosk_request} = [@$request];
            onpc_request_flow::prepare($approval, 'new', 'new', 'observed',
                'existing-fixture-child', 'fixture-parent', 1200, 1, 'kiosk');
            onpc_request_flow::approve($approval, 'existing-fixture-child', 'fixture-parent', 1200, 1, 'automatic');
            onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'approval-return');
        } elsif ($name eq 'positive') {
            onpc_allowance_boundaries::custom_value($journey, 'positive', 30);
        } elsif ($name eq 'zero') {
            onpc_allowance_selection::select($journey, 'zero', [0], 'confirm');
        } else {
            $journey->seen("$name-toggle");
        }
        $journey->seen($_) for ("$name-settings", "$name-balance");
        my $leave = $journey->scope("$name-leave");
        onpc_desktop_session::switch_user($leave, $leave->seen('desktop'));
        my $denied = $name eq 'enabled' || $name eq 'reenabled';
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'fresh',
            $denied ? 'time-denied' : 'success', "$name-entry");
        if ($denied) {
            onpc_gdm::return_from_time_denial($journey,
                "$name-denial-denied-return-ready", "$name-denial-denied-return-state",
                "$name-denial-denied-returned");
        } else {
            $journey->seen("$name-countdown");
            if ($name eq 'grant' || $name eq 'off') {
                onpc_app_rows::native_blocked_app($journey->scope("$name-hard"), 'H');
                my $allowed = $journey->scope("$name-allowed");
                onpc_app_rows::native_usable_app($allowed, 'grid', $allowed->seen('desktop'), 'other-child');
                onpc_app_rows::native_finish_app($allowed);
            }
            my $logout = $journey->scope("$name-logout");
            onpc_desktop_session::log_out($logout, $logout->seen('desktop'));
        }
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', "$name-return");
        onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'existing', "$name-supplied", 0);
        $journey->seen("$name-returned-balance");
    }
    $journey->finish();
}

sub daily_only {
    onpc_progress::operation('Checking daily time changes and child access');
    my ($exchange, $declared, $challenges, $retained) = @_;
    die 'daily-access:arguments' unless @_ == 4 && ref($exchange) eq 'CODE'
        && defined($retained) && $retained =~ /\A[01]\z/
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $retained ? 'daily-retained-access-case' : 'daily-access-case', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'initial',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    $journey->consume_observation('parent-selected', onpc_parent::select_child($journey, 'existing',
        $journey->seen('child-picker-opened'), 'child-picker-opened', 'child-choice-highlighted', 'parent-selected'));
    $journey->seen($_) for qw(initial-balance setup-enable);
    onpc_allowance_boundaries::custom_value($journey, 'thirty', 30);
    $journey->seen($_) for qw(setup-settings apps-page);
    for my $edit (['A', 'match-precise', 'allowed', 'allowed'],
                  ['H', 'match-hard-precise', 'permanent', 'hard']) {
        my ($role, $draft, $access, $prefix) = @$edit;
        my $app = 'parent-app-' . substr(Digest::SHA::sha256_hex(
            'com.puffyslippers.ONPCTest.' . $role . '.desktop'), 0, 16);
        onpc_app_rows::edit_policy($journey, $app, $draft, $access, $prefix, []);
    }
    $journey->seen($_) for qw(policy-screen setup-disable setup-off-settings setup-off-balance);
    if ($retained) {
        my $leave = $journey->scope('prepare-leave');
        onpc_desktop_session::switch_user($leave, $leave->seen('desktop'));
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'fresh', 'success', 'prepare-entry');
        onpc_app_rows::native_activity_entry($journey, 'original', 'grid', 'other-child');
        $journey->seen('original-session');
        my $child_leave = $journey->scope('prepare-child-leave');
        onpc_desktop_session::switch_user($child_leave, $child_leave->seen('desktop'));
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'prepare-return');
        $journey->consume_observation('prepared-parent-retained',
            onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'existing', 'prepared', 0));
    }
    for my $name (qw(enabled forty zero off reenabled)) {
        if ($name eq 'forty') {
            onpc_allowance_boundaries::custom_value($journey, 'forty', 40);
        } elsif ($name eq 'zero') {
            onpc_allowance_selection::select($journey, 'zero', [0], 'confirm');
        } else {
            $journey->seen("$name-toggle");
        }
        $journey->seen($_) for ("$name-settings", "$name-balance");
        next if $retained && $name eq 'forty';
        my $leave = $journey->scope("$name-leave");
        onpc_desktop_session::switch_user($leave, $leave->seen('desktop'));
        my $denied = $name eq 'zero' || $name eq 'reenabled';
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', $retained ? 'retained' : 'fresh',
            $denied ? 'time-denied' : 'success', "$name-entry");
        if ($denied) {
            onpc_gdm::return_from_time_denial($journey,
                "$name-denial-denied-return-ready", "$name-denial-denied-return-state",
                "$name-denial-denied-returned");
        } else {
            $journey->seen("$name-countdown");
            if ($name eq 'enabled' || $name eq 'off') {
                if ($retained && $name eq 'enabled') {
                    onpc_app_rows::native_activity_resume($journey, 'enabled-original');
                    onpc_app_rows::native_finish_app($journey->scope('enabled-original'));
                }
                onpc_app_rows::native_blocked_app($journey->scope("$name-hard"), 'H');
                my $allowed = $journey->scope("$name-allowed");
                onpc_app_rows::native_usable_app($allowed, 'grid', $allowed->seen('desktop'), 'other-child');
                onpc_app_rows::native_finish_app($allowed);
            }
            if ($retained) {
                my $child_leave = $journey->scope("$name-child-leave");
                onpc_desktop_session::switch_user($child_leave, $child_leave->seen('desktop'));
            } else {
                my $logout = $journey->scope("$name-logout");
                onpc_desktop_session::log_out($logout, $logout->seen('desktop'));
            }
        }
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', "$name-return");
        onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'existing', "$name-supplied", 0);
        $journey->seen("$name-returned-balance");
    }
    $journey->finish();
}

sub run {
    onpc_progress::operation('Checking representative daily allowances and reopened saved values');
    my ($exchange, $flow) = @_;
    $flow //= 'boundaries';
    die 'allowance-case:arguments' unless (@_ == 1 || @_ == 2)
        && ref($exchange) eq 'CODE' && ($flow eq 'boundaries' || $flow eq 'save-order');
    return onpc_feedback_states::run_save_order($exchange) if $flow eq 'save-order';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'allowance-case', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('parent-selected',
        onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child'));
    $journey->seen('allowance-configured');
    onpc_allowance_selection::select($journey, 'preset-15', [15], 'confirm');
    $journey->seen('preset-15-read');
    onpc_allowance_selection::select($journey, 'custom-choice', ['custom'], 'confirm');
    onpc_allowance_boundaries::custom_value($journey, 'custom', 1);
    # Each selection already returns the child's complete allowance/settings.
    # The controller checks both children before and after reopening; a second
    # custom-editor read would repeat the same saved-value observation.
    onpc_allowance_boundaries::reload_child($journey, 'edited');
    onpc_lifecycle::reopen($journey, 'parent', $journey->seen('prior-window'), 'management');
    onpc_allowance_boundaries::reload_child($journey, 'persist');
    $journey->finish();
}
1;
