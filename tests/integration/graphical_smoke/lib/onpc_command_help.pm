package onpc_command_help;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_documentation ();

sub run {
    onpc_progress::operation('Checking installed command documentation');
    my ($exchange) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'command-help', review => 0);
    onpc_parent::login_functional($journey);
    for my $binding (qw(parent-help station-help parent-manual station-manual)) {
        onpc_documentation::read($journey, $binding);
    }
    $journey->seen('complete');
    $journey->finish();
}

1;
