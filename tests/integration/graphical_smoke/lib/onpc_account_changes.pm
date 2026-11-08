package onpc_account_changes;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_desktop_session ();

sub remove_selected {
    my ($exchange, $invocations, $challenges) = @_;
    onpc_progress::operation('Checking both screens after removing the selected child');
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'remove-selected', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'initial',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    $journey->seen($_) for qw(jordan-selected jordan-allowance riley-selected riley-allowance jordan-retained
        switch-user gdm-switched);
    onpc_gdm::enter_station($journey, '');
    $journey->seen($_) for qw(jordan-choices jordan-saved riley-choices riley-saved remember-jordan
        station-cancel station-returned);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'return');
    $journey->seen($_) for qw(remove-requested parent-fallback reopen-switch reopen-greeter);
    onpc_gdm::enter_station($journey->scope('reopen'), '');
    $journey->seen($_) for qw(station-fallback final-cancel final-greeter);
    $journey->finish();
}

sub remove_last_child {
    my ($exchange, $invocations, $challenges) = @_;
    onpc_progress::operation('Checking Parent after removing the last eligible child');
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'remove-last-child', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'initial',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    $journey->seen($_) for qw(jordan-only parent-empty);
    $journey->finish();
}

1;
