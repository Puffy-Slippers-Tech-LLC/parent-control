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
    my ($journey, $desktop, $stage) = @_;
    $stage //= 'desktop';
    die 'desk:switch-binding' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey'
        && ($stage eq 'desktop' || $stage eq 'repeat-desktop');
    $journey->consume_observation($stage, $desktop);
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

# DESK06: no secret or empty submission. A fresh curtain proof guards one Space.
sub observe_lock {
    onpc_progress::operation('Revealing the bound lock challenge');
    my ($journey, $entry) = @_;
    $entry //= 'curtain';
    die 'desk:lock-binding' unless (@_ == 1 || @_ == 2) && ref($journey) eq 'onpc_journey'
        && ($entry eq 'curtain' || $entry eq 'challenge');
    return $journey->seen('challenge') if $entry eq 'challenge';
    $journey->consume_observation('curtain', $journey->seen('curtain'));
    $journey->consume_observation('reveal-ready', $journey->seen('reveal-ready'));
    testapi::send_key('spc');
    return $journey->seen('challenge');
}

# DESK05: one public session command; callers independently observe DESK06.
sub lock {
    onpc_progress::operation('Locking the fixture desktop');
    my ($journey, $desktop, $stage) = @_;
    $stage //= 'desktop';
    die 'desk:lock-binding' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey'
        && ($stage eq 'desktop' || $stage eq 'lock-ready');
    $journey->consume_observation($stage, $desktop);
    $journey->seen('lock');
    return observe_lock($journey);
}

sub qualify_lock {
    onpc_progress::operation('Qualifying the desktop lock surface');
    my ($exchange, $supplied) = @_;
    die 'desk:lock-qualification-binding' unless @_ == 2 && ref($exchange) eq 'CODE'
        && ($supplied == 0 || $supplied == 1);
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $supplied ? 'lock-supplied' : 'lock-command', review => 0);
    my $desktop = onpc_parent::login_functional($journey);
    $journey->seen('unlocked-refused');
    if ($supplied) {
        # Independent normal desktop shortcut supplies entry to the observer.
        $journey->consume_observation('lock-ready', $journey->seen('lock-ready'));
        testapi::send_key('super-l');
        observe_lock($journey);
    } else {
        lock($journey, $journey->seen('lock-ready'), 'lock-ready');
    }
    $journey->seen('lock-refusals');
    $journey->seen('independent-challenge');
    $journey->finish();
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
