package onpc_kiosk_reminders;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_allowance_boundaries ();
use onpc_request_flow ();
use onpc_desktop_session ();
use onpc_app_rows ();

sub run {
    onpc_progress::operation('Qualifying child-bound reminder saves across request surfaces');
    my ($exchange, $invocations, $challenges) = @_;
    die 'kiosk-reminders:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'kiosk-reminders', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for ('allowance-configured', 'riley-policy-before');
    onpc_allowance_boundaries::select_child($journey, 'jordan');
    $journey->seen($_) for ('jordan-enabled', 'jordan-saved', 'jordan-policy-before',
        'parent-logout-ready', 'parent-logout', 'parent-logged-out');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    onpc_request_flow::overlay_entry($journey, 'direct', 'command');
    $journey->seen($_) for ('initial-save', 'overlay-before', 'overlay-defaults',
        'overlay-created', 'overlay-saved', 'overlay-saved-form', 'overlay-exit',
        'overlay-returned', 'child-logout', 'child-logged-out');
    onpc_gdm::enter_station($journey, 'initial-');
    $journey->seen($_) for ('jordan-language', 'jordan-language-save', 'jordan-jamie',
        'jordan-before', 'jordan-reminders-before', 'jordan-close',
        'riley-select', 'riley-saved-read', 'riley-edited', 'riley-saved', 'riley-reopened',
        'riley-close', 'riley-saved-form', 'approver-select', 'approver-reminders',
        'approver-close', 'approver-form', 'jordan-select', 'jordan-reminders-after',
        'jordan-after-close', 'jordan-after', 'riley-return-select', 'riley-return-read',
        'riley-return-close', 'riley-return-form', 'station-exit', 'station-returned');
    onpc_gdm::sign_in_challenge($journey, 'renewed-child',
        'renewed-installed-greeter', 'renewed-child-focused', 'renewed-desktop');
    onpc_request_flow::overlay_entry($journey, 'renewed', 'command');
    $journey->seen($_) for ('overlay-final-before', 'overlay-final-read',
        'overlay-restored-draft', 'overlay-restored-save', 'overlay-restored-read', 'overlay-final-close',
        'overlay-final-form', 'overlay-final-exit', 'overlay-final-returned',
        'final-child-logout', 'final-child-logged-out');
    $desktop = onpc_gdm::sign_in_challenge($journey, 'return-parent',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
    onpc_parent::launch($journey, $desktop, 'management', 'return-desktop');
    $selected = onpc_parent::select_child($journey, 'child', $journey->seen('return-child-picker-opened'),
        'return-child-picker-opened', 'return-child-choice-highlighted', 'return-parent-selected');
    $journey->consume_observation('return-parent-selected', $selected);
    $journey->seen('riley-policy-after');
    onpc_allowance_boundaries::select_child($journey, 'jordan-final');
    $journey->seen('jordan-policy-after');
    $journey->finish();
}

sub child_station {
    onpc_progress::operation('Checking Jordan reminders and Riley station deletion persistence');
    my ($exchange, $invocations, $challenges) = @_;
    die 'reminder-child-station:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'reminder-child-station', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for ('allowance-configured', 'riley-policy-before');
    onpc_allowance_boundaries::select_child($journey, 'jordan');
    $journey->seen($_) for ('jordan-allowance-configured', 'jordan-policy-before',
        'parent-logout-ready', 'parent-logout', 'parent-logged-out');
    onpc_gdm::enter_station($journey, 'initial-');
    $journey->seen($_) for ('jordan-language', 'jordan-language-save', 'jordan-jamie',
        'jordan-before', 'jordan-reminders-before', 'jordan-close', 'defaults-riley-select',
        'riley-defaults-before', 'riley-defaults-close', 'defaults-jordan-select',
        'defaults-station-exit', 'defaults-station-returned');
    onpc_gdm::sign_in_challenge($journey, 'jordan-login',
        'jordan-installed-greeter', 'jordan-standard-focused', 'jordan-desktop');
    $journey->seen($_) for ('jordan-overlay-launch', 'jordan-overlay-ready', 'jordan-overlay-read',
        'jordan-overlay-close', 'jordan-overlay-exit', 'jordan-overlay-returned',
        'jordan-logout', 'jordan-logged-out');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    onpc_request_flow::overlay_entry($journey, 'direct', 'command');
    $journey->seen($_) for ('overlay-defaults', 'overlay-created',
        'overlay-saved', 'overlay-saved-form', 'overlay-exit', 'overlay-returned',
        'child-logout', 'child-logged-out');
    onpc_gdm::enter_station($journey, 'renewed-');
    $journey->seen($_) for ('riley-select', 'riley-saved-read', 'riley-delete-cancel-draft',
        'riley-delete-cancel', 'riley-cancel-read', 'riley-delete-save-draft', 'riley-delete-save',
        'riley-deleted-read', 'riley-close', 'riley-saved-form', 'jordan-select',
        'jordan-reminders-after', 'jordan-after-close', 'jordan-after', 'station-exit', 'station-returned');
    $desktop = onpc_gdm::sign_in_challenge($journey, 'return-parent',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
    onpc_parent::launch($journey, $desktop, 'management', 'return-desktop');
    $selected = onpc_parent::select_child($journey, 'child', $journey->seen('return-child-picker-opened'),
        'return-child-picker-opened', 'return-child-choice-highlighted', 'return-parent-selected');
    $journey->consume_observation('return-parent-selected', $selected);
    $journey->seen('riley-policy-after');
    onpc_allowance_boundaries::select_child($journey, 'jordan-final');
    $journey->seen('jordan-policy-after');
    $journey->finish();
}

sub persistence {
    onpc_progress::operation('Saving child reminders and checking both accounts after a restart');
    my ($exchange, $invocations, $challenges) = @_;
    die 'reminder-persistence:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'reminder-persistence', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for ('allowance-configured', 'riley-policy-before');
    onpc_allowance_boundaries::select_child($journey, 'jordan');
    $journey->seen($_) for ('jordan-allowance-configured', 'jordan-policy-before',
        'parent-logout-ready', 'parent-logout', 'parent-logged-out');
    onpc_gdm::enter_station($journey, 'initial-');
    $journey->seen($_) for ('jordan-language', 'jordan-language-save', 'jordan-jamie',
        'jordan-before', 'jordan-defaults', 'jordan-defaults-close', 'defaults-riley-select',
        'riley-defaults', 'riley-defaults-close', 'defaults-jordan-select',
        'initial-station-exit', 'initial-station-returned');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    onpc_request_flow::overlay_entry($journey, 'direct', 'command');
    $journey->seen($_) for ('overlay-defaults', 'overlay-created', 'overlay-edited',
        'overlay-saved', 'overlay-saved-form', 'overlay-exit', 'overlay-returned',
        'child-logout', 'child-logged-out');
    onpc_gdm::enter_station($journey, 'renewed-');
    $journey->seen($_) for ('riley-select', 'station-saved-read', 'station-delete-draft',
        'station-cancel', 'station-cancel-read', 'station-clear-draft', 'station-empty-save',
        'station-empty-read', 'station-empty-close', 'station-riley-form',
        'station-exit', 'station-returned');
    onpc_gdm::sign_in_challenge($journey, 'reboot-parent',
        'reboot-parent-installed-greeter', 'reboot-parent-parent-focused', 'reboot-parent-desktop');
    $journey->seen($_) for ('reboot-requested', 'reboot-greeter');
    onpc_gdm::enter_station($journey->scope('after'), 'initial-');
    $journey->seen($_) for ('after-jordan-select', 'after-jordan-form', 'after-jordan-station', 'after-jordan-close',
        'after-riley-select', 'after-riley-station', 'after-riley-close', 'after-station-riley-form',
        'after-station-exit', 'after-station-returned');
    onpc_gdm::sign_in_challenge($journey, 'after-riley',
        'after-riley-installed-greeter', 'after-riley-child-focused', 'after-riley-desktop');
    onpc_request_flow::overlay_entry($journey, 'after-riley', 'command');
    $journey->seen($_) for ('after-riley-overlay', 'after-riley-overlay-close',
        'after-riley-exit', 'after-riley-returned', 'after-riley-logout', 'after-riley-logged-out');
    onpc_gdm::sign_in_challenge($journey, 'after-jordan',
        'after-jordan-installed-greeter', 'after-jordan-standard-focused', 'after-jordan-desktop');
    $journey->seen($_) for ('after-jordan-overlay-launch', 'after-jordan-overlay-ready',
        'after-jordan-overlay', 'after-jordan-overlay-close', 'after-jordan-overlay-exit',
        'after-jordan-overlay-returned', 'after-jordan-logout', 'after-jordan-logged-out');
    $desktop = onpc_gdm::sign_in_challenge($journey, 'return-parent',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
    onpc_parent::launch($journey, $desktop, 'management', 'return-desktop');
    $selected = onpc_parent::select_child($journey, 'child', $journey->seen('return-child-picker-opened'),
        'return-child-picker-opened', 'return-child-choice-highlighted', 'return-parent-selected');
    $journey->consume_observation('return-parent-selected', $selected);
    $journey->seen('riley-policy-after');
    onpc_allowance_boundaries::select_child($journey, 'jordan-final');
    $journey->seen('jordan-policy-after');
    $journey->finish();
}

sub notifications {
    onpc_progress::operation('Following both children’s saved warnings through play and restart');
    my ($exchange, $invocations, $challenges) = @_;
    die 'reminder-notifications:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'reminder-notifications', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    $journey->consume_observation('parent-selected', onpc_parent::select_child($journey, 'child',
        $journey->seen('child-picker-opened'), 'child-picker-opened',
        'child-choice-highlighted', 'parent-selected'));
    $journey->seen($_) for ('riley-zero', 'riley-policy-before');
    onpc_allowance_boundaries::select_child($journey, 'jordan');
    $journey->seen($_) for ('jordan-zero', 'jordan-policy-before', 'parent-logout', 'parent-greeter');
    for my $name ('first', 'enabled', 'disabled') {
        my $request = $journey->scope($name);
        my $seconds = $name eq 'first' ? 240 : 600;
        $request->{kiosk_request} = ['child', 'parent', $seconds, 1];
        onpc_request_flow::obtain_time($request, 'observed',
            'fixture-child', 'fixture-parent', $seconds, 1, 'automatic');
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'child',
            $name eq 'first' ? 'fresh' : 'retained', 'success', "$name-child");
        onpc_app_rows::native_activity_entry($journey, 'activity', 'command', 'child') if $name eq 'first';
        $journey->seen($_) for ("$name-warning", "$name-leave-lock", "$name-greeter");
    }
    my $persistence = $journey->scope('persistence');
    $persistence->{kiosk_request} = ['child', 'parent', 600, 1];
    onpc_request_flow::prepare($persistence, 'new', 'new', 'observed',
        'fixture-child', 'fixture-parent', 600, 1, 'kiosk');
    $journey->seen($_) for ('persistence-cancel', 'persistence-returned');
    onpc_gdm::sign_in_challenge($journey, 'reboot-parent',
        'reboot-parent-installed-greeter', 'reboot-parent-parent-focused', 'reboot-parent-desktop');
    $journey->seen($_) for ('reboot-requested', 'reboot-greeter');
    my $after = $journey->scope('after');
    $after->{kiosk_request} = ['child', 'parent', 600, 1];
    onpc_request_flow::obtain_time($after, 'observed',
        'fixture-child', 'fixture-parent', 600, 1, 'automatic');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'after-child');
    $journey->seen($_) for ('after-warning', 'after-leave-lock', 'after-greeter');
    $desktop = onpc_gdm::sign_in_challenge($journey, 'return',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
    onpc_parent::launch($journey, $desktop, 'management', 'return-desktop');
    $journey->consume_observation('return-parent-selected', onpc_parent::select_child($journey, 'child',
        $journey->seen('return-child-picker-opened'), 'return-child-picker-opened',
        'return-child-choice-highlighted', 'return-parent-selected'));
    $journey->seen('riley-policy-after');
    onpc_allowance_boundaries::select_child($journey, 'jordan-final');
    $journey->seen($_) for ('jordan-policy-after', 'final-logout', 'final-greeter');
    $journey->finish();
}

1;
