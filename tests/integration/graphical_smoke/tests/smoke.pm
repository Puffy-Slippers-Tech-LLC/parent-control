use strict;
use warnings;
use base 'basetest';
use testapi;
use JSON::PP;
use Time::HiRes qw(time sleep);
use onpc_password ();
use onpc_serial ();
use onpc_gdm ();
use onpc_fresh_desktop ();
use onpc_shell_search ();
use onpc_parent_search_launch ();
use onpc_parent_terminal_provider ();
use onpc_shell_search_standard ();
use onpc_vt6 ();
use onpc_parent_about ();
use onpc_license_viewer_provider ();
use onpc_parent_access ();
use onpc_parent_terminal ();
use onpc_command_help ();
use onpc_desktop_session ();
use onpc_kiosk_entry ();
use onpc_kiosk_eligible_choices ();
use onpc_kiosk_valid_duration ();
use onpc_request_flow ();
use onpc_kiosk_cancel ();
use onpc_request_choices ();
use onpc_kiosk_no_child ();
use onpc_kiosk_no_approver ();
use onpc_no_child ();
use onpc_no_parent ();
use onpc_disabled_child ();
use onpc_request_exit ();
use onpc_parent_toggle ();
use onpc_allowance_presets ();
use onpc_allowance ();
use onpc_allowance_boundaries ();
use onpc_allowance_case ();
use onpc_time_explanation ();
use onpc_set_allowance ();
use onpc_app_restart ();
use onpc_zero_total ();
use onpc_app_rows ();
use onpc_feedback_read ();
use onpc_text ();
use onpc_parent_discovery ();
use onpc_journey ();
use onpc_flow00 ();
use onpc_repeated_operations ();
use onpc_challenges ();
use onpc_product_free_entry ();
use onpc_package_authority ();
use onpc_package_install ();
use onpc_customer_reboot ();
use onpc_clean_install ();

# Only fixed stage metadata crosses this local file rendezvous. No guest
# credentials or command output enters the distribution or public test log.
sub exchange {
    my ($stage, $shot) = @_;
    open(my $request, '>', "$stage.request.tmp") or die 'smoke:request';
    print {$request} encode_json({stage => $stage, screenshot => $shot});
    close($request) or die 'smoke:request-close';
    rename("$stage.request.tmp", "$stage.request.json") or die 'smoke:request-publish';
    my $deadline = time + ($stage eq 'setup-detached' ? 1500
        : $stage eq 'package-submitted' ? 780
        : $stage eq 'reboot-installed-greeter' ? 780 : 420);
    while (!-f "$stage.reply.json") {
        die 'smoke:controller-timeout' if time >= $deadline;
        sleep 0.1;
    }
    open(my $reply, '<', "$stage.reply.json") or die 'smoke:reply';
    local $/;
    return decode_json(<$reply>);
}

sub capture {
    die 'smoke:image-capture-route-refused';
}

sub run {
    my $ready = exchange('ready', undef);
    if ($ready->{clean_install}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_clean_install::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{customer_reboot}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{package_install}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_package_install::run(\&exchange);
        return;
    }
    if ($ready->{package_authority}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_package_authority::run(\&exchange);
        return;
    }
    if ($ready->{product_free_entry}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_product_free_entry::run(\&exchange);
        return;
    }
    if ($ready->{challenges}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{repeated_operations}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_repeated_operations::run(\&exchange, $ready->{invocations});
        return;
    }
    # generalhw opens graphics during boot without setting testapi's selected
    # console. Establish that public selection before checking its identity.
    if ($ready->{functional_smoke}) {
        my $journey = onpc_journey->new(exchange => \&exchange, prefix => 'smokeui', review => 0);
        onpc_flow00::run($journey, \&exchange);
        $journey->finish();
        return;
    }
    if ($ready->{parent_about}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_about::run(\&exchange, $ready->{parent_review} ? 1 : 0);
        return;
    }
    if ($ready->{license_viewer_provider}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_license_viewer_provider::run(\&exchange);
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
    if ($ready->{gdm_navigation}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_gdm::navigation_qualification(\&exchange);
        return;
    }
    if ($ready->{gdm_product_free}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_gdm::product_free_qualification(\&exchange);
        return;
    }
    if ($ready->{gdm_recipient}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_gdm::recipient_qualification(\&exchange);
        return;
    }
    if ($ready->{parent_search_launch}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_search_launch::run(\&exchange);
        return;
    }
    if ($ready->{parent_terminal_provider}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_terminal_provider::run(\&exchange);
        return;
    }
    if ($ready->{shell_search}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_shell_search_standard::run(\&exchange);
        return;
    }
    if ($ready->{shell_search_results}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_shell_search::run(\&exchange);
        return;
    }
    if ($ready->{fresh_parent_desktop} || $ready->{fresh_standard_desktop}
        || $ready->{keyring_standard_desktop}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_fresh_desktop::run(\&exchange,
            $ready->{fresh_parent_desktop} ? 'parent' : 'standard',
            $ready->{keyring_standard_desktop} ? 1 : 0);
        return;
    }
    if ($ready->{disabled_child}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_disabled_child::run(\&exchange);
        return;
    }
    if ($ready->{no_child}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_no_child::run(\&exchange);
        return;
    }
    if ($ready->{no_parent}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_no_parent::run(\&exchange);
        return;
    }
    if ($ready->{kiosk_no_approver}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_no_approver::run(\&exchange);
        return;
    }
    if ($ready->{kiosk_no_child}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_no_child::run(\&exchange);
        return;
    }
    if ($ready->{request_choices}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_choices::run(\&exchange);
        return;
    }
    if ($ready->{kiosk_cancel}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_cancel::run(\&exchange);
        return;
    }
    if ($ready->{request_flow}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::run(\&exchange);
        return;
    }
    if ($ready->{request_duration}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_valid_duration::run(\&exchange, 'invalid');
        return;
    }
    if ($ready->{kiosk_valid_duration}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_valid_duration::run(\&exchange);
        return;
    }
    if ($ready->{kiosk_eligible_choices}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_eligible_choices::run(\&exchange);
        return;
    }
    if ($ready->{kiosk_entry}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_entry::run(\&exchange);
        return;
    }
    if ($ready->{request_exit}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_exit::run(\&exchange);
        return;
    }
    if ($ready->{parent_toggle}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_toggle::run(\&exchange);
        return;
    }
    if ($ready->{app_row_observations}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::run(\&exchange);
        return;
    }
    if ($ready->{zero_total}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_zero_total::run(\&exchange);
        return;
    }
    if ($ready->{set_allowance}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_set_allowance::run(\&exchange);
        return;
    }
    if ($ready->{app_restart}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_restart::run(\&exchange);
        return;
    }
    if ($ready->{time_explanation}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_time_explanation::run(\&exchange);
        return;
    }
    if ($ready->{allowance_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_allowance_case::run(\&exchange);
        return;
    }
    if ($ready->{allowance_boundaries}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_allowance_boundaries::run(\&exchange);
        return;
    }
    if ($ready->{allowance}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_allowance::run(\&exchange);
        return;
    }
    if ($ready->{allowance_presets}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_allowance_presets::run(\&exchange);
        return;
    }
    if ($ready->{text_qualification}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_text::run(\&exchange);
        return;
    }
    if ($ready->{feedback_read}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_read::run(\&exchange);
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
    # Remaining modes use retired image, pointer, VT or unqualified graphical
    # input routes. Keep the modes visible for their owning controllers, but
    # refuse before selecting a console, matching pixels or sending input.
    die 'smoke:legacy-ui-route-refused';
}

1;
