package onpc_station;
use strict;
use warnings;
use testapi ();
use onpc_progress ();

sub restrictions {
    onpc_progress::operation('Checking ordinary station shortcuts leave only the request form');
    my ($journey) = @_;
    die 'station:journey' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    for my $binding (['overview', 'super'], ['grid', 'super-a'], ['terminal', 'ctrl-alt-t']) {
        my ($route, $key) = @$binding;
        my $ready = "restriction-$route-ready";
        $journey->consume_observation($ready, $journey->seen($ready));
        testapi::send_key($key);
        my $read = "restriction-$route-read";
        $journey->consume_observation($read, $journey->seen($read));
    }
}
1;
