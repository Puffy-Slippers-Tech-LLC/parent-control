package onpc_allowance_selection;
use strict;
use warnings;
use testapi ();
use onpc_progress ();

# PARENT06: identical ordered observations/input for host UI and installed E2E.
# Values and preservation assertions belong to the caller, never to VM metadata.
sub select {
    onpc_progress::operation('Selecting an allowance through keyboard typing');
    my ($journey, $prefix, $values, $response) = @_;
    die 'allowance:keyboard-binding' unless @_ == 4 && ref($journey) eq 'onpc_journey'
        && defined($prefix) && $prefix =~ /\A[a-z][a-z0-9-]*\z/
        && ref($values) eq 'ARRAY' && @$values && @$values <= 4
        && ($response eq 'confirm' || $response eq 'cancel');
    for my $value (@$values) {
        die 'allowance:keyboard-value' unless defined($value)
            && ($value eq 'custom' || $value =~ /\A(?:0|15|30|45)\z/
                || $value =~ /\A[1-9][0-9]{1,3}\z/
                    && $value >= 60 && $value <= 1410 && $value % 30 == 0);
    }
    $journey->consume_observation("$prefix-ready", $journey->seen("$prefix-ready"));
    testapi::send_key('spc');
    $journey->consume_observation("$prefix-opened", $journey->seen("$prefix-opened"));
    for my $index (0 .. $#$values) {
        my $value = $values->[$index];
        my $text = $value eq 'custom' ? 'c'
            : $value >= 60 && $value % 60 == 0 ? ($value / 60) . 'h' : $value . 'm';
        testapi::type_string($text, max_interval => 20);
        my $stage = "$prefix-highlight-$index";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    testapi::send_key($response eq 'confirm' ? 'ret' : 'esc');
    my $stage = "$prefix-$response";
    return $journey->consume_observation($stage, $journey->seen($stage));
}
1;
