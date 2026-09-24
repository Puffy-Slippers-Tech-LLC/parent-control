package onpc_challenges;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_journey ();
use onpc_gdm ();
use onpc_desktop_session ();

sub run {
    onpc_progress::operation('Qualifying distinct graphical authentication challenges');
    my ($exchange, $declared, $challenges) = @_;
    my @stages = qw(wrong-list wrong-focused wrong-refused wrong-returned
        installed-greeter parent-focused recipient-qualified recipient-rechecked desktop
        second-installed-greeter second-parent-focused second-recipient-qualified
        second-recipient-rechecked second-desktop);
    die 'challenges:plan' unless ref($declared) eq 'ARRAY'
        && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 2;
    for my $id ('first-login', 'second-login') {
        my $prefix = $id eq 'first-login' ? '' : 'second-';
        die 'challenges:plan' unless ref($challenges->{$id}) eq 'ARRAY'
            && join('/', @{$challenges->{$id}}) eq
                "parent/${prefix}recipient-qualified/${prefix}recipient-rechecked";
    }
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'challenges', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $list = $journey->invoke('wrong-list');
    my $focus = $journey->highlight_choice($list, 'wrong-list', 'wrong-focused');
    $journey->consume_observation('wrong-focused', $focus);
    testapi::send_key('ret');
    my $refusal = $journey->invoke('wrong-refused');
    $journey->consume_observation('wrong-refused', $refusal);
    testapi::send_key('esc');
    $journey->invoke('wrong-returned');
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'first-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_desktop_session::log_out($journey, $desktop);
    onpc_gdm::sign_in_challenge($journey, 'second-login',
        'second-installed-greeter', 'second-parent-focused', 'second-desktop');
    $journey->finish();
}

1;
