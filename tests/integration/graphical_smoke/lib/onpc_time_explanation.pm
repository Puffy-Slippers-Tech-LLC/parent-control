package onpc_time_explanation;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying saved time controls and non-collapsing balance reads');
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
                   'time-explanation-read', 'time-explanation-reread',
                   'time-explanation-reach-wrong-child', 'time-explanation-config-wrong-child',
                   'time-explanation-config-wrong-state',
                   'time-explanation-collapse-again',
                   'time-explanation-reach-read', 'time-explanation-reach-reread',
                   'time-explanation-off-read', 'time-explanation-positive-read',
                   'time-explanation-zero-read', 'time-explanation-zero-reread') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
