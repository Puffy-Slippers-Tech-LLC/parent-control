package onpc_allowance;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();

sub run {
    onpc_progress::operation('Qualifying ordinary custom allowance commit routes');
    my ($exchange) = @_;
    die 'allowance:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'allowance', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('custom-disabled', 'allowance-disabled', 'parent-toggle-enabled',
                   'parent-save-enabled', 'allowance-wrong-child',
                   'allowance-0-select', 'allowance-0-read', 'allowance-0-reopen',
                   'allowance-15-select', 'allowance-15-read', 'allowance-15-reopen',
                   'custom-wrong-child') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    for my $value (1, 2, 3) {
        my $prefix = "custom-$value";
        $journey->consume_observation("$prefix-open", $journey->seen("$prefix-open"));
        onpc_text::replace_text($journey, "daily-$value");
        $journey->consume_observation("$prefix-saved", $journey->seen("$prefix-saved"));
        for my $direction ('away', 'back') {
            for my $action ('open', 'focus') {
                my $stage = "$prefix-$direction-$action";
                $journey->consume_observation($stage, $journey->seen($stage));
            }
            testapi::send_key('ret');
            my $stage = "$prefix-$direction-selected";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
        $journey->consume_observation("$prefix-reopen", $journey->seen("$prefix-reopen"));
    }
    $journey->finish();
}
1;
