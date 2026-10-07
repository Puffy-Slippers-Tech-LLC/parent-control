package onpc_lifecycle;
use strict;
use warnings;
use onpc_progress ();
use onpc_parent ();
use onpc_window ();
use onpc_journey ();
use onpc_gdm ();
use onpc_request_flow ();
use onpc_allowance_boundaries ();

# LIFE01: consume the named prior window, independently guard its active state,
# close normally, prove absence, and use PARENT01 without selecting or editing.
sub reopen {
    onpc_progress::operation('Closing and reopening Parent');
    my ($journey, $window, $prior, $destination) = @_;
    die 'lifecycle:binding' unless @_ == 4 && ref($journey) eq 'onpc_journey'
        && $window eq 'parent' && $destination eq 'management';
    $journey->consume_observation('prior-window', $prior);
    onpc_window::close($journey, $window, $journey->seen('close-ready'));
    onpc_parent::launch($journey, $journey->seen('same-desktop'),
        $destination, 'same-desktop');
    return $journey->seen('initial-selection');
}
sub run_removal {
    onpc_progress::operation('Following one continuous removal, retention and purge history');
    my ($exchange, $declared, $challenges) = @_;
    die 'package-removal:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'package-removal', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_parent::login_functional($journey);
    $journey->seen($_) for qw(command-context package-submitted package-result activated-reboot-requested);
    onpc_gdm::named_login($journey, 'activated', 'parent');
    onpc_parent::named_management($journey, 'initial', 'child');
    $journey->seen($_) for qw(initial-apps initial-rows initial-screen limit-enabled save-enabled);
    onpc_allowance_boundaries::custom_value($journey, 'initial-allowance', 4);
    $journey->seen($_) for qw(initial-apps-again initial-block
        initial-block-read initial-policy switch-user gdm-switched);
    onpc_gdm::enter_station($journey, '');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1);
    $journey->seen($_) for qw(open-cancel open-returned);
    onpc_gdm::named_login($journey, 'restricted-child', 'child');
    $journey->seen($_) for qw(blocked-before-remove overlay-launch overlay-approver
        overlay-choices overlay-cancel restricted-logout);
    onpc_request_flow::obtain_time($journey, 'selected', 'fixture-child', 'fixture-parent', 75, 1, 'automatic');
    onpc_gdm::named_login($journey, 'remove-parent', 'parent');
    onpc_parent::named_management($journey, 'before-remove', 'child');
    $journey->seen($_) for qw(active-grant remove-submitted remove-result removed-reboot-requested);
    onpc_gdm::named_login($journey, 'removed', 'parent');
    $journey->seen('removed-parent-logout');
    onpc_gdm::named_login($journey, 'healthy-child', 'child');
    $journey->seen($_) for qw(healthy-command healthy-opened healthy-submit healthy-submitted
        healthy-close healthy-closed healthy-child-logout);
    onpc_gdm::named_login($journey, 'reinstall-parent', 'parent');
    $journey->seen($_) for qw(reinstall-submitted reinstall-result retained-reboot-requested);
    onpc_gdm::named_login($journey, 'retained', 'parent');
    onpc_parent::named_management($journey, 'retained', 'child');
    $journey->seen($_) for qw(retained-policy retained-switch retained-greeter);
    onpc_gdm::enter_station($journey->scope('retained'), '');
    $journey->seen($_) for qw(retained-accounts retained-request retained-cancel retained-returned);
    onpc_gdm::named_login($journey, 'reapply-parent', 'parent');
    onpc_parent::named_management($journey, 'reapply', 'child');
    onpc_allowance_boundaries::custom_value($journey, 'reapply-allowance', 5);
    $journey->seen($_) for qw(reapply-apps reapply-allowed reapply-allowed-read reapply-block
        reapply-block-read reapply-policy reapply-switch reapply-greeter);
    onpc_gdm::named_login($journey, 'reblocked-child', 'child');
    $journey->seen($_) for qw(blocked-after-reinstall reblocked-logout);
    onpc_gdm::named_login($journey, 'purge-parent', 'parent');
    $journey->seen($_) for qw(purge-submitted purge-result purged-reboot-requested);
    onpc_gdm::named_login($journey, 'purged', 'parent');
    $journey->seen($_) for qw(fresh-submitted fresh-result fresh-reboot-requested);
    onpc_gdm::named_login($journey, 'fresh', 'parent');
    onpc_parent::named_management($journey, 'fresh', 'child');
    $journey->seen($_) for qw(fresh-apps fresh-rows fresh-switch fresh-greeter);
    onpc_gdm::enter_station($journey->scope('fresh'), '');
    $journey->seen($_) for qw(fresh-request fresh-cancel fresh-returned);
    $journey->finish();
}

1;
