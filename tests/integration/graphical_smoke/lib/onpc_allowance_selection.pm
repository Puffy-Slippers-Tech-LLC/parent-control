package onpc_allowance_selection;
use strict;
use warnings;
use testapi ();
use onpc_progress ();

# PARENT06: identical ordered observations/input for host UI and installed E2E.
# Values and preservation assertions belong to the caller, never to VM metadata.
sub select {
    onpc_progress::operation('Clicking, typing and confirming the daily allowance');
    my ($journey, $prefix, $values, $response) = @_;
    die 'allowance:keyboard-binding' unless @_ == 4 && ref($journey) eq 'onpc_journey'
        && defined($prefix) && $prefix =~ /\A[a-z][a-z0-9-]*\z/
        && ref($values) eq 'ARRAY' && @$values == 1 && $response eq 'confirm';
    my $value = $values->[0];
    die 'allowance:keyboard-value' unless defined($value)
        && ($value eq 'custom' || $value =~ /\A(?:0|15|30|45)\z/
            || $value =~ /\A[1-9][0-9]{1,3}\z/
                && $value >= 60 && $value <= 1410 && $value % 30 == 0);
    # The ID-owned shared block performs click, typing and Enter together;
    # only the saved value is observed after input, never popup/highlight state.
    $journey->consume_observation("$prefix-ready", $journey->seen("$prefix-ready"));
    return $journey->consume_observation("$prefix-confirm", $journey->seen("$prefix-confirm"));
}
1;
