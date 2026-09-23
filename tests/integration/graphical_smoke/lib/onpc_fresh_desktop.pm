package onpc_fresh_desktop;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying a fresh fixture desktop');
    my ($exchange, $role, $keyring) = @_;
    die 'fresh-desktop:binding' unless (@_ == 2 || @_ == 3) && ref($exchange) eq 'CODE'
        && ($role eq 'parent' || $role eq 'standard')
        && (!$keyring || $role eq 'standard');
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => ($keyring ? 'keyring-' : 'fresh-') . $role,
        review => 0);
    $role eq 'parent' ? onpc_parent::login_functional($journey)
        : onpc_parent::login_standard_functional($journey);
    $journey->seen('keyring-cancelled-desktop') if $keyring;
    $journey->finish();
}

1;
