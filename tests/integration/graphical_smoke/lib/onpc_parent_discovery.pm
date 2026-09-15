package onpc_parent_discovery;
use strict;
use warnings;
use testapi ();
use onpc_journey ();
use onpc_parent ();
use onpc_pointer ();

sub run {
    my ($exchange) = @_;
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-discovery', review => 0,
    );
    onpc_parent::login($journey);
    onpc_parent::launch_from_app_grid($journey);
    onpc_parent::select_existing_child($journey);
    $journey->observe('onpc-parent-child-selected', 30);
    $journey->seen('fixture-requested');
    onpc_pointer::click('onpc-parent-child-picker', 30);
    $journey->observe('onpc-parent-new-child-choice', 45);
    $journey->seen('new-child-visible');
    onpc_pointer::click('onpc-parent-new-child-choice', 30);
    $journey->observe('onpc-parent-new-child-selected', 60);
    $journey->seen('new-child-selected');
    onpc_pointer::click('onpc-parent-child-picker', 30);
    onpc_pointer::click('onpc-parent-child-choice', 30);
    $journey->observe('onpc-parent-child-selected', 60);
    $journey->seen('existing-returned');
    $journey->finish();
}

sub run_none {
    my ($exchange) = @_;
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-empty', review => 0,
    );
    onpc_parent::login($journey);
    testapi::send_key('super-a');
    testapi::assert_screen('onpc-parent-app-grid', 30);
    $journey->seen('app-grid');
    # Pause before launching Parent so the fixed fixture state is complete and
    # durably recorded before the customer-visible result can be produced.
    $journey->observe('onpc-parent-app-grid', 30);
    $journey->seen('fixture-requested');
    testapi::type_string('Oh No! Parent Control');
    testapi::wait_still_screen(1, 10);
    testapi::send_key('ret');
    $journey->observe('onpc-parent-empty', 60);
    $journey->seen('empty');
    $journey->finish();
}

1;
