package onpc_set_allowance;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying fresh and same-user daily allowance setup');
    my ($exchange) = @_;
    die 'set-allowance:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'set-allowance', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 0, 1));
    for my $stage ('zero-reread', 'wrong-child', 'wrong-window', 'close-ready') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->seen('closed');
    $journey->consume_observation('same-allowance-configured', onpc_parent::set_allowance(
        $journey, 'desktop', 'parent', 'same-user', 'new', 'child', 1, 15, 1));
    $journey->seen('positive-reread');
    $journey->seen('final-settings');
    $journey->finish();
}
sub qualify_daily {
    onpc_progress::operation('Qualifying daily-only time from a new Parent window');
    my ($exchange, $same) = @_;
    die 'time-profile:arguments' unless @_ == 2 && ref($exchange) eq 'CODE'
        && ($same eq '0' || $same eq '1');
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $same ? 'time-profiles-same' : 'time-profiles-daily', review => 0);
    onpc_gdm::reattach_functional();
    if ($same) {
        $journey->consume_observation('parent-selected', onpc_parent::open_for_child(
            $journey, 'gdm', 'fresh', 'new', 'child'));
        $journey->seen($_) for qw(wrong-child wrong-window close-ready closed);
    }
    onpc_parent::daily_time_profile($journey, $same ? 'desktop' : 'gdm', 'parent',
        $same ? 'same-user' : 'fresh', 'new', 'child', 0, $same ? 4 : 2);
    $journey->finish();
}
sub qualify_grant {
    onpc_progress::operation('Checking a parent giving a child twenty additional minutes');
    my ($exchange, $invocations, $challenges, $revoke, $daily_minutes) = @_;
    $daily_minutes = 0 if @_ == 4;
    die 'time-profile:arguments' unless (@_ == 4 || @_ == 5) && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && defined($daily_minutes) && $daily_minutes =~ /\A(?:0|4)\z/
        && !($daily_minutes && $revoke)
        && ($revoke eq '0' || $revoke eq '1');
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $daily_minutes ? 'time-profiles-grant' : 'grant-only-profile', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    if ($revoke) {
        require onpc_time_explanation;
        onpc_time_explanation::revoke_entry($journey);
    } else {
        onpc_gdm::reattach_functional();
    }
    onpc_parent::grant_only_time_profile($journey, $revoke ? 'desktop' : 'gdm',
        $revoke ? 'same-user' : 'fresh', $revoke ? 'retained' : 'new', $revoke, $revoke, 1200,
        $revoke ? 'selected' : 'default', 1, $daily_minutes);
    $journey->finish();
}
1;
