package onpc_kiosk_cancel;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_desktop_session ();
use onpc_app_rows ();
use onpc_request_flow ();
use onpc_request_exit ();
use onpc_journey ();

sub run {
    onpc_progress::operation('Preparing a kiosk request and taking its declared exit');
    my ($exchange, $exit, $declared, $challenges) = @_;
    $exit //= 'cancel';
    die 'kiosk-cancel:arguments' unless (@_ == 1 || @_ == 4 && ($exit eq 'approved' || $exit eq 'overlay' || $exit eq 'overlay-escape'))
        && ref($exchange) eq 'CODE';
    return overlay_cancel($exchange, $declared, $challenges,
        $exit eq 'overlay-escape' ? 'escape' : 'cancel') if $exit =~ /^overlay/;
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $exit eq 'approved' ? 'kiosk-approval' : 'kiosk-cancel', review => 0);
    if ($exit eq 'approved') {
        $journey->declare_invocations($declared);
        $journey->declare_challenges($challenges);
    }
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    onpc_request_flow::daily_station_entry($journey);
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
                               'fixture-child', 'fixture-parent', 75, 1);
    if ($exit eq 'approved') {
        onpc_request_flow::approve($journey, 'fixture-child', 'fixture-parent', 75, 1, 'immediate');
        onpc_gdm::sign_in_challenge($journey, 'child-login',
            'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
        $journey->consume_observation('countdown', $journey->seen('countdown'));
    } else {
        for my $stage ('cancel-action', 'cancel-returned') {
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    }
    $journey->finish();
}

sub overlay_cancel {
    onpc_progress::operation('Exiting the child overlay and resuming the original activity');
    my ($exchange, $declared, $challenges, $exit) = @_;
    $exit //= 'cancel';
    die 'overlay-cancel:arguments' unless (@_ == 3 || @_ == 4) && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ($exit eq 'cancel' || $exit eq 'escape');
    my $prefix = 'overlay-' . $exit;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => $prefix, review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->consume_observation('allowance-configured', $journey->seen('allowance-configured'));
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    my $activity = onpc_app_rows::native_activity_entry($journey, 'activity', 'command');
    onpc_request_flow::overlay_entry($journey, 'direct', 'command');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
        'fixture-child', 'fixture-parent', 75, 1, 'overlay');
    if ($exit eq 'escape') {
        onpc_request_exit::escape($journey);
    } else {
        $journey->consume_observation('cancel', $journey->seen('cancel'));
        $journey->consume_observation('cancel-returned', $journey->seen('cancel-returned'));
    }
    onpc_app_rows::native_read_activity($activity, 'returned');
    onpc_app_rows::native_activity_resume($journey, 'resumed');
    onpc_app_rows::native_finish_app($activity);
    $journey->finish();
}
1;
