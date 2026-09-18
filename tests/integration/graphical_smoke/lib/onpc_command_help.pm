package onpc_command_help;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_terminal ();

my %commands = (
    'parent-help' => '/usr/bin/oh-no-parent-control-parent --help',
    'station-help' => '/usr/bin/oh-no-parent-control --help',
    'parent-manual' => 'man oh-no-parent-control-parent',
    'station-manual' => 'man oh-no-parent-control',
);

# FILE02 leaf: finite nonsecret bindings, fresh single-use focused shell proof.
sub submit {
    my ($journey, $binding, $entry) = @_;
    die 'help:binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && defined($binding) && exists($commands{$binding});
    $journey->consume_observation($binding . '-entry', $entry);
    onpc_progress::operation('Submitting installed command documentation: ' . $binding);
    testapi::type_string($commands{$binding});
    testapi::send_key('ret');
}

# INFO02: independently observed Terminal, no command interface or input replay.
sub read_installed {
    my ($journey, $binding, $entry) = @_;
    submit($journey, $binding, $entry);
    my $content = $journey->seen($binding . '-content');
    $journey->consume_observation($binding . '-content', $content);
    testapi::send_key('q') if $binding =~ /-manual$/;
    return $journey->seen($binding . '-returned');
}

sub run {
    my ($exchange) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'command-help', review => 0);
    my $desktop = onpc_parent::login_functional($journey);
    my $opened = onpc_terminal::open($journey, $desktop);
    my $focused = onpc_terminal::focus($journey, $opened, 'opened');
    $journey->consume_observation('terminal-opened-focused', $focused);
    for my $binding (qw(parent-help station-help parent-manual station-manual)) {
        # After the first command, qualify independently opened terminals.
        testapi::send_key('ctrl-alt-t') unless $binding eq 'parent-help';
        my $entry = $journey->seen($binding . '-entry');
        my $returned = read_installed($journey, $binding, $entry);
        $journey->consume_observation($binding . '-returned', $returned);
        testapi::send_key('alt-f4');
        $journey->seen($binding . '-closed');
    }
    $journey->seen('complete');
    $journey->finish();
}

1;
