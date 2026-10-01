package onpc_kiosk_cancel;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_request_flow ();
use onpc_journey ();

sub run {
    onpc_progress::operation('Preparing a kiosk request and taking its declared exit');
    my ($exchange, $exit, $declared, $challenges) = @_;
    $exit //= 'cancel';
    die 'kiosk-cancel:arguments' unless (@_ == 1 || @_ == 4 && $exit eq 'approved')
        && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $exit eq 'approved' ? 'kiosk-approval' : 'kiosk-cancel', review => 0);
    if ($exit eq 'approved') {
        $journey->declare_invocations($declared);
        $journey->declare_challenges($challenges);
    }
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    onpc_request_flow::daily_station_entry($journey);
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
                               'fixture-child', 'fixture-parent', 75, 1);
    if ($exit eq 'approved') {
        onpc_request_flow::approve($journey, 'fixture-child', 'fixture-parent', 75, 1, 'immediate');
        onpc_gdm::sign_in_challenge($journey, 'child-login',
            'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
        $journey->consume_observation('countdown', $journey->seen('countdown'));
    } else {
        for my $stage ('cancel-action', 'cancel-returned') {
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    }
    $journey->finish();
}
1;
