package onpc_parent_discovery;
use strict;
use warnings;
use testapi ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();

sub run {
    my ($exchange) = @_;
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-discovery', review => 0,
    );
    onpc_gdm::reattach_functional();
    onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'existing');
    $journey->seen('existing-apps');
    $journey->seen('fixture-requested');
    onpc_parent::select_child($journey, 'new', $journey->seen('new-child-visible'),
        'new-child-visible', 'new-child-choice-highlighted', 'new-child-selected');
    $journey->seen('new-child-apps');
    $journey->seen('new-child-screen');
    onpc_parent::select_child($journey, 'returned', $journey->seen('existing-child-picker-opened'),
        'existing-child-picker-opened', 'existing-child-choice-highlighted', 'existing-returned');
    $journey->finish();
}

sub run_none {
    my ($exchange) = @_;
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-empty', review => 0,
    );
    onpc_gdm::reattach_functional();
    my $desktop = onpc_parent::sign_in($journey, 'parent', 'other-parent', 'success');
    onpc_parent::search_whole_query($journey, $desktop, 'Oh No! Parent Control', 'app-grid');
    # Pause before launching Parent so the fixed fixture state is complete and
    # durably recorded before the customer-visible result can be produced.
    my $prepared = $journey->seen('fixture-requested');
    $journey->consume_observation('fixture-requested', $prepared);
    testapi::send_key('ret');
    $journey->seen('empty');
    $journey->finish();
}

1;
