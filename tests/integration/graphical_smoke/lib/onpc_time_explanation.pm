package onpc_time_explanation;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying read-only expanded remaining-time balances');
    my ($exchange) = @_;
    die 'time-explanation:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'time-explanation', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('parent-toggle-enabled', 'parent-save-enabled',
                   'allowance-15-select', 'allowance-15-read',
                   'time-explanation-collapse', 'time-explanation-collapsed',
                   'time-explanation-expand', 'time-explanation-wrong-child',
                   'time-explanation-read', 'time-explanation-reread') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
