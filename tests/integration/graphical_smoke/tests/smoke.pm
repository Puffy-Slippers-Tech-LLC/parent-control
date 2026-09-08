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
    my $ready = exchange('ready', undef);
    # The guest-side greeter session can become active while Plymouth is still
    # handing the display to GDM.  Give that supported session transition time
    # to render before asking for a stable feasibility capture.  Task 19B will
    # replace this fixed-baseline settling period with needle-based readiness.
    sleep 10;
    wait_still_screen(2, 30);
    my $screen = capture('gdm');
    # Match only the reviewed canonical fixture label. The match area's center
    # is inside that account tile; no baseline ordering/coordinate fallback.
    die 'smoke:mouse-no-change' unless wait_screen_change(sub {
        assert_and_click('onpc-gdm-parent-account', timeout => 30, mousehide => 1);
    }, 15);
    wait_still_screen(1, 10);
    capture('selected');
    die 'smoke:keyboard-no-change' unless wait_screen_change(sub { send_key('esc'); }, 15);
    wait_still_screen(1, 10);
    capture('dismissed');
    if ($ready->{authenticate}) {
        # Prove the role-specific password needle refuses the account list
        # before allowing any secret operation. A failed assertion stops here.
        die 'smoke:prompt-false-positive' if check_screen('onpc-gdm-parent-masked-password', 1);
        assert_and_click('onpc-gdm-other-parent-account', timeout => 30, mousehide => 1);
        wait_still_screen(1, 10);
        die 'smoke:wrong-role-prompt' if check_screen('onpc-gdm-parent-masked-password', 1);
        record_info('prompt-refusal', 'Parent password needle refused the account list and other fixture prompt.');
        send_key('esc');
        assert_and_click('onpc-gdm-parent-account', timeout => 30, mousehide => 1);
        onpc_password::enter_password('parent', 'gdm');
        send_key('ret');
        # The controller waits for the actual canonical fixture's local GDM
        # session. No raw authentication screen or terminal output is exported.
        exchange('authenticated', undef);
        record_info('authentication', 'Fixture graphical session independently verified.');
    }
    record_info('smoke', 'Credential-free mouse and keyboard screen changes completed.');
}

1;
