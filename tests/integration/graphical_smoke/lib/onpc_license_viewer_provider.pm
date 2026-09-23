package onpc_license_viewer_provider;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();
use onpc_about ();
use onpc_window ();

sub run {
    onpc_progress::operation('Qualifying the installed license viewer');
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
    for my $kind ('unrelated', 'empty') {
        $journey->seen('license-' . $kind . '-launched');
        my $ready = $journey->seen('license-' . $kind . '-ready');
        onpc_window::close($journey, 'license-' . $kind . '-fixture', $ready);
    }
    my $rechecked = $journey->seen('about-rechecked');
    onpc_about::open_license($journey, $rechecked, 'about-rechecked');
    $journey->seen('license-ambiguous-launched');
    my $ambiguous = $journey->seen('license-ambiguous-ready');
    onpc_window::close($journey, 'license-ambiguous-fixture', $ambiguous);
    my $qualified = $journey->seen('license-provider-refusals');
    my $returned = onpc_window::close($journey, 'license-qualified', $qualified);
    my $footer = onpc_about::read_footer($journey, $returned, 'semantic-reveal');
    onpc_window::close($journey, 'about', $footer);
    $journey->finish();
}

1;
