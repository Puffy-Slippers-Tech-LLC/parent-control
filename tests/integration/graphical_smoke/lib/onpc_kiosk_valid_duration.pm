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
    my ($exchange, $invalid) = @_;
    die 'kiosk-valid:arguments' unless (@_ == 1 || @_ == 2 && $invalid eq 'invalid')
        && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $invalid ? 'request-duration' : 'kiosk-valid-duration', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('wrong-entry', 'valid-wrong-entry', ($invalid ? ('invalid-wrong-entry') : ()),
                   'limit-enabled', 'save-enabled',
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
                   'kiosk-valid-excluded-select', 'kiosk-valid-excluded-read') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    if ($invalid) {
        $journey->consume_observation('invalid-custom-open', $journey->seen('invalid-custom-open'));
        for my $binding ('empty', 'letters', 'negative', 'zero', 'below', 'over', 'comma') {
            onpc_text::replace_text($journey, "kiosk-invalid-$binding");
            for my $action ('ready', 'submit', 'read') {
                my $stage = "kiosk-invalid-$binding-$action";
                $journey->consume_observation($stage, $journey->seen($stage));
            }
        }
    }
    for my $stage ('kiosk-request-cancel', 'gdm-station-returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
