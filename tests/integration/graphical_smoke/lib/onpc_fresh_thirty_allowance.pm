package onpc_fresh_thirty_allowance;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_app_rows ();
use onpc_feedback_privacy ();
use onpc_desktop_session ();
use onpc_lifecycle ();
use onpc_text ();

sub run {
    onpc_progress::operation('Qualifying fresh thirty-minute daily allowance setup');
    my ($exchange, $child) = @_;
    $child //= 'child';
    die 'fresh-thirty-allowance:arguments' unless (@_ == 1 || @_ == 2)
        && ref($exchange) eq 'CODE' && ($child eq 'child' || $child eq 'existing');
    my $prefix = $child eq 'child' ? 'fresh-thirty-allowance' : 'jordan-thirty-allowance';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => $prefix, review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', $child, 0, 30, 1));
    for my $stage ('balance-reread', 'wrong-child', 'wrong-state', 'wrong-window', 'final-settings') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
# Case composition: shared Parent entry, query/filter and complete-row leaves.
sub search_filters {
    onpc_progress::operation('Searching Jordan catalogue and checking unchanged app policies');
    my ($exchange) = @_;
    die 'search-filters:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'search-filters', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('parent-selected', onpc_parent::open_for_child(
        $journey, 'gdm', 'fresh', 'new', 'existing'));
    $journey->consume_observation('apps-page', $journey->seen('apps-page'));
    onpc_app_rows::read_rows($journey, 'initial-rows');
    onpc_app_rows::search($journey, 'catalogue-name', 'name-rows');
    onpc_app_rows::filter($journey, 'match-rule', 2, 'precise');
    onpc_app_rows::filter($journey, 'access-rule', 1, 'allowed');
    onpc_app_rows::read_rows($journey, 'filtered-rows');
    onpc_app_rows::filter($journey, 'match-rule', 3, 'restore-match');
    onpc_app_rows::filter($journey, 'access-rule', 7, 'restore-access');
    onpc_app_rows::search($journey, 'catalogue-clear', 'cleared-rows');
    $journey->finish();
}
# Parent app-policy/report case composition; mechanics remain in shared leaves.
sub match_editor_case {
    onpc_progress::operation('Checking saved app matching and rejection before child app use');
    my ($exchange, $declared, $challenges) = @_;
    die 'match-case:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'match-editor-case', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    for my $stage ('saved-settings', 'apps-page', 'initial-rule') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_app_rows::match_edit($journey, 'match-wildcard', 'confirmed',
        'confirmed-open', 'confirmed-read', 'confirmed-rule');
    onpc_app_rows::access_choice($journey, 'block-save', 'blocked-access');
    onpc_app_rows::match_edit($journey, 'match-rejected-directory', 'rejected',
        'rejected-open', 'rejected-read', undef);
    onpc_feedback_privacy::close_parent_report($journey, 'rejected');
    for my $stage ('restored-rule', 'restored-access', 'parent-logout') {
        $journey->seen($stage);
    }
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'other-child', 'fresh', 'success', 'child-entry');
    onpc_app_rows::native_blocked_app($journey->scope('blocked'), 'A');
    my $other = $journey->scope('nonmatching');
    onpc_app_rows::native_usable_app($other, 'command', $other->seen('desktop'), 'other-child', 'N');
    onpc_app_rows::native_finish_app($other);
    $journey->finish();
}

sub catalogue_refresh {
    my ($journey, $prefix) = @_;
    my $reopen = $journey->scope($prefix . 'reopen');
    onpc_lifecycle::reopen($reopen, 'parent', $reopen->seen('prior-window'), 'management');
    my $selection = $journey->scope($prefix . 'jordan');
    onpc_parent::select_child($selection, 'existing', $selection->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
}

sub catalogue_update_case {
    onpc_progress::operation('Keeping the parent draft open while the app package changes');
    my ($exchange, $declared, $challenges, $change) = @_;
    $change //= 'update';
    die 'catalogue-update:arguments' unless (@_ == 3 || @_ == 4) && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ($change eq 'update' || $change eq 'remove');
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'catalogue-' . $change, review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    $journey->seen($_) for qw(saved-settings apps-page block-save);
    onpc_app_rows::match_editor($journey, 'editor-open', 'opened-rule');
    onpc_text::replace_text($journey, 'match-update-wildcard', 'draft');
    $journey->seen($_) for qw(draft-before-update draft-after-update save);
    if ($change eq 'remove') {
        catalogue_refresh($journey, 'removed-');
        $journey->seen($_) for qw(removed-loaded-apps removed-row-absent);
    }
    catalogue_refresh($journey, '');
    $journey->seen($_) for qw(loaded-apps loaded-rule loaded-access parent-logout);
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'other-child', 'fresh', 'success', 'child-entry');
    $journey->seen('updated-launch');
    $journey->finish();
}

