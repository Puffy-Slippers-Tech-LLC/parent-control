package onpc_lifecycle;
use strict;
use warnings;
use onpc_progress ();
use onpc_parent ();
use onpc_window ();
use onpc_journey ();
use onpc_gdm ();
use onpc_request_flow ();
use onpc_allowance_boundaries ();

# LIFE01: consume the named prior window, independently guard its active state,
# close normally, prove absence, and use PARENT01 without selecting or editing.
sub reopen {
    onpc_progress::operation('Closing and reopening Parent');
    my ($journey, $window, $prior, $destination) = @_;
    die 'lifecycle:binding' unless @_ == 4 && ref($journey) eq 'onpc_journey'
        && $window eq 'parent' && $destination eq 'management';
    $journey->consume_observation('prior-window', $prior);
    onpc_window::close($journey, $window, $journey->seen('close-ready'));
    onpc_parent::launch($journey, $journey->seen('same-desktop'),
        $destination, 'same-desktop');
    return $journey->seen('initial-selection');
}

sub app_restart_active {
    onpc_progress::operation('Reopening the apps while the child keeps approved time and work');
    my ($exchange, $declared, $challenges, $request) = @_;
    die 'app-restart-active:binding' unless @_ == 4 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ref($request) eq 'ARRAY' && join(',', @$request) eq 'other-child,parent,1200,1';
    require onpc_app_rows;
    require onpc_desktop_session;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'app-restart-active', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_app_rows::named_app_set($journey, 'gdm', 'fresh', 'new', 'existing', [
        ['A', 'match-precise', 'allowed'], ['H', 'match-hard-precise', 'permanent'],
        ['S', 'match-soft-wildcard', 'conditional']], 'rules');
    my $enter = sub {
        my ($prefix, $role, $entry) = @_;
        onpc_desktop_session::enter_desktop($journey, 'gdm', $role, $entry, 'success', $prefix);
    };
    my $leave = sub {
        my ($prefix) = @_;
        my $section = $journey->scope($prefix);
        onpc_desktop_session::switch_user($section, $section->seen('desktop'));
    };
    my $select = sub {
        my ($prefix, $child) = @_;
        my $section = $journey->scope($prefix);
        $section->consume_observation('parent-selected', onpc_parent::select_child($section, $child,
            $section->seen('child-picker-opened'), 'child-picker-opened',
            'child-choice-highlighted', 'parent-selected'));
    };
    $enter->('setup-return', 'parent', 'retained');
    $select->('riley-setup', 'child');
    $journey->seen('riley-time');
    $select->('jordan-setup', 'existing');
    $journey->seen($_) for qw(no-grant jordan-time);
    $leave->('setup-leave');
    onpc_gdm::enter_station($journey->scope('seed-station'), '');
    $journey->seen($_) for qw(seed-riley-select seed-riley-parent seed-station-cancel seed-station-returned);
    $enter->('seed-riley', 'child', 'fresh');
    $journey->seen("seed-riley-form-$_") for qw(launch approver custom text apps read cancel returned);
    $leave->('seed-riley-leave');
    my $approval = $journey->scope('request');
    $approval->{kiosk_request} = [@$request];
    onpc_request_flow::prepare($approval, 'new', 'new', 'observed',
        'existing-fixture-child', 'fixture-parent', 1200, 1, 'kiosk');
    onpc_request_flow::approve($approval, 'existing-fixture-child', 'fixture-parent', 1200, 1, 'automatic');
    $enter->('issued-return', 'parent', 'retained');
    $journey->seen('issued-policy');
    $leave->('issued-leave');
    $enter->('original-entry', 'other-child', 'fresh');
    $journey->seen('original-countdown');
    onpc_app_rows::native_activity_entry($journey, 'original', 'command', 'other-child', 1, 'policy');
    $journey->seen("jordan-$_") for qw(launch custom text apps read cancel returned);
    $leave->('original-leave');
    onpc_gdm::enter_station($journey->scope('capture-station'), '');
    $journey->seen($_) for qw(capture-jordan capture-riley-select capture-riley capture-cancel capture-returned);
    $enter->('before-parent', 'parent', 'retained');
    $journey->seen('before-policy');
    my $restart = $journey->scope('reopen');
    reopen($restart, 'parent', $restart->seen('prior-window'), 'management');
    $journey->seen('boundary-wait');
    $select->('returned-jordan', 'existing');
    $journey->seen('returned-policy');
    $select->('returned-riley', 'child');
    $journey->seen('returned-riley-settings');
    $select->('final-jordan', 'existing');
    $leave->('returned-parent-leave');
    onpc_gdm::enter_station($journey->scope('returned-station'), '');
    $journey->seen($_) for qw(returned-riley returned-jordan-select returned-jordan returned-cancel returned-greeter);
    $enter->('returned-riley-entry', 'child', 'retained');
    $journey->seen("returned-riley-form-$_") for qw(launch read cancel returned);
    $leave->('returned-riley-leave');
    $enter->('final-parent', 'parent', 'retained');
    $journey->seen('final-policy');
    $leave->('final-parent-leave');
    $enter->('returned-jordan-entry', 'other-child', 'retained');
    $journey->seen("returned-jordan-form-$_") for qw(launch read cancel returned);
    onpc_app_rows::native_activity_resume($journey, 'resume');
    $journey->seen($_) for qw(original-close original-closed);
    onpc_app_rows::native_blocked_app($journey->scope('hard'), 'H');
    my $soft = $journey->scope('soft');
    onpc_app_rows::native_usable_app($soft, 'command', $soft->seen('desktop'), 'other-child', 'unmatched-soft');
    $journey->seen('final-countdown');
    $journey->finish();
}

