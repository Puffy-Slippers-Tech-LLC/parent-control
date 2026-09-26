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

# FLOW05 uses the fixed single-use approval challenge and observes automatic GDM exit.
sub approve {
    onpc_progress::operation('Approving the prepared kiosk request and observing automatic return');
    my ($journey, $child, $approver, $seconds, $soft, $exit) = @_;
    die 'approved-flow:binding' unless @_ == 6 && ref($journey) eq 'onpc_journey'
        && $child eq 'fixture-child' && $approver eq 'fixture-parent'
        && $seconds eq '75' && $soft eq '1' && $exit eq 'automatic';
    $journey->consume_observation('approval-open', $journey->seen('approval-open'));
    onpc_password::enter_kiosk_mate_password($journey);
    $journey->consume_observation('approval-success', $journey->seen('approval-success'));
    $journey->consume_observation('new-returned', $journey->seen('new-returned'));
}

# FLOW06: the caller supplies GDM and enabled policy, never a previous attempt.
sub obtain_time {
    onpc_progress::operation('Obtaining time through a fresh request-station entry');
    my ($journey, $initial, $child, $approver, $seconds, $soft, $exit) = @_;
    die 'approved-flow:binding' unless @_ == 7 && ref($journey) eq 'onpc_journey'
        && ($initial eq 'default' || $initial eq 'selected')
        && $child eq 'fixture-child' && $approver eq 'fixture-parent'
        && $seconds eq '75' && $soft eq '1' && $exit eq 'automatic';
    prepare($journey, 'new', 'new', $initial, $child, $approver, $seconds, $soft);
    approve($journey, $child, $approver, $seconds, $soft, $exit);
}

sub run {
    onpc_progress::operation('Qualifying open and fresh kiosk request composition');
    my ($exchange, $mate) = @_;
    die 'request-flow:arguments' unless (@_ == 1 || @_ == 2 && ($mate eq 'mate' || $mate eq 'approval' || $mate eq 'rejection' || $mate eq 'immediate' || $mate eq 'approved-flow'))
        && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $mate && ($mate eq 'immediate' || $mate eq 'approved-flow') ? 'kiosk-approval' :
            $mate && $mate eq 'rejection' ? 'kiosk-rejection' :
            $mate && $mate eq 'approval' ? 'kiosk-approval' : $mate ? 'mate-prompt' : 'request-flow', review => 0);
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
    if ($mate && $mate eq 'approved-flow') {
        obtain_time($journey, 'selected', 'fixture-child', 'fixture-parent', 75, 1, 'automatic');
        $journey->finish();
        return;
    }
    prepare($journey, 'new', 'new', 'selected', 'fixture-child', 'fixture-parent', 75, 1);
    if ($mate && ($mate eq 'approval' || $mate eq 'immediate')) {
        $journey->consume_observation('approval-open', $journey->seen('approval-open'));
        onpc_password::enter_kiosk_mate_password($journey);
        $journey->consume_observation('approval-success', $journey->seen('approval-success'));
    } elsif ($mate && $mate eq 'rejection') {
        $journey->consume_observation('rejection-open', $journey->seen('rejection-open'));
        onpc_password::enter_kiosk_mate_password($journey, 'wrong');
        for my $stage ('rejection-result', 'rejection-form') {
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    } elsif ($mate) {
        $journey->consume_observation('new-mate', $journey->seen('new-mate'));
    }
    for my $stage (($mate && ($mate eq 'approval' || $mate eq 'immediate') ? () : ('new-cancel')), 'new-returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
