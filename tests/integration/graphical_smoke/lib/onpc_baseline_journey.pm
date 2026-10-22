package onpc_baseline_journey;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_app_rows ();
use onpc_request_flow ();
use onpc_desktop_session ();

sub run {
    onpc_progress::operation('Qualifying the complete ordered baseline request and restriction history');
    my ($exchange, $declared, $challenges) = @_;
    die 'baseline-journey:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'baseline-journey', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 0, 1));
    $journey->seen($_) for qw(saved-settings apps-page);
    for my $role ('hard', 'soft') {
        onpc_app_rows::access_choice($journey, "$role-access-save", "$role-access");
        $journey->seen("$role-final-match");
    }
    $journey->seen($_) for qw(saved-policy setup-switch-ready setup-switch setup-greeter);

    for my $outcome ('rejection', 'cancel') {
        my $request = $journey->scope('kiosk-' . $outcome);
        onpc_request_flow::prepare($request, 'open', 'new',
            $outcome eq 'rejection' ? 'default' : 'selected', 'fixture-child', 'fixture-parent', 75, 1);
        onpc_request_flow::reject($request, $outcome, 'fixture-child', 'fixture-parent', 75, 1);
        $request->seen($outcome eq 'rejection' ? 'form-cancel' : 'form-escape');
        $request->seen('form-returned');
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', "$outcome-parent");
        $journey->consume_observation("$outcome-supplied-parent-retained", onpc_parent::open_for_child(
            $journey, 'desktop', 'same-user', 'retained', 'child', "$outcome-supplied", 0));
        $journey->seen("$outcome-$_") for qw(policy switch greeter);
    }
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'time-denied', 'zero-child');
    onpc_gdm::return_from_time_denial($journey, 'zero-child-denied-return-ready',
        'zero-child-denied-return-state', 'zero-child-denied-returned');
    my $first = $journey->scope('kiosk-first');
    onpc_gdm::enter_station($first, '');
    onpc_request_flow::continued_request($first, 'kiosk', 75, 600);
    onpc_request_flow::approve($first, 'fixture-child', 'fixture-parent', 600, 1, 'automatic');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'first-child');
    $journey->seen('first-countdown');
    for my $binding (['allowed-use', 'A'], ['soft-use', 'S']) {
        my $section = $journey->scope($binding->[0]);
        onpc_app_rows::native_usable_app($section, 'command', undef, 'child', $binding->[1]);
    }
    $journey->seen($_) for qw(soft-close soft-closed allowed-close allowed-closed hard-denied remaining-countdown);
    onpc_app_rows::native_activity_entry($journey, 'activity', 'command', 'child', 0);
    for my $outcome ('rejection', 'cancel') {
        my $request = $journey->scope('overlay-' . $outcome);
        onpc_request_flow::overlay_entry($request, 'entry', 'command');
        onpc_request_flow::continued_request($request, 'overlay', 600, 75) if $outcome eq 'rejection';
        onpc_request_flow::overlay_reject($request, $outcome);
        $request->seen($_) for qw(form-cancel returned);
        onpc_app_rows::native_read_activity($journey, "$outcome-activity");
    }
    my $overlay = $journey->scope('overlay-approval');
    onpc_request_flow::overlay_entry($overlay, 'entry', 'command');
    $overlay->seen('open-estimate');
    onpc_request_flow::overlay_approve($overlay, 'immediate');
    onpc_app_rows::native_read_activity($journey, 'approved-activity');
    $journey->seen($_) for qw(approved-activity-submit approved-activity-submitted activity-close activity-closed overlay-countdown);
    my $soft = $journey->scope('overlay-soft-use');
    onpc_app_rows::native_usable_app($soft, 'command', undef, 'child', 'S');
    $journey->seen($_) for qw(overlay-soft-close overlay-soft-closed overlay-hard-denied
        child-switch-ready child-switch child-greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'revoke-parent');
    $journey->consume_observation('revoke-supplied-parent-retained', onpc_parent::open_for_child(
        $journey, 'desktop', 'same-user', 'retained', 'child', 'revoke-supplied', 0));
    $journey->seen($_) for qw(overlay-policy revoke-open revoke-warning revoke-confirm revoked-policy
        revoked-switch revoked-greeter enter-locked);
    $journey->consume_observation('time-denied', onpc_desktop_session::reveal_lock($journey, 'time-denied'));
    $journey->seen($_) for qw(soft-denied return-greeter denied-returned);

    my $final = $journey->scope('kiosk-final');
    onpc_gdm::enter_station($final, '');
    onpc_request_flow::continued_request($final, 'kiosk', 75, 600);
    onpc_request_flow::approve($final, 'fixture-child', 'fixture-parent', 600, 1, 'automatic');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'retained', 'success', 'final-child');
    $journey->seen('final-countdown');
    my $final_soft = $journey->scope('final-soft-use');
    onpc_app_rows::native_usable_app($final_soft, 'command', undef, 'child', 'S');
    $journey->seen($_) for qw(final-soft-close final-soft-closed final-hard-denied
        final-switch-ready final-switch final-greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'restore-parent');
    $journey->consume_observation('restore-supplied-parent-retained', onpc_parent::open_for_child(
        $journey, 'desktop', 'same-user', 'retained', 'child', 'restore-supplied', 0));
    $journey->seen($_) for qw(final-policy restore-apps);
    for my $role ('hard', 'soft') {
        onpc_app_rows::access_choice($journey, "restore-$role-access-save", "restore-$role-access");
        $journey->seen("restore-$role-final-match");
    }
    $journey->seen($_) for qw(restore-screen restore-disabled restore-saved restore-settings restore-balance);
    $journey->finish();
}
1;
