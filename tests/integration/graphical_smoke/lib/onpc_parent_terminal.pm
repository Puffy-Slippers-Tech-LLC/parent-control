package onpc_parent_terminal;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Checking Parent access by direct command');
    my ($exchange) = @_;
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-terminal', review => 0);
    my $desktop = onpc_parent::login_standard_functional($journey);
    my $denied = onpc_parent::launch($journey, $desktop, 'denied');
    $journey->consume_observation('management-denied', $denied);
    testapi::send_key('alt-f4');
    $journey->seen('denial-closed');
    $journey->finish();
}

1;
