package onpc_allowance_case;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_lifecycle ();
use onpc_allowance_boundaries ();

sub run {
    onpc_progress::operation('Checking representative daily allowances and reopened saved values');
    my ($exchange) = @_;
    die 'allowance-case:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'allowance-case', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('parent-selected',
        onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child'));
    $journey->seen('editor-disabled');
    $journey->seen('allowance-configured');
    for my $value (0, 60, 90, 1410) {
        $journey->seen("preset-$value-$_") for ('select', 'read');
    }
    onpc_allowance_boundaries::exercise($journey);
    onpc_lifecycle::reopen($journey, 'parent', $journey->seen('prior-window'), 'management');
    onpc_allowance_boundaries::reload_child($journey, 'persist');
    $journey->seen('persist-saved');
    $journey->seen('persist-editor');
    $journey->finish();
}
1;
