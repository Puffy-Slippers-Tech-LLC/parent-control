package onpc_parent_search_launch;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();
use onpc_window ();
use testapi ();

sub run {
    onpc_progress::operation('Qualifying Parent search launch and return');
    my ($exchange) = @_;
    die 'parent-search:binding' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-search-launch', review => 0);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_parent::sign_in($journey, 'parent', 'success');
    onpc_parent::open_from_app_grid($journey, $desktop);
    onpc_window::close($journey, 'parent', $journey->seen('close-ready'));

    # A new caller supplies a separate search entry. A desktop proof must
    # refuse before Enter; reacquire fresh entry after that refusal.
    my $repeat = onpc_journey->new(
        exchange => sub { $exchange->('repeat-' . $_[0], $_[1]) },
        prefix => 'parent-search-launch-repeat', review => 0);
    my $wrong = $repeat->seen('wrong-entry');
    my $accepted = eval {
        onpc_parent::launch_search_result($repeat, $wrong, 'management'); 1;
    };
    die 'parent-search:wrong-entry-accepted' if $accepted;
    die 'parent-search:wrong-refusal' unless $@ =~ /journey:stale-observation/;
    my $entry = $repeat->seen('desktop');
    my $result = onpc_parent::search_whole_query(
        $repeat, $entry, 'Oh No! Parent Control', 'app-grid');
    onpc_parent::launch_search_result($repeat, $result, 'management');
    onpc_window::close($repeat, 'parent', $repeat->seen('close-ready'));
    $journey->finish();
}

1;
