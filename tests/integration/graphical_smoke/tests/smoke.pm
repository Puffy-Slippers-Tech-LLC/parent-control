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
use onpc_lifecycle ();
use onpc_kiosk_entry ();
use onpc_public_desktop_selection ();
use onpc_station_shortcuts ();
use onpc_kiosk_eligible_choices ();
use onpc_kiosk_multiple ();
use onpc_account_changes ();
use onpc_restricted_station_about ();
use onpc_kiosk_about ();
use onpc_kiosk_preferences_confinement ();
use onpc_kiosk_valid_duration ();
use onpc_request_flow ();
use onpc_kiosk_reminders ();
use onpc_remembered_choices ();
use onpc_kiosk_cancel ();
use onpc_kiosk_escape ();
use onpc_request_choices ();
use onpc_kiosk_no_child ();
use onpc_kiosk_no_approver ();
use onpc_no_child ();
use onpc_no_parent ();
use onpc_disabled_child ();
use onpc_restricted_station ();
use onpc_request_exit ();
use onpc_parent_toggle ();
use onpc_allowance_presets ();
use onpc_allowance ();
use onpc_allowance_boundaries ();
use onpc_allowance_case ();
use onpc_time_explanation ();
use onpc_set_allowance ();
use onpc_fresh_thirty_allowance ();
use onpc_app_restart ();
use onpc_zero_total ();
use onpc_app_rows ();
use onpc_app_launch ();
use onpc_app_rule_changes ();
use onpc_revocation_case ();
use onpc_offline_approvals ();
use onpc_baseline_app_effects ();
use onpc_active_grant_disable ();
use onpc_baseline_journey ();
use onpc_overlay_recovery ();
use onpc_kiosk_recovery ();
use onpc_confinement_usability ();
use onpc_child_isolation ();
use onpc_feedback_read ();
use onpc_feedback_privacy ();
use onpc_feedback_states ();
use onpc_format ();
use onpc_text ();
use onpc_parent_discovery ();
use onpc_journey ();
use onpc_parent ();
use onpc_flow00 ();
use onpc_repeated_operations ();
use onpc_challenges ();
use onpc_product_free_entry ();
use onpc_package_authority ();
use onpc_package_install ();
use onpc_customer_reboot ();
use onpc_chinese_lifecycle ();
use onpc_language_persistence ();
use onpc_parent_presentation ();
use onpc_clean_install ();

# Only fixed stage metadata crosses this local file rendezvous. No guest
# credentials or command output enters the distribution or public test log.
sub exchange {
    my ($stage, $shot, $input) = @_;
    die 'smoke:input-callback' if defined($input) && ref($input) ne 'CODE';
    my $consumed = 0;
    open(my $request, '>', "$stage.request.tmp") or die 'smoke:request';
    print {$request} encode_json({stage => $stage, screenshot => $shot});
    close($request) or die 'smoke:request-close';
    rename("$stage.request.tmp", "$stage.request.json") or die 'smoke:request-publish';
    my $deadline = time + ($stage =~ /\Apublic-/ ? 120 : $stage eq 'setup-detached' ? 1500
        : $stage eq 'ready' ? 600
        # Natural expiry can consume the complete real 25-minute balance, plus
        # observation/transport time. Its controller keeps the product deadline.
        : $stage eq 'minute-progression' || $stage eq 'natural-expiry' || $stage eq 'peer-expiry'
            || $stage eq 'expiry-wait' || $stage eq 'replacement-cross' ? 1800
        : $stage eq 'package-submitted' || $stage eq 'upgrade-submitted' ? 780
        : $stage eq 'reboot-installed-greeter' || $stage eq 'second-reboot-greeter'
            || $stage eq 'reboot-greeter' ? 780 : 420);
    while (!-f "$stage.reply.json") {
        die 'smoke:controller-timeout' if time >= $deadline;
        if (defined($input) && !$consumed && -f "$stage.input.json") {
            die 'smoke:input-file' if -l "$stage.input.json" || -s "$stage.input.json" > 1024;
            open(my $proof, '<', "$stage.input.json") or die 'smoke:input-file';
            my $value = do { local $/; decode_json(<$proof>) };
            close($proof) or die 'smoke:input-close';
            die 'smoke:input-proof' unless ref($value) eq 'HASH' && keys(%$value) == 6
                && ($value->{child} eq 'child' || $value->{child} eq 'existing' || $value->{child} eq 'other-child')
                && $value->{stage} eq $stage && $value->{token} =~ /\A[0-9a-f]{32}\z/
                && $value->{source} =~ /\A[0-9a-f]{64}\z/;
            $consumed = 1; # An uncertain callback can never be replayed.
            $input->($value);
            die 'smoke:input-replay' if -e "$stage.input-done.tmp" || -e "$stage.input-done.json";
            open(my $done, '>', "$stage.input-done.tmp") or die 'smoke:input-done';
            print {$done} encode_json({stage => $stage, token => $value->{token}});
            close($done) or die 'smoke:input-done-close';
            rename("$stage.input-done.tmp", "$stage.input-done.json") or die 'smoke:input-done-publish';
        }
        sleep 0.1;
    }
    die 'smoke:input-missing' if defined($input) && !$consumed;
    open(my $reply, '<', "$stage.reply.json") or die 'smoke:reply';
    local $/;
    return decode_json(<$reply>);
}

