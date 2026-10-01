package onpc_kiosk_cancel;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_desktop_session ();
use onpc_app_rows ();
use onpc_request_flow ();
use onpc_journey ();

sub run {
    onpc_progress::operation('Preparing a kiosk request and taking its declared exit');
    my ($exchange, $exit, $declared, $challenges) = @_;
    $exit //= 'cancel';
    die 'kiosk-cancel:arguments' unless (@_ == 1 || @_ == 4 && ($exit eq 'approved' || $exit eq 'overlay'))
        && ref($exchange) eq 'CODE';
    return overlay_cancel($exchange, $declared, $challenges) if $exit eq 'overlay';
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
    onpc_progress::operation('Cancelling the child overlay and resuming the original activity');
    my ($exchange, $declared, $challenges) = @_;
    die 'overlay-cancel:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'overlay-cancel', review => 0);
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
    my $activity = onpc_journey->new(exchange => sub { $exchange->('activity-' . $_[0], $_[1]) },
        prefix => 'overlay-cancel-activity', review => 0);
    onpc_app_rows::native_usable_app($activity, 'command', $activity->seen('desktop'));
    onpc_app_rows::native_read_activity($activity, 'capture');
    onpc_request_flow::overlay_entry($journey, 'direct', 'command');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
        'fixture-child', 'fixture-parent', 75, 1, 'overlay');
    $journey->consume_observation('cancel', $journey->seen('cancel'));
    $journey->consume_observation('cancel-returned', $journey->seen('cancel-returned'));
    onpc_app_rows::native_read_activity($activity, 'returned');
    my $resumed = onpc_journey->new(exchange => sub { $exchange->('resumed-' . $_[0], $_[1]) },
        prefix => 'overlay-cancel-resumed', review => 0);
    onpc_app_rows::native_use_app($resumed, $resumed->seen('opened'));
    onpc_app_rows::native_finish_app($activity);
    $journey->finish();
}
1;
