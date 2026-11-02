package onpc_parent_access;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_window ();

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
    # Independently observe the actual query and Parent launcher/window absence
    # through public accessibility. Do not activate unrelated search results.
    $journey->seen('unavailable');
    # The fixed command's shared launcher leaves Overview and independently
    # observes its closure before submitting as this same standard account.
    my $direct = $journey->scope('direct');
    my $returned = $direct->seen('desktop');
    my $denied = onpc_parent::launch($direct, $returned, 'denied');
    onpc_window::close($direct, 'management-denied', $denied);
    $journey->finish();
}

1;
