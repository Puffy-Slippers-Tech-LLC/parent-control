package onpc_request_flow;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_parent ();
use onpc_text ();
use onpc_journey ();
use onpc_password ();
use onpc_desktop_session ();
use onpc_app_rows ();
use onpc_request_exit ();
use onpc_about ();
use testapi ();

sub overlay_license {
    onpc_progress::operation('Qualifying overlay About information and license clickability');
    my ($exchange, $declared, $challenges, $links) = @_;
    $links //= 'license';
    die 'overlay-license:arguments' unless (@_ == 3 || @_ == 4) && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    die 'overlay-about:links' unless $links eq 'license' || $links eq 'browser-links' || $links eq 'information';
    my $prefix = $links eq 'license' ? 'overlay-license' : $links eq 'browser-links'
        ? 'overlay-browser-links' : 'overlay-information';
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
    $journey->seen('wrong-entry-refused');
    $journey->seen('allowance-configured');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    overlay_entry($journey, 'direct', 'command');
    prepare($journey, 'open', 'open', 'default',
        'fixture-child', 'fixture-parent', 75, 1, 'overlay');
    my $entry = $journey->seen('missing-about-refused');
    # Fresh wrong-stage proof must refuse before opening any window.
    my $wrong = onpc_journey->new(exchange => $exchange, prefix => 'overlay-license-wrong', review => 0);
    $wrong->{last_observation} = {stage => 'missing-about-refused', reply => $entry};
    my $accepted = eval { onpc_about::overlay_license($wrong, $entry, 'open-estimate', '', $links); 1 };
    die 'overlay-license:wrong-proof-accepted' if $accepted;
    die 'overlay-license:wrong-proof-refusal' unless $@ =~ /journey:stale-observation/;
    my $returned = onpc_about::overlay_license($journey, $entry, 'missing-about-refused', '', $links);
    onpc_about::overlay_license($journey, $returned, 'form-returned', 'independent-', $links);
    $journey->seen('cancel');
    $journey->seen('returned');
    $journey->finish();
}

sub overlay_browser_links {
    onpc_progress::operation('Qualifying overlay website and privacy clickability');
    die 'overlay-browser-links:arguments' unless @_ == 3;
    return overlay_license(@_, 'browser-links');
}

sub overlay_information {
    onpc_progress::operation('Qualifying all offered overlay information links and unchanged choices');
    die 'overlay-information:arguments' unless @_ == 3;
    return overlay_license(@_, 'information');
}

sub overlay_prompt {
    onpc_progress::operation('Qualifying one real Shell prompt and preserved form after Cancel');
    my ($exchange, $declared, $challenges, $approval) = @_;
    die 'overlay-prompt:arguments' unless (@_ == 3 || @_ == 4 && $approval eq 'approval') && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $approval ? 'overlay-approved-exit' : 'overlay-prompt', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen('allowance-configured');
    $journey->seen('wrong-account-refused');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    my $activity;
    if ($approval) {
        $activity = onpc_app_rows::native_activity_entry($journey, 'activity', 'command');
    }
    overlay_entry($journey, 'direct', 'command');
    $journey->seen('wrong-surface-refused');
    prepare($journey, 'open', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1, 'overlay');
    if ($approval) {
        shell_approve($journey);
    } else {
        shell_cancel($journey, 'shell-cancel-ready', 'shell-dismissed');
        $journey->seen('form-returned');
        $journey->seen('cancel');
    }
    $journey->seen('returned');
    if ($approval) {
        onpc_app_rows::native_read_activity($activity, 'returned');
        onpc_app_rows::native_finish_app($activity);
    }
    $journey->finish();
}

