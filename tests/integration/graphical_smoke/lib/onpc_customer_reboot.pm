package onpc_customer_reboot;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();
use onpc_allowance_boundaries ();

sub run {
    onpc_progress::operation('Installing the product before the planned customer reboot');
    my ($exchange, $declared, $challenges) = @_;
    my @stages = qw(reboot-installed-greeter reboot-parent-focused
        reboot-recipient-qualified reboot-recipient-rechecked reboot-desktop);
    die 'customer-reboot:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 1
        && ref($challenges->{'after-reboot'}) eq 'ARRAY'
        && join('/', @{$challenges->{'after-reboot'}}) eq
            'parent/reboot-recipient-qualified/reboot-recipient-rechecked';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'customer-reboot', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    install_entry($journey);
    return_entry($journey);
    $journey->finish();
}

sub install_entry {
    onpc_progress::operation('Installing the verified release and requesting its declared activation reboot');
    my ($journey) = @_;
    die 'customer-reboot:entry-arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    $journey->seen('wrong-entry');
    onpc_parent::login_functional($journey);
    $journey->seen('command-context');
    $journey->seen('package-submitted');
    $journey->seen('package-result');
    $journey->seen('reboot-requested');
}

sub return_entry {
    onpc_progress::operation('Observing the new greeter and signing in after reboot');
    my ($journey) = @_;
    die 'customer-reboot:return-arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_gdm::sign_in_challenge($journey, 'after-reboot',
        'reboot-installed-greeter', 'reboot-parent-focused', 'reboot-desktop');
}

sub unrelated_request {
    onpc_progress::operation('Qualifying the genuine Ubuntu libc6 reboot request after product activation');
    my ($exchange, $declared, $challenges) = @_;
    die 'unrelated-reboot:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq
            'reboot-installed-greeter/reboot-parent-focused/reboot-recipient-qualified/reboot-recipient-rechecked/reboot-desktop'
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 1
        && ref($challenges->{'after-reboot'}) eq 'ARRAY'
        && join('/', @{$challenges->{'after-reboot'}}) eq
            'parent/reboot-recipient-qualified/reboot-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'unrelated-reboot', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    install_entry($journey);
    return_entry($journey);
    $journey->seen($_) for qw(unrelated-context unrelated-submitted unrelated-result);
    $journey->finish();
}

sub run_upgrade {
    onpc_progress::operation('Installing the authentic old release before the real upgrade');
    my ($exchange, $declared, $challenges) = @_;
    die 'package-upgrade:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq
            'reboot-installed-greeter/reboot-parent-focused/reboot-recipient-qualified/reboot-recipient-rechecked/reboot-desktop'
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 1
        && ref($challenges->{'after-reboot'}) eq 'ARRAY'
        && join('/', @{$challenges->{'after-reboot'}}) eq
            'parent/reboot-recipient-qualified/reboot-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'package-upgrade', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_progress::operation('Installing the authentic old release and observing its activation reboot');
    install_entry($journey);
    return_entry($journey);
    onpc_progress::operation('Upgrading once and independently observing completion without another reboot');
    $journey->seen($_) for qw(upgrade-context upgrade-submitted upgrade-result upgrade-reread);
    $journey->finish();
}

sub run_no_action { run_automatic_update('update-no-action', @_); }
sub run_process { run_automatic_update('activation-process', @_); }

