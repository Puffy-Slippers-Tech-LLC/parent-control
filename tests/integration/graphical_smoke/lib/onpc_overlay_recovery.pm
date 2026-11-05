package onpc_overlay_recovery;
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
    onpc_progress::operation('Checking a child request after a wrong password and a cancelled approval');
    my ($exchange, $declared, $challenges) = @_;
    die 'overlay-recovery:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'baseline-journey', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 30, 1));
    $journey->seen('apps-page');
    onpc_app_rows::edit_policy($journey, onpc_app_rows::fixture_app('H'),
        'match-hard-precise', 'permanent', 'hard', [], 1);
    onpc_app_rows::edit_policy($journey, onpc_app_rows::fixture_app('S'),
        'match-soft-wildcard', 'conditional', 'soft', [], 1);
    onpc_text::replace_text($journey, 'catalogue-clear', 'setup-clear');
    $journey->seen($_) for qw(saved-policy switch-ready switch-user gdm-switched);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'child-entry');
    onpc_app_rows::native_activity_entry($journey, 'activity', 'command', 'child', 0);
    onpc_request_flow::overlay_entry($journey, 'entry', 'command');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
        'fixture-child', 'fixture-parent', 75, 1, 'overlay');
    for my $outcome ('rejection', 'cancel') {
        my $request = $journey->scope('overlay-' . $outcome);
        onpc_request_flow::overlay_entry($request, 'entry', 'command') if $outcome eq 'cancel';
        onpc_request_flow::overlay_reject($request, $outcome);
        $request->seen($_) for qw(form-cancel returned hard-denied soft-denied);
    }
    my $approval = $journey->scope('overlay-approval');
    onpc_request_flow::overlay_entry($approval, 'entry', 'command');
    $approval->seen('open-estimate');
    onpc_request_flow::overlay_approve($approval, 'immediate');
    onpc_app_rows::native_read_activity($journey, 'approved-activity');
    $journey->seen($_) for qw(approved-activity-submit approved-activity-submitted
        activity-close activity-closed approved-countdown);
    my $soft = $journey->scope('soft-use');
    onpc_app_rows::native_usable_app($soft, 'command', undef, 'child', 'S');
    $journey->seen($_) for qw(soft-close soft-closed hard-denied child-switch-ready child-switch child-greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'parent-return');
    $journey->consume_observation('supplied-parent-retained', onpc_parent::open_for_child(
        $journey, 'desktop', 'same-user', 'retained', 'child', 'supplied', 0));
    $journey->seen('approved-policy');
    $journey->finish();
}
1;
