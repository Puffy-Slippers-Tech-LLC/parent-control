package onpc_parent_access;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Checking Parent access from a standard account');
    my ($exchange, $review) = @_;
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-access', review => $review,
    );
    my $desktop = onpc_parent::login_standard_functional($journey);
    my $field = onpc_parent::open_search($journey, $desktop, 'overview');
    my $focused = onpc_parent::focus_search($journey, $field, 'overview');
    onpc_parent::enter_search_query($journey, $focused, 'Oh No! Parent Control');
    # Independently observe the actual query and web-only result through public
    # accessibility. Enter would launch that unrelated web suggestion.
    $journey->seen('unavailable');
    $journey->finish();
}

1;
