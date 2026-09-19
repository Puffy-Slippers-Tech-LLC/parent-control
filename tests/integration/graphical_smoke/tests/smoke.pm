use strict;
use warnings;
use base 'basetest';
use testapi;
use JSON::PP;
use Time::HiRes qw(time sleep);
use onpc_password ();
use onpc_serial ();
use onpc_gdm ();
use onpc_vt6 ();
use onpc_parent_about ();
use onpc_parent_access ();
use onpc_parent_terminal ();
use onpc_command_help ();
use onpc_desktop_session ();
use onpc_kiosk_entry ();
use onpc_parent_discovery ();
use onpc_journey ();
use onpc_flow00 ();

# Only fixed stage metadata crosses this local file rendezvous. No guest
# credentials or command output enters the distribution or public test log.
sub exchange {
    my ($stage, $shot) = @_;
    open(my $request, '>', "$stage.request.tmp") or die 'smoke:request';
    print {$request} encode_json({stage => $stage, screenshot => $shot});
    close($request) or die 'smoke:request-close';
    rename("$stage.request.tmp", "$stage.request.json") or die 'smoke:request-publish';
    my $deadline = time + ($stage eq 'setup-detached' ? 1500 : 420);
    my $prompt_sequence = 1;
    while (!-f "$stage.reply.json") {
        die 'smoke:controller-timeout' if time >= $deadline;
        if ($prompt_sequence <= 3 && onpc_journey::service_system_prompt($stage, $prompt_sequence)) {
            $prompt_sequence++;
        }
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
    if ($ready->{functional_smoke}) {
        my $journey = onpc_journey->new(exchange => \&exchange, prefix => 'smokeui', review => 0);
        onpc_flow00::run($journey, \&exchange);
        $journey->finish();
        return;
    }
    select_console('sut');
    if ($ready->{parent_about}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_about::run(\&exchange, $ready->{parent_review} ? 1 : 0);
        return;
    }
    if ($ready->{command_help}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_command_help::run(\&exchange);
        return;
    }
    if ($ready->{desktop_session_logout}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::run(\&exchange, 'logout');
        return;
    }
    if ($ready->{desktop_session_switch}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::run(\&exchange, 'switch-user');
        return;
    }
    if ($ready->{kiosk_entry}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_entry::run(\&exchange);
        return;
    }
    if ($ready->{parent_terminal}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_terminal::run(\&exchange);
        return;
    }
    if ($ready->{parent_access}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_access::run(\&exchange, $ready->{parent_access_review} ? 1 : 0);
        return;
    }
    if ($ready->{parent_discovery}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_discovery::run(\&exchange);
        return;
    }
    if ($ready->{parent_discovery_none}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_discovery::run_none(\&exchange);
        return;
    }
    if ($ready->{parent_setup}) {
        # Fixture setup owns the reboot, before customer interaction. Disable
        # VNC polling first; no serial console or password API is attached.
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_gdm::reattach_after_setup();
        capture('installed-greeter');
        if ($ready->{parent_input}) {
            onpc_gdm::inspect_installed_parent();
            capture('installed-parent-prompt');
            send_key('esc');
            assert_screen('onpc-gdm-parent-installed-account', 30);
            capture('installed-parent-dismissed');
        }
        if ($ready->{parent_standard_input}) {
            onpc_gdm::inspect_installed_standard();
            capture('installed-standard-prompt');
            send_key('esc');
            assert_screen('onpc-gdm-parent-installed-account', 30);
            capture('installed-standard-dismissed');
        }
        console('sut')->disable();
        power('off');
        die 'smoke:shutdown-unverified' unless check_shutdown(0);
        record_info('setup', 'Installed fixture greeter observed; no password submitted.');
        return;
    }
    # Backend/session readiness can precede GDM rendering. Wait for the
    # reviewed account region instead of sleeping through that transition.
    onpc_gdm::wait_list(90);
    my $screen = capture('gdm');
    onpc_gdm::select_parent();
    capture('selected');
    onpc_gdm::dismiss_prompt();
    capture('dismissed');
    if ($ready->{vt6_prompt}) {
        onpc_vt6::inspect_prompt(\&exchange);
    }
    if ($ready->{vt6_auth}) {
        onpc_vt6::authenticate(\&exchange);
        record_info('vt6-authentication', 'Fixture terminal command completion independently verified.');
    }
    if ($ready->{install_refusal}) {
        onpc_serial::run_install_refusal(\&exchange);
    } elsif ($ready->{install}) {
        onpc_serial::run_install(\&exchange);
    } elsif ($ready->{serial}) {
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