sub shell_approve {
    onpc_progress::operation('Approving the declared overlay request once');
    my ($journey) = @_;
    die 'shell-approve:binding' unless @_ == 1 && ref($journey) eq 'onpc_journey'
        && ($journey->{prefix} // '') eq 'overlay-approved-exit';
    die 'shell-approve:replay' if $journey->{shell_approval_started} || $journey->{invocation_failed};
    $journey->{shell_approval_started} = 1;
    my $ok = eval {
        $journey->consume_observation('approval-open', $journey->seen('approval-open'));
        onpc_password::enter_overlay_shell_password($journey);
        $journey->consume_observation('approval-submit-ready', $journey->seen('approval-submit-ready'));
        my $submitted = 0;
        my $result = $journey->seen('approval-success', sub {
            my ($proof) = @_;
            die 'shell-approve:input-proof' unless !$submitted && ref($proof) eq 'HASH'
                && keys(%$proof) == 6 && ($proof->{stage} // '') eq 'approval-success'
                && ($proof->{binding} // '') eq 'overlay-approve'
                && ($proof->{child} // '') eq 'child'
                && ($proof->{source} // '') =~ /\A[0-9a-f]{64}\z/
                && ($proof->{token} // '') eq substr($proof->{source}, 0, 32)
                && ref($proof->{values}) eq 'ARRAY' && @{$proof->{values}} == 1
                && $proof->{values}[0] eq 'ret';
            $submitted = 1;
            testapi::send_key('ret');
        });
        die 'shell-approve:input-missing' unless $submitted;
        $journey->consume_observation('approval-success', $result);
        1;
    };
    unless ($ok) {
        $journey->{invocation_failed} = 1;
        die $@;
    }
}

# Shell's documented Escape binding is its ordinary Cancel action. Consume a
# fresh controller proof once; refusal or uncertain input never releases a key.
sub shell_cancel {
    onpc_progress::operation('Cancelling the freshly qualified Shell authentication challenge');
    my ($journey, $ready, $dismissed) = @_;
    die 'shell-cancel:arguments' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && defined($ready) && $ready =~ /\A[a-z][a-z0-9-]*\z/
        && defined($dismissed) && $dismissed =~ /\A[a-z][a-z0-9-]*\z/;
    my $returned;
    my $ok = eval {
        my $proof = $journey->seen($ready);
        $journey->consume_observation($ready, $proof);
        testapi::send_key('esc');
        $returned = $journey->seen($dismissed);
        1;
    };
    unless ($ok) {
        $journey->{invocation_failed} = 1;
        die $@;
    }
    return $returned;
}

sub overlay_valid_choices {
    onpc_progress::operation('Qualifying valid overlay choices and unchanged app activity after Cancel');
    my ($exchange, $declared, $challenges) = @_;
    die 'overlay-valid:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'overlay-valid-choices', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen('allowance-configured');
    $journey->seen('wrong-account-refused');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    my $activity = onpc_app_rows::native_activity_entry($journey, 'activity', 'command');
    overlay_entry($journey, 'direct', 'command');
    for my $stage ('wrong-surface-refused', 'overlay-valid-approver-select', 'overlay-valid-approver-read',
                   'overlay-valid-preset-select', 'overlay-valid-preset-read', 'overlay-valid-custom-open') {
        $journey->seen($stage);
    }
    onpc_text::replace_text($journey, 'overlay-fraction');
    for my $stage ('overlay-valid-fraction-read', 'overlay-valid-rest-select', 'overlay-valid-rest-read',
                   'overlay-valid-soft-select', 'overlay-valid-soft-read',
                   'overlay-valid-excluded-select', 'overlay-valid-excluded-read',
                   'cancel', 'returned-desktop') {
        $journey->seen($stage);
    }
    onpc_app_rows::native_read_activity($activity, 'returned');
    overlay_entry($journey, 'independent', 'command');
    for my $stage ('independent-preset', 'independent-read', 'independent-cancel', 'independent-desktop') {
        $journey->invoke($stage);
    }
    onpc_app_rows::native_read_activity($activity, 'independent');
    onpc_app_rows::native_finish_app($activity);
    $journey->finish();
}

# REQUEST02/13: one explicit input and independent REQUEST03 observation.
# The caller owns entry, repeated customer inputs and subsequent exits.
sub overlay_entry {
    onpc_progress::operation('Opening and independently reading the child overlay');
    my ($journey, $prefix, $route) = @_;
    die 'request-flow:overlay-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $prefix =~ /\A[a-z][a-z0-9-]*\z/
        && ($route eq 'command' || $route eq 'panel' || $route eq 'panel-reopen');
    if ($route eq 'panel-reopen') {
        # The fullscreen overlay hides the panel. Reveal it once through
        # Overview after proving the fixed-child form and closed Overview.
        $journey->invoke("$prefix-reveal");
        testapi::send_key('super');
    }
    $journey->invoke("$prefix-panel") if $route ne 'command';
    $journey->invoke("$prefix-launch");
    # The panel checkpoint proves focus on child-request-button by public ID.
    # StButtonAccessible has no Action interface; activate with one ordinary key.
    testapi::send_key('ret') if $route ne 'command';
    if ($route eq 'panel-reopen') {
        $journey->invoke("$prefix-overview");
        testapi::send_key('esc');
    }
    return $journey->invoke("$prefix-form");
}

# FLOW04: finite, explicit choices. The caller prepares policy independently.
sub prepare {
    onpc_progress::operation('Preparing the declared kiosk request without submitting');
    my ($journey, $prefix, $entry, $initial, $child, $approver, $seconds, $soft, $invalid) = @_;
    die 'request-flow:binding' unless (@_ == 8 || @_ == 9 && ($invalid eq 'invalid' || $invalid eq 'overlay'))
        && ref($journey) eq 'onpc_journey'
        && ($prefix eq 'open' || $prefix eq 'new')
        && ($entry eq 'open' || $entry eq 'new')
        && ($initial eq 'default' || $initial eq 'selected')
        && $child eq 'fixture-child' && $approver eq 'fixture-parent'
        && $seconds eq '75' && $soft eq '1';
    if ($invalid && $invalid eq 'overlay') {
        overlay_entry($journey, "$prefix-entry", 'command') if $entry eq 'new';
        for my $suffix ('form', 'approver', 'selections', 'duration') {
            my $stage = "$prefix-$suffix";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
        onpc_text::replace_text($journey, 'overlay-fraction', "$prefix-text");
        for my $suffix ('duration-read', 'apps', 'estimate') {
            my $stage = "$prefix-$suffix";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
        return;
    }
    onpc_gdm::enter_station($journey, 'cancel-') if $entry eq 'new';
    for my $suffix ('form', 'child', 'approver', 'selections') {
        my $stage = "$prefix-$suffix";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    if ($invalid) {
        $journey->consume_observation('invalid-custom-open', $journey->seen('invalid-custom-open'));
        onpc_text::replace_text($journey, 'kiosk-invalid-letters');
        for my $action ('ready', 'submit', 'read') {
            my $stage = "kiosk-invalid-letters-$action";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    }
    $journey->consume_observation("$prefix-duration", $journey->seen("$prefix-duration"));
    onpc_text::replace_text($journey, 'kiosk-fraction', "$prefix-text");
    for my $suffix ('duration-read', 'apps', 'estimate') {
        my $stage = "$prefix-$suffix";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

sub overlay_choices {
    onpc_progress::operation('Qualifying overlay composition, invalid requests and unchanged activity after exits');
    my ($exchange, $declared, $challenges) = @_;
    die 'overlay-choices:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'overlay-choices', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen('allowance-configured');
    $journey->seen('wrong-account-refused');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    my $activity = onpc_app_rows::native_activity_entry($journey, 'activity', 'command');
    overlay_entry($journey, 'direct', 'command');
    $journey->seen('wrong-surface-refused');
    prepare($journey, 'open', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1, 'overlay');
    $journey->seen('cancel');
    $journey->seen('cancel-returned');
    onpc_app_rows::native_read_activity($activity, 'cancel');
    prepare($journey, 'new', 'new', 'selected', 'fixture-child', 'fixture-parent', 75, 1, 'overlay');
    $journey->seen('exclude-soft');
    $journey->seen('excluded-read');
    # The local seven-value matrix belongs to UI tests; installed qualification
    # exercises the recipe's representative lower-bound rejection.
    for my $binding ('below') {
        onpc_text::replace_text($journey, "overlay-invalid-$binding");
        $journey->seen("overlay-invalid-$binding-$_") for ('ready', 'submit', 'read');
    }
    onpc_request_exit::escape($journey);
    onpc_app_rows::native_read_activity($activity, 'escape');
    onpc_app_rows::native_finish_app($activity);
    $journey->finish();
}

# FLOW05 uses the fixed single-use challenge and the caller's declared exit leaf.
sub approve {
    onpc_progress::operation('Approving the prepared kiosk request and observing return');
    my ($journey, $child, $approver, $seconds, $soft, $exit) = @_;
    die 'approved-flow:binding' unless @_ == 6 && ref($journey) eq 'onpc_journey'
        && $child eq 'fixture-child' && $approver eq 'fixture-parent'
        && $seconds eq '75' && $soft eq '1' && ($exit eq 'automatic' || $exit eq 'immediate');
    $journey->consume_observation('approval-open', $journey->seen('approval-open'));
    onpc_password::enter_kiosk_mate_password($journey);
    $journey->consume_observation('approval-success', $journey->seen('approval-success'));
    $journey->consume_observation('new-returned', $journey->seen('new-returned'));
}

# FLOW06: the caller supplies GDM and enabled policy, never a previous attempt.
sub obtain_time {
    onpc_progress::operation('Obtaining time through a fresh request-station entry');
    my ($journey, $initial, $child, $approver, $seconds, $soft, $exit) = @_;
    die 'approved-flow:binding' unless @_ == 7 && ref($journey) eq 'onpc_journey'
        && ($initial eq 'default' || $initial eq 'selected')
        && $child eq 'fixture-child' && $approver eq 'fixture-parent'
        && $seconds eq '75' && $soft eq '1' && $exit eq 'automatic';
    prepare($journey, 'new', 'new', $initial, $child, $approver, $seconds, $soft);
    approve($journey, $child, $approver, $seconds, $soft, $exit);
}

# FLOW07 ends before any retry or form exit. The caller owns a later approval.
sub reject {
    onpc_progress::operation('Rejecting or cancelling one request and comparing the open form');
    my ($journey, $outcome, $child, $approver, $seconds, $soft) = @_;
    die 'approval-flow:binding' unless @_ == 6 && ref($journey) eq 'onpc_journey'
        && ($outcome eq 'rejection' || $outcome eq 'cancel')
        && $child eq 'fixture-child' && $approver eq 'fixture-parent'
        && $seconds eq '75' && $soft eq '1';
    $journey->consume_observation('flow-before', $journey->seen('flow-before'));
    if ($outcome eq 'rejection') {
        $journey->consume_observation('rejection-open', $journey->seen('rejection-open'));
        onpc_password::enter_kiosk_mate_password($journey, 'wrong');
        $journey->consume_observation('rejection-result', $journey->seen('rejection-result'));
    } else {
        $journey->consume_observation('flow-cancel', $journey->seen('flow-cancel'));
    }
    $journey->consume_observation('flow-preserved', $journey->seen('flow-preserved'));
}

# Requires the fixture child already selected in Parent. This preparation has
# no request or exit branch and can be composed with Cancel, Escape or approval.
sub daily_station_entry {
    onpc_progress::operation('Saving daily time and entering the request station');
    my ($journey) = @_;
    die 'request-flow:station-entry' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    for my $stage ('limit-enabled', 'save-enabled', 'allowance-15-select',
                   'allowance-15-read', 'time-explanation-read', 'switch-user', 'gdm-switched') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    return onpc_gdm::enter_station($journey, '');
}

sub run {
    onpc_progress::operation('Qualifying open and fresh kiosk request composition');
    my ($exchange, $mate) = @_;
    die 'request-flow:arguments' unless (@_ == 1 || @_ == 2 && ($mate eq 'mate' || $mate eq 'approval' || $mate eq 'rejection' || $mate eq 'immediate' || $mate eq 'approved-flow' || $mate eq 'flow-rejection' || $mate eq 'flow-cancel'))
        && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $mate && $mate =~ /^flow-/ ? 'kiosk-approval-flow' :
            $mate && ($mate eq 'immediate' || $mate eq 'approved-flow') ? 'kiosk-approval' :
            $mate && $mate eq 'rejection' ? 'kiosk-rejection' :
            $mate && $mate eq 'approval' ? 'kiosk-approval' : $mate ? 'mate-prompt' : 'request-flow', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('wrong-entry', 'valid-wrong-entry', ($mate ? ('mate-wrong-entry') : ())) {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    # Independent caller-owned entry; prepare(open) must not open it again.
    daily_station_entry($journey);
    prepare($journey, 'open', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1,
            ($mate ? ('invalid') : ()));
    $journey->consume_observation('open-mate', $journey->seen('open-mate')) if $mate;
    for my $stage ('open-cancel', 'open-returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    if ($mate && $mate eq 'approved-flow') {
        obtain_time($journey, 'selected', 'fixture-child', 'fixture-parent', 75, 1, 'automatic');
        $journey->finish();
        return;
    }
    prepare($journey, 'new', 'new', 'selected', 'fixture-child', 'fixture-parent', 75, 1);
    if ($mate && $mate =~ /^flow-(rejection|cancel)$/) {
        reject($journey, $1, 'fixture-child', 'fixture-parent', 75, 1);
        approve($journey, 'fixture-child', 'fixture-parent', 75, 1, 'automatic');
        $journey->finish();
        return;
    }
    if ($mate && ($mate eq 'approval' || $mate eq 'immediate')) {
        $journey->consume_observation('approval-open', $journey->seen('approval-open'));
        onpc_password::enter_kiosk_mate_password($journey);
        $journey->consume_observation('approval-success', $journey->seen('approval-success'));
    } elsif ($mate && $mate eq 'rejection') {
        $journey->consume_observation('rejection-open', $journey->seen('rejection-open'));
        onpc_password::enter_kiosk_mate_password($journey, 'wrong');
        for my $stage ('rejection-result', 'rejection-form') {
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    } elsif ($mate) {
        $journey->consume_observation('new-mate', $journey->seen('new-mate'));
    }
    for my $stage (($mate && ($mate eq 'approval' || $mate eq 'immediate') ? () : ('new-cancel')), 'new-returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
