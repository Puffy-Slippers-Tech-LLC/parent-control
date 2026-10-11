package onpc_time_explanation;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_request_flow ();

sub run {
    onpc_progress::operation('Qualifying saved time controls and non-collapsing balance reads');
    my ($exchange) = @_;
    die 'time-explanation:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'time-explanation', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('parent-toggle-enabled', 'parent-save-enabled',
                   'allowance-15-select', 'allowance-15-read',
                   'time-explanation-collapse', 'time-explanation-collapsed',
                   'time-explanation-expand', 'time-explanation-wrong-child',
                   'time-explanation-read', 'time-explanation-reread',
                   'time-explanation-reach-wrong-child', 'time-explanation-config-wrong-child',
                   'time-explanation-config-wrong-state',
                   'time-explanation-collapse-again',
                   'time-explanation-reach-read', 'time-explanation-reach-reread',
                   'time-explanation-off-read', 'time-explanation-positive-read',
                   'time-explanation-zero-read', 'time-explanation-zero-reread') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
sub revoke_cancel {
    onpc_progress::operation('Qualifying owned revocation warning and unchanged time after Cancel');
    my ($exchange, $invocations, $challenges) = @_;
    die 'revoke-cancel:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'revoke-cancel', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for ('allowance-configured', 'before-window', 'switch-user', 'gdm-switched');
    onpc_request_flow::obtain_time($journey, 'default', 'fixture-child', 'fixture-parent', 75, 1, 'automatic');
    onpc_gdm::sign_in_challenge($journey, 'return',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
    $journey->consume_observation('supplied-parent-retained',
        onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'child', 'supplied'));
    $journey->seen('before');
    for my $prefix ('first', 'second') {
        $journey->seen("$prefix-$_") for ('open', 'warning', 'wrong-child', 'wrong-confirmation', 'cancel', 'balances');
    }
    $journey->finish();
}
1;
