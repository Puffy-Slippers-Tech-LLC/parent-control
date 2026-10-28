package onpc_child_isolation;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_desktop_session ();
use onpc_request_flow ();
use onpc_password ();
use onpc_text ();
use onpc_allowance_boundaries ();

sub run {
    onpc_progress::operation('Checking healthy, unavailable and restored child requests');
    my ($exchange, $declared, $challenges) = @_;
    die 'child-isolation:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'child-isolation', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('parent-selected', onpc_parent::open_for_child(
        $journey, 'gdm', 'fresh', 'new', 'child'));
    $journey->seen('healthy-allowance');
    onpc_allowance_boundaries::select_child($journey, 'setup-jordan');
    $journey->seen($_) for qw(unavailable-allowance setup-switch setup-greeter);
    for my $phase (qw(healthy unavailable restored)) {
        my $request = $journey->scope($phase);
        onpc_gdm::enter_station($request, '');
        if ($phase eq 'healthy') {
            onpc_request_flow::prepare($request, 'new', 'open', 'default',
                'fixture-child', 'fixture-parent', 75, 1, 'compact');
        } elsif ($phase eq 'unavailable') {
            $request->seen($_) for qw(new-child new-duration);
            onpc_text::replace_text($request, 'jordan-kiosk-fraction', 'new-text');
            $request->seen($_) for qw(new-apps new-estimate);
        } else {
            $request->seen('new-estimate');
        }
        $request->seen('approval-open');
        onpc_password::enter_kiosk_mate_password($request);
        $request->seen($_) for qw(approval-success new-returned);
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', "$phase-parent");
        onpc_allowance_boundaries::select_child($journey, 'restored-selected-away') if $phase eq 'restored';
        onpc_allowance_boundaries::select_child($journey, "$phase-selected");
        $journey->seen("$phase-$_") for qw(balance switch greeter);
    }
    my $reentry = $journey->scope('reentry');
    onpc_gdm::enter_station($reentry, '');
    $reentry->seen($_) for qw(usable exit returned);
    $journey->finish();
}
1;
