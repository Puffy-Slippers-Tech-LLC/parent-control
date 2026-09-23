package onpc_shell_search;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();
use testapi ();

sub run {
    onpc_progress::operation('Reading the Parent Shell search result');
    my ($exchange) = @_;
    die 'shell-search:binding' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'shell-search-results', review => 0);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_parent::sign_in($journey, 'parent', 'success');
    my $field = onpc_parent::open_search($journey, $desktop, 'overview');
    my $focused = onpc_parent::focus_search($journey, $field, 'overview');
    $journey->consume_observation('search-focused', $focused);
    testapi::type_string('O', max_interval => 20);
    $journey->seen('search-started');
    testapi::type_string('h No! Parent Control', max_interval => 20);
    $journey->seen('search-entered');
    $journey->seen('wrong-result-refused');
    $journey->seen('result');
    testapi::send_key('esc');
    $journey->seen('search-cleared');
    # Escape from Super-A search clears the query, then leaves the app grid
    # before closing Overview. Toggle the observed Overview closed directly.
    testapi::send_key('super');
    $journey->seen('dismissed');
    $journey->finish();
}

1;
