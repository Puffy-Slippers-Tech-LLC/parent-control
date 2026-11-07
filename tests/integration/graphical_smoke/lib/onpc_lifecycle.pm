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
    my ($exchange, $declared, $challenges, $request, $sign_out, $reboot, $idle) = @_;
    $sign_out //= 0;
    $reboot //= 0;
    $idle //= 0;
    onpc_progress::operation($idle
        ? 'Returning from idle before and after child time expires, then approving recovery'
        : $reboot
        ? 'Rebooting while both children keep saved choices and approved time'
        : $sign_out
        ? 'Signing each child out and back in with saved choices and approved time'
        : 'Reopening the apps while the child keeps approved time and work');
    die 'app-restart-active:binding' unless (@_ >= 4 && @_ <= 7)
        && ($sign_out == 0 || $sign_out == 1) && ($reboot == 0 || $reboot == 1)
        && (!$reboot || $sign_out)
        && ($idle == 0 || $idle == 1) && (!$idle || (!$sign_out && !$reboot))
        && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ref($request) eq 'ARRAY' && join(',', @$request) eq 'other-child,parent,1200,1';
    require onpc_app_rows;
    require onpc_desktop_session;
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $idle ? 'idle-active-expired' : $reboot ? 'reboot-active'
            : $sign_out ? 'sign-out-in-active' : 'app-restart-active', review => 0);
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
    $journey->seen('riley-policy-before') if $sign_out;
    $select->('jordan-setup', 'existing');
    $journey->seen($_) for qw(no-grant jordan-time);
    $journey->seen('prepared-policy') if $idle;
    $leave->('setup-leave');
    onpc_gdm::enter_station($journey->scope('seed-station'), '');
    $journey->seen($_) for qw(seed-riley-select seed-riley-parent seed-station-cancel seed-station-returned);
    $enter->('seed-riley', 'child', 'fresh');
    $journey->seen("seed-riley-form-$_") for qw(launch approver custom text apps read cancel returned);
    if ($sign_out) {
        $journey->seen($_) for qw(riley-animation-set riley-animation-read);
        my $app = $journey->scope('riley-before-app');
        onpc_app_rows::native_usable_app($app, 'command', $app->seen('desktop'), 'child', 'A');
    }
    $leave->('seed-riley-leave');
    if ($sign_out) {
        $enter->('riley-policy-entry', 'parent', 'retained');
        $select->('riley-policy-select', 'child');
        $journey->seen('riley-policy-after');
        $select->('riley-policy-finish', 'existing');
        $leave->('riley-policy-leave');
    }
    my $approval = $journey->scope('request');
    my $grant_seconds = $idle ? 600 : 1200;
    $approval->{kiosk_request} = ['other-child', 'parent', $grant_seconds, 1];
    onpc_request_flow::prepare($approval, 'new', 'new', 'observed',
        'existing-fixture-child', 'fixture-parent', $grant_seconds, 1, 'kiosk');
    onpc_request_flow::approve($approval, 'existing-fixture-child', 'fixture-parent', $grant_seconds, 1, 'automatic');
    unless ($idle) {
        $enter->('issued-return', 'parent', 'retained');
        $journey->seen('issued-policy');
        $leave->('issued-leave');
    }
    $enter->('original-entry', 'other-child', 'fresh');
    $journey->seen('original-countdown');
    $journey->seen($_) for $sign_out ? qw(jordan-animation-set jordan-animation-read) : ();
    onpc_app_rows::native_activity_entry($journey, 'original', 'command', 'other-child', 1, 'policy');
    $journey->seen("jordan-$_") for qw(launch custom text apps read cancel returned);
    $leave->('original-leave');
    onpc_gdm::enter_station($journey->scope('capture-station'), '');
    $journey->seen($_) for qw(capture-jordan capture-riley-select capture-riley capture-cancel capture-returned);
    unless ($idle) {
        $enter->('before-parent', 'parent', 'retained');
        $journey->seen('before-policy');
    }
    if ($idle) {
        $enter->('early-child', 'other-child', 'retained');
        $journey->seen($_) for qw(early-idle early-countdown);
        onpc_app_rows::native_activity_resume($journey, 'early-resume');
        $leave->('early-leave');
        $enter->('early-parent', 'parent', 'retained');
    } elsif ($reboot) {
        $journey->seen($_) for qw(reboot-requested reboot-greeter);
        $enter->('boundary-parent-entry', 'parent', 'fresh');
        my $parent = $journey->scope('boundary-parent-launch');
        onpc_parent::launch($parent, $parent->seen('desktop'), 'management');
    } elsif ($sign_out) {
        $leave->('boundary-parent-leave');
        for my $binding (['jordan', 'other-child'], ['riley', 'child']) {
            my ($child, $role) = @$binding;
            $enter->("boundary-$child-entry", $role, 'retained');
            my $section = $journey->scope("boundary-$child");
            onpc_desktop_session::log_out($section, $section->seen('desktop'));
        }
        $enter->('boundary-parent-entry', 'parent', 'retained');
    } else {
        my $restart = $journey->scope('reopen');
        reopen($restart, 'parent', $restart->seen('prior-window'), 'management');
        $journey->seen('boundary-wait');
    }
    $select->('returned-jordan', 'existing');
    $journey->seen('returned-policy');
    $select->('returned-riley', 'child');
    $journey->seen('returned-riley-settings');
    $select->('final-jordan', 'existing');
    $leave->('returned-parent-leave');
    onpc_gdm::enter_station($journey->scope('returned-station'), '');
    $journey->seen($_) for qw(returned-riley returned-jordan-select returned-jordan returned-cancel returned-greeter);
    $enter->('returned-riley-entry', 'child', $sign_out ? 'fresh' : 'retained');
    $journey->seen('returned-riley-animation') if $sign_out;
    $journey->seen("returned-riley-form-$_") for qw(launch read cancel returned);
    if ($sign_out) {
        my $app = $journey->scope('riley-after-app');
        onpc_app_rows::native_usable_app($app, 'command', $app->seen('desktop'), 'child', 'A');
    }
    $leave->('returned-riley-leave');
    unless ($idle) {
        $enter->('final-parent', 'parent', 'retained');
        $journey->seen('final-policy');
        $leave->('final-parent-leave');
    }
    $enter->('returned-jordan-entry', 'other-child', $sign_out ? 'fresh' : 'retained');
    $journey->seen('returned-jordan-animation') if $sign_out;
    $journey->seen("returned-jordan-form-$_") for qw(launch read cancel returned);
    if ($sign_out) {
        my $app = $journey->scope('new-allowed');
        onpc_app_rows::native_usable_app($app, 'command', $app->seen('desktop'), 'other-child');
    } else {
        onpc_app_rows::native_activity_resume($journey, 'resume');
        $journey->seen($_) for $idle ? () : qw(original-close original-closed);
    }
    unless ($idle) {
        onpc_app_rows::native_blocked_app($journey->scope('hard'), 'H');
        my $soft = $journey->scope('soft');
        onpc_app_rows::native_usable_app($soft, 'command', $soft->seen('desktop'), 'other-child', 'unmatched-soft');
    }
    if ($idle) {
        $journey->seen($_) for qw(tour-countdown expiry-wait expired-return expired-greeter);
        $enter->('expired-parent', 'parent', 'retained');
        $journey->seen('expired-policy');
        $leave->('expired-parent-leave');
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'retained',
            'time-denied', 'denied-child');
        onpc_gdm::return_from_time_denial($journey,
            'denied-return-ready', 'denied-return-state', 'denied-returned');
        onpc_gdm::enter_station($journey->scope('recovery-station'), '');
        $journey->seen('recovery-jordan');
        my $recovery = $journey->scope('recovery');
        $recovery->{kiosk_request} = [@$request];
        onpc_request_flow::prepare($recovery, 'new', 'open', 'observed',
            'existing-fixture-child', 'fixture-parent', 1200, 1, 'kiosk');
        onpc_request_flow::approve($recovery, 'existing-fixture-child', 'fixture-parent', 1200, 1, 'automatic');
        $enter->('recovered-parent', 'parent', 'retained');
        $journey->seen('recovered-policy');
        $leave->('recovered-parent-leave');
        $enter->('recovered-child', 'other-child', 'retained');
        $journey->seen('recovered-countdown');
        onpc_app_rows::native_activity_resume($journey, 'recovered-resume');
        onpc_app_rows::native_blocked_app($journey->scope('recovered-hard'), 'H');
        my $soft = $journey->scope('recovered-soft');
        onpc_app_rows::native_usable_app($soft, 'command', $soft->seen('desktop'), 'other-child', 'unmatched-soft');
    } else {
        $journey->seen('final-countdown');
    }
    $journey->finish();
}

