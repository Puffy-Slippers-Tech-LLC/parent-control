package onpc_kiosk_eligible_choices;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying eligible request station account choices');
    my ($exchange, $engineering) = @_;
    die 'kiosk-choices:arguments' unless (@_ == 1 || @_ == 2 && defined($engineering)
        && ($engineering == 1 || $engineering == 2))
        && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'kiosk-eligible-choices', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('wrong-entry', 'limit-enabled', 'save-enabled',
                   'switch-user', 'gdm-switched') {
        my $result = $journey->seen($stage);
        $journey->consume_observation($stage, $result);
    }
    onpc_gdm::enter_station($journey, '');
    for my $stage ('request-form', 'wrong-choices', 'child-selected',
                   'approver-selected', 'selections-read') {
        my $result = $journey->seen($stage);
        $journey->consume_observation($stage, $result);
    }
    if ($engineering && $engineering == 1) {
        for my $stage ('kiosk-diagnostic-error', 'kiosk-diagnostic-report', 'kiosk-diagnostic-editor',
                      'kiosk-diagnostic-privacy') {
            my $result = $journey->seen($stage);
            $journey->consume_observation($stage, $result);
        }
    }
    if ($engineering && $engineering == 2) {
        for my $stage ('kiosk-reminder-preview', 'kiosk-reminder-preview-cancel') {
            my $result = $journey->seen($stage);
            $journey->consume_observation($stage, $result);
        }
    }
    $journey->finish();
}

1;
