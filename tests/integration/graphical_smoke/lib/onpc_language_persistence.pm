package onpc_language_persistence;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_allowance_boundaries ();
use onpc_lifecycle ();
use onpc_request_flow ();
use onpc_text ();

sub run {
    onpc_progress::operation('Testing independent personal languages through offline normal entries');
    my ($exchange, $invocations, $challenges) = @_;
    die 'language-persistence:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'language-persistence', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'initial-language');
    $journey->seen('initial-save');
    for my $child ('riley', 'jordan') {
        onpc_allowance_boundaries::select_child($journey, "$child-setup");
        $journey->seen("$child-$_") for qw(enabled saved allowance before);
    }
    $journey->seen('offline-enter');
    onpc_parent::language_selection($journey, 'chinese');
    $journey->seen('chinese-save');
    for my $prefix ('parent-riley', 'parent-jordan', 'parent-riley-return') {
        onpc_allowance_boundaries::select_child($journey, $prefix);
        $journey->seen("$prefix-$_") for qw(state choice close);
    }
    onpc_lifecycle::reopen($journey, 'parent', $journey->seen('prior-window'), 'management');
    $journey->seen($_) for qw(reopened-choice reopened-close);
    onpc_allowance_boundaries::select_child($journey, 'riley-session');
    $journey->seen($_) for qw(riley-session-before parent-switch parent-greeter);
    onpc_gdm::enter_station($journey, 'initial-');
    $journey->seen($_) for qw(station-initial-language station-initial-save jordan-jamie jordan-custom);
    onpc_text::replace_text($journey, 'jordan-kiosk-fraction', 'jordan-text');
    $journey->seen($_) for qw(jordan-soft jordan-original);
    onpc_parent::language_selection($journey, 'german');
    $journey->seen($_) for qw(german-save jordan-german riley-initial riley-custom);
    onpc_text::replace_text($journey, 'kiosk-fraction', 'riley-text');
    $journey->seen($_) for qw(riley-soft riley-original);
    onpc_parent::language_selection($journey, 'hebrew');
    $journey->seen($_) for qw(hebrew-save riley-hebrew);
    onpc_parent::language_selection($journey, 'cancel-german');
    $journey->seen($_) for qw(cancel-german-response cancel-retained cancel-close riley-cancelled
        jordan-restored jordan-restored-form jordan-choice jordan-close
        jordan-casey-select jordan-casey jordan-casey-choice jordan-casey-close jordan-jamie-select
        riley-restored riley-restored-form riley-choice riley-close
        riley-casey-select riley-casey riley-casey-choice riley-casey-close riley-jamie-select
        jordan-final station-cancel station-returned);
    onpc_gdm::enter_station($journey, 'renewed-');
    $journey->seen($_) for qw(jordan-reentered jordan-reentered-choice jordan-reentered-close
        riley-reentered-select riley-reentered riley-reentered-choice riley-reentered-close
        final-station-cancel final-station-returned);
    onpc_gdm::named_login($journey, 'child', 'child');
    onpc_request_flow::overlay_entry($journey, 'direct', 'command');
    $journey->seen($_) for qw(overlay-choice overlay-close overlay-cancel overlay-returned);
    onpc_request_flow::overlay_entry($journey, 'relaunched', 'command');
    $journey->seen($_) for qw(relaunched-choice relaunched-close relaunched-cancel relaunched-returned child-logout);
    onpc_gdm::named_login($journey, 'renewed', 'child');
    onpc_request_flow::overlay_entry($journey, 'renewed-overlay', 'command');
    $journey->seen($_) for qw(renewed-choice renewed-close renewed-cancel renewed-returned child-switch child-greeter);
    my $returned = onpc_gdm::sign_in_challenge($journey, 'return',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
    onpc_parent::launch($journey, $returned, 'management', 'return-desktop');
    onpc_allowance_boundaries::select_child($journey, 'final-jordan');
    $journey->seen('jordan-offline-final');
    onpc_allowance_boundaries::select_child($journey, 'final-riley');
    $journey->seen($_) for qw(riley-offline-final parent-final-choice parent-final-close offline-restore riley-online-final);
    onpc_allowance_boundaries::select_child($journey, 'online-jordan');
    $journey->seen('jordan-online-final');
    $journey->finish();
}

1;
