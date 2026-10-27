package onpc_public_desktop_selection;
use strict;
use warnings;
use testapi ();
use onpc_gdm ();
use onpc_journey ();
use onpc_password ();
use onpc_progress ();

sub select_account {
    my ($journey, $prefix) = @_;
    my $list = $journey->invoke("$prefix-list");
    my $focused = $journey->highlight_choice($list, "$prefix-list", "$prefix-focused");
    $journey->consume_observation("$prefix-focused", $focused);
    testapi::send_key('ret');
}

sub parent_settings {
    my ($journey, $prefix, $restore) = @_;
    onpc_gdm::sign_in_challenge($journey, $prefix,
        "$prefix-installed-greeter", "$prefix-parent-focused", "$prefix-desktop");
    $journey->invoke("$prefix-$_") for qw(parent-command parent-window
        child-picker-opened child-choice-highlighted parent-selected toggle saved);
    $journey->invoke("$prefix-restored") if $restore;
    $journey->seen("$prefix-logout");
    $journey->invoke("$prefix-returned");
}

sub run {
    my ($exchange, $invocations, $challenges) = @_;
    die 'public-desktop:arguments' unless @_ == 3 && ref($exchange) eq 'CODE';
    onpc_progress::operation('Qualifying the public desktop choices and their launch results');
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'public-desktop-selection', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    parent_settings($journey, 'public-setup', 0);
    select_account($journey, 'public-standard');
    $journey->invoke($_) for qw(public-standard-open public-standard-selected);
    onpc_password::enter_gdm_challenge($journey, 'standard-login');
    testapi::send_key('ret');
    $journey->invoke('public-standard-desktop');
    $journey->invoke('public-standard-launch');
    $journey->seen('public-standard-logout');
    $journey->invoke('public-standard-returned');
    for my $attempt ('direct', 'carry') {
        if ($attempt eq 'carry') {
            select_account($journey, 'public-cancel');
            $journey->invoke($_) for qw(public-cancel-open public-cancel-selected
                public-cancel-prompt public-cancel-returned);
        }
        select_account($journey, "public-$attempt");
        $journey->invoke("public-$attempt-$_") for qw(open selected launch child approver result exit returned);
    }
    $journey->invoke('public-routing-restored');
    for my $prefix ('public-restored', 'public-fresh') {
        select_account($journey, "$prefix-station");
        $journey->invoke("$prefix-station-branch");
        $journey->invoke("$prefix-$_") for qw(child approver usable cancel returned);
    }
    parent_settings($journey, 'public-policy-restore', 1);
    $journey->finish();
}

1;
