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
use onpc_allowance_boundaries ();
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
    die 'overlay-prompt:arguments' unless (@_ == 3 || @_ == 4 && $approval =~ /\A(?:approval|rejection|approval-immediate|approval-translated|flow-rejection|flow-cancel)\z/) && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => !$approval ? 'overlay-prompt' : $approval =~ /^flow-/ ? 'overlay-approval-flow'
            : $approval =~ /^approval/ ? 'overlay-approved-exit' : 'overlay-rejection', review => 0);
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
    if ($approval && $approval ne 'rejection') {
        $activity = onpc_app_rows::native_activity_entry($journey, 'activity', 'command');
    }
    overlay_entry($journey, 'direct', 'command');
    $journey->seen('wrong-surface-refused');
    prepare($journey, 'open', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1, 'overlay');
    if ($approval && $approval eq 'approval-translated') {
        onpc_parent::language_selection($journey, 'hebrew');
        $journey->seen($_) for ('hebrew-save', 'translated-estimate');
    }
    if ($approval && $approval ne 'rejection') {
        overlay_reject($journey, substr($approval, 5)) if $approval =~ /^flow-/;
        overlay_approve($journey, $approval eq 'approval-immediate' || $approval eq 'flow-cancel'
            ? 'immediate' : 'automatic');
    } else {
        if ($approval) {
            shell_reject($journey, 'rejection');
        } else {
            shell_cancel($journey, 'shell-cancel-ready', 'shell-dismissed');
        }
        $journey->seen('form-returned');
        $journey->seen('cancel');
    }
    $journey->seen('returned') unless $approval && $approval ne 'rejection';
    if ($approval && $approval ne 'rejection') {
        onpc_app_rows::native_read_activity($activity, 'returned');
        $journey->seen('countdown') if $approval eq 'approval-translated';
        onpc_app_rows::native_finish_app($activity);
    }
    $journey->finish();
}

sub overlay_language_history {
    onpc_progress::operation('Preserving the child request and saved activity across Hebrew approval and English restoration');
    my ($exchange, $declared, $challenges) = @_;
    die 'overlay-history:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'overlay-approved-exit', review => 0);
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
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    my $activity = onpc_app_rows::native_activity_entry($journey, 'activity', 'command');
    overlay_entry($journey, 'direct', 'command');
    prepare($journey, 'open', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1, 'overlay');
    $journey->seen('english-form');
    onpc_parent::language_selection($journey, 'hebrew');
    $journey->seen($_) for ('hebrew-save', 'hebrew-form', 'translated-estimate');
    overlay_approve($journey, 'automatic');
    onpc_app_rows::native_read_activity($activity, 'returned');
    $journey->seen('approved-countdown');
    overlay_entry($journey, 'reopened', 'command');
    onpc_parent::language_selection($journey, 'english');
    $journey->seen($_) for ('english-save', 'restored-form', 'cancel', 'cancel-returned');
    onpc_app_rows::native_read_activity($activity, 'restored');
    $journey->seen('restored-countdown');
    onpc_app_rows::native_finish_app($activity);
    $journey->finish();
}

sub overlay_approve {
    onpc_progress::operation('Approving the prepared overlay and observing its declared exit');
    my ($journey, $exit) = @_;
    die 'overlay-flow:exit' unless @_ == 2 && defined($exit)
        && ($exit eq 'automatic' || $exit eq 'immediate');
    shell_approve($journey, $exit);
    return $journey->seen('returned');
}

sub approval_return {
    onpc_progress::operation('Approving time and returning to the same child and saved work');
    my ($exchange, $declared, $challenges, $binding, $entry) = @_;
    die 'overlay-return:binding' unless @_ == 5 && ref($binding) eq 'ARRAY'
        && @$binding == 4 && ($entry eq 'new' || $entry eq 'open')
        && $binding->[0] =~ /\A(?:child|other-child)\z/
        && $binding->[1] =~ /\A(?:parent|other-parent)\z/
        && $binding->[2] =~ /\A(?:30|60|75|120|150|180|900)\z/
        && ($binding->[3] == 0 || $binding->[3] == 1);
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'overlay-approval-return', review => 0);
    $journey->{overlay_request} = $binding;
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, $binding->[0] eq 'child' ? 'child' : 'returned',
        $journey->seen('child-picker-opened'), 'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen('allowance-configured');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    my $recipient = $binding->[0] eq 'child' ? 'child' : 'standard';
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', "fresh-$recipient-focused", 'fresh-desktop');
    my $activity = onpc_app_rows::native_activity_entry($journey, 'activity', 'command');
    $journey->seen('before-countdown');
    $journey->seen('independent-launch') if $entry eq 'open';
    prepare($journey, $entry, $entry, 'observed',
        $binding->[0] eq 'child' ? 'fixture-child' : 'existing-fixture-child',
        $binding->[1] eq 'parent' ? 'fixture-parent' : 'other-fixture-parent',
        $binding->[2], $binding->[3], 'overlay');
    overlay_approve($journey, 'automatic');
    $journey->seen('countdown');
    onpc_app_rows::native_read_activity($activity, 'returned');
    onpc_app_rows::native_finish_app($activity);
    $journey->finish();
}

