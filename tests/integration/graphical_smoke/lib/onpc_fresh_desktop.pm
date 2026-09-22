package onpc_fresh_desktop;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();

sub run {
    my ($exchange, $role) = @_;
    die 'fresh-desktop:binding' unless @_ == 2 && ref($exchange) eq 'CODE'
        && ($role eq 'parent' || $role eq 'standard');
    onpc_progress::operation('Qualifying a fresh fixture desktop');
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'fresh-' . $role, review => 0);
    $role eq 'parent' ? onpc_parent::login_functional($journey)
        : onpc_parent::login_standard_functional($journey);
    $journey->finish();
}

1;
