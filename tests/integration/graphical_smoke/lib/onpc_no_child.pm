package onpc_no_child;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();

sub run {
    onpc_progress::operation('Checking unavailable station requests with no child accounts');
    my ($exchange) = @_;
    die 'no-child:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'no-child', review => 0);
    onpc_gdm::reattach_functional();
    onpc_gdm::enter_station($journey, '');
    for my $stage ('empty-form', 'empty-rechecked', 'cancel-action', 'cancel-returned') {
        my $result = $journey->seen($stage);
        $journey->consume_observation($stage, $result);
    }
    $journey->finish();
}

1;
