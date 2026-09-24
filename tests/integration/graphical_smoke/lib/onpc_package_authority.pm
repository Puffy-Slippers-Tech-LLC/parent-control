package onpc_package_authority;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying administrator package authority and completion');
    my ($exchange) = @_;
    die 'package-authority:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'package-authority', review => 0);
    $journey->seen('wrong-entry');
    onpc_parent::login_functional($journey);
    $journey->seen('command-context');
    $journey->seen('package-submitted');
    $journey->seen('package-result');
    $journey->finish();
}

1;