sub overlay_reject {
    onpc_progress::operation('Rejecting or cancelling the overlay and comparing the preserved form');
    my ($journey, $outcome) = @_;
    die 'overlay-flow:outcome' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && (($journey->{prefix} // '') eq 'overlay-approval-flow'
            || ($journey->{prefix} // '') eq 'baseline-journey-overlay-' . ($outcome // ''))
        && defined($outcome) && ($outcome eq 'rejection' || $outcome eq 'cancel');
    die 'overlay-flow:replay' if $journey->{shell_flow_started} || $journey->{invocation_failed};
    $journey->{shell_flow_started} = 1;
    my $preserved;
    my $ok = eval {
        $journey->seen('flow-before');
        if ($outcome eq 'rejection') {
            shell_reject($journey, 'rejection');
        } else {
            shell_cancel($journey, 'shell-cancel-ready', 'shell-dismissed');
        }
        $preserved = $journey->seen('flow-preserved');
        1;
    };
    unless ($ok) {
        $journey->{invocation_failed} = 1;
        die $@;
    }
    return $preserved;
}

sub shell_reject {
    onpc_progress::operation('Observing one wrong overlay password and safely cancelling its rejected challenge');
    my ($journey, $prefix) = @_;
    die 'shell-reject:binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($prefix) && $prefix =~ /\A[a-z][a-z0-9-]*\z/;
    die 'shell-reject:replay' if $journey->{shell_rejection_started} || $journey->{invocation_failed};
    $journey->{shell_rejection_started} = 1;
    my $ok = eval {
        $journey->consume_observation("$prefix-open", $journey->seen("$prefix-open"));
        onpc_password::enter_overlay_shell_password($journey, 'wrong', $prefix);
        $journey->consume_observation("$prefix-submit-ready", $journey->seen("$prefix-submit-ready"));
        testapi::send_key('ret');
        shell_cancel($journey, "$prefix-cancel-ready", "$prefix-dismissed");
        1;
    };
    unless ($ok) {
        $journey->{invocation_failed} = 1;
        die $@;
    }
}

sub shell_approve {
    onpc_progress::operation('Approving the declared overlay request once');
    my ($journey, $exit) = @_;
    $exit //= 'automatic';
    die 'shell-approve:binding' unless (@_ == 1 || @_ == 2) && ref($journey) eq 'onpc_journey'
        && (($journey->{prefix} // '') eq 'overlay-approved-exit'
            || ($journey->{prefix} // '') eq 'overlay-approval-flow'
            || ($journey->{prefix} // '') eq 'overlay-approval-return'
                && ref($journey->{overlay_request}) eq 'ARRAY' && $exit eq 'automatic'
            || ($journey->{prefix} // '') eq 'baseline-journey-overlay-approval'
                && $exit eq 'immediate')
        && ($exit eq 'automatic' || $exit eq 'immediate');
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
                && keys(%$proof) == 6 && ($proof->{stage} // '') eq
                    ($journey->{stage_prefix} // '') . 'approval-success'
                && ($proof->{binding} // '') eq 'overlay-approve'
                && ($proof->{child} // '') eq ($journey->{overlay_request}
                    ? $journey->{overlay_request}[0] : 'child')
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
    }
    $journey->invoke("$prefix-panel") if $route ne 'command';
    $journey->invoke("$prefix-launch");
    # The panel checkpoint proves focus on child-request-button by public ID.
    # StButtonAccessible has no Action interface; activate with one ordinary key.
    if ($route eq 'panel-reopen') {
        $journey->invoke("$prefix-overview");
    }
    return $journey->invoke("$prefix-form");
}

# FLOW12 owns the exit/entry and untouched destination read; the caller owns
# source capture, values and comparison endpoints. No request is submitted.
sub overlay_to_kiosk {
    onpc_progress::operation('Carrying the selected child choices from overlay to kiosk');
    my ($journey, $proof, $source_stage, $prefix, $child) = @_;
    die 'request-transfer:binding' unless @_ == 5 && ref($journey) eq 'onpc_journey'
        && $source_stage =~ /\A[a-z][a-z0-9-]*\z/ && $prefix =~ /\A[a-z][a-z0-9-]*\z/
        && ($child eq 'riley' || $child eq 'jordan');
    $journey->consume_observation($source_stage, $proof);
    my $section = $journey->scope($prefix);
    $section->seen($_) for qw(cancel desktop switch greeter);
    onpc_gdm::enter_station($section, '');
    $section->seen('child');
    return $section->seen('read');
}

sub qualify_choices_overlay_to_kiosk {
    onpc_progress::operation('Comparing both child overlays with independently remembered station choices');
    my ($exchange, $declared, $challenges) = @_;
    die 'request-transfer:arguments' unless @_ == 3 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'choices-overlay-to-kiosk', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    prepare_transfer_allowances($journey);
    onpc_gdm::enter_station($journey->scope('seed'), '');
    $journey->seen($_) for qw(seed-child seed-approver seed-cancel seed-returned);
    for my $binding (['riley', 'riley', 'child', 'fresh'],
                     ['jordan', 'jordan', 'other-child', 'fresh']) {
        my ($prefix, $child, $role, $entry) = @$binding;
        onpc_desktop_session::enter_desktop($journey, 'gdm', $role, $entry, 'success', "$prefix-entry");
        $journey->seen("$prefix-launch");
        $journey->seen("$prefix-$_") for qw(default refused approver custom text apps);
        my $source = $journey->seen("$prefix-source");
        # A wrong source receipt cannot release even the first Cancel.
        my $wrong = onpc_journey->new(exchange => $exchange, prefix => 'transfer-wrong', review => 0);
        my $accepted = eval { overlay_to_kiosk($wrong, $source, "$prefix-source", 'wrong-transfer', $child); 1 };
        die 'request-transfer:wrong-entry-accepted' if $accepted;
        die 'request-transfer:wrong-entry-refusal' unless $@ =~ /journey:stale-observation/;
        overlay_to_kiosk($journey, $source, "$prefix-source", "$prefix-transfer", $child);
        $journey->seen("$prefix-$_") for $prefix eq 'riley' ? qw(exit greeter) : ();
    }
    for my $child (qw(riley jordan)) {
        $journey->seen("$child-revisit-select");
        $journey->seen("$child-revisit-read");
    }
    $journey->finish();
}

sub prepare_transfer_allowances {
    onpc_progress::operation('Enabling both children with ample public daily time');
    my ($journey) = @_;
    die 'request-transfer:setup' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'initial',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    $journey->consume_observation('parent-selected', onpc_parent::select_child($journey, 'child',
        $journey->seen('child-picker-opened'), 'child-picker-opened', 'child-choice-highlighted', 'parent-selected'));
    $journey->seen('riley-allowance');
    $journey->consume_observation('existing-returned', onpc_parent::select_child($journey, 'returned',
        $journey->seen('existing-child-picker-opened'), 'existing-child-picker-opened',
        'existing-child-choice-highlighted', 'existing-returned'));
    $journey->seen('jordan-allowance');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
}

sub kiosk_to_overlay {
    onpc_progress::operation('Carrying the selected child choices from kiosk to overlay');
    my ($journey, $proof, $source_stage, $prefix, $child, $entry) = @_;
    die 'request-transfer:binding' unless @_ == 6 && ref($journey) eq 'onpc_journey'
        && $source_stage =~ /\A[a-z][a-z0-9-]*\z/ && $prefix =~ /\A[a-z][a-z0-9-]*\z/
        && ($child eq 'riley' || $child eq 'jordan') && ($entry eq 'fresh' || $entry eq 'retained');
    $journey->consume_observation($source_stage, $proof);
    my $section = $journey->scope($prefix);
    $section->seen($_) for qw(cancel greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm',
        $child eq 'riley' ? 'child' : 'other-child', $entry, 'success', "$prefix-entry");
    $section->seen('launch');
    return $section->seen('read');
}

sub qualify_cross_surface {
    onpc_progress::operation('Comparing both station choices with independently remembered overlay approvers');
    my ($exchange, $declared, $challenges) = @_;
    die 'request-transfer:arguments' unless @_ == 3 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'cross-surface', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    prepare_transfer_allowances($journey);
    for my $binding (['riley', 'child'], ['jordan', 'other-child']) {
        my ($child, $role) = @$binding;
        onpc_desktop_session::enter_desktop($journey, 'gdm', $role, 'fresh', 'success', "$child-seed-entry");
        $journey->seen("$child-seed-$_") for qw(launch default refused wrong-child approver cancel returned logout greeter);
    }
    onpc_gdm::enter_station($journey->scope('station'), '');
    for my $child (qw(riley jordan)) {
        $journey->seen("$child-$_") for qw(select approver custom text apps);
        my $source = $journey->seen("$child-source");
        my $wrong = onpc_journey->new(exchange => $exchange, prefix => 'transfer-wrong', review => 0);
        my $accepted = eval { kiosk_to_overlay($wrong, $source, "$child-source", 'wrong-transfer', $child, 'fresh'); 1 };
        die 'request-transfer:wrong-entry-accepted' if $accepted;
        die 'request-transfer:wrong-entry-refusal' unless $@ =~ /journey:stale-observation/;
        kiosk_to_overlay($journey, $source, "$child-source", "$child-transfer", $child, 'fresh');
        if ($child eq 'riley') {
            $journey->seen("$child-$_") for qw(exit desktop switch greeter);
            onpc_gdm::enter_station($journey->scope('next-station'), '');
        }
    }
    $journey->finish();
}

# FLOW04: finite, explicit choices. The caller prepares policy independently.
sub prepare {
    onpc_progress::operation('Preparing the declared kiosk request without submitting');
    my ($journey, $prefix, $entry, $initial, $child, $approver, $seconds, $soft, $invalid) = @_;
    if (@_ == 9 && $initial eq 'observed' && $invalid eq 'overlay') {
        die 'request-flow:binding' unless ref($journey) eq 'onpc_journey'
            && ($prefix eq 'open' || $prefix eq 'new') && ($entry eq 'open' || $entry eq 'new')
            && ($child eq 'fixture-child' || $child eq 'existing-fixture-child')
            && ($approver eq 'fixture-parent' || $approver eq 'other-fixture-parent')
            && $seconds =~ /\A(?:30|60|75|120|150|180|900)\z/ && ($soft == 0 || $soft == 1)
            && ref($journey->{overlay_request}) eq 'ARRAY'
            && $journey->{overlay_request}[0] eq ($child eq 'fixture-child' ? 'child' : 'other-child')
            && $journey->{overlay_request}[1] eq ($approver eq 'fixture-parent' ? 'parent' : 'other-parent')
            && $journey->{overlay_request}[2] == $seconds && $journey->{overlay_request}[3] == $soft;
        $journey->seen("$prefix-launch") if $entry eq 'new';
        $journey->seen("$prefix-choices");
        return $journey->seen("$prefix-estimate");
    }
    die 'request-flow:binding' unless (@_ == 8 || @_ == 9
        && ($invalid eq 'invalid' || $invalid eq 'overlay' || $invalid eq 'compact'))
        && ref($journey) eq 'onpc_journey'
        && ($prefix eq 'open' || $prefix eq 'new')
        && ($entry eq 'open' || $entry eq 'new')
        && ($initial eq 'default' || $initial eq 'selected')
        && $child eq 'fixture-child' && $approver eq 'fixture-parent'
        && ($seconds eq '75' || $seconds =~ /\A(?:120|180|240|600|1200)\z/
            && !defined($invalid))
        && $soft eq '1';
    my $compact = defined($invalid) && $invalid eq 'compact';
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
    if ($compact && $initial eq 'selected') {
        # Fresh reentry's complete public request is the result. Do not rewrite
        # unchanged persisted choices before independently comparing them.
        return $journey->consume_observation("$prefix-estimate", $journey->seen("$prefix-estimate"));
    }
    for my $suffix ('form', 'child', 'approver', 'selections') {
        next if $compact && $suffix eq 'selections';
        my $stage = "$prefix-$suffix";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    if ($seconds ne '75') {
        for my $suffix ('duration', 'duration-read', 'apps', 'estimate') {
            my $stage = "$prefix-$suffix";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
        return;
    }
    if ($invalid && !$compact) {
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
        next if $compact && $suffix eq 'duration-read';
        my $stage = "$prefix-$suffix";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

# The caller supplies the open form and immutable preceding choice state.
# These two finite transitions preserve soft-app inclusion while changing only
# the declared duration, using the same public operations as other requests.
sub continued_request {
    onpc_progress::operation('Preparing the next request from its observed saved choices');
    my ($journey, $surface, $initial_seconds, $seconds) = @_;
    die 'request-flow:continued-binding' unless @_ == 4 && ref($journey) eq 'onpc_journey'
        && (($surface eq 'kiosk' && $initial_seconds eq '75' && $seconds eq '600')
            || ($surface eq 'overlay' && $initial_seconds eq '600' && $seconds eq '75'));
    if ($surface eq 'kiosk') {
        $journey->consume_observation($_, $journey->seen($_))
            for qw(new-form new-child new-approver new-duration new-estimate);
    } else {
        $journey->consume_observation($_, $journey->seen($_))
            for qw(open-selections open-duration);
        onpc_text::replace_text($journey, 'overlay-fraction', 'open-text');
        $journey->consume_observation('open-estimate', $journey->seen('open-estimate'));
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
        && ($seconds eq '75' || $seconds =~ /\A(?:120|180|240|600|1200)\z/ && $exit eq 'automatic')
        && $soft eq '1' && ($exit eq 'automatic' || $exit eq 'immediate');
    $journey->consume_observation('approval-open', $journey->seen('approval-open'));
    if ($seconds ne '75' && $seconds ne '600') {
        onpc_password::enter_kiosk_mate_password($journey, 'request-' . $seconds);
    } elsif ($seconds eq '600') {
        onpc_password::enter_kiosk_mate_password($journey, 'long-request');
    } else {
        onpc_password::enter_kiosk_mate_password($journey);
    }
    $journey->consume_observation('approval-success', $journey->seen('approval-success'));
    $journey->consume_observation('new-returned', $journey->seen('new-returned'));
}

sub prepare_chinese {
    onpc_progress::operation('Preparing the declared Chinese Jordan request');
    my ($journey, $prefix) = @_;
    die 'request-flow:chinese-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && ($prefix eq 'first' || $prefix eq 'second');
    $journey->consume_observation("$prefix-duration", $journey->seen("$prefix-duration"));
    onpc_text::replace_text($journey, 'chinese-kiosk-fraction', "$prefix-text");
    for my $suffix ('apps', 'choices') {
        $journey->consume_observation("$prefix-$suffix", $journey->seen("$prefix-$suffix"));
    }
}

sub approve_chinese {
    onpc_progress::operation('Approving one freshly qualified Chinese native challenge');
    my ($journey, $prefix) = @_;
    die 'approved-flow:chinese-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && ($prefix eq 'first' || $prefix eq 'second');
    $journey->consume_observation("$prefix-approval-open", $journey->seen("$prefix-approval-open"));
    onpc_password::enter_kiosk_mate_password($journey, "chinese-$prefix");
    $journey->consume_observation("$prefix-approval-success", $journey->seen("$prefix-approval-success"));
}

sub chinese_native_auth {
    onpc_progress::operation('Qualifying Chinese native approvals across two fresh kiosk sessions');
    my ($exchange) = @_;
    die 'chinese-auth:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'chinese-native-auth', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for ('chinese-assets', 'wrong-entry');
    my $other = onpc_parent::select_child($journey, 'returned',
        $journey->seen('existing-child-picker-opened'), 'existing-child-picker-opened',
        'existing-child-choice-highlighted', 'existing-returned');
    $journey->consume_observation('existing-returned', $other);
    $journey->seen($_) for ('other-enabled', 'other-saved', 'switch-user', 'gdm-switched');
    onpc_gdm::enter_station($journey, '');
    $journey->seen('other-first-parent');
    $journey->seen('first-language');
    prepare_chinese($journey, 'first');
    approve_chinese($journey, 'first');
    $journey->seen('first-returned');
    onpc_gdm::enter_station($journey, 'cancel-');
    $journey->seen('second-language');
    prepare_chinese($journey, 'second');
    approve_chinese($journey, 'second');
    $journey->seen('second-returned');
    $journey->finish();
}

sub overlay_reminder_editing {
    onpc_progress::operation('Qualifying saved child overlay reminders and discarded drafts');
    my ($exchange, $invocations, $challenges) = @_;
    die 'overlay-reminders:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'overlay-reminders', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for ('wrong-entry', 'allowance-configured', 'policy-before', 'wrong-account-refused');
    $journey->consume_observation('logout-ready', $journey->seen('logout-ready'));
    $journey->seen($_) for ('logout', 'gdm-logged-out');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    overlay_entry($journey, 'direct', 'command');
    $journey->seen($_) for ('initial-save', 'initial-form',
        'defaults-open', 'created', 'edited', 'saved', 'saved-read', 'deleted-draft',
        'cancelled', 'cancel-read', 'cleared-draft', 'empty-saved', 'empty-read', 'empty-close',
        'final-form', 'cancel', 'returned', 'child-switch-user', 'child-gdm-switched');
    my $returned_desktop = onpc_gdm::sign_in_challenge($journey, 'return-parent',
        'return-greeter', 'return-focused', 'return-desktop');
    onpc_parent::launch($journey, $returned_desktop, 'management', 'return-desktop');
    $selected = onpc_parent::select_child($journey, 'child', $journey->seen('return-child-picker-opened'),
        'return-child-picker-opened', 'return-child-choice-highlighted', 'return-parent-selected');
    $journey->consume_observation('return-parent-selected', $selected);
    $journey->seen('policy-after');
    $journey->finish();
}

sub reminder_fullscreen_preference {
    onpc_progress::operation('Qualifying saved fullscreen reminder preference and discarded changes');
    my ($exchange, $invocations, $challenges) = @_;
    die 'reminder-fullscreen:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'reminder-fullscreen', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for ('allowance-configured', 'policy-before', 'logout-ready', 'logout',
        'gdm-logged-out');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    overlay_entry($journey, 'direct', 'command');
    $journey->seen($_) for ('initial-save', 'initial-form', 'defaults-open', 'fullscreen-disabled',
        'saved', 'saved-read', 'fullscreen-enabled-draft', 'cancelled', 'cancel-read',
        'preferences-close', 'final-form', 'cancel', 'returned', 'child-logout', 'child-logged-out');
    $desktop = onpc_gdm::sign_in_challenge($journey, 'return-parent',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
    onpc_parent::launch($journey, $desktop, 'management', 'return-desktop');
    $selected = onpc_parent::select_child($journey, 'child', $journey->seen('return-child-picker-opened'),
        'return-child-picker-opened', 'return-child-choice-highlighted', 'return-parent-selected');
    $journey->consume_observation('return-parent-selected', $selected);
    $journey->seen('policy-after');
    $journey->finish();
}

sub overlay_language {
    onpc_progress::operation('Qualifying child overlay language and normal command relaunch');
    my ($exchange, $invocations, $challenges) = @_;
    die 'overlay-language:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'overlay-language', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for ('wrong-entry', 'allowance-configured', 'policy-before', 'wrong-account-refused');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    overlay_entry($journey, 'direct', 'command');
    $journey->seen($_) for ('initial-save', 'initial-form');
    for my $prefix ('german', 'cancel-chinese', 'chinese', 'hebrew', 'english', 'final-german') {
        onpc_parent::language_selection($journey, $prefix);
        $journey->seen("$prefix-$_") for ('response', 'form', 'retained', 'close', 'closed-form');
    }
    $journey->seen($_) for ('cancel', 'returned');
    overlay_entry($journey, 'renewed', 'command');
    $journey->seen($_) for ('reentered-open', 'reentered-close', 'final-form',
                           'final-cancel', 'final-returned', 'child-switch-user', 'child-gdm-switched');
    onpc_gdm::sign_in_challenge($journey, 'return-parent', 'return-greeter', 'return-focused', 'return-desktop');
    $journey->seen('policy-after');
    $journey->finish();
}

sub panel_language_refresh {
    onpc_progress::operation('Checking that the child countdown follows the saved language without extra time');
    my ($exchange, $invocations, $challenges) = @_;
    die 'panel-language:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'panel-language', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for ('allowance-configured', 'policy-before');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    overlay_entry($journey, 'direct', 'command');
    $journey->seen($_) for ('initial-save', 'initial-form', 'initial-cancel', 'initial-returned');
    $journey->invoke('panel-before');
    overlay_entry($journey, 'renewed', 'command');
    onpc_parent::language_selection($journey, 'hebrew');
    $journey->seen($_) for ('hebrew-save', 'hebrew-form', 'cancel', 'returned');
    $journey->invoke('panel-after');
    $journey->seen($_) for ('child-switch-user', 'child-gdm-switched');
    onpc_gdm::sign_in_challenge($journey, 'return-parent', 'return-greeter', 'return-focused', 'return-desktop');
    $journey->seen('policy-after');
    $journey->finish();
}

sub panel_language_expiry {
    onpc_progress::operation('Following the child language changes, original work and countdown until time runs out');
    my ($exchange, $invocations, $challenges) = @_;
    die 'panel-expiry:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'panel-expiry', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::daily_time_settings($journey, 'desktop', 'parent', 'same-user', 'new', 'child', 0, 10);
    $journey->consume_observation('policy-before', $journey->seen('policy-before'));
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    onpc_app_rows::native_activity_entry($journey, 'activity', 'command', 'child');
    overlay_entry($journey, 'direct', 'command');
    $journey->seen($_) for ('initial-save', 'initial-form', 'initial-cancel', 'initial-returned');
    $journey->invoke('initial-countdown');
    for my $language ('hebrew', 'english') {
        overlay_entry($journey, "$language-entry", 'command');
        onpc_parent::language_selection($journey, $language);
        $journey->seen("$language-$_") for ('save', 'form', 'cancel', 'returned');
        onpc_app_rows::native_read_activity($journey, "$language-activity");
        $journey->invoke($language eq 'hebrew' ? 'panel-hebrew' : 'panel-restored');
    }
    $journey->invoke($_) for ('minute-progression', 'final-second-transition',
        'second-progression', 'independent-second-progression', 'natural-expiry');
    $journey->consume_observation('lock-input-ready', $journey->invoke('lock-input-ready'));
    testapi::send_key('shift');
    $journey->invoke('lock-result');
    $journey->seen($_) for ('return-greeter', 'returned-gdm');
    onpc_gdm::sign_in_challenge($journey, 'return-parent',
        'parent-greeter', 'parent-focused-return', 'parent-desktop-return');
    $journey->seen('policy-after');
    $journey->finish();
}

sub kiosk_language_history {
    onpc_progress::operation('Checking that the child request language stays independent of the approving parent');
    my ($exchange, $invocations, $challenges) = @_;
    die 'kiosk-language-history:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'kiosk-language-history', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen($_) for qw(limit-enabled save-enabled switch-user gdm-switched);
    onpc_gdm::enter_station($journey, '');
    prepare($journey, 'open', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1, 'compact');
    $journey->seen('english-form');
    onpc_parent::language_selection($journey, 'hebrew');
    $journey->seen($_) for qw(hebrew-save hebrew-form casey-select casey-form);
    onpc_parent::language_selection($journey, 'english');
    $journey->seen($_) for qw(english-save restored-form cancel returned);
    $journey->finish();
}

sub kiosk_language_restoration {
    onpc_progress::operation('Qualifying selected-child kiosk language restoration and approver independence');
    my ($exchange, $invocations, $challenges) = @_;
    die 'kiosk-language-restoration:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'kiosk-language-restoration', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('parent-selected',
        onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child'));
    $journey->seen($_) for ('wrong-entry', 'limit-enabled', 'save-enabled', 'riley-policy-before');
    onpc_allowance_boundaries::select_child($journey, 'jordan');
    $journey->seen($_) for ('other-enabled', 'other-saved', 'jordan-policy-before', 'switch-user', 'gdm-switched');
    onpc_gdm::enter_station($journey, 'initial-');
    $journey->seen($_) for ('initial-language', 'initial-save', 'jordan-jamie', 'jordan-original');
    onpc_parent::language_selection($journey, 'german');
    $journey->seen($_) for ('german-save', 'german-form', 'account-refusals', 'riley-initial', 'riley-original');
    onpc_parent::language_selection($journey, 'hebrew');
    $journey->seen($_) for ('hebrew-save', 'hebrew-form');
    for my $child ('jordan', 'riley') {
        $journey->seen("$child-restored");
        $journey->seen("$child-retained-$_") for ('form', 'open', 'close');
        for my $approver ('casey', 'jamie-restored') {
            $journey->seen("$child-$approver");
            $journey->seen("$child-$approver-$_") for ('form', 'open', 'close');
        }
    }
    $journey->seen($_) for ('jordan-before-exit', 'cancel', 'returned');
    onpc_gdm::enter_station($journey, 'renewed-');
    $journey->seen("jordan-reentered-$_") for ('form', 'open', 'close');
    $journey->seen('riley-reentered');
    $journey->seen("riley-reentered-$_") for ('form', 'open', 'close');
    $journey->seen('jordan-final');
    $journey->seen("jordan-final-$_") for ('form', 'open', 'close');
    $journey->seen($_) for ('final-cancel', 'final-returned');
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    my $returned_desktop = onpc_gdm::sign_in_challenge(
        $journey, 'return-parent', 'return-greeter', 'return-focused', 'return-desktop');
    # Desktop discovery does not bind the retained Parent endpoint. Use ordinary
    # app entry once, then independently bind its API surface before policy reads.
    onpc_parent::launch($journey, $returned_desktop, 'management', 'return-desktop');
    $journey->seen('jordan-policy-after');
    onpc_allowance_boundaries::select_child($journey, 'riley-final');
    $journey->seen($_) for ('riley-policy-after', 'parent-english-open', 'parent-english-close');
    $journey->finish();
}

sub kiosk_language {
    onpc_progress::operation('Qualifying kiosk personal language and normal station re-entry');
    my ($exchange, $invocations, $challenges) = @_;
    die 'kiosk-language:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'kiosk-language', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen('wrong-entry');
    my $other = onpc_parent::select_child($journey, 'returned',
        $journey->seen('existing-child-picker-opened'), 'existing-child-picker-opened',
        'existing-child-choice-highlighted', 'existing-returned');
    $journey->consume_observation('existing-returned', $other);
    $journey->seen($_) for ('other-enabled', 'other-saved', 'policy-before', 'switch-user', 'gdm-switched');
    onpc_gdm::enter_station($journey, 'initial-');
    $journey->seen($_) for ('initial-language', 'initial-retained', 'initial-save', 'other-first-parent', 'initial-form');
    for my $prefix ('german', 'cancel-chinese', 'chinese', 'hebrew', 'english', 'final-german') {
        onpc_parent::language_selection($journey, $prefix);
        $journey->seen("$prefix-$_") for ('response', 'form', 'retained', 'close');
    }
    $journey->seen($_) for ('cancel', 'returned');
    onpc_gdm::enter_station($journey, 'renewed-');
    $journey->seen($_) for ('reentered-form', 'reentered-open', 'reentered-close', 'final-form');
    onpc_parent::language_selection($journey, 'restore-english');
    $journey->seen($_) for ('restore-english-save', 'restore-english-form', 'final-cancel', 'final-returned');
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    my $returned_desktop = onpc_gdm::sign_in_challenge(
        $journey, 'return-parent', 'return-greeter', 'return-focused', 'return-desktop');
    # Rebind the retained Parent endpoint after leaving the kiosk session.
    onpc_parent::launch($journey, $returned_desktop, 'management', 'return-desktop');
    $journey->seen($_) for ('policy-after', 'restore-policy');
    $journey->finish();
}

# FLOW06: the caller supplies GDM and enabled policy, never a previous attempt.
sub obtain_time {
    onpc_progress::operation('Obtaining time through a fresh request-station entry');
    my ($journey, $initial, $child, $approver, $seconds, $soft, $exit) = @_;
    die 'approved-flow:binding' unless @_ == 7 && ref($journey) eq 'onpc_journey'
        && ($initial eq 'default' || $initial eq 'selected')
        && $child eq 'fixture-child' && $approver eq 'fixture-parent'
        && ($seconds eq '75' || $seconds =~ /\A(?:120|180|240|600|1200)\z/)
        && $soft eq '1' && $exit eq 'automatic';
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

sub auth_pause {
    onpc_progress::operation('Approving the same MATE challenge after the guarded human pause');
    my ($exchange, $declared, $challenges) = @_;
    die 'auth-pause:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'baseline-auth-pause', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 0, 1));
    $journey->seen($_) for qw(switch-user gdm-switched);
    onpc_gdm::enter_station($journey, '');
    prepare($journey, 'new', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1);
    # The durable opening reply is withheld by TIME03. It carries no recipient
    # authority; the password helper obtains both proofs after that reply.
    approve($journey, 'fixture-child', 'fixture-parent', 75, 1, 'automatic');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'return');
    $journey->consume_observation('supplied-parent-retained', onpc_parent::open_for_child(
        $journey, 'desktop', 'same-user', 'retained', 'child', 'supplied'));
    $journey->seen('approved-balance');
    $journey->finish();
}

sub run {
    onpc_progress::operation('Qualifying open and fresh kiosk request composition');
    my ($exchange, $mate, $declared, $challenges) = @_;
    die 'request-flow:arguments' unless (@_ == 1 || @_ == 4 && $mate eq 'approval'
        || @_ == 2 && ($mate eq 'mate' || $mate eq 'rejection' || $mate eq 'immediate' || $mate eq 'approved-flow' || $mate eq 'flow-rejection' || $mate eq 'flow-cancel'))
        && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $mate && $mate =~ /^flow-/ ? 'kiosk-approval-flow' :
            $mate && ($mate eq 'immediate' || $mate eq 'approved-flow') ? 'kiosk-approval' :
            $mate && $mate eq 'rejection' ? 'kiosk-rejection' :
            $mate && $mate eq 'approval' ? 'kiosk-approval' : $mate ? 'mate-prompt' : 'request-flow', review => 0);
    if ($mate && $mate eq 'approval') {
        $journey->declare_invocations($declared);
        $journey->declare_challenges($challenges);
    }
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
    if ($mate && $mate eq 'approval') {
        onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'return');
        $journey->consume_observation('supplied-parent-retained',
            onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'child', 'supplied'));
        $journey->consume_observation('approved-balance', $journey->seen('approved-balance'));
    }
    $journey->finish();
}
1;
