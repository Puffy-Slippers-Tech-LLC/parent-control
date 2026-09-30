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

# Complete E2E-042/parent-links composition, independent of qualification.
sub run_links {
    onpc_progress::operation('Reading Parent Help and About information');
    my ($exchange) = @_;
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-links', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    my $help = onpc_about::read_help($journey, $selected);
    my $about = onpc_about::open_from_help($journey, $help);
    my $links = onpc_about::check_link($journey, $about, 'information');
    onpc_about::return_to_parent($journey, $links, 'semantic-reveal');
    $journey->finish();
}

sub run_interval {
    onpc_progress::operation('Qualifying a guarded real interval between About reads');
    my ($exchange) = @_;
    die 'real-interval:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'real-interval', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    onpc_about::open_about($journey, $selected);
    $journey->seen('before');
    $journey->seen('after');
    $journey->finish();
}

1;
