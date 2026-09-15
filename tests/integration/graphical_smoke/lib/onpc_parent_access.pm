package onpc_parent_access;
use strict;
use warnings;
use testapi ();
use onpc_journey ();
use onpc_parent ();

sub run {
    my ($exchange, $review) = @_;
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-access', review => $review,
    );
    onpc_parent::login_standard($journey);
    onpc_parent::open_app_grid($journey);
    testapi::type_string('Oh No! Parent Control');
    testapi::wait_still_screen(1, 10);
    # The administrator-only launcher is absent for this account. The reviewed
    # search screen includes the full query, the web-only suggestion and empty
    # application results. Enter would launch that unrelated web suggestion.
    $journey->observe('onpc-parent-standard-unavailable', 30);
    $journey->seen('unavailable');
    $journey->finish();
}

1;
