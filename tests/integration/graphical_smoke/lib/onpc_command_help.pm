package onpc_command_help;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
my %bindings = map { $_ => 1 } qw(parent-help station-help parent-manual station-manual);

sub run {
    onpc_progress::operation('Checking installed command documentation');
    my ($exchange) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'command-help', review => 0);
    onpc_parent::login_functional($journey);
    for my $binding (qw(parent-help station-help parent-manual station-manual)) {
        die 'help:binding' unless $bindings{$binding};
        $journey->seen($binding . '-content');
        $journey->seen($binding . '-desktop');
    }
    $journey->seen('complete');
    $journey->finish();
}

1;
