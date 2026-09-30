package onpc_license_viewer_provider;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();
use onpc_about ();

sub run {
    onpc_progress::operation('Qualifying Parent information link clickability');
    my ($exchange, $link) = @_;
    $link //= 'license';
    die 'license-provider:binding' unless (@_ == 1 || @_ == 2)
        && ref($exchange) eq 'CODE'
        && ($link eq 'license' || $link eq 'website' || $link eq 'privacy'
            || $link eq 'support' || $link eq 'information');
    my $prefix = $link eq 'license' ? 'license-provider' : 'parent-' . $link;
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => $prefix, review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    my $wrong = onpc_journey->new(
        exchange => $exchange, prefix => $prefix . '-wrong', review => 0);
    $wrong->{last_observation} = {stage => 'parent-selected', reply => $selected};
    my $accepted = eval { onpc_about::check_link($wrong, $selected, $link); 1 };
    die 'license-provider:wrong-entry-accepted' if $accepted;
    die 'license-provider:wrong-entry-refusal' unless $@ =~ /journey:stale-observation/;
    my $about = $link eq 'information'
        ? onpc_about::open_from_help($journey, onpc_about::read_help($journey, $selected))
        : onpc_about::open_about($journey, $selected);
    onpc_about::check_link($journey, $about, $link);
    my $qualified = $journey->seen('license-provider-refusals');
    onpc_about::return_to_parent(
        $journey, $qualified, 'semantic-reveal', 'license-provider-refusals');
    $journey->finish();
}

1;