# Case 186 keeps lifecycle and child selection explicit; no implicit rule repair.
sub match_reopen_case {
    onpc_progress::operation('Checking remembered app rules and child access after reopening Parent');
    my ($exchange, $declared, $challenges) = @_;
    die 'match-reopen:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'match-reopen-case', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    $journey->seen($_) for qw(saved-settings apps-page initial-rule);
    onpc_app_rows::match_edit($journey, 'match-wildcard', 'custom',
        'custom-open', 'custom-read', 'custom-rule');
    onpc_app_rows::access_choice($journey, 'allowed-save', 'allowed-access');
    my $reopen = $journey->scope('custom-reopen');
    onpc_lifecycle::reopen($reopen, 'parent', $reopen->seen('prior-window'), 'management');
    my $selection = $journey->scope('custom-return');
    onpc_parent::select_child($selection, 'existing', $selection->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $selection->seen('apps-page');
    $journey->seen($_) for qw(remembered-rule remembered-access suggested-rule);
    onpc_app_rows::match_edit($journey, 'match-soft-precise', 'precise',
        'precise-open', 'precise-read', 'precise-rule');
    $selection = $journey->scope('select-riley');
    onpc_parent::select_child($selection, 'child', $selection->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $selection = $journey->scope('reselect-jordan');
    onpc_parent::select_child($selection, 'existing', $selection->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $selection->seen('apps-page');
    $journey->seen('reselected-suggested');
    onpc_app_rows::match_edit($journey, 'match-soft-precise', 'before-reopen',
        'before-reopen-open', 'before-reopen-read', 'before-reopen-rule');
    $reopen = $journey->scope('precise-reopen');
    onpc_lifecycle::reopen($reopen, 'parent', $reopen->seen('prior-window'), 'management');
    $selection = $journey->scope('precise-return');
    onpc_parent::select_child($selection, 'existing', $selection->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $selection->seen('apps-page');
    $journey->seen('reopened-suggested');
    onpc_app_rows::match_edit($journey, 'match-soft-precise', 'before-rejection',
        'before-rejection-open', 'before-rejection-read', 'before-rejection-rule');
    onpc_app_rows::match_edit($journey, 'match-rejected-directory', 'rejected',
        'rejected-open', 'rejected-read', undef);
    onpc_feedback_privacy::close_parent_report($journey, 'rejected');
    $journey->seen($_) for qw(restored-rule restored-access restored-suggested);
    onpc_app_rows::match_edit($journey, 'match-soft-precise', 'recovered',
        'recovered-open', 'recovered-read', 'recovered-rule');
    onpc_app_rows::access_choice($journey, 'soft-save', 'soft-access');
    $journey->seen($_) for qw(final-precise parent-logout);
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'other-child', 'fresh', 'success', 'child-entry');
    onpc_app_rows::native_blocked_app($journey->scope('blocked'), 'S');
    my $allowed = $journey->scope('allowed');
    onpc_app_rows::native_usable_app($allowed, 'command', $allowed->seen('desktop'), 'other-child');
    onpc_app_rows::native_finish_app($allowed);
    $journey->finish();
}

# Case 187 owns the complete forward/reverse block and recovery history.
sub shared_launchers_case {
    onpc_progress::operation('Checking that either launcher block prevents child access to their shared app');
    my ($exchange, $declared, $challenges) = @_;
    die 'shared-launchers:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'shared-launchers-case', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    $journey->seen($_) for qw(saved-settings apps-page initial-rows retained-window parent-session);
    for my $round (
        ['original-blocked', [['A', 'permanent'], ['Alias', 'allowed']], 0],
        ['original-allowed', [['A', 'allowed']], 1],
        ['alias-blocked', [['Alias', 'permanent']], 0],
        ['alias-allowed', [['Alias', 'allowed']], 1]) {
        my ($name, $edits, $usable) = @$round;
        for my $edit (@$edits) {
            my ($role, $choice) = @$edit;
            onpc_app_rows::edit_policy($journey, onpc_app_rows::fixture_app($role),
                $role eq 'Alias' ? 'match-alias-precise' : 'match-precise',
                $choice, "$name-" . lc($role), []);
        }
        onpc_text::replace_text($journey, 'catalogue-clear', "$name-clear");
        $journey->seen($_) for ("$name-original-choice", "$name-alias-choice",
                              "$name-leave-desktop", "$name-leave-switch", "$name-leave-greeter");
        onpc_desktop_session::enter_desktop(
            $journey, 'gdm', 'other-child', 'fresh', 'success', "$name-entry");
        for my $role ('A', 'Alias') {
            my $app = $journey->scope("$name-" . ($role eq 'A' ? 'original' : 'alias'));
            if ($usable) {
                onpc_app_rows::native_usable_app($app, 'grid', $app->seen('desktop'),
                    'other-child', $role eq 'Alias' ? $role : undef);
                onpc_app_rows::native_finish_app($app);
            } else {
                onpc_app_rows::native_blocked_app($app, $role, 'grid');
            }
        }
        $journey->seen($_) for ("$name-logout", "$name-greeter");
        if ($name ne 'alias-allowed') {
            onpc_desktop_session::enter_desktop(
                $journey, 'gdm', 'parent', 'retained', 'success', "$name-return");
            $journey->consume_observation("$name-supplied-parent-retained",
                onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained',
                                            'existing', "$name-supplied", 0));
            $journey->seen($_) for ("$name-parent-session", "$name-apps-page");
        }
    }
    $journey->finish();
}

sub special_paths_case {
    onpc_progress::operation('Checking that parent blocks deny special-path apps and their identical copies');
    my ($exchange, $declared, $challenges) = @_;
    die 'special-paths:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'special-paths-case', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    $journey->seen($_) for qw(saved-settings apps-page initial-rows space-copy comma-copy);
    for my $name ('hard', 'soft') {
        onpc_app_rows::access_choice($journey, "$name-$_-save", "$name-$_-row")
            for ('hard', 'comma');
        my $leaving = $journey->scope("$name-leave");
        onpc_desktop_session::switch_user($leaving, $leaving->seen('desktop'));
        onpc_desktop_session::enter_desktop(
            $journey, 'gdm', 'other-child', 'fresh', 'success', "$name-entry");
        for my $app (['space-original', 'H'], ['space-copy', 'SpaceCopy'],
                     ['comma-original', 'C'], ['comma-copy', 'CommaCopy']) {
            onpc_app_rows::native_blocked_app($journey->scope($name . '-' . $app->[0]), $app->[1]);
        }
        my $allowed = $journey->scope("$name-allowed");
        onpc_app_rows::native_usable_app($allowed, 'command', $allowed->seen('desktop'), 'other-child', 'N');
        onpc_app_rows::native_finish_app($allowed);
        $journey->seen($_) for ("$name-logout", "$name-greeter");
        onpc_desktop_session::enter_desktop(
            $journey, 'gdm', 'parent', 'retained', 'success', "$name-return");
        $journey->consume_observation("$name-supplied-parent-retained",
            onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained',
                                        'existing', "$name-supplied", 0));
        $journey->seen("$name-apps-page");
    }
    onpc_app_rows::access_choice($journey, "restore-$_-save", "restore-$_-row")
        for ('hard', 'comma');
    $journey->seen($_) for qw(space-cleanup comma-cleanup parent-logout);
    $journey->finish();
}

sub parent_error_report {
    onpc_progress::operation('Reviewing and closing reports from rejected Parent match rules');
    my ($exchange) = @_;
    die 'report:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'parent-error-report', review => 0);
    onpc_app_rows::native_entry($journey);
    for my $stage ('apps-page', 'initial-rule') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_app_rows::match_edit($journey, 'match-wildcard', 'confirmed',
        'confirmed-open', 'confirmed-read', 'confirmed-rule');
    onpc_app_rows::match_edit($journey, 'match-rejected-directory', 'rejected',
        'editor-open', 'editor-read', undef);
    onpc_feedback_privacy::review_parent_report($journey, 'review');
    $journey->consume_observation('restored-rule', $journey->seen('restored-rule'));
    onpc_app_rows::match_edit($journey, 'match-rejected-directory', 'repeat',
        'repeat-open', 'repeat-read', undef);
    onpc_feedback_privacy::close_parent_report($journey, 'decline');
    $journey->consume_observation('final-rule', $journey->seen('final-rule'));
    $journey->finish();
}
1;
