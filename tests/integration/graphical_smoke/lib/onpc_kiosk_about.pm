package onpc_kiosk_about;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_journey ();
use onpc_request_flow ();
use onpc_window ();

sub run {
    onpc_progress::operation('Reading station About and returning to the unchanged request');
    my ($exchange) = @_;
    die 'kiosk-about:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'kiosk-about', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 30, 1));
    for my $stage ('switch-user', 'gdm-switched') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_gdm::enter_station($journey, '');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
        'fixture-child', 'fixture-parent', 75, 1);
    for my $stage ('about-open', 'about-read') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->consume_observation('about-closed', onpc_window::close(
        $journey, 'station-about', $journey->seen('about-close-ready')));
    for my $stage ('form-returned', 'cancel', 'returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
