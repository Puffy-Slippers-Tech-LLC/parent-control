package onpc_request_exit_cases;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_desktop_session ();
use onpc_app_rows ();
use onpc_request_flow ();
use onpc_request_exit ();
use onpc_journey ();

sub run_kiosk {
    onpc_progress::operation('Preparing a kiosk request and taking its declared exit');
    my ($exchange, $declared, $challenges) = @_;
    die 'kiosk-exit:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'kiosk-approval', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    onpc_request_flow::daily_station_entry($journey);
    my $cancel = $journey->scope('cancel-exit');
    onpc_request_flow::prepare($cancel, 'open', 'open', 'default',
        'fixture-child', 'fixture-parent', 75, 1, 'compact');
    $cancel->seen($_) for qw(cancel-action cancel-returned);
    my $close = $journey->scope('close-exit');
    onpc_request_flow::prepare($close, 'open', 'new', 'selected',
        'fixture-child', 'fixture-parent', 75, 1, 'compact');
    onpc_request_exit::escape($close);
    onpc_request_flow::prepare($journey, 'open', 'new', 'selected',
        'fixture-child', 'fixture-parent', 75, 1, 'compact');
    onpc_request_flow::approve($journey, 'fixture-child', 'fixture-parent', 75, 1, 'immediate');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    $journey->consume_observation('countdown', $journey->seen('countdown'));
    $journey->finish();
}

sub run_overlay {
    onpc_progress::operation('Exiting the child overlay and resuming the original activity');
    my ($exchange, $declared, $challenges) = @_;
    die 'overlay-exit:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'overlay-approved-exit', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->consume_observation('allowance-configured', $journey->seen('allowance-configured'));
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    my $activity = onpc_app_rows::native_activity_entry($journey, 'activity', 'command');
    my $cancel = $journey->scope('cancel-exit');
    onpc_request_flow::prepare($cancel, 'open', 'new', 'default',
        'fixture-child', 'fixture-parent', 75, 1, 'overlay');
    $cancel->seen($_) for qw(cancel cancel-returned);
    onpc_app_rows::native_activity_resume($cancel, 'resumed');
    my $close = $journey->scope('close-exit');
    onpc_request_flow::overlay_entry($close, 'open-entry', 'command');
    onpc_request_exit::escape($close);
    onpc_app_rows::native_activity_resume($close, 'resumed');
    onpc_request_flow::overlay_entry($journey, 'open-entry', 'command');
    onpc_request_flow::overlay_approve($journey, 'immediate');
    onpc_app_rows::native_activity_resume($journey, 'resumed');
    $journey->seen('countdown');
    onpc_app_rows::native_finish_app($activity);
    $journey->finish();
}
1;
