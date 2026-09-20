package onpc_desktop_session;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();

# DESK02: consume the observed Parent desktop; controller stages perform the
# ID-addressed semantic actions and then read the resulting menu.
sub open_menu {
    onpc_progress::operation('Opening the desktop session menu');
    my ($journey, $desktop) = @_;
    die 'desk:menu-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('desktop', $desktop);
    $journey->seen('session-menu-toggle');
    $journey->seen('session-menu-power');
    return $journey->seen('session-menu');
}

# DESK03: activate Switch User from the open menu and independently observe GDM.
sub switch_user {
    onpc_progress::operation('Switching user from the session menu');
    my ($journey, $menu) = @_;
    die 'desk:switch-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('session-menu', $menu);
    $journey->seen('switch-user');
    return $journey->seen('gdm-switched');
}

# DESK04: activate Log Out, confirm the declared dialog, then observe GDM.
sub log_out {
    onpc_progress::operation('Logging out from the session menu');
    my ($journey, $menu) = @_;
    die 'desk:logout-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('session-menu', $menu);
    $journey->seen('logout');
    $journey->seen('logout-confirm');
    return $journey->seen('gdm-logged-out');
}

sub run {
    onpc_progress::operation('Checking desktop session controls');
    my ($exchange, $action) = @_;
    die 'desk:action-binding' unless @_ == 2
        && ($action eq 'logout' || $action eq 'switch-user');
    my $prefix = $action eq 'logout' ? 'desktop-logout' : 'desktop-switch';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => $prefix, review => 0);
    my $desktop = onpc_parent::login_functional($journey);
    my $menu = open_menu($journey, $desktop);
    $action eq 'logout' ? log_out($journey, $menu) : switch_user($journey, $menu);
    $journey->finish();
}

1;
