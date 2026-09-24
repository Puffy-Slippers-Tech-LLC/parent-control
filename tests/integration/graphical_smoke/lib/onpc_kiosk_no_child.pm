package onpc_kiosk_no_child;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();

sub run {
    onpc_progress::operation('Qualifying the empty child set in the request station');
    my ($exchange) = @_;
    die 'kiosk-no-child:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'kiosk-no-child', review => 0);
    onpc_gdm::reattach_functional();
    my $wrong = $journey->seen('wrong-entry');
    $journey->consume_observation('wrong-entry', $wrong);
    onpc_gdm::enter_station($journey, '');
    for my $stage ('empty-form', 'empty-rechecked') {
        my $result = $journey->seen($stage);
        $journey->consume_observation($stage, $result);
    }
    $journey->finish();
}

1;
