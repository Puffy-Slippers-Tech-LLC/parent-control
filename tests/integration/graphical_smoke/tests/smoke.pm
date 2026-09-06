use strict;
use warnings;
use base 'basetest';
use testapi;
use JSON::PP;
use Time::HiRes qw(time sleep);

# Only fixed stage metadata crosses this local file rendezvous. No guest
# credentials or command output enters the distribution or public test log.
sub exchange {
    my ($stage, $shot) = @_;
    open(my $request, '>', "$stage.request.tmp") or die 'smoke:request';
    print {$request} encode_json({stage => $stage, screenshot => $shot});
    close($request) or die 'smoke:request-close';
    rename("$stage.request.tmp", "$stage.request.json") or die 'smoke:request-publish';
    my $deadline = time + 420;
    while (!-f "$stage.reply.json") {
        die 'smoke:controller-timeout' if time >= $deadline;
        sleep 0.1;
    }
    open(my $reply, '<', "$stage.reply.json") or die 'smoke:reply';
    local $/;
    return decode_json(<$reply>);
}

sub capture {
    my ($stage) = @_;
    my $result = save_screenshot();
    die 'smoke:no-screenshot' unless $result && $result->{screenshot};
    return exchange($stage, $result->{screenshot});
}

sub run {
    exchange('ready', undef);
    wait_still_screen(2, 30);
    my $screen = capture('gdm');
    mouse_set($screen->{width} - 24, 16);
    wait_still_screen(1, 10);
    die 'smoke:mouse-no-change' unless wait_screen_change(sub { mouse_click('left'); }, 15);
    wait_still_screen(1, 10);
    capture('menu');
    die 'smoke:keyboard-no-change' unless wait_screen_change(sub { send_key('esc'); }, 15);
    wait_still_screen(1, 10);
    capture('dismissed');
    record_info('smoke', 'Credential-free mouse and keyboard screen changes completed.');
}

1;
