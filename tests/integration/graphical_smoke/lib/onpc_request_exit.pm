package onpc_request_exit;
use strict;
use warnings;
use testapi ();
use onpc_gdm ();
use onpc_journey ();
use onpc_progress ();

sub enter_station {
    my ($journey, $route) = @_;
    die 'request-exit:entry-arguments' unless @_ == 2
        && ref($journey) eq 'onpc_journey'
        && defined($route) && $route =~ /\A(?:cancel|escape)\z/;

    # Each route independently refuses the normal password account before
    # entering the passwordless request station through its qualified row.
    my $list = $journey->seen($route . '-greeter');
    my $parent = $journey->highlight_choice(
        $list, $route . '-greeter', $route . '-parent-focused');
    $journey->consume_observation($route . '-parent-focused', $parent);
    testapi::send_key('ret');
    my $refused = $journey->seen($route . '-wrong-entry-refused');
    $journey->consume_observation($route . '-wrong-entry-refused', $refused);
    testapi::send_key('esc');

    my $station_list = $journey->seen($route . '-station-list');
    my $station = $journey->highlight_choice(
        $station_list, $route . '-station-list', $route . '-station-focused');
    $journey->consume_observation($route . '-station-focused', $station);
    testapi::send_key('ret');
    my $branch = $journey->seen($route . '-station-branch');
    die 'request-exit:unresolved-session-choice' unless
        ($branch->{station_destination} // '') eq 'default-request-form';
    $journey->seen($route . '-request-form');
}

sub run {
    onpc_progress::operation('Qualifying request-station Cancel and Escape exits');
    my ($exchange) = @_;
    die 'request-exit:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'request-exit', review => 0);
    onpc_gdm::reattach_functional();

    enter_station($journey, 'cancel');
    $journey->seen('cancel-action');
    $journey->seen('cancel-returned');

    enter_station($journey, 'escape');
    $journey->seen('escape-ready');
    testapi::send_key('esc');
    $journey->seen('escape-returned');
    $journey->finish();
}

1;