sub run_reboot {
    onpc_progress::operation('Following the update restart notice and checking the saved parent and child choices');
    my ($exchange, $declared, $challenges) = @_;
    die 'activation-reboot:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    require onpc_desktop_session;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'activation-reboot', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_parent::login_functional($journey);
    $journey->seen($_) for qw(command-context package-submitted package-result reboot-requested);
    my $desktop = return_entry($journey);
    onpc_parent::launch($journey, $desktop, 'management', 'reboot-desktop');
    onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->seen($_) for qw(allowance-configured settings-before);
    my $leave = sub {
        my ($prefix) = @_;
        my $section = $journey->scope($prefix);
        onpc_desktop_session::switch_user($section, $section->seen('desktop'));
    };
    $leave->('initial-leave');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'before-child');
    $journey->seen($_) for qw(animation-configured animation-before);
    $leave->('child-leave');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'update-parent');
    $journey->seen($_) for qw(upgrade-context upgrade-submitted upgrade-result updated-reboot-requested);
    $desktop = onpc_gdm::sign_in_challenge($journey, 'after-update',
        'updated-reboot-installed-greeter', 'updated-reboot-parent-focused', 'updated-reboot-desktop');
    $journey->consume_observation('updated-reboot-desktop', $desktop);
    onpc_parent::named_management($journey, 'updated', 'child');
    $journey->seen('settings-after');
    $leave->('updated-leave');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'after-child');
    $journey->seen($_) for qw(animation-after usable-countdown);
    $journey->finish();
}

sub run_session {
    onpc_progress::operation('Updating and renewing the affected child session with its saved choices');
    my ($exchange, $declared, $challenges) = @_;
    die 'activation-session:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    require onpc_desktop_session;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'activation-session', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_parent::login_functional($journey);
    $journey->seen($_) for qw(command-context package-submitted package-result reboot-requested);
    my $desktop = return_entry($journey);
    onpc_parent::launch($journey, $desktop, 'management', 'reboot-desktop');
    onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->seen($_) for qw(allowance-configured settings-before);
    my $leave = sub {
        my ($prefix) = @_;
        my $section = $journey->scope($prefix);
        onpc_desktop_session::switch_user($section, $section->seen('desktop'));
    };
    $leave->('initial-leave');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'before-child');
    $journey->seen($_) for qw(animation-configured animation-before);
    $leave->('child-leave');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'update-parent');
    $journey->seen($_) for qw(upgrade-context upgrade-submitted upgrade-result);
    $leave->('updated-leave');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'retained', 'success', 'renew-child');
    $journey->consume_observation('renewal-desktop', $journey->seen('renewal-desktop'));
    $journey->seen($_) for qw(renewal-logout renewal-greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'after-child');
    $journey->seen($_) for qw(animation-after usable-countdown);
    $leave->('renewed-leave');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'final-parent');
    $journey->seen('settings-after');
    $journey->finish();
}

sub run_process_case {
    run_update_case('process', @_);
}

sub run_session_case {
    run_update_case('session', @_);
}

sub run_reboot_case {
    run_update_case('reboot', @_);
}

