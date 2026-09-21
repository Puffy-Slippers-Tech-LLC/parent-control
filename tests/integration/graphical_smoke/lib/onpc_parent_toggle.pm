package onpc_parent_toggle;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_gdm ();
use onpc_journey ();

sub next_observation {
    my ($journey, $prior_stage, $prior, $stage) = @_;
    die 'toggle:stage-binding' unless @_ == 4 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation($prior_stage, $prior);
    return $journey->seen($stage);
}

sub run {
    onpc_progress::operation('Qualifying the Parent screen time limit switch');
    my ($exchange) = @_;
    die 'toggle:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-toggle', review => 0);
    onpc_gdm::reattach_functional();
    my $observed = $journey->seen('parent-window');
    for my $stage ('parent-selected', 'wrong-control-refused', 'limit-enabled',
                   'limit-disabled', 'limit-current', 'hidden-control-refused',
                   'disabled-settings') {
        my $prior = $stage eq 'parent-selected' ? 'parent-window'
            : $stage eq 'wrong-control-refused' ? 'parent-selected'
            : $stage eq 'limit-enabled' ? 'wrong-control-refused'
            : $stage eq 'limit-disabled' ? 'limit-enabled'
            : $stage eq 'limit-current' ? 'limit-disabled'
            : $stage eq 'hidden-control-refused' ? 'limit-current'
            : 'hidden-control-refused';
        $observed = next_observation($journey, $prior, $observed, $stage);
    }
    $journey->consume_observation('disabled-settings', $observed);
    $journey->finish();
}

1;
