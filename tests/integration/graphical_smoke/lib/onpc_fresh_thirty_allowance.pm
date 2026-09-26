package onpc_fresh_thirty_allowance;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying fresh thirty-minute daily allowance setup');
    my ($exchange) = @_;
    die 'fresh-thirty-allowance:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'fresh-thirty-allowance', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 30, 1));
    for my $stage ('balance-reread', 'wrong-child', 'wrong-state', 'wrong-window', 'final-settings') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