sub expired_daily_replacement {
    onpc_progress::operation('Replacing expired extra time before the child returns');
    my ($exchange, $declared, $challenges, $request, $retained) = @_;
    $retained //= 0;
    die 'expired-daily:binding' unless (@_ == 4 || @_ == 5) && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ($retained == 0 || $retained == 1)
        && ref($request) eq 'ARRAY' && join(',', @$request) =~ /\Achild,parent,1200,[01]\z/;
    require onpc_app_rows;
    require onpc_desktop_session;
    require onpc_allowance_boundaries;
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => 'expired-daily-replacement', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $enter = sub {
        my ($prefix, $role, $entry) = @_;
        onpc_desktop_session::enter_desktop($journey, 'gdm', $role, $entry, 'success', $prefix);
    };
    my $leave = sub {
        my ($prefix) = @_;
        my $section = $journey->scope($prefix);
        onpc_desktop_session::switch_user($section, $section->seen('desktop'));
    };
    onpc_app_rows::named_app_set($journey, 'gdm', 'fresh', 'new', 'child', [
        ['A', 'match-precise', 'allowed'], ['H', 'match-hard-precise', 'permanent'],
        ['S', 'match-soft-wildcard', 'conditional']], 'rules');
    $enter->('setup-return', 'parent', 'retained');
    onpc_parent::grant_only_time_profile($journey, 'desktop', 'same-user', 'retained',
        0, 0, 600, 'default', 0);
    $enter->('original-entry', 'child', 'fresh');
    $journey->seen('original-countdown');
    my $soft = $journey->scope('original-soft');
    onpc_app_rows::native_usable_app($soft, 'command', $soft->seen('desktop'), 'child', 'S');
    onpc_app_rows::native_read_activity($journey, 'original-capture');
    $leave->('original-leave');
    $enter->('daily-parent', 'parent', 'retained');
    $journey->seen('daily-page');
    onpc_allowance_boundaries::custom_value($journey, 'daily', 30);
    $journey->seen('before-departure');
    $leave->('daily-parent-leave');
    $journey->seen('original-session') if $retained;
    unless ($retained) {
        $enter->('departure-child', 'child', 'retained');
        my $departure = $journey->scope('departure');
        onpc_desktop_session::log_out($departure, $departure->seen('desktop'));
    }
    $journey->seen($_) for qw(expiry-wait-first expiry-wait-last);
    $enter->('expired-parent', 'parent', 'retained');
    $journey->seen('expired-balances');
    $leave->('expired-parent-leave');
    $journey->{kiosk_request} = [@$request];
    onpc_request_flow::obtain_time($journey, 'observed',
        'fixture-child', 'fixture-parent', 1200, $request->[3], 'automatic');
    $enter->('replacement-child', 'child', $retained ? 'retained' : 'fresh');
    $journey->seen('replacement-countdown');
    if ($retained) {
        if ($request->[3]) {
            onpc_app_rows::native_activity_resume($journey, 'original-soft-return');
            # Both denied probes and new soft launches use the secondary fixture
            # slot. Close only after proving the original work remains usable.
            onpc_app_rows::native_finish_app($journey->scope('original-soft-return'));
        } else {
            onpc_app_rows::native_read_activity($journey, 'original-soft-closed');
        }
    }
    $journey->seen('hard-denied');
    if ($request->[3]) {
        my $soft = $journey->scope('soft');
        onpc_app_rows::native_usable_app($soft, 'command', $soft->seen('desktop'), 'child', 'S');
    } else {
        $journey->seen('soft-denied');
    }
    my $allowed = $journey->scope('allowed');
    onpc_app_rows::native_usable_app($allowed, 'command', $allowed->seen('desktop'), 'child', 'A');
    $journey->finish();
}

