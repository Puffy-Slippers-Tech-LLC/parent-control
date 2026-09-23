package onpc_kiosk_entry;
use strict;
use warnings;
use testapi ();
use onpc_gdm ();
use onpc_journey ();
use onpc_progress ();

sub run {
    onpc_progress::operation('Entering and reading the request station');
    my ($exchange) = @_;
    die 'kiosk-entry:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'kiosk-entry', review => 0);
    onpc_gdm::reattach_functional();

    onpc_gdm::enter_station($journey, '');
    $journey->seen('request-form');
    $journey->finish();
}

1;