sub capture {
    die 'smoke:image-capture-route-refused';
}

sub run {
    my $ready = exchange('ready', undef);
    if ($ready->{local_calendar}) {
        console('sut')->disable();
        record_info('clock', 'Read-only local clock and independent readback verified');
        power('off');
        die 'smoke:shutdown-unverified' unless check_shutdown(0);
        record_info('shutdown', 'Owned VM shutdown verified');
        return;
    }
    if ($ready->{vt6_input_probe}) {
        onpc_password::seal_capture();
        onpc_vt6::select_boot_console();
        onpc_progress::operation('Sending one nonsecret Ctrl+Alt+F6 chord');
        send_key('ctrl-alt-f6');
        exchange('vt6-input-observed', undef);
        die 'vt6-input:controller-must-retain-scene';
    }
    if ($ready->{gdm_credentials}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_gdm::credential_qualification(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{parent_presentation}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_presentation::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{language_persistence}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_language_persistence::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{chinese_lifecycle}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_chinese_lifecycle::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_reminder_editing}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::overlay_reminder_editing(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{kiosk_reminder_binding}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_reminders::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{reminder_child_station_binding}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_reminders::child_station(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{reminder_persistence}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_reminders::persistence(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{reminder_fullscreen_preference}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::reminder_fullscreen_preference(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{panel_language_expiry}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::panel_language_expiry(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{panel_language_refresh}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::panel_language_refresh(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_language}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::overlay_language(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{kiosk_language}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::kiosk_language(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{kiosk_language_history}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::kiosk_language_history(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{kiosk_language_restoration}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::kiosk_language_restoration(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{chinese_native_auth}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::chinese_native_auth(\&exchange);
        return;
    }
    if ($ready->{chinese_kiosk_lifecycle}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_chinese(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{chinese_current_install}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_chinese_current(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{fresh_kiosk_restart}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_kiosk_notice(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{fresh_child_restart}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_child_notice(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{fresh_parent_restart}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_parent_notice(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{restart_notice}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::restart_notice(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{update_no_action}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_no_action(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{update_process_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_process_case(\&exchange, $ready->{invocations},
            $ready->{challenge_bindings}, $ready->{kiosk_request});
        return;
    }
    if ($ready->{update_session_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_session_case(\&exchange, $ready->{invocations},
            $ready->{challenge_bindings}, $ready->{kiosk_request});
        return;
    }
    if ($ready->{update_reboot_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_reboot_case(\&exchange, $ready->{invocations},
            $ready->{challenge_bindings}, $ready->{kiosk_request});
        return;
    }
    if ($ready->{activation_process}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_process(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{activation_session}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_session(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{activation_reboot}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_reboot(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{package_upgrade}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::run_upgrade(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{package_removal}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_lifecycle::run_removal(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
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
    if ($ready->{unrelated_reboot_request}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_customer_reboot::unrelated_request(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
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
    if ($ready->{overlay_cancel}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_cancel::run(\&exchange, 'overlay', $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_escape}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_cancel::run(\&exchange, 'overlay-escape', $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{offline_approvals}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_offline_approvals::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
            $ready->{overlay_request}, $ready->{kiosk_request});
        return;
    }
    if ($ready->{panel_request_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::panel_request_case(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
            $ready->{overlay_request});
        return;
    }
    if ($ready->{overlay_approved}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_cancel::run(\&exchange, 'overlay-approved', $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{remembered_return_entry_diagnosis}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_remembered_choices::enter_return_for_diagnosis(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{remembered_return_diagnosis}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_remembered_choices::repeat_return_for_diagnosis(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{remembered_choices}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_remembered_choices::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{remembered_reverse}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_remembered_choices::run_reverse(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{cross_surface}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::qualify_cross_surface(\&exchange,
            $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{ineligible_approver}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_account_changes::ineligible_approver(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{remove_selected}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_account_changes::remove_selected(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{remove_last_child}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_account_changes::remove_last_child(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{choices_overlay_to_kiosk}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::qualify_choices_overlay_to_kiosk(\&exchange,
            $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_lock_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::overlay_lock_case(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{pending_overlay_lock}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::pending_overlay_lock(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_prompt}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::overlay_prompt(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_language_history}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::overlay_language_history(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_approved_exit}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::overlay_prompt(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, 'approval');
        return;
    }
    if ($ready->{kiosk_delayed_approval} || $ready->{kiosk_delayed_grant_approval}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::kiosk_delayed_approval(\&exchange, $ready->{invocations},
            $ready->{challenge_bindings}, $ready->{kiosk_request},
            $ready->{kiosk_delayed_grant_approval} ? 'grant-dominant' : 'daily-only');
        return;
    }
    if ($ready->{delayed_approval} || $ready->{delayed_grant_approval}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::delayed_approval(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
            $ready->{delayed_grant_approval} ? 'grant-only' : 'daily-only');
        return;
    }
    for my $entry ('new', 'open') {
        if ($ready->{'kiosk_retained_return_' . $entry}) {
            console('sut')->disable();
            exchange('setup-detached', undef);
            onpc_request_flow::kiosk_fresh_return(\&exchange, $ready->{invocations},
                $ready->{challenge_bindings}, $ready->{kiosk_request}, $entry, 'retained');
            return;
        }
        if ($ready->{'kiosk_fresh_return_' . $entry}) {
            console('sut')->disable();
            exchange('setup-detached', undef);
            onpc_request_flow::kiosk_fresh_return(\&exchange, $ready->{invocations},
                $ready->{challenge_bindings}, $ready->{kiosk_request}, $entry);
            return;
        }
        if ($ready->{'approval_return_' . $entry}) {
            console('sut')->disable();
            exchange('setup-detached', undef);
            onpc_request_flow::approval_return(\&exchange, $ready->{invocations},
                $ready->{challenge_bindings}, $ready->{overlay_request}, $entry);
            return;
        }
    }
    if ($ready->{overlay_rejection}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::overlay_prompt(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, 'rejection');
        return;
    }
    for my $binding (['overlay_approval_immediate', 'approval-immediate'],
                     ['overlay_translated_approval', 'approval-translated'],
                     ['overlay_flow_rejection', 'flow-rejection'],
                     ['overlay_flow_cancel', 'flow-cancel']) {
        if ($ready->{$binding->[0]}) {
            console('sut')->disable();
            exchange('setup-detached', undef);
            onpc_request_flow::overlay_prompt(\&exchange, $ready->{invocations},
                $ready->{challenge_bindings}, $binding->[1]);
            return;
        }
    }
    if ($ready->{overlay_choices}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::overlay_choices(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_license}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::overlay_license(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_browser_links}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::overlay_browser_links(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_information}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::overlay_information(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_about}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_about::run_overlay(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_valid_choices}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::overlay_valid_choices(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{shell_panel}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::shell_panel(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{countdown_session}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::countdown_session(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{countdown_minutes}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::countdown_minutes(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{countdown_ticks}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::countdown_ticks(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{countdown_daily}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::countdown_daily(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{countdown_grant}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::countdown_grant(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{countdown_combined}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::countdown_combined(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{grant_work_recovery}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::grant_work_recovery(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, $ready->{kiosk_request});
        return;
    }
    if ($ready->{natural_access}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::natural_access(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{natural_expiry}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::natural_expiry(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{countdown_animation}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::countdown_animation(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{countdown_enabled} || $ready->{countdown_off}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::countdown($ready->{countdown_enabled} ? 1 : 0,
            \&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{jordan_daily_access}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::jordan_daily_access(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{fresh_child_denied}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::fresh_child_denied(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{fresh_child_allowed}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::fresh_child_allowed(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
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
    if ($ready->{parent_website}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_license_viewer_provider::run(\&exchange, 'website');
        return;
    }
    if ($ready->{parent_privacy}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_license_viewer_provider::run(\&exchange, 'privacy');
        return;
    }
    if ($ready->{parent_support}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_license_viewer_provider::run(\&exchange, 'support');
        return;
    }
    if ($ready->{parent_information}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_license_viewer_provider::run(\&exchange, 'information');
        return;
    }
    if ($ready->{parent_links}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_about::run_links(\&exchange);
        return;
    }
    if ($ready->{command_help}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_command_help::run(\&exchange);
        return;
    }
    if ($ready->{retained_entry}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::qualify_retained_entry(\&exchange,
            $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{retained_parent}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::qualify_retained_parent(\&exchange,
            $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{retained_unlock_denied} || $ready->{child_unlock_denied}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::qualify_retained_denial(\&exchange,
            $ready->{retained_unlock_denied} ? 1 : 0, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{retained_unlock_success} || $ready->{child_unlock_success}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::qualify_retained_unlock(\&exchange,
            $ready->{retained_unlock_success} ? 1 : 0, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{lock_recipient}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::qualify_lock_recipient(\&exchange);
        return;
    }
    if ($ready->{lock_surface_command} || $ready->{lock_surface_supplied}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::qualify_lock(\&exchange, $ready->{lock_surface_supplied} ? 1 : 0);
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
    if ($ready->{parent_dialog_language}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent::qualify_dialog_language(\&exchange);
        return;
    }
    if ($ready->{parent_rtl}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent::qualify_rtl(\&exchange);
        return;
    }
    if ($ready->{parent_hebrew_policy}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent::qualify_hebrew_policy(\&exchange);
        return;
    }
    if ($ready->{parent_language_isolation}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent::qualify_language_isolation(\&exchange);
        return;
    }
    if ($ready->{parent_language}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent::qualify_language(\&exchange);
        return;
    }
    if ($ready->{parent_search_launch}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_search_launch::run(\&exchange);
        return;
    }
    if ($ready->{native_grid_soft_blocked}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'enabled', 'grid', 'soft-blocked');
        return;
    }
    if ($ready->{native_grid_hard_blocked}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'enabled', 'grid', 'hard-blocked');
        return;
    }
    if ($ready->{native_desktop_soft_blocked}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'enabled', 'desktop', 'soft-blocked');
        return;
    }
    if ($ready->{native_desktop_hard_blocked}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'enabled', 'desktop', 'hard-blocked');
        return;
    }
    if ($ready->{native_desktop_allowed}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, 'enabled', 'desktop');
        return;
    }
    if ($ready->{native_files_allowed}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, 'enabled', 'files');
        return;
    }
    if ($ready->{native_files_hard_blocked}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'enabled', 'files', 'hard-blocked');
        return;
    }
    if ($ready->{native_files_soft_blocked}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'enabled', 'files', 'soft-blocked');
        return;
    }
    if ($ready->{native_grid_allowed}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, 'enabled', 'grid');
        return;
    }
    if ($ready->{native_command_soft_blocked}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'enabled', 'command', 'soft-blocked');
        return;
    }
    if ($ready->{native_command_soft_blocked_disabled}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'disabled', 'command', 'soft-blocked');
        return;
    }
    if ($ready->{native_command_hard_blocked}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'enabled', 'command', 'hard-blocked');
        return;
    }
    if ($ready->{native_command_hard_blocked_disabled}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'disabled', 'command', 'hard-blocked');
        return;
    }
    if ($ready->{flatpak_grid_allowed} || $ready->{flatpak_grid_hard_blocked}
            || $ready->{flatpak_grid_soft_blocked}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'enabled', 'grid', $ready->{flatpak_grid_hard_blocked}
                                ? 'hard-blocked' : $ready->{flatpak_grid_soft_blocked}
                                ? 'soft-blocked' : 'allowed', 'flatpak');
        return;
    }
    for my $binding (
        ['flatpak_command_allowed', 'enabled', 'allowed'],
        ['flatpak_command_allowed_disabled', 'disabled', 'allowed'],
        ['flatpak_command_hard_blocked', 'enabled', 'hard-blocked'],
        ['flatpak_command_hard_blocked_disabled', 'disabled', 'hard-blocked'],
        ['flatpak_command_soft_blocked', 'enabled', 'soft-blocked'],
        ['flatpak_command_soft_blocked_disabled', 'disabled', 'soft-blocked']) {
        next unless $ready->{$binding->[0]};
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            $binding->[1], 'command', $binding->[2], 'flatpak');
        return;
    }
    if ($ready->{snap_grid_allowed}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'enabled', 'grid', 'allowed', 'snap');
        return;
    }
    if ($ready->{snap_command_allowed}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'enabled', 'command', 'allowed', 'snap');
        return;
    }
    if ($ready->{snap_command_allowed_disabled}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
                            'disabled', 'command', 'allowed', 'snap');
        return;
    }
    if ($ready->{native_command_allowed}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{native_command_allowed_disabled}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_launch::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, 'disabled');
        return;
    }
    if ($ready->{retained_app_visits}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::retained_app_visits(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{native_desktop_route}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::native_policy_closure(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, 'desktop');
        return;
    }
    if ($ready->{native_desktop_new_window}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::native_desktop_new_window(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{native_desktop_usable}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::native_desktop_usable(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{native_files_usable}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::native_files_usable(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{app_activity}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::app_activity(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{shared_target_launchers}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::shared_target_launchers(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{versioned_appimage_assets}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::versioned_appimage_assets(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{native_space_path} || $ready->{native_comma_path}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::native_space_path(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
            $ready->{native_comma_path} ? 'comma' : 'space');
        return;
    }
    if ($ready->{native_denial}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::native_denial(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{flatpak_temporary_access} || $ready->{flatpak_grid_temporary_access}
            || $ready->{native_grid_temporary_access} || $ready->{native_desktop_temporary_access}
            || $ready->{native_grid_kiosk_temporary_access}
            || $ready->{native_command_kiosk_temporary_access} || $ready->{native_files_kiosk_temporary_access}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::flatpak_temporary_access(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
            $ready->{flatpak_grid_temporary_access} || $ready->{native_grid_temporary_access}
                || $ready->{native_grid_kiosk_temporary_access} ? 'grid'
                : $ready->{native_desktop_temporary_access} ? 'desktop'
                : $ready->{native_files_kiosk_temporary_access} ? 'files' : 'command',
            $ready->{native_grid_temporary_access} || $ready->{native_grid_kiosk_temporary_access}
                || $ready->{native_command_kiosk_temporary_access}
                || $ready->{native_files_kiosk_temporary_access} || $ready->{native_desktop_temporary_access} ? 'native' : 'flatpak',
            $ready->{native_grid_temporary_access} || $ready->{flatpak_grid_temporary_access}
                || $ready->{native_desktop_temporary_access} ? 'overlay' : 'kiosk');
        return;
    }
    if ($ready->{flatpak_retained_work}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::flatpak_retained_work(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{flatpak_policy_closure}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::flatpak_policy_closure(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{native_files_routes}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::native_policy_closure(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, 'files');
        return;
    }
    if ($ready->{native_policy_closure}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::native_policy_closure(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{app_rule_changes_case} || $ready->{app_rule_changes_pattern_case}
        || $ready->{app_rule_changes_disabled_case} || $ready->{app_rule_changes_disabled_pattern_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rule_changes::run(\&exchange, $ready->{invocations},
            $ready->{challenge_bindings}, $ready->{kiosk_request},
            ($ready->{app_rule_changes_pattern_case} || $ready->{app_rule_changes_disabled_pattern_case})
                ? 'pattern' : 'precise',
            ($ready->{app_rule_changes_disabled_case} || $ready->{app_rule_changes_disabled_pattern_case}) ? 1 : 0);
        return;
    }
    if ($ready->{flatpak_grid}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::flatpak_grid(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{snap_grid}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::snap_grid(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{snap_command_usable}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::snap_command_usable(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{flatpak_command_usable}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::flatpak_command_usable(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{game_time_extension}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::game_time_extension(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, $ready->{overlay_request});
        return;
    }
    if ($ready->{game_access}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::game_access(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, $ready->{kiosk_request});
        return;
    }
    if ($ready->{game_expiry}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::game_expiry(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, $ready->{kiosk_request});
        return;
    }
    if ($ready->{game_activity}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::game_activity(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{native_app}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::native_app(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{native_grid_usable}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::native_grid_usable(\&exchange);
        return;
    }
    if ($ready->{riley_native_grid}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::riley_native_grid(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
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
    if ($ready->{restricted_station_cancelled}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_restricted_station::run(\&exchange, 'cancelled');
        return;
    }
    if ($ready->{restricted_station_denied}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_restricted_station::run(\&exchange, 'denied');
        return;
    }
    if ($ready->{restricted_station}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_restricted_station::run(\&exchange);
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
    if ($ready->{kiosk_escape}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_escape::run(\&exchange);
        return;
    }
    if ($ready->{kiosk_approved}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_cancel::run(\&exchange, 'approved', $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{kiosk_cancel}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_cancel::run(\&exchange);
        return;
    }
    if ($ready->{kiosk_rejection}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::run(\&exchange, 'rejection');
        return;
    }
    if ($ready->{kiosk_approved_flow}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::run(\&exchange, 'approved-flow');
        return;
    }
    if ($ready->{approval_flow_rejection} || $ready->{approval_flow_cancel}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::run(\&exchange, $ready->{approval_flow_rejection} ? 'flow-rejection' : 'flow-cancel');
        return;
    }
    if ($ready->{auth_result}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::run(\&exchange, 'immediate');
        return;
    }
    if ($ready->{kiosk_approval}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::run(\&exchange, 'approval', $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{baseline_auth_pause}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::auth_pause(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{active_grant_disable}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_active_grant_disable::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, 'public');
        return;
    }
    if ($ready->{active_grant_disable_engineering}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_active_grant_disable::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, 'engineering');
        return;
    }
    if ($ready->{baseline_app_effects}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_baseline_app_effects::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{kiosk_recovery}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_recovery::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{overlay_recovery}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_overlay_recovery::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{baseline_journey}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_baseline_journey::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{child_isolation}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_child_isolation::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{kiosk_optional_artwork}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_confinement_usability::optional_artwork(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{kiosk_agent_recovery}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_confinement_usability::service_recovery(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, 1);
        return;
    }
    if ($ready->{kiosk_service_recovery}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_confinement_usability::service_recovery(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{confinement_usability}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_confinement_usability::run(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{mate_prompt}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_flow::run(\&exchange, 'mate');
        return;
    }
    if ($ready->{multiple_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_multiple::run(\&exchange, 1);
        return;
    }
    if ($ready->{kiosk_about}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_about::run(\&exchange);
        return;
    }
    if ($ready->{kiosk_preferences_confinement}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_preferences_confinement::run(\&exchange);
        return;
    }
    if ($ready->{restricted_station_about}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_restricted_station_about::run(\&exchange);
        return;
    }
    if ($ready->{kiosk_multiple}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_multiple::run(\&exchange);
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
    if ($ready->{kiosk_feedback_confinement}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_eligible_choices::run(\&exchange, 1);
        return;
    }
    if ($ready->{kiosk_notification_wellbeing}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_eligible_choices::run(\&exchange, 2);
        return;
    }
    if ($ready->{kiosk_eligible_choices}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_kiosk_eligible_choices::run(\&exchange);
        return;
    }
    if ($ready->{station_shortcuts}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_station_shortcuts::run(\&exchange,
            $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{public_desktop_selection}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_public_desktop_selection::run(\&exchange,
            $ready->{invocations}, $ready->{challenge_bindings});
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
    if ($ready->{search_filters}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_fresh_thirty_allowance::search_filters(\&exchange);
        return;
    }
    if ($ready->{pattern_files_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_fresh_thirty_allowance::pattern_files_case(
            \&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{match_editor_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_fresh_thirty_allowance::match_editor_case(
            \&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{catalogue_update_case} || $ready->{catalogue_remove_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_fresh_thirty_allowance::catalogue_update_case(
            \&exchange, $ready->{invocations}, $ready->{challenge_bindings},
            $ready->{catalogue_remove_case} ? 'remove' : 'update');
        return;
    }
    if ($ready->{match_reopen_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_fresh_thirty_allowance::match_reopen_case(
            \&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{shared_launchers_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_fresh_thirty_allowance::shared_launchers_case(
            \&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{special_paths_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_fresh_thirty_allowance::special_paths_case(
            \&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{match_save_cancel}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::match_save_cancel(\&exchange);
        return;
    }
    if ($ready->{named_app_set}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::qualify_named_app_set(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{policy_edit}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::policy_edit(\&exchange);
        return;
    }
    if ($ready->{access_choices}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::access_choices(\&exchange);
        return;
    }
    if ($ready->{match_editor}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::match_editor_validation(\&exchange);
        return;
    }
    if ($ready->{rejected_parent_rule}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::rejected_parent_rule(\&exchange);
        return;
    }
    if ($ready->{parent_error_report}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_fresh_thirty_allowance::parent_error_report(\&exchange);
        return;
    }
    if ($ready->{policy_legend}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::policy_legend(\&exchange);
        return;
    }
    if ($ready->{catalogue_filters}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::catalogue_filters(\&exchange);
        return;
    }
    if ($ready->{catalogue_search}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::catalogue_search(\&exchange);
        return;
    }
    if ($ready->{flatpak_fixtures}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::flatpak_fixtures(\&exchange);
        return;
    }
    if ($ready->{native_fixtures}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::native_fixtures(\&exchange);
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
    if ($ready->{fresh_thirty_allowance}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_fresh_thirty_allowance::run(\&exchange);
        return;
    }
    if ($ready->{jordan_thirty_allowance}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_fresh_thirty_allowance::run(\&exchange, 'existing');
        return;
    }
    if ($ready->{extension_login}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::extension_login(\&exchange,
            $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{extension_parent}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::extension_parent(\&exchange,
            $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{system_foreground_revoke}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::foreground_revoke(\&exchange,
            $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{system_session_replacement}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::session_replacement(\&exchange,
            $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{system_broker_stop}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::broker_stop(\&exchange,
            $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{system_graphical_expiry}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_desktop_session::system_graphical_expiry(\&exchange,
            $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{switch_user_expiry_parent}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::switch_user_expiry_parent(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{switch_user_expiry_other_child}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_rows::switch_user_expiry_other_child(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{suspend_active_grant}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_challenges::suspend_active_grant(\&exchange, $ready->{invocations}, $ready->{challenge_bindings},
            $ready->{kiosk_request});
        return;
    }
    if ($ready->{daily_soft_profile} || $ready->{daily_soft_expiry} || $ready->{daily_soft_unlock}
            || $ready->{daily_soft_fresh_login} || $ready->{daily_soft_allowance_edit}
            || $ready->{daily_soft_toggle} || $ready->{daily_soft_app_save} || $ready->{daily_soft_revoke}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        my $run = $ready->{daily_soft_expiry} || $ready->{daily_soft_unlock}
                || $ready->{daily_soft_fresh_login} || $ready->{daily_soft_allowance_edit}
                || $ready->{daily_soft_toggle} || $ready->{daily_soft_app_save} || $ready->{daily_soft_revoke}
                ? \&onpc_app_rows::daily_soft_expiry
                                            : \&onpc_app_rows::daily_soft_profile;
        $run->(\&exchange, $ready->{invocations}, $ready->{challenge_bindings}, $ready->{kiosk_request},
            $ready->{daily_soft_unlock} ? ('unlock')
                : $ready->{daily_soft_fresh_login} ? ('fresh-login')
                : $ready->{daily_soft_allowance_edit} ? ('allowance-edit')
                : $ready->{daily_soft_toggle} ? ('toggle')
                : $ready->{daily_soft_app_save} ? ('app-save')
                : $ready->{daily_soft_revoke} ? ('revoke') : ());
        return;
    }
    if ($ready->{time_profiles_dominant}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        require onpc_set_allowance;
        onpc_set_allowance::qualify_dominant(\&exchange, $ready->{invocations},
            $ready->{challenge_bindings}, $ready->{kiosk_request});
        return;
    }
    if ($ready->{grant_only_profile} || $ready->{grant_only_revoke} || $ready->{time_profiles_grant}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        require onpc_set_allowance;
        onpc_set_allowance::qualify_grant(\&exchange, $ready->{invocations},
            $ready->{challenge_bindings}, $ready->{grant_only_revoke} ? 1 : 0,
            $ready->{time_profiles_grant} ? 4 : 0);
        return;
    }
    if ($ready->{time_profiles_daily} || $ready->{time_profiles_same}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_set_allowance::qualify_daily(\&exchange, $ready->{time_profiles_same} ? 1 : 0);
        return;
    }
    if ($ready->{set_allowance}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_set_allowance::run(\&exchange);
        return;
    }
    if ($ready->{expired_daily_replacement} || $ready->{expired_daily_replacement_retained}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        require onpc_lifecycle;
        onpc_lifecycle::expired_daily_replacement(\&exchange, $ready->{invocations},
            $ready->{challenge_bindings}, $ready->{kiosk_request},
            $ready->{expired_daily_replacement_retained} ? 1 : 0);
        return;
    }
    if ($ready->{app_restart_expired} || $ready->{sign_out_in_expired} || $ready->{reboot_expired}
            || $ready->{suspend_wake_expired}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        require onpc_lifecycle;
        onpc_lifecycle::app_restart_expired(\&exchange, $ready->{invocations},
            $ready->{challenge_bindings}, $ready->{kiosk_request},
            ($ready->{sign_out_in_expired} || $ready->{reboot_expired}) ? 1 : 0,
            $ready->{reboot_expired} ? 1 : 0, $ready->{suspend_wake_expired} ? 1 : 0);
        return;
    }
    if ($ready->{app_restart_active} || $ready->{idle_active_expired} || $ready->{suspend_wake_active}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        require onpc_lifecycle;
        onpc_lifecycle::app_restart_active(\&exchange, $ready->{invocations},
            $ready->{challenge_bindings}, $ready->{kiosk_request}, 0, 0,
            $ready->{idle_active_expired} ? 1 : 0, $ready->{suspend_wake_active} ? 1 : 0);
        return;
    }
    if ($ready->{sign_out_in_active} || $ready->{reboot_active}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_lifecycle::app_restart_active(\&exchange, $ready->{invocations},
            $ready->{challenge_bindings}, $ready->{kiosk_request}, 1, $ready->{reboot_active} ? 1 : 0);
        return;
    }
    if ($ready->{app_restart}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_app_restart::run(\&exchange);
        return;
    }
    if ($ready->{real_interval}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_parent_about::run_interval(\&exchange);
        return;
    }
    if ($ready->{revoke_cancel}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_time_explanation::revoke_cancel(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{revocation}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_time_explanation::revocation(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        return;
    }
    if ($ready->{time_explanation}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_time_explanation::run(\&exchange);
        return;
    }
    if ($ready->{revocation_case} || $ready->{revocation_remaining_case} || $ready->{revocation_no_grant_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_revocation_case::run(\&exchange, $ready->{invocations},
            $ready->{challenge_bindings}, $ready->{kiosk_request},
            $ready->{revocation_no_grant_case} ? 15 : $ready->{revocation_remaining_case} ? 30 : 0);
        return;
    }
    if ($ready->{grant_access_case} || $ready->{grant_retained_access_case}
        || $ready->{combined_access_case} || $ready->{combined_retained_access_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        if ($ready->{combined_retained_access_case}) {
            onpc_allowance_case::combined_retained(\&exchange, $ready->{invocations},
                $ready->{challenge_bindings}, $ready->{kiosk_request});
        } elsif ($ready->{combined_access_case}) {
            onpc_allowance_case::combined_new(\&exchange, $ready->{invocations},
                $ready->{challenge_bindings}, $ready->{kiosk_request});
        } elsif ($ready->{grant_retained_access_case}) {
            onpc_allowance_case::grant_only_retained(\&exchange, $ready->{invocations},
                $ready->{challenge_bindings}, $ready->{kiosk_request});
        } else {
            onpc_allowance_case::grant_only_new(\&exchange, $ready->{invocations},
                $ready->{challenge_bindings}, $ready->{kiosk_request});
        }
        return;
    }
    if ($ready->{daily_access_case} || $ready->{daily_retained_access_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        if ($ready->{daily_retained_access_case}) {
            onpc_allowance_case::daily_only_retained(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        } else {
            onpc_allowance_case::daily_only_new(\&exchange, $ready->{invocations}, $ready->{challenge_bindings});
        }
        return;
    }
    if ($ready->{allowance_case}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_allowance_case::run(\&exchange);
        return;
    }
    if ($ready->{save_order}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_allowance_case::run(\&exchange, 'save-order');
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
    if ($ready->{feedback_draft}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_privacy::run(\&exchange, 'draft');
        return;
    }
    if ($ready->{feedback_validation}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_privacy::run(\&exchange, 'validation');
        return;
    }
    if ($ready->{feedback_attachments}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_privacy::run(\&exchange, 'attachments');
        return;
    }
    if ($ready->{feedback_length}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_states::run_length(\&exchange);
        return;
    }
    if ($ready->{feedback_rejection}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_states::run_rejection(\&exchange);
        return;
    }
    if ($ready->{window_switch}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_read::run_window_switch(\&exchange);
        return;
    }
    if ($ready->{feedback_link_semantics}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_format::run_links(\&exchange);
        return;
    }
    if ($ready->{feedback_formats}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_format::run_formats(\&exchange);
        return;
    }
    if ($ready->{feedback_block_semantics}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_format::run_blocks(\&exchange);
        return;
    }
    if ($ready->{format_qualification}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_format::run(\&exchange);
        return;
    }
    if ($ready->{named_child_custom_saves}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_states::run_named_child_custom_saves(\&exchange);
        return;
    }
    if ($ready->{custom_save_trace}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_states::run_custom_save_trace(\&exchange);
        return;
    }
    if ($ready->{parent_diagnostic_export}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_privacy::run(\&exchange, 'export');
        return;
    }
    if ($ready->{diagnostic_export}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_read::run_diagnostic_export(\&exchange);
        return;
    }
    if ($ready->{save_chooser}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_read::run_save_chooser(\&exchange);
        return;
    }
    if ($ready->{feedback_collection}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_states::run_collection(\&exchange);
        return;
    }
    if ($ready->{parent_save_trace}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_states::run_parent_save_trace(\&exchange);
        return;
    }
    if ($ready->{accessibility_input_trace}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_states::run_accessibility_trace(\&exchange);
        return;
    }
    if ($ready->{compose_observation}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_states::run_composition(\&exchange);
        return;
    }
    if ($ready->{trace_transition}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_states::run_transition(\&exchange);
        return;
    }
    if ($ready->{trace_stable_state}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_states::run_trace(\&exchange);
        return;
    }
    if ($ready->{feedback_states}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_states::run(\&exchange);
        return;
    }
    if ($ready->{feedback_reset}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_privacy::run_reset(\&exchange);
        return;
    }
    if ($ready->{feedback_privacy}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_privacy::run(\&exchange);
        return;
    }
    if ($ready->{attachment_boundaries}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_read::run_file_chooser(\&exchange, 3);
        return;
    }
    if ($ready->{attachment_preview}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_read::run_file_chooser(\&exchange, 2);
        return;
    }
    if ($ready->{attachment_items}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_read::run_file_chooser(\&exchange, 1);
        return;
    }
    if ($ready->{file_chooser}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_feedback_read::run_file_chooser(\&exchange);
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
    if ($ready->{vt6_auth}) {
        onpc_vt6::authenticate_text(\&exchange);
        console('sut')->disable();
        power('off');
        die 'smoke:shutdown-unverified' unless check_shutdown(0);
        record_info('shutdown', 'Owned VM shutdown verified');
        return;
    }
    # Remaining modes use retired image, pointer, VT or unqualified graphical
    # input routes. Keep the modes visible for their owning controllers, but
    # refuse before selecting a console, matching pixels or sending input.
    die 'smoke:legacy-ui-route-refused';
}

1;
