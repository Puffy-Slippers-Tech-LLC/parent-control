package onpc_zero_total;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Checking zero balances keep Revoke disabled with limits on and off');
    my ($exchange) = @_;
    die 'zero-total:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'zero-total', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 0, 1));
    for my $stage ('revoke-on', 'limit-disabled', 'save-disabled', 'revoke-off', 'retained-allowance') {
        $journey->seen($stage);
    }
    $journey->finish();
}
1;
