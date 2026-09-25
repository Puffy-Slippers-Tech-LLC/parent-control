package onpc_set_allowance;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying fresh and same-user daily allowance setup');
    my ($exchange) = @_;
    die 'set-allowance:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'set-allowance', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 0, 1));
    for my $stage ('zero-reread', 'wrong-child', 'wrong-window', 'close-ready') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    testapi::send_key('alt-f4');
    $journey->seen('closed');
    $journey->consume_observation('same-allowance-configured', onpc_parent::set_allowance(
        $journey, 'desktop', 'parent', 'same-user', 'new', 'child', 1, 15, 1));
    $journey->seen('positive-reread');
    $journey->seen('final-settings');
    $journey->finish();
}
1;
