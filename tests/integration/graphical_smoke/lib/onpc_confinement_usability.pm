package onpc_confinement_usability;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_request_flow ();
use onpc_desktop_session ();

sub parent_return {
    my ($journey, $prefix) = @_;
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', "$prefix-parent");
    $journey->consume_observation("$prefix-supplied-parent-retained", onpc_parent::open_for_child(
        $journey, 'desktop', 'same-user', 'retained', 'child', "$prefix-supplied", 0));
}

sub run {
    onpc_progress::operation('Checking passwordless requests, denial, approval and fresh reentry');
    my ($exchange, $declared, $challenges) = @_;
    die 'confinement-usability:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'confinement-usability', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('parent-selected', onpc_parent::open_for_child(
        $journey, 'gdm', 'fresh', 'new', 'child'));
    onpc_request_flow::daily_station_entry($journey);
    for my $outcome ('rejection', 'cancel') {
        my $request = $journey->scope($outcome);
        onpc_request_flow::prepare($request, 'open', $outcome eq 'rejection' ? 'open' : 'new',
            $outcome eq 'rejection' ? 'default' : 'selected', 'fixture-child', 'fixture-parent', 75, 1, 'compact');
        onpc_request_flow::reject($request, $outcome, 'fixture-child', 'fixture-parent', 75, 1);
        $request->seen($_) for qw(exit returned);
        parent_return($journey, $outcome);
        $journey->seen("$outcome-$_") for qw(balance switch greeter);
    }
    onpc_request_flow::prepare($journey, 'new', 'new', 'selected', 'fixture-child', 'fixture-parent', 75, 1, 'compact');
    onpc_request_flow::approve($journey, 'fixture-child', 'fixture-parent', 75, 1, 'automatic');
    parent_return($journey, 'approved');
    $journey->seen($_) for qw(approved-balance approved-switch approved-greeter);
    my $reentry = $journey->scope('reentry');
    onpc_request_flow::prepare($reentry, 'open', 'new', 'selected', 'fixture-child', 'fixture-parent', 75, 1, 'compact');
    $reentry->seen($_) for qw(exit returned);
    parent_return($journey, 'restore');
    $journey->seen($_) for qw(revoke-open revoke-warning revoke-confirm revoked-balance
        restore-allowance restore-disabled restore-saved restore-settings restore-balance);
    $journey->finish();
}

sub optional_artwork {
    onpc_progress::operation('Requesting time with missing optional scenery and restoring it');
    my ($exchange, $declared, $challenges) = @_;
    die 'kiosk-optional-artwork:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'kiosk-optional-artwork', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('parent-selected', onpc_parent::open_for_child(
        $journey, 'gdm', 'fresh', 'new', 'child'));
    onpc_request_flow::daily_station_entry($journey);
    onpc_request_flow::prepare($journey, 'new', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1, 'compact');
    onpc_request_flow::approve($journey, 'fixture-child', 'fixture-parent', 75, 1, 'automatic');
    parent_return($journey, 'approved');
    $journey->seen($_) for qw(approved-balance approved-switch approved-greeter);
    my $reentry = $journey->scope('reentry');
    onpc_request_flow::prepare($reentry, 'open', 'new', 'selected', 'fixture-child', 'fixture-parent', 75, 1, 'compact');
    $reentry->seen($_) for qw(exit returned);
    $journey->finish();
}

sub service_recovery {
    onpc_progress::operation('Recovering a request after one owned broker outage');
    my ($exchange, $declared, $challenges) = @_;
    die 'kiosk-service-recovery:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'kiosk-service-recovery', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('parent-selected', onpc_parent::open_for_child(
        $journey, 'gdm', 'fresh', 'new', 'child'));
    $journey->seen($_) for qw(limit-enabled save-enabled allowance-15-select
        allowance-15-read time-explanation-read setup-parent-closed
        switch-user gdm-switched);
    onpc_gdm::enter_station($journey, '');
    $journey->seen($_) for qw(request-form child-selected approver-selected selections-read
        kiosk-diagnostic-error kiosk-diagnostic-exit outage-returned);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'outage-parent');
    onpc_parent::named_management($journey, 'outage-supplied', 'child');
    $journey->seen($_) for qw(outage-balance outage-switch outage-greeter);
    onpc_gdm::enter_station($journey, 'cancel-');
    $journey->seen($_) for qw(new-duration new-text-focus new-text-selected
        new-text-read new-apps new-estimate);
    onpc_request_flow::approve($journey, 'fixture-child', 'fixture-parent', 75, 1, 'automatic');
    parent_return($journey, 'approved');
    $journey->seen('approved-balance');
    $journey->finish();
}
1;
