use strict;
use warnings;
use base 'basetest';
use testapi;
use JSON::PP;
use Time::HiRes qw(time sleep);
use onpc_password ();

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
    my $result = onpc_password::capture_before_authentication();
    die 'smoke:no-screenshot' unless $result && $result->{screenshot};
    return exchange($stage, $result->{screenshot});
}

sub run {
    exchange('ready', undef);
    # The guest-side greeter session can become active while Plymouth is still
    # handing the display to GDM.  Give that supported session transition time
    # to render before asking for a stable feasibility capture.  Task 19B will
    # replace this fixed-baseline settling period with needle-based readiness.
    sleep 10;
    wait_still_screen(2, 30);
    my $screen = capture('gdm');
    # The first user tile is a large, stable target on this fixed product-free
    # baseline. The tiny status icons vary with the GNOME theme and are not a
    # suitable transport feasibility target; Task 19B adds needle-based UI
    # helpers. Selecting a user remains credential-free and changes no state.
    mouse_set(int($screen->{width} / 2), int($screen->{height} * 0.14));
    wait_still_screen(1, 10);
    die 'smoke:mouse-no-change' unless wait_screen_change(sub { mouse_click('left'); }, 15);
    wait_still_screen(1, 10);
    capture('selected');
    die 'smoke:keyboard-no-change' unless wait_screen_change(sub { send_key('esc'); }, 15);
    wait_still_screen(1, 10);
    capture('dismissed');
    record_info('smoke', 'Credential-free mouse and keyboard screen changes completed.');
}

1;
