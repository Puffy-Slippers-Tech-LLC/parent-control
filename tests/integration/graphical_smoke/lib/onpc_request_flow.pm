package onpc_request_flow;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_text ();
use onpc_journey ();

# FLOW04: finite, explicit choices. The caller prepares policy independently.
sub prepare {
    onpc_progress::operation('Preparing the declared kiosk request without submitting');
    my ($journey, $prefix, $entry, $initial, $child, $approver, $seconds, $soft) = @_;
    die 'request-flow:binding' unless @_ == 8 && ref($journey) eq 'onpc_journey'
        && ($prefix eq 'open' || $prefix eq 'new')
        && ($entry eq 'open' || $entry eq 'new')
        && ($initial eq 'default' || $initial eq 'selected')
        && $child eq 'fixture-child' && $approver eq 'fixture-parent'
        && $seconds eq '75' && $soft eq '1';
    onpc_gdm::enter_station($journey, 'cancel-') if $entry eq 'new';
    for my $suffix ('form', 'child', 'approver', 'selections', 'duration') {
        my $stage = "$prefix-$suffix";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_text::replace_text($journey, 'kiosk-fraction', "$prefix-text");
    for my $suffix ('duration-read', 'apps', 'estimate') {
        my $stage = "$prefix-$suffix";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

sub run {
    onpc_progress::operation('Qualifying open and fresh kiosk request composition');
    my ($exchange) = @_;
    die 'request-flow:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'request-flow', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('wrong-entry', 'valid-wrong-entry', 'limit-enabled', 'save-enabled',
                   'allowance-15-select', 'allowance-15-read', 'time-explanation-read',
                   'switch-user', 'gdm-switched') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    # Independent caller-owned entry; prepare(open) must not open it again.
    onpc_gdm::enter_station($journey, '');
    prepare($journey, 'open', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1);
    for my $stage ('open-cancel', 'open-returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    prepare($journey, 'new', 'new', 'selected', 'fixture-child', 'fixture-parent', 75, 1);
    for my $stage ('new-cancel', 'new-returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
