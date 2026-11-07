package onpc_offline_approvals;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_app_rows ();
use onpc_desktop_session ();
use onpc_request_flow ();

sub app_results {
    my ($journey, $prefix, $retained) = @_;
    my $allowed = $journey->scope($prefix . '-allowed');
    my $used = onpc_app_rows::native_usable_app($allowed, 'command', undef, 'child', 'A');
    if ($retained) {
        $journey->seen($prefix . '-allowed-capture');
    } else {
        onpc_app_rows::native_close_app($allowed, $used);
    }
    $journey->seen($prefix . '-hard-denied');
    my $soft = $journey->scope($prefix . '-soft');
    $used = onpc_app_rows::native_usable_app($soft, 'command', undef, 'child', 'S');
    if ($retained) {
        $journey->seen($prefix . '-soft-capture');
    } else {
        onpc_app_rows::native_close_app($soft, $used);
    }
}

sub run {
    onpc_progress::operation('Approving extra time on both child screens offline, then revoking soft app access');
    my ($exchange, $invocations, $challenges, $overlay_request, $kiosk_request) = @_;
    die 'offline-approvals:binding' unless @_ == 5 && ref($exchange) eq 'CODE'
        && ref($overlay_request) eq 'ARRAY' && ref($kiosk_request) eq 'ARRAY'
        && join(',', @$overlay_request) eq 'child,parent,180,1'
        && join(',', @$kiosk_request) eq 'child,parent,180,1';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'offline-approvals', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child',
        $journey->seen('child-picker-opened'), 'child-picker-opened',
        'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for qw(offline-enter allowance);
    onpc_app_rows::named_app_set($journey, 'desktop', 'same-user', 'retained', 'child', [
        ['A', 'match-precise', 'allowed'], ['H', 'match-hard-precise', 'permanent'],
        ['S', 'match-soft-wildcard', 'conditional']], 'rules');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'child');
    $journey->seen($_) for qw(before-countdown overlay-launch);
    my $overlay = $journey->scope('overlay');
    $overlay->{overlay_request} = $overlay_request;
    onpc_request_flow::prepare($overlay, 'open', 'open', 'observed',
        'fixture-child', 'fixture-parent', 180, 1, 'overlay');
    onpc_request_flow::overlay_approve($overlay, 'automatic');
    $overlay->seen('countdown');
    app_results($journey, 'first', 0);
    my $logout = $journey->scope('logout');
    onpc_desktop_session::log_out($logout, $logout->seen('desktop'));
    my $station = $journey->scope('station');
    $station->{kiosk_request} = $kiosk_request;
    onpc_request_flow::prepare($station, 'open', 'new', 'observed',
        'fixture-child', 'fixture-parent', 180, 1, 'kiosk');
    onpc_request_flow::approve($station, 'fixture-child', 'fixture-parent', 180, 1, 'automatic');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'station-fresh');
    $station->seen('countdown');
    app_results($journey, 'second', 1);
    onpc_desktop_session::enter_desktop($journey, 'desktop', 'parent', 'retained',
        'success', 'parent-return', 'child');
    $journey->consume_observation('supplied-parent-retained', onpc_parent::open_for_child(
        $journey, 'desktop', 'same-user', 'retained', 'child', 'supplied', 0));
    $journey->seen($_) for qw(before-revoke revoke-open revoke-confirm after-revoke);
    onpc_desktop_session::enter_desktop($journey, 'desktop', 'child', 'retained',
        'success', 'child-return', 'parent');
    $journey->seen($_) for qw(soft-closed allowed-retained allowed-submit allowed-submitted
                            soft-denied hard-denied offline-restore);
    $journey->finish();
}

1;