sub run_update_case {
    onpc_progress::operation('Updating while preserving the child rules and original extra time');
    my ($activation, $exchange, $declared, $challenges, $request) = @_;
    die 'update-case:arguments' unless @_ == 5 && $activation =~ /\A(?:process|session|reboot)\z/
        && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ref($request) eq 'ARRAY' && join(',', @$request) eq 'other-child,parent,1200,0';
    require onpc_app_rows;
    require onpc_desktop_session;
    require onpc_request_flow;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => "update-$activation-case", review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_parent::login_functional($journey);
    $journey->seen($_) for qw(command-context package-submitted package-result reboot-requested);
    my $desktop = return_entry($journey);
    onpc_parent::launch($journey, $desktop, 'management', 'reboot-desktop');
    $journey->consume_observation('parent-selected', onpc_parent::select_child($journey, 'existing',
        $journey->seen('child-picker-opened'), 'child-picker-opened',
        'child-choice-highlighted', 'parent-selected'));
    $journey->seen('allowance-configured');
    my $apps = [['A', 'match-precise', 'allowed'], ['H', 'match-hard-precise', 'permanent'],
                ['S', 'match-soft-wildcard', 'conditional']];
    onpc_app_rows::named_app_set($journey, 'desktop', 'same-user', 'retained', 'existing', $apps, 'rules');
    my $select = sub {
        my ($prefix, $child) = @_;
        my $section = $journey->scope($prefix);
        $section->consume_observation('parent-selected', onpc_parent::select_child($section, $child,
            $section->seen('child-picker-opened'), 'child-picker-opened',
            'child-choice-highlighted', 'parent-selected'));
    };
    my $leave = sub {
        my ($prefix) = @_;
        my $section = $journey->scope($prefix);
        onpc_desktop_session::switch_user($section, $section->seen('desktop'));
    };
    if ($activation eq 'reboot') {
        onpc_progress::operation('Saving both children request choices before the measured approval');
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'seed-parent');
        $select->('riley-setup', 'child');
        $journey->seen($_) for qw(riley-time riley-before);
        $select->('jordan-setup', 'existing');
        $leave->('seed-leave');
        onpc_gdm::enter_station($journey->scope('seed-station'), '');
        $journey->seen($_) for qw(seed-riley-select seed-riley-parent seed-cancel seed-returned);
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'seed-riley');
        $journey->seen("seed-riley-form-$_") for qw(launch approver custom text apps read cancel returned);
        $leave->('seed-riley-leave');
    }
    my $approval = $journey->scope('request');
    $approval->{kiosk_request} = [@$request];
    onpc_request_flow::obtain_time($approval, 'observed',
        'existing-fixture-child', 'fixture-parent', 1200, 0, 'automatic');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'issued-parent');
    $journey->seen($_) for qw(issued-screen issued-balance);
    my $apps_result = sub {
        my ($prefix) = @_;
        my $section = $journey->scope($prefix)->scope('allowed');
        onpc_app_rows::native_usable_app($section, 'command', $section->seen('desktop'));
        $section->seen($_) for qw(close closed);
        onpc_app_rows::native_blocked_app($journey->scope($prefix)->scope('hard'), 'H');
        onpc_app_rows::native_blocked_app($journey->scope($prefix)->scope('soft'), 'S');
    };
    $leave->('issued-leave');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'fresh', 'success', 'before-child');
    $journey->seen('before-countdown');
    $apps_result->('before');
    if ($activation eq 'reboot') {
        $journey->seen("seed-jordan-form-$_") for qw(launch custom text apps read cancel returned);
    }
    $leave->('child-leave');
    if ($activation eq 'reboot') {
        onpc_gdm::enter_station($journey->scope('capture-station'), '');
        $journey->seen($_) for qw(capture-jordan capture-riley-select capture-riley capture-cancel capture-returned);
    }
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'before-parent');
    $journey->seen($_) for qw(settings-before upgrade-context upgrade-submitted upgrade-result);
    if ($activation eq 'session') {
        onpc_progress::operation('Signing the affected child out and back in after the update');
        $leave->('renewal-leave');
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'retained', 'success', 'renew-child');
        $journey->consume_observation('renewal-desktop', $journey->seen('renewal-desktop'));
        $journey->seen($_) for qw(renewal-logout renewal-greeter);
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'fresh', 'success', 'renewed-child');
        $leave->('renewed-leave');
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'renewed-parent');
    } elsif ($activation eq 'reboot') {
        onpc_progress::operation('Following the update reboot notice before reading saved choices');
        $journey->seen('updated-reboot-requested');
        my $updated_desktop = onpc_gdm::sign_in_challenge($journey, 'after-update',
            'updated-reboot-installed-greeter', 'updated-reboot-parent-focused', 'updated-reboot-desktop');
        $journey->consume_observation('updated-reboot-desktop', $updated_desktop);
        onpc_parent::named_management($journey, 'updated', 'existing');
    }
    $journey->seen('settings-after');
    if ($activation eq 'reboot') {
        $select->('riley-return', 'child');
        $journey->seen('riley-after');
        $select->('jordan-return', 'existing');
    }
    $journey->seen('saved-apps');
    onpc_app_rows::saved_rows($journey, $apps, 'saved');
    $journey->seen($_) for qw(saved-screen final-balance about-information about-returned);
    $leave->('updated-leave');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child',
        $activation eq 'reboot' ? 'fresh' : 'retained', 'success', 'after-child');
    $journey->seen('after-countdown');
    $apps_result->('after');
    $journey->seen($_) for qw(overlay-launch overlay-ready overlay-cancel overlay-returned);
    $leave->('request-leave');
    onpc_gdm::enter_station($journey, 'renewed-');
    $journey->seen('kiosk-ready');
    $journey->seen($_) for $activation eq 'reboot' ? qw(returned-jordan-select returned-jordan) : ();
    $journey->seen($_) for qw(kiosk-cancel kiosk-returned);
    if ($activation eq 'reboot') {
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'after-riley');
        $journey->seen("returned-riley-form-$_") for qw(launch read cancel returned);
    }
    $journey->finish();
}

