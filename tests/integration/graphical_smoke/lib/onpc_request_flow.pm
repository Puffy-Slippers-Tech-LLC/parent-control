package onpc_request_flow;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_text ();
use onpc_journey ();
use onpc_password ();

# FLOW04: finite, explicit choices. The caller prepares policy independently.
sub prepare {
    onpc_progress::operation('Preparing the declared kiosk request without submitting');
    my ($journey, $prefix, $entry, $initial, $child, $approver, $seconds, $soft, $invalid) = @_;
    die 'request-flow:binding' unless (@_ == 8 || @_ == 9 && $invalid eq 'invalid')
        && ref($journey) eq 'onpc_journey'
        && ($prefix eq 'open' || $prefix eq 'new')
        && ($entry eq 'open' || $entry eq 'new')
        && ($initial eq 'default' || $initial eq 'selected')
        && $child eq 'fixture-child' && $approver eq 'fixture-parent'
        && $seconds eq '75' && $soft eq '1';
    onpc_gdm::enter_station($journey, 'cancel-') if $entry eq 'new';
    for my $suffix ('form', 'child', 'approver', 'selections') {
        my $stage = "$prefix-$suffix";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    if ($invalid) {
        $journey->consume_observation('invalid-custom-open', $journey->seen('invalid-custom-open'));
        onpc_text::replace_text($journey, 'kiosk-invalid-letters');
        for my $action ('ready', 'submit', 'read') {
            my $stage = "kiosk-invalid-letters-$action";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    }
    $journey->consume_observation("$prefix-duration", $journey->seen("$prefix-duration"));
    onpc_text::replace_text($journey, 'kiosk-fraction', "$prefix-text");
    for my $suffix ('duration-read', 'apps', 'estimate') {
        my $stage = "$prefix-$suffix";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

sub run {
    onpc_progress::operation('Qualifying open and fresh kiosk request composition');
    my ($exchange, $mate) = @_;
    die 'request-flow:arguments' unless (@_ == 1 || @_ == 2 && ($mate eq 'mate' || $mate eq 'approval'))
        && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $mate && $mate eq 'approval' ? 'kiosk-approval' : $mate ? 'mate-prompt' : 'request-flow', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('wrong-entry', 'valid-wrong-entry', ($mate ? ('mate-wrong-entry') : ()),
                   'limit-enabled', 'save-enabled',
                   'allowance-15-select', 'allowance-15-read', 'time-explanation-read',
                   'switch-user', 'gdm-switched') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    # Independent caller-owned entry; prepare(open) must not open it again.
    onpc_gdm::enter_station($journey, '');
    prepare($journey, 'open', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1,
            ($mate ? ('invalid') : ()));
    $journey->consume_observation('open-mate', $journey->seen('open-mate')) if $mate;
    for my $stage ('open-cancel', 'open-returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    prepare($journey, 'new', 'new', 'selected', 'fixture-child', 'fixture-parent', 75, 1);
    if ($mate && $mate eq 'approval') {
        $journey->consume_observation('approval-open', $journey->seen('approval-open'));
        onpc_password::enter_kiosk_mate_password($journey);
        $journey->consume_observation('approval-success', $journey->seen('approval-success'));
    } elsif ($mate) {
        $journey->consume_observation('new-mate', $journey->seen('new-mate'));
    }
    for my $stage (($mate && $mate eq 'approval' ? () : ('new-cancel')), 'new-returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
