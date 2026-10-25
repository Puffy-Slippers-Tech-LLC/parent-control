package onpc_allowance_case;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_lifecycle ();
use onpc_allowance_boundaries ();
use onpc_allowance_selection ();
use onpc_feedback_states ();

sub run {
    onpc_progress::operation('Checking representative daily allowances and reopened saved values');
    my ($exchange, $flow) = @_;
    $flow //= 'boundaries';
    die 'allowance-case:arguments' unless (@_ == 1 || @_ == 2)
        && ref($exchange) eq 'CODE' && ($flow eq 'boundaries' || $flow eq 'save-order');
    return onpc_feedback_states::run_save_order($exchange) if $flow eq 'save-order';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'allowance-case', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('parent-selected',
        onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child'));
    $journey->seen('allowance-configured');
    onpc_allowance_selection::select($journey, 'preset-15', [15], 'confirm');
    $journey->seen('preset-15-read');
    onpc_allowance_selection::select($journey, 'custom-choice', ['custom'], 'confirm');
    onpc_allowance_boundaries::custom_value($journey, 'custom', 1);
    # Each selection already returns the child's complete allowance/settings.
    # The controller checks both children before and after reopening; a second
    # custom-editor read would repeat the same saved-value observation.
    onpc_allowance_boundaries::reload_child($journey, 'edited');
    onpc_lifecycle::reopen($journey, 'parent', $journey->seen('prior-window'), 'management');
    onpc_allowance_boundaries::reload_child($journey, 'persist');
    $journey->finish();
}
1;
