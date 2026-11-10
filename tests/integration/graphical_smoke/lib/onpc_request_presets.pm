package onpc_request_presets;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_journey ();
use onpc_request_flow ();

sub run {
    onpc_progress::operation('Keeping a child request unchanged through saved preset edits and return');
    my ($exchange, $declared, $challenges) = @_;
    die 'request-presets:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'request-presets', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 0, 1));
    $journey->seen($_) for qw(policy-before parent-logout parent-logged-out);
    onpc_gdm::enter_station($journey, '');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
        'fixture-child', 'fixture-parent', 75, 1, 'compact');
    for my $stage (qw(presets-shipped preset-added preset-reopened preset-selected preset-deleted
            deleted-custom hours-selected hours-read presets-restored minutes-restored minutes-read
            cancel returned)) {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_gdm::enter_station($journey, 'cancel-');
    $journey->seen($_) for qw(reentered-minutes reentered-presets final-cancel final-returned);
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'return-parent',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
    $journey->consume_observation('return-desktop', $desktop);
    onpc_parent::named_management($journey, 'return', 'child');
    $journey->seen($_) for qw(policy-after final-parent-logout final-greeter);
    $journey->finish();
}
1;
