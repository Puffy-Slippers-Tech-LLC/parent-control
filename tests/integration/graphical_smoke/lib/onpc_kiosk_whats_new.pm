package onpc_kiosk_whats_new;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_journey ();
use onpc_request_flow ();

sub run {
    my ($exchange, $invocations, $challenges) = @_;
    die 'kiosk-whats-new:arguments' unless @_ == 3 && ref($exchange) eq 'CODE';
    _run($exchange, $invocations, $challenges, 0);
}

sub run_case {
    my ($exchange, $invocations, $challenges) = @_;
    die 'kiosk-whats-new:arguments' unless @_ == 3 && ref($exchange) eq 'CODE';
    _run($exchange, $invocations, $challenges, 1);
}

sub _run {
    my ($exchange, $invocations, $challenges, $complete_case) = @_;
    onpc_progress::operation('Riley reads child release notes and returns to the same request for Jamie');
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $complete_case ? 'kiosk-release-notes' : 'kiosk-whats-new', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->consume_observation('wrong-owner', $journey->seen('wrong-owner')) unless $complete_case;
    for my $stage ('allowance-configured', 'policy-before', 'switch-user', 'gdm-switched') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_gdm::enter_station($journey, '');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
        'fixture-child', 'fixture-parent', 75, 1, 'compact');
    for my $stage ('notes-open', 'notes-read', 'notes-close', 'form-returned', 'cancel', 'returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_gdm::named_login($journey, 'verify', 'parent');
    for my $stage ('policy-after', 'balance-after') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    if ($complete_case) {
        for my $stage ('parent-logout', 'final-greeter') {
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    }
    $journey->finish();
}
1;
