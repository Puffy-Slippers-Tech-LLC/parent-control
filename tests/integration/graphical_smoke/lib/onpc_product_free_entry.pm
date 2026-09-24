package onpc_product_free_entry;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying product-free administrator entry and package staging');
    my ($exchange) = @_;
    die 'product-free-entry:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'product-free-entry', review => 0);
    $journey->seen('wrong-entry');
    onpc_parent::login_functional($journey);
    $journey->seen('command-context');
    $journey->finish();
}

1;