sub app_restart_expired {
    my ($exchange, $declared, $challenges, $request, $sign_out, $reboot) = @_;
    $sign_out //= 0;
    $reboot //= 0;
    onpc_progress::operation($reboot
        ? 'Rebooting, letting child time expire and approving a fresh session'
        : $sign_out
        ? 'Signing the child out, letting time expire and approving a fresh session'
        : 'Reopening the apps, letting child time expire and approving recovery');
    die 'app-restart-expired:binding' unless (@_ == 4 || @_ == 5 || @_ == 6)
        && ($sign_out == 0 || $sign_out == 1) && ($reboot == 0 || $reboot == 1)
        && (!$reboot || $sign_out)
        && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ref($request) eq 'ARRAY' && join(',', @$request) eq 'child,parent,1200,0';
    require onpc_app_rows;
    require onpc_desktop_session;
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $reboot ? 'reboot-expired' : $sign_out ? 'sign-out-in-expired' : 'app-restart-expired', review => 0);
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
    for my $prefix ($sign_out ? () : ('first-overlay', 'reopened-overlay')) {
        onpc_request_flow::overlay_entry($journey, $prefix, 'command');
        $journey->seen("$prefix-cancel");
        $journey->seen("$prefix-returned");
    }
    $leave->('original-leave');
    $enter->('before-parent', 'parent', 'retained');
    $journey->seen('before-policy');
    if ($reboot) {
        $journey->seen($_) for qw(reboot-requested reboot-greeter);
        $enter->('returned-parent', 'parent', 'fresh');
        my $parent = $journey->scope('returned-parent-launch');
        onpc_parent::launch($parent, $parent->seen('desktop'), 'management');
    } elsif ($sign_out) {
        $leave->('boundary-parent-leave');
        $enter->('boundary-child-entry', 'child', 'retained');
        my $section = $journey->scope('boundary-child');
        onpc_desktop_session::log_out($section, $section->seen('desktop'));
        $enter->('returned-parent', 'parent', 'retained');
    } else {
        my $restart = $journey->scope('reopen');
        reopen($restart, 'parent', $restart->seen('prior-window'), 'management');
    }
    if (!$sign_out || $reboot) {
        my $selected = $journey->scope('returned-child');
        $selected->consume_observation('parent-selected', onpc_parent::select_child($selected, 'child',
            $selected->seen('child-picker-opened'), 'child-picker-opened',
            'child-choice-highlighted', 'parent-selected'));
    }
    $journey->seen('returned-policy');
    $leave->('returned-parent-leave');
    unless ($sign_out) {
        onpc_gdm::enter_station($journey->scope('reopened-station'), '');
        $journey->seen($_) for qw(reopened-station-cancel reopened-station-returned);
    }
    $journey->seen($_) for qw(expiry-wait-first expiry-wait-last);
    $enter->('expired-parent', 'parent', 'retained');
    $journey->seen('expired-policy');
    $leave->('expired-parent-leave');
    $enter->('denied-child', 'child', $sign_out ? 'fresh' : 'retained', 'time-denied');
    onpc_gdm::return_from_time_denial($journey,
        'denied-return-ready', 'denied-return-state', 'denied-returned');
    $journey->{kiosk_request} = [@$request];
    onpc_request_flow::prepare($journey, 'new', 'new', 'observed',
        'fixture-child', 'fixture-parent', 1200, 0, 'kiosk');
    onpc_request_flow::approve($journey, 'fixture-child', 'fixture-parent', 1200, 0, 'automatic');
    $enter->('recovered-parent', 'parent', 'retained');
    $journey->seen('recovered-policy');
    $leave->('recovered-parent-leave');
    $enter->('recovered-child', 'child', $sign_out ? 'fresh' : 'retained');
    $journey->seen('recovered-countdown');
    onpc_app_rows::native_activity_resume($journey, 'resume') unless $sign_out;
    $journey->seen($_) for qw(hard-denied soft-denied);
    unless ($sign_out) {
        onpc_app_rows::native_read_activity($journey, 'retained-work');
        onpc_app_rows::native_finish_app($journey->scope('original'));
    }
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
