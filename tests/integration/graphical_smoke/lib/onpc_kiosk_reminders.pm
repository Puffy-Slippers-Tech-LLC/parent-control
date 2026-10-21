package onpc_kiosk_reminders;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_allowance_boundaries ();
use onpc_request_flow ();

sub run {
    onpc_progress::operation('Qualifying child-bound reminder saves across request surfaces');
    my ($exchange, $invocations, $challenges) = @_;
    die 'kiosk-reminders:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'kiosk-reminders', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for ('allowance-configured', 'riley-policy-before');
    onpc_allowance_boundaries::select_child($journey, 'jordan');
    $journey->seen($_) for ('jordan-enabled', 'jordan-saved', 'jordan-policy-before',
        'parent-logout-ready', 'parent-logout', 'parent-logged-out');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    onpc_request_flow::overlay_entry($journey, 'direct', 'command');
    $journey->seen($_) for ('initial-save', 'overlay-before', 'overlay-defaults',
        'overlay-created', 'overlay-saved', 'overlay-saved-form', 'overlay-exit',
        'overlay-returned', 'child-logout', 'child-logged-out');
    onpc_gdm::enter_station($journey, 'initial-');
    $journey->seen($_) for ('jordan-language', 'jordan-language-save', 'jordan-jamie',
        'jordan-before', 'jordan-reminders-before', 'jordan-close',
        'riley-select', 'riley-saved-read', 'riley-edited', 'riley-saved', 'riley-reopened',
        'riley-close', 'riley-saved-form', 'approver-select', 'approver-reminders',
        'approver-close', 'approver-form', 'jordan-select', 'jordan-reminders-after',
        'jordan-after-close', 'jordan-after', 'riley-return-select', 'riley-return-read',
        'riley-return-close', 'riley-return-form', 'station-exit', 'station-returned');
    onpc_gdm::sign_in_challenge($journey, 'renewed-child',
        'renewed-installed-greeter', 'renewed-child-focused', 'renewed-desktop');
    onpc_request_flow::overlay_entry($journey, 'renewed', 'command');
    $journey->seen($_) for ('overlay-final-before', 'overlay-final-read',
        'overlay-restored-draft', 'overlay-restored-save', 'overlay-restored-read', 'overlay-final-close',
        'overlay-final-form', 'overlay-final-exit', 'overlay-final-returned',
        'final-child-logout', 'final-child-logged-out');
    $desktop = onpc_gdm::sign_in_challenge($journey, 'return-parent',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
    onpc_parent::launch($journey, $desktop, 'management', 'return-desktop');
    $selected = onpc_parent::select_child($journey, 'child', $journey->seen('return-child-picker-opened'),
        'return-child-picker-opened', 'return-child-choice-highlighted', 'return-parent-selected');
    $journey->consume_observation('return-parent-selected', $selected);
    $journey->seen('riley-policy-after');
    onpc_allowance_boundaries::select_child($journey, 'jordan-final');
    $journey->seen('jordan-policy-after');
    $journey->finish();
}

1;
