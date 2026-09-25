package onpc_allowance_boundaries;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_journey ();
use onpc_allowance ();
use onpc_text ();

sub seen {
    onpc_progress::operation('Observing the declared allowance result');
    my ($journey, $stage) = @_;
    $journey->consume_observation($stage, $journey->seen($stage));
}

sub reload_child {
    onpc_progress::operation('Reloading the selected child through the public selector');
    my ($journey, $prefix) = @_;
    for my $direction ('away', 'back') {
        seen($journey, "$prefix-$direction-$_") for ('open', 'focus');
        testapi::send_key('ret');
        seen($journey, "$prefix-$direction-selected");
    }
}

sub run {
    onpc_progress::operation('Qualifying daily allowance boundaries and rejection');
    my ($exchange) = @_;
    die 'allowance-boundaries:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => 'allowance-boundaries', review => 0);
    onpc_allowance::qualify($journey);
    for my $value (0, 1, 15, 1439) {
        my $prefix = "boundary-$value";
        seen($journey, "$prefix-open");
        onpc_text::replace_text($journey, "daily-$value", "$prefix-text");
        seen($journey, "$prefix-saved");
        reload_child($journey, $prefix);
        seen($journey, "$prefix-reopen");
    }
    for my $binding ('empty', 'letters', 'negative', 'fraction', 'maximum', 'over') {
        my $prefix = "invalid-$binding";
        seen($journey, "$prefix-$_") for ('baseline', 'baseline-read', 'open');
        onpc_text::replace_text($journey, "daily-invalid-$binding", "$prefix-text");
        seen($journey, "$prefix-rejected");
        reload_child($journey, $prefix);
        seen($journey, "$prefix-unchanged");
        seen($journey, "$prefix-reopen");
    }
    $journey->finish();
}
1;