sub run_automatic_update {
    onpc_progress::operation('Updating while the parent keeps the child allowance open');
    my ($prefix, $exchange, $declared, $challenges) = @_;
    die 'automatic-update:arguments' unless @_ == 4 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq
            'reboot-installed-greeter/reboot-parent-focused/reboot-recipient-qualified/reboot-recipient-rechecked/reboot-desktop'
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 1
        && ref($challenges->{'after-reboot'}) eq 'ARRAY'
        && join('/', @{$challenges->{'after-reboot'}}) eq
            'parent/reboot-recipient-qualified/reboot-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => $prefix, review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    install_entry($journey);
    my $desktop = return_entry($journey);
    onpc_parent::launch($journey, $desktop, 'management', 'reboot-desktop');
    onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->seen($_) for qw(allowance-configured settings-before upgrade-context upgrade-submitted upgrade-result upgrade-reread);
    $journey->finish();
}

sub run_chinese {
    onpc_progress::operation('Qualifying the continuous Chinese upgrade and first kiosk presentation');
    my ($exchange, $declared, $challenges) = @_;
    die 'chinese-kiosk:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && keys(%$challenges) == 4;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'chinese-kiosk', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    install_entry($journey);
    return_entry($journey);
    $journey->seen($_) for qw(upgrade-context language-setting language-parent-logout);
    chinese_desktop_renewal($journey, 'upgrade-', 'upgrade-parent');
    $journey->seen($_) for qw(upgrade-ready upgrade-submitted upgrade-result upgrade-reread upgrade-switch);
    chinese_initial_notice($journey);
    $journey->seen($_) for qw(second-reboot-requested second-reboot-greeter);
    chinese_initial_form($journey);
    $journey->finish();
}

sub chinese_desktop_renewal {
    onpc_progress::operation('Renewing the Chinese child desktop and returning to the administrator');
    my ($journey, $prefix, $challenge) = @_;
    die 'chinese-renewal:arguments' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && (($prefix eq 'upgrade-' && $challenge eq 'upgrade-parent')
            || ($prefix eq 'install-' && $challenge eq 'install-parent'));
    onpc_gdm::sign_in_challenge($journey, 'chinese-child',
        'language-installed-greeter', 'language-standard-focused', 'language-desktop');
    $journey->seen('language-child-logout');
    onpc_gdm::sign_in_challenge($journey, $challenge,
        $prefix . 'installed-greeter', $prefix . 'parent-focused', $prefix . 'desktop');
}

