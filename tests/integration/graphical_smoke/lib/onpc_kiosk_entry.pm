package onpc_kiosk_entry;
use strict;
use warnings;
use testapi ();
use onpc_gdm ();
use onpc_journey ();
use onpc_progress ();

sub run {
    onpc_progress::operation('Entering and reading the request station');
    my ($exchange) = @_;
    die 'kiosk-entry:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'kiosk-entry', review => 0);
    onpc_gdm::reattach_functional();

    # A normal account must lead to its password prompt, never the station.
    my $list = $journey->seen('installed-greeter');
    my $focused = $journey->highlight_choice(
        $list, 'installed-greeter', 'wrong-parent-focused');
    $journey->consume_observation('wrong-parent-focused', $focused);
    testapi::send_key('ret');
    my $refused = $journey->seen('wrong-entry-refused');
    $journey->consume_observation('wrong-entry-refused', $refused);
    testapi::send_key('esc');

    # Provisioning records the dedicated session as this account's default.
    # An explicit GDM session choice needs its own UI15 binding if GDM offers it.
    my $station_list = $journey->seen('station-list');
    my $station = $journey->highlight_choice(
        $station_list, 'station-list', 'station-focused');
    $journey->consume_observation('station-focused', $station);
    testapi::send_key('ret');
    my $branch = $journey->seen('station-branch');
    die 'kiosk-entry:unresolved-session-choice' unless
        ($branch->{station_destination} // '') eq 'default-request-form';
    $journey->seen('request-form');
    $journey->finish();
}

1;
