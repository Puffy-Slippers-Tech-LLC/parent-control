package onpc_station;
use strict;
use warnings;
use testapi ();
use onpc_progress ();

sub shortcut {
    my ($journey, $account, $route, $stage_prefix) = @_;
    my %keys = (overview => 'super', grid => 'super-a', run => 'alt-f2',
                terminal => 'ctrl-alt-t');
    die 'station:shortcut-binding' unless (@_ == 3 || @_ == 4)
        && ref($journey) eq 'onpc_journey'
        && ($account eq 'standard' || $account eq 'kiosk') && exists($keys{$route});
    $stage_prefix //= "$account-shortcut";
    die 'station:shortcut-prefix' unless $stage_prefix eq "$account-shortcut"
        || $account eq 'kiosk' && $stage_prefix eq 'restriction';
    my $ready = "$stage_prefix-$route-ready";
    my $read = "$stage_prefix-$route-read";
    my $observe = sub {
        my ($stage) = @_;
        return (grep { $_ eq $stage } @{$journey->{invocations} // []})
            ? $journey->invoke($stage) : $journey->seen($stage);
    };
    $journey->consume_observation($ready, $observe->($ready));
    testapi::send_key($keys{$route});
    return $journey->consume_observation($read, $observe->($read));
}

sub restrictions {
    onpc_progress::operation('Checking ordinary station shortcuts leave only the request form');
    my ($journey, $prefix) = @_;
    die 'station:journey' unless (@_ == 1 || @_ == 2 && $prefix eq 'after-')
        && ref($journey) eq 'onpc_journey';
    $prefix //= '';
    if ($prefix eq '') {
        shortcut($journey, 'kiosk', $_, 'restriction')
            for ('overview', 'grid', 'terminal');
        return;
    }
    for my $binding (['overview', 'super'], ['grid', 'super-a'], ['terminal', 'ctrl-alt-t']) {
        my ($route, $key) = @$binding;
        my $ready = "${prefix}restriction-$route-ready";
        $journey->consume_observation($ready, $journey->seen($ready));
        testapi::send_key($key);
        my $read = "${prefix}restriction-$route-read";
        $journey->consume_observation($read, $journey->seen($read));
    }
}
1;