sub app_restart_expired {
    onpc_progress::operation('Reopening the apps, letting child time expire and approving recovery');
    my ($exchange, $declared, $challenges, $request) = @_;
    die 'app-restart-expired:binding' unless @_ == 4 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ref($request) eq 'ARRAY' && join(',', @$request) eq 'child,parent,1200,0';
    require onpc_app_rows;
    require onpc_desktop_session;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'app-restart-expired', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_app_rows::named_app_set($journey, 'gdm', 'fresh', 'new', 'child', [
        ['A', 'match-precise', 'allowed'], ['H', 'match-hard-precise', 'permanent'],
        ['S', 'match-soft-wildcard', 'conditional']], 'rules');
    my $enter = sub {
        my ($prefix, $role, $entry, $expected) = @_;
        onpc_desktop_session::enter_desktop($journey, 'gdm', $role, $entry,
            $expected // 'success', $prefix);
    };
    my $leave = sub {
        my ($prefix) = @_;
        my $section = $journey->scope($prefix);
        onpc_desktop_session::switch_user($section, $section->seen('desktop'));
    };
    $enter->('setup-return', 'parent', 'retained');
    onpc_parent::grant_only_time_profile($journey, 'desktop', 'same-user', 'retained', 0, 0, 600, 'default', 0);
    $enter->('original-entry', 'child', 'fresh');
    $journey->seen('original-countdown');
    onpc_app_rows::native_activity_entry($journey, 'original', 'command', 'child');
    for my $prefix ('first-overlay', 'reopened-overlay') {
        onpc_request_flow::overlay_entry($journey, $prefix, 'command');
        $journey->seen("$prefix-cancel");
        $journey->seen("$prefix-returned");
    }
    $leave->('original-leave');
    $enter->('before-parent', 'parent', 'retained');
    $journey->seen('before-policy');
    my $restart = $journey->scope('reopen');
    reopen($restart, 'parent', $restart->seen('prior-window'), 'management');
    my $selected = $journey->scope('returned-child');
    $selected->consume_observation('parent-selected', onpc_parent::select_child($selected, 'child',
        $selected->seen('child-picker-opened'), 'child-picker-opened',
        'child-choice-highlighted', 'parent-selected'));
    $journey->seen('returned-policy');
    $leave->('returned-parent-leave');
    onpc_gdm::enter_station($journey->scope('reopened-station'), '');
    $journey->seen($_) for qw(reopened-station-cancel reopened-station-returned
        expiry-wait-first expiry-wait-last);
    $enter->('expired-parent', 'parent', 'retained');
    $journey->seen('expired-policy');
    $leave->('expired-parent-leave');
    $enter->('denied-child', 'child', 'retained', 'time-denied');
    onpc_gdm::return_from_time_denial($journey,
        'denied-return-ready', 'denied-return-state', 'denied-returned');
    $journey->{kiosk_request} = [@$request];
    onpc_request_flow::prepare($journey, 'new', 'new', 'observed',
        'fixture-child', 'fixture-parent', 1200, 0, 'kiosk');
    onpc_request_flow::approve($journey, 'fixture-child', 'fixture-parent', 1200, 0, 'automatic');
    $enter->('recovered-parent', 'parent', 'retained');
    $journey->seen('recovered-policy');
    $leave->('recovered-parent-leave');
    $enter->('recovered-child', 'child', 'retained');
    $journey->seen('recovered-countdown');
    onpc_app_rows::native_activity_resume($journey, 'resume');
    $journey->seen($_) for qw(hard-denied soft-denied);
    onpc_app_rows::native_read_activity($journey, 'retained-work');
    onpc_app_rows::native_finish_app($journey->scope('original'));
    my $allowed = $journey->scope('allowed');
    onpc_app_rows::native_usable_app($allowed, 'command', $allowed->seen('desktop'), 'child', 'A');
    $journey->finish();
}

sub run_removal {
    onpc_progress::operation('Following one continuous removal, retention and purge history');
    my ($exchange, $declared, $challenges) = @_;
    die 'package-removal:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'package-removal', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_parent::login_functional($journey);
    $journey->seen($_) for qw(command-context package-submitted package-result activated-reboot-requested);
    onpc_gdm::named_login($journey, 'activated', 'parent');
    onpc_parent::named_management($journey, 'initial', 'child');
    $journey->seen($_) for qw(initial-apps initial-rows initial-screen limit-enabled save-enabled);
    onpc_allowance_boundaries::custom_value($journey, 'initial-allowance', 4);
    $journey->seen($_) for qw(initial-apps-again initial-block
        initial-block-read initial-policy switch-user gdm-switched);
    onpc_gdm::enter_station($journey, '');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1);
    $journey->seen($_) for qw(open-cancel open-returned);
    onpc_gdm::named_login($journey, 'restricted-child', 'child');
    $journey->seen($_) for qw(blocked-before-remove overlay-launch overlay-approver
        overlay-choices overlay-cancel restricted-logout);
    onpc_request_flow::obtain_time($journey, 'selected', 'fixture-child', 'fixture-parent', 75, 1, 'automatic');
    onpc_gdm::named_login($journey, 'remove-parent', 'parent');
    onpc_parent::named_management($journey, 'before-remove', 'child');
    $journey->seen($_) for qw(active-grant remove-submitted remove-result removed-reboot-requested);
    onpc_gdm::named_login($journey, 'removed', 'parent');
    $journey->seen('removed-parent-logout');
    onpc_gdm::named_login($journey, 'healthy-child', 'child');
    $journey->seen($_) for qw(healthy-command healthy-opened healthy-submit healthy-submitted
        healthy-close healthy-closed healthy-child-logout);
    onpc_gdm::named_login($journey, 'reinstall-parent', 'parent');
    $journey->seen($_) for qw(reinstall-submitted reinstall-result retained-reboot-requested);
    onpc_gdm::named_login($journey, 'retained', 'parent');
    onpc_parent::named_management($journey, 'retained', 'child');
    $journey->seen($_) for qw(retained-policy retained-switch retained-greeter);
    onpc_gdm::enter_station($journey->scope('retained'), '');
    $journey->seen($_) for qw(retained-accounts retained-request retained-cancel retained-returned);
    onpc_gdm::named_login($journey, 'reapply-parent', 'parent');
    onpc_parent::named_management($journey, 'reapply', 'child');
    onpc_allowance_boundaries::custom_value($journey, 'reapply-allowance', 5);
    $journey->seen($_) for qw(reapply-apps reapply-allowed reapply-allowed-read reapply-block
        reapply-block-read reapply-policy reapply-switch reapply-greeter);
    onpc_gdm::named_login($journey, 'reblocked-child', 'child');
    $journey->seen($_) for qw(blocked-after-reinstall reblocked-logout);
    onpc_gdm::named_login($journey, 'purge-parent', 'parent');
    $journey->seen($_) for qw(purge-submitted purge-result purged-reboot-requested);
    onpc_gdm::named_login($journey, 'purged', 'parent');
    $journey->seen($_) for qw(fresh-submitted fresh-result fresh-reboot-requested);
    onpc_gdm::named_login($journey, 'fresh', 'parent');
    onpc_parent::named_management($journey, 'fresh', 'child');
    $journey->seen($_) for qw(fresh-apps fresh-rows fresh-switch fresh-greeter);
    onpc_gdm::enter_station($journey->scope('fresh'), '');
    $journey->seen($_) for qw(fresh-request fresh-cancel fresh-returned);
    $journey->finish();
}

1;
