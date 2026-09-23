package onpc_request_exit;
use strict;
use warnings;
use testapi ();
use onpc_gdm ();
use onpc_journey ();
use onpc_progress ();

sub enter_station {
    onpc_progress::operation('Entering the request station through the greeter');
    my ($journey, $route) = @_;
    die 'request-exit:entry-arguments' unless @_ == 2
        && ref($journey) eq 'onpc_journey'
        && defined($route) && $route =~ /\A(?:cancel|escape)\z/;

    onpc_gdm::enter_station($journey, $route . '-');
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
