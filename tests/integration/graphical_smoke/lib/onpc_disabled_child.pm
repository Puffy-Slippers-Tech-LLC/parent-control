package onpc_disabled_child;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Checking disabled child request availability without enabling limits');
    my ($exchange) = @_;
    die 'disabled-child:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'disabled-child', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('save-disabled', 'switch-user', 'gdm-switched') {
        $journey->seen($stage);
    }
    onpc_gdm::enter_station($journey, '');
    $journey->seen('request-form');
    $journey->seen('child-choices-open');
    for my $stage ('child-choices-closed', 'child-selected', 'availability-read',
                   'cancel-action', 'cancel-returned') {
        $journey->seen($stage);
    }
    $journey->finish();
}

1;
