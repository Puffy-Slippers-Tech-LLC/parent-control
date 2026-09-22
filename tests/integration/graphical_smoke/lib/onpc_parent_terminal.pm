package onpc_parent_terminal;
use strict;
use warnings;
use onpc_progress ();
use onpc_window ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Checking Parent access by direct command');
    my ($exchange) = @_;
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-terminal', review => 0);
    my $desktop = onpc_parent::login_standard_functional($journey);
    my $denied = onpc_parent::launch($journey, $desktop, 'denied');
    onpc_window::close($journey, 'management-denied', $denied);
    $journey->finish();
}

1;
