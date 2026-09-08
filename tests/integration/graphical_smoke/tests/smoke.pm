use strict;
use warnings;
use base 'basetest';
use testapi;
use JSON::PP;
use Time::HiRes qw(time sleep);
use onpc_password ();
use onpc_serial ();
use onpc_gdm ();

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
    # generalhw opens graphics during boot without setting testapi's selected
    # console. Establish that public selection before checking its identity.
    select_console('sut');
    # Backend/session readiness can precede GDM rendering. Wait for the
    # reviewed account region instead of sleeping through that transition.
    onpc_gdm::wait_list(90);
    my $screen = capture('gdm');
    onpc_gdm::select_parent();
    capture('selected');
    onpc_gdm::dismiss_prompt();
    capture('dismissed');
    if ($ready->{serial}) {
        onpc_serial::run(\&exchange);
    }
    if ($ready->{authenticate}) {
        # Prove the role-specific password needle refuses the account list
        # before allowing any secret operation. A failed assertion stops here.
        die 'smoke:prompt-false-positive' if check_screen('onpc-gdm-parent-masked-password', 1);
        assert_and_click('onpc-gdm-other-parent-account', timeout => 30, mousehide => 1);
        wait_still_screen(1, 10);
        die 'smoke:wrong-role-prompt' if check_screen('onpc-gdm-parent-masked-password', 1);
        record_info('prompt-refusal', 'Parent password needle refused the account list and other fixture prompt.');
        onpc_gdm::dismiss_prompt();
        onpc_gdm::select_parent();
        onpc_password::enter_password('parent', 'gdm');
        send_key('ret');
        # The controller waits for the actual canonical fixture's local GDM
        # session. No raw authentication screen or terminal output is exported.
        exchange('authenticated', undef);
        record_info('authentication', 'Fixture graphical session independently verified.');
    }
    record_info('smoke', 'Credential-free mouse and keyboard screen changes completed.');
    # End the complete attempt through the public lifecycle API. generalhw's
    # final status command must observe a genuinely stopped lease-owned guest.
    # Stop VNC polling/reconnects before revoking the owned graphics endpoint.
    # The documented console proxy calls the console's public disable method.
    console('sut')->disable();
    power('off');
    # assert_shutdown also takes a screenshot; after shutdown no display may
    # be reacquired. Use its public status-only counterpart and fail explicitly.
    die 'smoke:shutdown-unverified' unless check_shutdown(0);
    record_info('shutdown', 'Owned guest poweroff and off-state verification completed.');
}

1;
