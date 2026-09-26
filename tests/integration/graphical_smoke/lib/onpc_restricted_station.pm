package onpc_restricted_station;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_journey ();
use onpc_request_flow ();
use onpc_station ();

sub run {
    onpc_progress::operation('Checking request-station restrictions and the declared outcome');
    my ($exchange, $outcome) = @_;
    die 'station:arguments' unless (@_ == 1 || @_ == 2 && $outcome eq 'denied')
        && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $outcome ? 'kiosk-approval-flow' : 'kiosk-approval', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 0, 1));
    for my $stage ('time-explanation-read', 'switch-user', 'gdm-switched') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_gdm::enter_station($journey, '');
    $journey->consume_observation('request-form', $journey->seen('request-form'));
    onpc_station::restrictions($journey);
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
        'fixture-child', 'fixture-parent', 75, 1);
    if ($outcome) {
        onpc_request_flow::reject($journey, 'rejection', 'fixture-child', 'fixture-parent', 75, 1);
        onpc_station::restrictions($journey, 'after-');
        for my $stage ('new-cancel', 'new-returned') {
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    } else {
        onpc_request_flow::approve($journey, 'fixture-child', 'fixture-parent', 75, 1, 'automatic');
    }
    $journey->finish();
}
1;
