package onpc_kiosk_multiple;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_journey ();

sub run {
    onpc_progress::operation('Qualifying both children and both approving parents in the station');
    my ($exchange, $complete) = @_;
    die 'kiosk-multiple:arguments' unless (@_ == 1 || (@_ == 2 && $complete == 1)) && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'kiosk-multiple', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage (($complete ? () : ('wrong-entry', 'mate-wrong-entry')), 'limit-enabled', 'save-enabled') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    my $other = onpc_parent::select_child($journey, 'returned',
        $journey->seen('existing-child-picker-opened'), 'existing-child-picker-opened',
        'existing-child-choice-highlighted', 'existing-returned');
    $journey->consume_observation('existing-returned', $other);
    for my $stage ('other-enabled', 'other-saved', 'switch-user', 'gdm-switched') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_gdm::enter_station($journey, '');
    if ($complete) {
        for my $stage ('child-open', 'child-closed', 'approver-open', 'approver-closed') {
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    }
    for my $stage ('first-child', 'first-parent', 'first-first-cancel',
                   'other-parent', 'first-other-cancel', 'other-child',
                   'other-other-cancel', 'other-first-parent', 'other-first-cancel',
                   ($complete ? ('preserved') : ()), 'cancel', 'returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
