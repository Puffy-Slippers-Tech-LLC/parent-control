package onpc_kiosk_recovery;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_app_rows ();
use onpc_text ();
use onpc_request_flow ();
use onpc_desktop_session ();

sub run {
    onpc_progress::operation('Checking a child station request after a wrong password and a cancelled approval');
    my ($exchange, $declared, $challenges) = @_;
    die 'kiosk-recovery:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'baseline-journey', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 0, 1));
    $journey->seen('apps-page');
    onpc_app_rows::edit_policy($journey, onpc_app_rows::fixture_app('H'),
        'match-hard-precise', 'permanent', 'hard', [], 1);
    onpc_app_rows::edit_policy($journey, onpc_app_rows::fixture_app('S'),
        'match-soft-wildcard', 'conditional', 'soft', [], 1);
    onpc_text::replace_text($journey, 'catalogue-clear', 'setup-clear');
    $journey->seen($_) for qw(saved-policy setup-switch-ready setup-switch setup-greeter);
    onpc_request_flow::prepare($journey->scope('kiosk-rejection'), 'open', 'new', 'default',
        'fixture-child', 'fixture-parent', 75, 1, 'compact');
    for my $outcome ('rejection', 'cancel') {
        my $request = $journey->scope('kiosk-' . $outcome);
        onpc_request_flow::reject($request, $outcome, 'fixture-child', 'fixture-parent', 75, 1);
        $request->seen($_) for qw(form-cancel form-returned);
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'time-denied', "$outcome-child");
        onpc_gdm::return_from_time_denial($journey, "$outcome-child-denied-return-ready",
            "$outcome-child-denied-return-state", "$outcome-child-denied-returned");
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', "$outcome-parent");
        $journey->consume_observation("$outcome-supplied-parent-retained", onpc_parent::open_for_child(
            $journey, 'desktop', 'same-user', 'retained', 'child', "$outcome-supplied", 0));
        $journey->seen("$outcome-$_") for qw(policy switch greeter);
        my $next = $journey->scope($outcome eq 'rejection' ? 'kiosk-cancel' : 'kiosk-final');
        onpc_gdm::enter_station($next, '');
        $next->seen('remembered');
    }
    my $approval = $journey->scope('kiosk-final');
    onpc_request_flow::continued_request($approval, 'kiosk', 75, 1200);
    onpc_request_flow::approve($approval, 'fixture-child', 'fixture-parent', 1200, 1, 'automatic');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'approved-child');
    $journey->seen('child-countdown');
    my $soft = $journey->scope('soft-use');
    onpc_app_rows::native_usable_app($soft, 'command', undef, 'child', 'S');
    $journey->seen($_) for qw(soft-close soft-closed hard-denied child-switch-ready child-switch child-greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'approved-parent');
    $journey->consume_observation('approved-supplied-parent-retained', onpc_parent::open_for_child(
        $journey, 'desktop', 'same-user', 'retained', 'child', 'approved-supplied', 0));
    $journey->seen('approved-policy');
    $journey->finish();
}
1;
