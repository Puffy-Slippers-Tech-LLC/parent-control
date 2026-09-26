package onpc_kiosk_valid_duration;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();

sub run {
    onpc_progress::operation('Qualifying valid kiosk durations, estimates and soft app choices');
    my ($exchange) = @_;
    die 'kiosk-valid:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'kiosk-valid-duration', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('wrong-entry', 'valid-wrong-entry', 'limit-enabled', 'save-enabled',
                   'allowance-15-select', 'allowance-15-read',
                   'time-explanation-read', 'switch-user', 'gdm-switched') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_gdm::enter_station($journey, '');
    for my $stage ('request-form', 'wrong-choices', 'child-selected',
                   'approver-selected', 'selections-read',
                   'kiosk-valid-preset-select', 'kiosk-valid-preset-read', 'kiosk-valid-custom-open') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_text::replace_text($journey, 'kiosk-fraction');
    for my $stage ('kiosk-valid-fraction-read', 'kiosk-valid-rest-select', 'kiosk-valid-rest-read',
                   'kiosk-valid-soft-select', 'kiosk-valid-soft-read',
                   'kiosk-valid-excluded-select', 'kiosk-valid-excluded-read',
                   'kiosk-request-cancel', 'gdm-station-returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
