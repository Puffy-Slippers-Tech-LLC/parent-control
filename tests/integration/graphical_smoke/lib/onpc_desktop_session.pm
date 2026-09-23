package onpc_desktop_session;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();

# DESK03: shared system lock/switch command, then independent GDM observation.
sub switch_user {
    onpc_progress::operation('Switching to the greeter');
    my ($journey, $desktop) = @_;
    die 'desk:switch-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('desktop', $desktop);
    $journey->seen('switch-user');
    return $journey->seen('gdm-switched');
}

# DESK04: direct session logout, then independent GDM observation.
sub log_out {
    onpc_progress::operation('Logging out the fixture desktop');
    my ($journey, $desktop) = @_;
    die 'desk:logout-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('desktop', $desktop);
    $journey->seen('logout');
    return $journey->seen('gdm-logged-out');
}

sub run {
    onpc_progress::operation('Checking shared desktop session commands');
    my ($exchange, $action) = @_;
    die 'desk:action-binding' unless @_ == 2
        && ($action eq 'logout' || $action eq 'switch-user');
    my $prefix = $action eq 'logout' ? 'desktop-logout' : 'desktop-switch';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => $prefix, review => 0);
    my $desktop = onpc_parent::login_functional($journey);
    $action eq 'logout' ? log_out($journey, $desktop) : switch_user($journey, $desktop);
    $journey->finish();
}

1;
