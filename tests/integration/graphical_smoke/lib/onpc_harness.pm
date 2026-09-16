package onpc_harness;
use strict;
use warnings;
use onpc_progress ();
use testapi ();

# HAR01: select an existing console, never create or reconnect it. The initial
# runner selection is the only binding which permits an unselected console.
sub select_console {
    onpc_progress::operation('Selecting the test console');
    my ($from, $to) = @_;
    die 'harness:console-binding' unless @_ == 2 && defined($from) && defined($to)
        && (($from eq 'initial' && $to eq 'sut')
            || ($from eq 'sut' && $to eq 'onpc-serial')
            || ($from eq 'onpc-serial' && $to eq 'sut'));
    my $current = testapi::current_console();
    die 'harness:console-source' unless $from eq 'initial'
        ? (!defined($current) || $current eq '' || $current eq 'sut')
        : defined($current) && $current eq $from;
    testapi::select_console($to);
    die 'harness:console-result' unless testapi::current_console() eq $to;
}

1;
