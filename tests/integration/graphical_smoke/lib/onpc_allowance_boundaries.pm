package onpc_allowance_boundaries;
use strict;
use warnings;
use JSON::PP ();
use testapi ();
use onpc_progress ();
use onpc_journey ();
use onpc_allowance ();
use onpc_allowance_selection ();
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
        select_child($journey, "$prefix-$direction");
    }
}

sub select_child {
    onpc_progress::operation('Selecting and independently reading the declared child');
    my ($journey, $prefix, $route) = @_;
    $route //= 'action';
    die 'allowance:selection-binding' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey'
        && $prefix =~ /\A[a-z][a-z0-9-]*\z/ && ($route eq 'action' || $route eq 'keyboard');
    if ($route eq 'keyboard') {
        my $ready = seen($journey, "$prefix-ready");
        die 'allowance:picker-focus' unless defined($ready->{observed})
            && $ready->{observed} eq "$prefix-ready"
            && JSON::PP::is_bool($ready->{ui_focused}) && $ready->{ui_focused};
        testapi::send_key('spc');
    }
    seen($journey, "$prefix-$_") for ('open', 'focus');
    testapi::send_key('ret');
    seen($journey, "$prefix-selected");
}

sub exercise {
    onpc_progress::operation('Checking accepted and rejected custom daily allowances');
    my ($journey, $profile) = @_;
    $profile //= 'full';
    die 'allowance-boundaries:journey' unless (@_ == 1 || @_ == 2) && ref($journey) eq 'onpc_journey'
        && ($profile eq 'full' || $profile eq 'installed');
    for my $value ($profile eq 'installed' ? (1) : (0, 1, 15, 1439)) {
        my $prefix = "boundary-$value";
        onpc_allowance_selection::select($journey, "$prefix-choice", ['custom'], 'confirm');
        seen($journey, "$prefix-open");
        onpc_text::replace_text($journey, "daily-$value", "$prefix-text");
        seen($journey, "$prefix-saved");
        reload_child($journey, $prefix);
        if ($value == 0 || $value == 15) {
            seen($journey, "$prefix-reloaded-preset-read");
            onpc_allowance_selection::select($journey, "$prefix-reopen-choice", ['custom'], 'confirm');
        }
        seen($journey, "$prefix-reopen");
    }
    for my $binding ($profile eq 'installed' ? ('over') : ('empty', 'letters', 'negative', 'fraction', 'maximum', 'over')) {
        my $prefix = "invalid-$binding";
        onpc_allowance_selection::select($journey, "$prefix-baseline", [15], 'confirm');
        seen($journey, "$prefix-baseline-read");
        onpc_allowance_selection::select($journey, "$prefix-choice", ['custom'], 'confirm');
        seen($journey, "$prefix-open");
        onpc_text::replace_text($journey, "daily-invalid-$binding", "$prefix-text");
        seen($journey, "$prefix-rejected");
        reload_child($journey, $prefix);
        seen($journey, "$prefix-unchanged");
        onpc_allowance_selection::select($journey, "$prefix-reopen-choice", ['custom'], 'confirm');
        seen($journey, "$prefix-reopen");
    }
}

sub custom_value {
    onpc_progress::operation('Entering and independently reading the declared daily allowance');
    my ($journey, $prefix, $minutes) = @_;
    die 'allowance:custom-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && defined($prefix) && $prefix =~ /\A[a-z][a-z0-9-]*\z/
        && defined($minutes) && $minutes =~ /\A(?:0|1|4|5|6|7|15|1439)\z/;
    $journey->seen("$prefix-open");
    onpc_text::replace_text($journey, "daily-$minutes", "$prefix-text");
    $journey->seen("$prefix-saved");
}

sub run {
    onpc_progress::operation('Qualifying daily allowance boundaries and rejection');
    my ($exchange) = @_;
    die 'allowance-boundaries:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => 'allowance-boundaries', review => 0);
    onpc_allowance::qualify($journey);
    exercise($journey);
    $journey->finish();
}
1;
