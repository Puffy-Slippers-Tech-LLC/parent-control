package onpc_license_viewer_provider;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();
use onpc_about ();

sub run {
    onpc_progress::operation('Qualifying license link clickability');
    my ($exchange) = @_;
    die 'license-provider:binding' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'license-provider', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    my $wrong = onpc_journey->new(
        exchange => $exchange, prefix => 'license-provider-wrong', review => 0);
    $wrong->{last_observation} = {stage => 'parent-selected', reply => $selected};
    my $accepted = eval { onpc_about::open_license($wrong, $selected); 1 };
    die 'license-provider:wrong-entry-accepted' if $accepted;
    die 'license-provider:wrong-entry-refusal' unless $@ =~ /journey:stale-observation/;
    my $about = onpc_about::open_about($journey, $selected);
    onpc_about::open_license($journey, $about);
    my $qualified = $journey->seen('license-provider-refusals');
    onpc_about::return_to_parent(
        $journey, $qualified, 'semantic-reveal', 'license-provider-refusals');
    $journey->finish();
}

1;
