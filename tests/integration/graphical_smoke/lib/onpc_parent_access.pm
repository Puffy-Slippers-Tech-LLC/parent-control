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
    onpc_parent::login_standard_functional($journey);
    testapi::send_key('super-a');
    $journey->seen('system-prompt');
    $journey->click_target($journey->seen('app-grid'));
    $journey->seen('search-focused');
    # Use GNOME's normal type-to-search route. Independently observe its first
    # character before continuing the query; no character is repaired/replayed.
    testapi::type_string('O', max_interval => 20);
    $journey->seen('search-started');
    testapi::type_string('h No! Parent Control', max_interval => 20);
    # Independently observe the actual query and web-only result through public
    # accessibility. Enter would launch that unrelated web suggestion.
    $journey->seen('unavailable');
    $journey->finish();
}

1;
