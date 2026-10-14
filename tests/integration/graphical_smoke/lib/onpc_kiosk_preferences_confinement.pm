package onpc_kiosk_preferences_confinement;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_journey ();
use onpc_request_flow ();

sub run {
    onpc_progress::operation('Qualifying station Preferences restrictions and preserved request');
    my ($exchange) = @_;
    die 'kiosk-preferences:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => 'kiosk-preferences-confinement', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 30, 1));
    for my $stage ('switch-user', 'gdm-switched') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_gdm::enter_station($journey, '');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
        'fixture-child', 'fixture-parent', 75, 1);
    for my $stage ('preferences-confined', 'form-returned', 'cancel', 'returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
