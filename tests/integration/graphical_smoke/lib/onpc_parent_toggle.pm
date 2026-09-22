package onpc_parent_toggle;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

sub _next_observation {
    my ($journey, $prior_stage, $prior, $stage) = @_;
    die 'toggle:stage-binding' unless @_ == 4 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation($prior_stage, $prior);
    return $journey->seen($stage);
}

sub run {
    onpc_progress::operation('Qualifying the Parent screen time limit switch and saved state');
    my ($exchange) = @_;
    die 'toggle:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-toggle', review => 0);
    onpc_gdm::reattach_functional();
    my $observed = $journey->seen('parent-window');
    $journey->consume_observation('parent-window', $observed);
    $observed = onpc_parent::select_child(
        $journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    for my $stage ('wrong-control-refused', 'wrong-child-refused', 'limit-enabled',
                   'save-enabled', 'save-reopened', 'limit-disabled', 'save-disabled',
                   'limit-current', 'hidden-control-refused', 'disabled-settings') {
        my $prior = $stage eq 'wrong-control-refused' ? 'parent-selected'
            : $stage eq 'wrong-child-refused' ? 'wrong-control-refused'
            : $stage eq 'limit-enabled' ? 'wrong-child-refused'
            : $stage eq 'save-enabled' ? 'limit-enabled'
            : $stage eq 'save-reopened' ? 'save-enabled'
            : $stage eq 'limit-disabled' ? 'save-reopened'
            : $stage eq 'save-disabled' ? 'limit-disabled'
            : $stage eq 'limit-current' ? 'save-disabled'
            : $stage eq 'hidden-control-refused' ? 'limit-current'
            : 'hidden-control-refused';
        $observed = _next_observation($journey, $prior, $observed, $stage);
    }
    $journey->consume_observation('disabled-settings', $observed);
    $journey->finish();
}

1;
