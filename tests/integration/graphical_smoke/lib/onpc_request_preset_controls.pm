package onpc_request_preset_controls;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_journey ();
use onpc_request_flow ();

sub run {
    onpc_progress::operation('Saving Riley request presets and choosing custom hours');
    my ($exchange) = @_;
    die 'request-presets:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => 'request-preset-controls', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 0, 1));
    for my $stage ('switch-user', 'gdm-switched') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_gdm::enter_station($journey, '');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
        'fixture-child', 'fixture-parent', 75, 1, 'compact');
    for my $stage ('presets-shipped', 'preset-added', 'preset-reopened', 'preset-deleted',
                   'presets-restored', 'hours-selected', 'hours-read', 'minutes-restored',
                   'minutes-read', 'cancel', 'returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
