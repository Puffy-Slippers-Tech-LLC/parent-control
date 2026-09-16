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
    onpc_parent::login_functional($journey);
    testapi::send_key('super-a');
    testapi::type_string('Oh No! Parent Control');
    $journey->seen('app-grid');
    testapi::send_key('ret');
    $journey->navigate_choice($journey->seen('child-picker-opened'));
    $journey->seen('child-choice-highlighted');
    testapi::send_key('ret');
    $journey->seen('parent-selected');
    $journey->seen('existing-apps');
    $journey->seen('fixture-requested');
    $journey->navigate_choice($journey->seen('new-child-visible'));
    $journey->seen('new-child-choice-highlighted');
    testapi::send_key('ret');
    $journey->seen('new-child-selected');
    $journey->seen('new-child-apps');
    $journey->seen('new-child-screen');
    $journey->navigate_choice($journey->seen('existing-child-picker-opened'));
    $journey->seen('existing-child-choice-highlighted');
    testapi::send_key('ret');
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
