package onpc_shell_search_standard;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying standard-account Parent search unavailability');
    my ($exchange) = @_;
    die 'shell-search:binding' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'shell-search', review => 0);
    my $desktop = onpc_parent::login_standard_functional($journey);
    # A desktop is not a search-field proof. Refuse without focusing or typing,
    # then enter the shared search operations with a separately observed desktop.
    my $accepted = eval {
        onpc_parent::focus_search($journey, $desktop, 'overview'); 1;
    };
    die 'shell-search:wrong-entry-accepted' if $accepted;
    die 'shell-search:wrong-refusal' unless $@ =~ /journey:stale-observation/;
    my $entry = onpc_journey->new(
        exchange => sub { $exchange->('entry-' . $_[0], $_[1]) },
        prefix => 'shell-search-entry', review => 0);
    my $field = onpc_parent::open_search($entry, $entry->seen('desktop'), 'overview');
    my $focused = onpc_parent::focus_search($entry, $field, 'overview');
    onpc_parent::enter_search_query($entry, $focused, 'Oh No! Parent Control');
    $entry->seen('unavailable');
    # Enter would activate the web suggestion. The owned envelope shuts down.
    $journey->finish();
}

1;
