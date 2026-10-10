package onpc_remembered_choices;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_desktop_session ();
use onpc_request_flow ();

sub run {
    onpc_progress::operation('Remembering both children choices across overlay and kiosk visits');
    my ($exchange, $declared, $challenges) = @_;
    die 'remembered-choices:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'remembered-choices', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_request_flow::prepare_transfer_allowances($journey);
    onpc_gdm::enter_station($journey->scope('seed'), '');
    $journey->seen($_) for qw(seed-child seed-approver seed-cancel seed-returned);
    # Only explicit maintenance reproduction declares the old retained logins.
    # The customer case checks persistence by changing children in the open kiosk.
    my $diagnosis = grep { /^jordan-return-entry-/ } @$declared;
    my @entries = grep { /^(?:jordan|riley)-entry-/ } @$declared;
    die 'remembered-choices:child-order' unless @entries;
    my @children = $entries[0] =~ /^riley-/ ? qw(riley jordan) : qw(jordan riley);
    my @visits = map { [$_, $_, $_ eq 'riley' ? 'child' : 'other-child', 'fresh'] } @children;
    push @visits, (['jordan-return', 'jordan', 'other-child', 'retained'],
                   ['riley-return', 'riley', 'child', 'retained']) if $diagnosis;
    for my $binding (@visits) {
        my ($prefix, $child, $role, $entry) = @$binding;
        visit($journey, $prefix, $child, $role, $entry);
        $journey->seen("$prefix-$_") for $prefix eq ($diagnosis ? 'riley-return' : $children[-1])
            ? () : qw(exit greeter);
    }
    unless ($diagnosis) {
        $journey->seen("$_-revisit-select"), $journey->seen("$_-revisit-read") for @children;
    }
    $journey->finish();
}

sub visit {
    onpc_progress::operation('Comparing remembered choices across an overlay and kiosk visit');
    my ($journey, $prefix, $child, $role, $entry) = @_;
    onpc_desktop_session::enter_desktop($journey, 'gdm', $role, $entry, 'success', "$prefix-entry");
    $journey->seen("$prefix-launch");
    $journey->seen("$prefix-$_") for $entry eq 'fresh' ? qw(default approver custom text apps) : ();
    my $source = $journey->seen("$prefix-source");
    onpc_request_flow::overlay_to_kiosk($journey, $source, "$prefix-source", "$prefix-transfer", $child);
}

sub run_reverse {
    onpc_progress::operation('Remembering both children choices from kiosk to reopened overlays');
    my ($exchange, $declared, $challenges) = @_;
    die 'remembered-reverse:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'remembered-reverse', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    my @entries = grep { /^(?:jordan|riley)-seed-entry-/ } @$declared;
    die 'remembered-reverse:child-order' unless @entries;
    my @children = $entries[0] =~ /^riley-/ ? qw(riley jordan) : qw(jordan riley);
    onpc_request_flow::prepare_transfer_allowances($journey);
    for my $child (@children) {
        my $role = $child eq 'riley' ? 'child' : 'other-child';
        onpc_desktop_session::enter_desktop($journey, 'gdm', $role, 'fresh', 'success', "$child-seed-entry");
        $journey->seen("$child-seed-$_") for qw(launch default approver cancel returned logout greeter);
    }
    onpc_gdm::enter_station($journey->scope('station'), '');
    for my $child (@children) {
        $journey->seen("$child-$_") for qw(select-default approver custom text apps);
        my $source = $journey->seen("$child-source");
        onpc_request_flow::kiosk_to_overlay($journey, $source, "$child-source", "$child-transfer", $child, 'fresh');
        $journey->seen("$child-$_") for qw(exit desktop logout greeter);
        onpc_gdm::enter_station($journey->scope('next-station'), '') if $child eq $children[0];
    }
    for my $child (@children) {
        my $prefix = "$child-revisit";
        my $role = $child eq 'riley' ? 'child' : 'other-child';
        onpc_desktop_session::enter_desktop($journey, 'gdm', $role, 'fresh', 'success', "$prefix-entry");
        $journey->seen("$prefix-$_") for qw(launch read);
        $journey->seen("$prefix-$_") for $child eq $children[0] ? qw(exit desktop logout greeter) : ();
    }
    $journey->finish();
}

sub repeat_return_for_diagnosis {
    onpc_progress::operation('Reproducing the retained child transfer and desktop return');
    my ($exchange, $declared, $challenges) = @_;
    die 'remembered-return:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'remembered-return', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    visit($journey, 'riley-return', 'riley', 'child', 'retained');
    $journey->seen($_) for qw(riley-return-exit riley-return-greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'retained', 'success', 'jordan-return-entry');
    $journey->finish();
}

sub enter_return_for_diagnosis {
    onpc_progress::operation('Reproducing the retained child desktop entry');
    my ($exchange, $declared, $challenges) = @_;
    die 'remembered-return:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'remembered-return', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'retained', 'success', 'jordan-return-entry');
    $journey->finish();
}

1;
