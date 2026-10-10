package onpc_remembered_choices;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
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
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'initial',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    $journey->consume_observation('parent-selected', onpc_parent::select_child($journey, 'child',
        $journey->seen('child-picker-opened'), 'child-picker-opened', 'child-choice-highlighted', 'parent-selected'));
    $journey->seen('riley-allowance');
    $journey->consume_observation('existing-returned', onpc_parent::select_child($journey, 'returned',
        $journey->seen('existing-child-picker-opened'), 'existing-child-picker-opened',
        'existing-child-choice-highlighted', 'existing-returned'));
    $journey->seen('jordan-allowance');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
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
