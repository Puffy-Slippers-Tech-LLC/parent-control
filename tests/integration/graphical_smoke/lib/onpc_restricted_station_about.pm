package onpc_restricted_station_about;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_journey ();
use onpc_request_flow ();
use onpc_window ();

sub run {
    onpc_progress::operation('Qualifying restricted station About and unchanged form return');
    my ($exchange) = @_;
    die 'kiosk-about:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => 'restricted-station-about', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('wrong-entry', 'limit-enabled', 'save-enabled',
                   'allowance-15-select', 'allowance-15-read', 'time-explanation-read',
                   'switch-user', 'gdm-switched') {
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
