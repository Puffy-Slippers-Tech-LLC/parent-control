package onpc_parent_about;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();
use onpc_about ();

sub run {
    onpc_progress::operation('Checking About and license information');
    my ($exchange, $review) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'parent', review => $review);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    my $about = onpc_about::open_about($journey, $selected);
    my $license = onpc_about::open_license($journey, $about);
    onpc_about::return_to_parent($journey, $license, 'semantic-reveal');
    $journey->finish();
}

1;
