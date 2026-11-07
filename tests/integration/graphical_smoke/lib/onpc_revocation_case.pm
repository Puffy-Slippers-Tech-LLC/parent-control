package onpc_revocation_case;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_app_rows ();
use onpc_desktop_session ();
use onpc_request_flow ();

sub run {
    onpc_progress::operation('Checking Cancel preserves child work and Confirm removes extra time while another child keeps working');
    my ($exchange, $invocations, $challenges, $request, $daily) = @_;
    die 'revocation-case:binding' unless @_ == 5 && ref($exchange) eq 'CODE'
        && defined($daily) && ($daily == 0 || $daily == 15 || $daily == 30)
        && ref($request) eq 'ARRAY' && join(',', @$request) eq 'other-child,parent,1200,1';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'revocation-case', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'existing',
        $journey->seen('child-picker-opened'), 'child-picker-opened',
        'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    my $no_grant = $daily == 15;
    $journey->seen($_) for ('initial-balance', 'enable',
        $daily == 30 ? qw(daily-ready daily-confirm daily-balance) : qw(zero-ready zero-confirm zero-balance));
    onpc_app_rows::named_app_set($journey, 'desktop', 'same-user', 'retained', 'existing',
        [['A', 'match-precise', 'allowed'], ['H', 'match-hard-precise', 'permanent'],
         ['S', 'match-soft-precise', 'conditional']], 'rules');
    unless ($no_grant) {
        onpc_app_rows::retained_app_activities($journey, [['riley', 'child', 'fresh']]);
    }
    my $approval = $journey->scope('request');
    $approval->{kiosk_request} = $request;
    onpc_request_flow::obtain_time($approval, 'observed', 'existing-fixture-child',
        'fixture-parent', 1200, 1, 'automatic');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'fresh', 'success', 'jordan');
    onpc_app_rows::native_activity_entry($journey, 'allowed', 'command', 'other-child', 1, 'policy');
    onpc_app_rows::native_activity_entry($journey, 'soft', 'command', 'other-child', 1, 'unmatched-soft');
    $journey->seen('jordan-desktop-identity');
    onpc_desktop_session::enter_desktop($journey, 'desktop', 'parent', 'retained', 'success',
                                      'parent-before', 'other-child');
    $journey->consume_observation('supplied-parent-retained', onpc_parent::open_for_child(
        $journey, 'desktop', 'same-user', 'retained', 'existing', 'supplied', 0));
    if ($no_grant) {
        $journey->seen($_) for qw(granted-before daily-off daily-enable);
    }
    $journey->seen($_) for qw(before cancel-open cancel cancel-balance);
    onpc_app_rows::retained_app_visit($journey, 'cancel-child', 'other-child', 'desktop', 'parent');
    onpc_app_rows::native_read_activity($journey, 'cancel-soft');
    $journey->seen($_) for qw(cancel-soft-submit cancel-soft-submitted);
    onpc_desktop_session::enter_desktop($journey, 'desktop', 'parent', 'retained', 'success',
                                      'parent-confirm', 'other-child');
    $journey->seen($_) for qw(confirm-before confirm-open confirm confirmed-balance);
    if ($daily) {
        onpc_desktop_session::enter_desktop($journey, 'desktop', 'other-child', 'retained', 'success',
                                          'confirmed-child', 'parent');
        onpc_app_rows::native_read_activity($journey, 'confirmed-soft-closed');
        onpc_app_rows::native_read_activity($journey, 'confirmed-allowed-opened');
        $journey->seen($_) for qw(confirmed-allowed-submit confirmed-allowed-submitted);
        onpc_app_rows::native_blocked_app($journey->scope('denied-hard'), 'H');
        onpc_app_rows::native_blocked_app($journey->scope('denied-soft'), 'S');
        onpc_app_rows::retained_app_visit($journey, 'riley-return', 'child', 'desktop', 'other-child')
            unless $no_grant;
    } else {
        onpc_desktop_session::enter_desktop($journey, 'desktop', 'other-child', 'retained', 'time-denied',
                                          'denied-child', 'parent');
        onpc_gdm::return_from_time_denial($journey,
            'denied-return-ready', 'denied-return-state', 'denied-returned');
        onpc_app_rows::retained_app_visit($journey, 'riley-return', 'child', 'gdm');
    }
    onpc_app_rows::native_read_activity($journey, 'riley-usable') unless $no_grant;
    $journey->finish();
}

1;