sub chinese_initial_notice {
    onpc_progress::operation('Reading the untouched Chinese restart notice and returning normally');
    my ($journey) = @_;
    die 'chinese-notice:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_gdm::enter_station($journey, 'initial-');
    $journey->seen($_) for qw(initial-notice initial-notice-close initial-notice-return);
    onpc_gdm::sign_in_challenge($journey, 'return-parent',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
}

sub chinese_initial_form {
    onpc_progress::operation('Reading the untouched Chinese chooser and cancelling without saving');
    my ($journey) = @_;
    die 'chinese-form:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_gdm::enter_station($journey, 'renewed-');
    $journey->seen($_) for qw(initial-language initial-language-cancel initial-form);
}

sub run_chinese_current {
    onpc_progress::operation('Qualifying the latest installation and untouched Chinese first presentations');
    my ($exchange, $declared, $challenges) = @_;
    die 'chinese-current-install:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && keys(%$challenges) == 3;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'chinese-current-install', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    $journey->seen('wrong-entry');
    chinese_current_entry($journey);
    $journey->finish();
}

sub chinese_current_entry {
    onpc_progress::operation('Installing the current package and observing both Chinese first presentations');
    my ($journey) = @_;
    die 'chinese-current-entry:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_parent::login_functional($journey);
    $journey->seen($_) for qw(command-context language-setting language-parent-logout);
    chinese_desktop_renewal($journey, 'install-', 'install-parent');
    $journey->seen($_) for qw(install-ready package-submitted package-result package-reread install-switch);
    chinese_initial_notice($journey);
    $journey->seen($_) for qw(reboot-requested reboot-greeter);
    chinese_initial_form($journey);
}

sub restart_reentry {
    onpc_progress::operation('Closing the installed notice and reopening on the same boot');
    my ($journey, $surface) = @_;
    die 'restart:roundtrip-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && ($surface eq 'parent' || $surface eq 'overlay' || $surface eq 'kiosk');
    $journey->seen("$surface-close");
    $journey->seen("$surface-closed");
    if ($surface eq 'kiosk') {
        $journey->seen($_) for qw(kiosk-exit kiosk-returned);
        onpc_gdm::enter_station($journey, 'renewed-');
        $journey->seen('kiosk-reentry');
        return;
    }
    if ($surface eq 'overlay') {
        $journey->seen('overlay-exit');
        $journey->seen('overlay-desktop');
    }
    $journey->seen("$surface-relaunch");
    $journey->seen("$surface-reentry");
}

sub restart_roundtrip {
    onpc_progress::operation('Reading the installed notice, closing and reopening without reboot');
    my ($journey, $surface) = @_;
    die 'restart:roundtrip-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && ($surface eq 'parent' || $surface eq 'overlay');
    $journey->seen("$surface-launch");
    $journey->seen("$surface-notice");
    $journey->seen('parent-wrong-owner') if $surface eq 'parent';
    restart_reentry($journey, $surface);
    $journey->seen("$surface-second-close");
    $journey->seen("$surface-second-closed");
    if ($surface eq 'overlay') {
        $journey->seen('overlay-second-exit');
        $journey->seen('overlay-second-desktop');
    }
}

sub run_parent_notice {
    onpc_progress::operation('Installing before Parent Close, reopening and one normal modal reboot');
    my ($exchange, $declared, $challenges) = @_;
    die 'fresh-parent-restart:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'fresh-parent-restart', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_parent::login_functional($journey);
    $journey->seen($_) for qw(command-context package-submitted package-result
        parent-launch parent-notice);
    restart_reentry($journey, 'parent');
    $journey->seen($_) for qw(reboot-requested reboot-greeter);
    onpc_gdm::named_login($journey, 'return', 'parent');
    $journey->seen($_) for qw(usable-parent-launch usable-parent);
    $journey->finish();
}

sub run_child_notice {
    onpc_progress::operation('Installing before Child App Close, reopening and one normal modal reboot');
    my ($exchange, $declared, $challenges) = @_;
    die 'fresh-child-restart:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'fresh-child-restart', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_parent::login_functional($journey);
    $journey->seen($_) for qw(command-context package-submitted package-result parent-logout);
    onpc_gdm::named_login($journey, 'child', 'child');
    $journey->seen($_) for qw(overlay-launch overlay-notice);
    restart_reentry($journey, 'overlay');
    $journey->seen($_) for qw(reboot-requested reboot-greeter);
    onpc_gdm::named_login($journey, 'return', 'parent');
    $journey->seen($_) for qw(usable-parent-launch usable-parent);
    onpc_allowance_boundaries::select_child($journey, 'postboot-riley');
    $journey->seen($_) for qw(postboot-riley-configured return-parent-logout);
    onpc_gdm::named_login($journey, 'child-return', 'child');
    $journey->seen($_) for qw(usable-overlay-launch usable-overlay);
    $journey->finish();
}

sub restart_kiosk_usability {
    onpc_progress::operation('Selecting the declared kiosk approver and independently checking usability');
    my ($journey, $prefix) = @_;
    die 'restart:kiosk-usability-binding' unless (@_ == 1 || @_ == 2)
        && ref($journey) eq 'onpc_journey'
        && (!defined($prefix) || $prefix =~ /\A[a-z][a-z0-9-]*\z/);
    $prefix = defined($prefix) ? $prefix . '-' : '';
    $journey->seen($prefix . $_) for qw(usable-kiosk-approver usable-kiosk);
}

sub restart_request_usability {
    onpc_progress::operation('Opening fresh Child App and station requests without a restart modal');
    my ($journey, $prefix, $station_prefix) = @_;
    die 'restart:request-usability-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && defined($prefix) && $prefix =~ /\A[a-z][a-z0-9-]*\z/
        && defined($station_prefix) && $station_prefix =~ /\A(?:cancel-|escape-|initial-|renewed-)?\z/;
    onpc_gdm::named_login($journey, $prefix . '-child', 'child');
    $journey->seen($prefix . '-' . $_) for qw(overlay-launch usable-overlay child-logout);
    onpc_gdm::enter_station($journey, $station_prefix);
    restart_kiosk_usability($journey, $prefix);
    $journey->seen($prefix . '-' . $_) for qw(kiosk-exit kiosk-returned);
}

sub run_kiosk_notice {
    onpc_progress::operation('Installing before request-station Close, reentry and one normal modal reboot');
    my ($exchange, $declared, $challenges) = @_;
    die 'fresh-kiosk-restart:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'fresh-kiosk-restart', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_parent::login_functional($journey);
    $journey->seen($_) for qw(command-context package-submitted package-result parent-logout);
    onpc_gdm::enter_station($journey, 'initial-');
    $journey->seen('kiosk-notice');
    restart_reentry($journey, 'kiosk');
    $journey->seen($_) for qw(reboot-requested reboot-greeter);
    onpc_gdm::named_login($journey, 'return', 'parent');
    $journey->seen($_) for qw(usable-parent-launch usable-parent);
    onpc_allowance_boundaries::select_child($journey, 'postboot-jordan');
    $journey->seen($_) for qw(postboot-jordan-configured return-parent-logout);
    onpc_gdm::enter_station($journey, '');
    restart_kiosk_usability($journey);
    $journey->finish();
}

sub restart_notice {
    onpc_progress::operation('Qualifying the genuine first-install restart notice on all three surfaces');
    my ($exchange, $declared, $challenges) = @_;
    die 'restart:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH' && keys(%$challenges) == 3;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'restart-notice', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    $journey->seen('wrong-entry');
    onpc_parent::login_functional($journey);
    $journey->seen($_) for qw(command-context package-submitted package-result);
    restart_roundtrip($journey, 'parent');
    $journey->seen('parent-logout');
    onpc_gdm::named_login($journey, 'child', 'child');
    restart_roundtrip($journey, 'overlay');
    $journey->seen('child-logout');
    onpc_gdm::enter_station($journey, 'initial-');
    $journey->seen('kiosk-notice');
    restart_reentry($journey, 'kiosk');
    $journey->seen($_) for qw(reboot-requested reboot-greeter);
    onpc_gdm::named_login($journey, 'return', 'parent');
    $journey->seen($_) for qw(usable-parent-launch usable-parent missing-notice-refused);
    for my $prefix ('postboot-riley', 'postboot-jamie') {
        onpc_allowance_boundaries::select_child($journey, $prefix);
        $journey->seen("$prefix-configured");
    }
    $journey->seen('return-parent-logout');
    onpc_gdm::named_login($journey, 'child-return', 'child');
    $journey->seen($_) for qw(usable-overlay-launch usable-overlay return-child-logout);
    onpc_gdm::enter_station($journey, '');
    restart_kiosk_usability($journey);
    $journey->finish();
}

1;
