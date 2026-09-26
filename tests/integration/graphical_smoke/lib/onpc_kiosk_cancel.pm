package onpc_kiosk_cancel;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_request_flow ();
use onpc_journey ();

sub run {
    onpc_progress::operation('Preparing a kiosk request and cancelling to sign-in');
    my ($exchange) = @_;
    die 'kiosk-cancel:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'kiosk-cancel', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('limit-enabled', 'save-enabled', 'allowance-15-select',
                   'allowance-15-read', 'time-explanation-read', 'switch-user', 'gdm-switched') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_gdm::enter_station($journey, '');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
                               'fixture-child', 'fixture-parent', 75, 1);
    for my $stage ('cancel-action', 'cancel-returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
