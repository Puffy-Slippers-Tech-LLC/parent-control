package onpc_station_shortcuts;
use strict;
use warnings;
use testapi ();
use onpc_gdm ();
use onpc_journey ();
use onpc_progress ();
use onpc_public_desktop_selection ();
use onpc_station ();

sub run {
    my ($exchange, $invocations, $challenges) = @_;
    die 'station-shortcuts:arguments' unless @_ == 3 && ref($exchange) eq 'CODE';
    onpc_progress::operation('Checking request-session shortcuts and ordinary desktop controls');
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'station-shortcuts', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_public_desktop_selection::parent_settings($journey, 'shortcut-setup', 0);
    onpc_gdm::sign_in_challenge($journey, 'ordinary',
        'ordinary-installed-greeter', 'ordinary-standard-focused', 'ordinary-desktop');
    for my $route (qw(overview grid run terminal)) {
        onpc_station::shortcut($journey, 'standard', $route);
        my $close = $journey->invoke("standard-shortcut-$route-close-ready");
        die 'station-shortcuts:close-result' unless defined $close->{shortcut_outcome};
        testapi::send_key($route eq 'terminal' ? 'alt-f4' :
                          $route eq 'run' ? 'esc' : 'super')
            unless $close->{shortcut_outcome} eq 'no-result';
        $journey->invoke("standard-shortcut-$route-closed");
    }
    $journey->seen('ordinary-logout');
    $journey->invoke('ordinary-returned');
    onpc_public_desktop_selection::select_account($journey, 'station');
    $journey->invoke('station-branch');
    $journey->invoke("shortcut-$_") for qw(child approver usable);
    for my $route (qw(overview grid run terminal)) {
        onpc_station::shortcut($journey, 'kiosk', $route);
        $journey->invoke("usable-after-$route");
    }
    $journey->invoke('shortcut-cancel');
    $journey->invoke('shortcut-returned');
    onpc_public_desktop_selection::select_account($journey, 'renewed-station');
    $journey->invoke('renewed-station-branch');
    $journey->invoke("fresh-$_") for qw(usable cancel returned);
    onpc_public_desktop_selection::parent_settings($journey, 'shortcut-restore', 1);
    $journey->finish();
}

1;
