package onpc_app_restart;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_lifecycle ();

sub run {
    onpc_progress::operation('Qualifying normal Parent close and reopen');
    my ($exchange) = @_;
    die 'app-restart:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'app-restart', review => 0);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_parent::enter_desktop($journey, 'gdm', 'parent', 'fresh', 'success');
    onpc_parent::launch($journey, $desktop, 'management');
    $journey->seen('wrong-window-refused');
    onpc_lifecycle::reopen($journey, 'parent', $journey->seen('prior-window'), 'management');
    $journey->finish();
}
1;
