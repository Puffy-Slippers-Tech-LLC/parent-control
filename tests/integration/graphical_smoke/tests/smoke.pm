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
use onpc_request_choices ();
use onpc_request_exit ();
use onpc_parent_toggle ();
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
    if ($ready->{request_choices}) {
        console('sut')->disable();
        exchange('setup-detached', undef);
        onpc_request_choices::run(\&exchange);
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
