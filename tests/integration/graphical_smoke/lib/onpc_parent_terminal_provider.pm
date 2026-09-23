package onpc_parent_terminal_provider;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_window ();

sub run {
    onpc_progress::operation('Qualifying direct Parent-command denial');
    my ($exchange) = @_;
    die 'parent-terminal-provider:binding' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-terminal-provider', review => 0);
    onpc_parent::login_standard_functional($journey);
    my $wrong = $journey->seen('wrong-entry');
    my $accepted = eval { onpc_parent::launch($journey, $wrong, 'denied'); 1 };
    die 'parent-terminal-provider:wrong-entry-accepted' if $accepted;
    die 'parent-terminal-provider:wrong-refusal' unless $@ =~ /journey:stale-observation/;

    my $entry = onpc_journey->new(
        exchange => sub { $exchange->('entry-' . $_[0], $_[1]) },
        prefix => 'parent-terminal-provider-entry', review => 0);
    my $desktop = $entry->seen('desktop');
    my $denied = onpc_parent::launch($entry, $desktop, 'denied');
    onpc_window::close($entry, 'management-denied', $denied);
    $journey->finish();
}

1;
