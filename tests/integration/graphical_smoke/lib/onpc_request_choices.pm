package onpc_request_choices;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying disabled child request station availability');
    my ($exchange) = @_;
    die 'request-choices:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'request-choices', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('wrong-entry', 'limit-enabled', 'save-enabled',
                   'limit-disabled', 'save-disabled', 'switch-user', 'gdm-switched') {
        my $result = $journey->seen($stage);
        $journey->consume_observation($stage, $result);
    }
    onpc_gdm::enter_station($journey, '');
    for my $stage ('request-form', 'wrong-choices', 'child-selected', 'availability-read') {
        my $result = $journey->seen($stage);
        $journey->consume_observation($stage, $result);
    }
    $journey->finish();
}

1;
