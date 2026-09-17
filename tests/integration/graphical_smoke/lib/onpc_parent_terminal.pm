package onpc_parent_terminal;
use strict;
use warnings;
use testapi ();
use onpc_journey ();
use onpc_parent ();
use onpc_terminal ();

sub run {
    my ($exchange) = @_;
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-terminal', review => 0);
    my $desktop = onpc_parent::login_standard_functional($journey);
    my $opened = onpc_terminal::open($journey, $desktop);
    my $first = onpc_terminal::focus($journey, $opened, 'opened');
    $journey->consume_observation('terminal-opened-focused', $first);
    testapi::send_key('alt-f4');
    $journey->seen('terminal-first-closed');
    # Independent public entry: no dependency on FILE01's returned object.
    testapi::send_key('ctrl-alt-t');
    my $input = $journey->seen('terminal-input');
    my $focused = onpc_terminal::focus($journey, $input, 'input');
    onpc_terminal::submit_parent($journey, $focused);
    my $denied = onpc_terminal::observe_denial($journey);
    $journey->consume_observation('management-denied', $denied);
    testapi::send_key('alt-f4');
    my $returned = $journey->seen('denial-closed');
    $journey->consume_observation('denial-closed', $returned);
    testapi::send_key('alt-f4');
    $journey->seen('terminal-closed');
    $journey->finish();
}

1;
