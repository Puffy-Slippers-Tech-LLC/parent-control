package onpc_parent;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_gdm ();
use onpc_password ();

sub login_functional {
    onpc_progress::operation('Signing in as [Parent user]');
    my ($journey) = @_;
    die 'parent:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_gdm::reattach_functional();
    return sign_in($journey, 'parent', 'success');
}

# GDM07: registered fresh accounts; setup reattachment belongs to the envelope.
sub sign_in {
    onpc_progress::operation('Signing in through the greeter');
    my ($journey, $account, $expected) = @_;
    die 'parent:entry-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && ($account eq 'parent' || $account eq 'other-child')
        && $expected eq 'success';
    my $list = $journey->seen('installed-greeter');
    my $prefix = $account eq 'parent' ? 'parent' : 'standard';
    onpc_gdm::choose_account($journey, $account, $list, 'installed-greeter', "$prefix-focused");
    # GDM05 keeps both fresh controller recipient checks and the sealed UI19 API.
    $account eq 'parent' ? onpc_password::enter_parent_gdm_password($journey)
        : onpc_password::enter_standard_gdm_password($journey);
    testapi::send_key('ret');
    return $journey->seen('desktop');
}

# SEARCH01: consume an independently observed desktop; return the empty field.
sub open_search {
    onpc_progress::operation('Opening public app search');
    my ($journey, $desktop, $surface) = @_;
    die 'parent:search-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $surface eq 'overview';
    $journey->consume_observation('desktop', $desktop);
    # A modal can consume Super-A. Require a prompt-free desktop before the
    # single opening gesture; routine search never exercises keyring dismissal.
    $journey->seen('system-prompt');
    testapi::send_key('super-a');
    return $journey->seen('app-grid');
}

# UI21: the controller focuses the ID-addressed provider field semantically and
# independently observes focus before acknowledging this stage.
sub focus_search {
    onpc_progress::operation('Focusing the app search field');
    my ($journey, $field, $surface) = @_;
    die 'parent:search-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $surface eq 'overview';
    $journey->consume_observation('app-grid', $field);
    return $journey->seen('search-focused');
}

# SEARCH03: one complete query and independent final read, without input repair.
sub enter_search_query {
    onpc_progress::operation('Entering the Parent app search query');
    my ($journey, $focused, $product) = @_;
    die 'parent:search-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $product eq 'Oh No! Parent Control';
    $journey->consume_observation('search-focused', $focused);
    testapi::type_string($product, max_interval => 20);
    return $journey->seen('search-entered');
}

# SEARCH06: explicit observed desktop; stop at the launchable result, before Enter.
sub search_whole_query {
    onpc_progress::operation('Finding Parent through public app search');
    my ($journey, $desktop, $product, $result_stage) = @_;
    die 'parent:search-binding' unless @_ == 4 && ref($journey) eq 'onpc_journey'
        && (($product eq 'Oh No! Parent Control' && $result_stage eq 'app-grid')
            || ($product eq 'ONPC Allowed Fixture'
                && ($result_stage eq 'app-grid' || $result_stage eq 'refusals')));
    $journey->consume_observation('desktop', $desktop);
    testapi::send_key('super-a');
    my $field = $journey->seen('search-ready');
    $journey->consume_observation('search-ready', $field);
    my $focused = $journey->seen('search-focused');
    $journey->consume_observation('search-focused', $focused);
    testapi::type_string($product);
    $journey->seen('search-entered');
    return $journey->seen($result_stage);
}

# SEARCH05: explicit discovery-test exception; never ordinary Parent setup.
sub open_from_app_grid {
    onpc_progress::operation('Finding and launching Parent from the app grid');
    my ($journey, $desktop) = @_;
    die 'parent:launch-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    my $result = search_whole_query($journey, $desktop, 'Oh No! Parent Control', 'app-grid');
    return launch_search_result($journey, $result, 'management');
}

# SEARCH05's commit step also accepts the fresh result proof returned after
# FIX02. The fixture checkpoint rechecks result focus before its durable reply.
sub launch_search_result {
    onpc_progress::operation('Launching the focused Parent search result');
    my ($journey, $result, $expected) = @_;
    my %stages = (
        management => ['app-grid', 'parent-window'],
        empty => ['fixture-requested', 'empty'],
    );
    die 'parent:launch-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && defined($expected) && exists($stages{$expected});
    my ($before, $after) = @{$stages{$expected}};
    $journey->consume_observation($before, $result);
    testapi::send_key('ret');
    return $journey->seen($after);
}

# PARENT01: fixed public command, then independent owned-window observation.
sub launch {
    onpc_progress::operation('Opening Parent');
    my ($journey, $desktop, $expected, $desktop_stage) = @_;
    $desktop_stage //= 'desktop';
    die 'parent:launch-binding' unless (@_ == 3 || @_ == 4) && ref($journey) eq 'onpc_journey'
        && ($desktop_stage eq 'desktop' || $desktop_stage eq 'reboot-desktop'
            || $desktop_stage eq 'same-desktop' || $desktop_stage eq 'repeat-desktop'
            || $desktop_stage eq 'return-desktop')
        && ($expected eq 'management' || $expected eq 'denied' || $expected eq 'initial-language');
    $journey->consume_observation($desktop_stage, $desktop);
    # The controller executes the installed command once as this desktop user.
    # A transport failure is uncertain input; no terminal/search fallback.
    my $prefix = $desktop_stage eq 'same-desktop' ? 'same-'
        : $desktop_stage eq 'repeat-desktop' ? 'repeat-'
        : $desktop_stage eq 'return-desktop' ? 'return-' : '';
    $journey->seen($prefix . 'parent-command');
    return $journey->seen($prefix . ($expected eq 'management' ? 'parent-window'
        : $expected eq 'initial-language' ? 'initial-language' : 'management-denied'));
}

sub language_selection {
    onpc_progress::operation('Opening Preferences and selecting the declared language');
    my ($journey, $prefix) = @_;
    die 'parent:language-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && $prefix =~ /^[a-z][a-z0-9-]*$/;
    for my $suffix ('open', 'choose') {
        my $stage = "$prefix-$suffix";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

sub named_management {
    onpc_progress::operation('Opening Parent and independently selecting the declared child');
    my ($journey, $prefix, $child) = @_;
    die 'parent:named-management' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && defined($child) && ($child eq 'child' || $child eq 'existing');
    my $section = $journey->scope($prefix);
    $section->seen($_) for qw(parent-command parent-window);
    my $selected = select_child($section, $child,
        $section->seen('child-picker-opened'), 'child-picker-opened',
        'child-choice-highlighted', 'parent-selected');
    $section->consume_observation('parent-selected', $selected);
}

sub qualify_language {
    onpc_progress::operation('Qualifying installed Parent personal language selection');
    my ($exchange) = @_;
    die 'parent:language-arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    require onpc_journey;
    require onpc_lifecycle;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'parent-language', review => 0);
    my $desktop = login_functional($journey);
    $journey->consume_observation('initial-language', launch($journey, $desktop, 'initial-language'));
    for my $stage ('initial-save', 'initial-state') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    for my $prefix ('german', 'cancel-chinese', 'chinese', 'hebrew', 'english') {
        language_selection($journey, $prefix);
        my @stages = $prefix eq 'cancel-chinese' ? ('cancel-response', 'cancel-state')
            : ("$prefix-save", "$prefix-state");
        for my $stage (@stages) {
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    }
    onpc_lifecycle::reopen($journey, 'parent', $journey->seen('prior-window'), 'management');
    for my $stage ('relaunched-state', 'relaunched-open', 'relaunched-cancel', 'final-state') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}

sub language_presentation_roundtrip {
    onpc_progress::operation('Saving language and checking the independently reopened preference');
    my ($journey, $prefix) = @_;
    die 'parent:language-roundtrip-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && $prefix =~ /^[a-z][a-z0-9-]*$/;
    language_selection($journey, $prefix);
    for my $suffix ('save', 'state', 'reopen') {
        my $stage = "$prefix-$suffix";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    for my $suffix ('cancel', 'preserved') {
        my $stage = "$prefix-$suffix";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

# Customer changes language once and independently reads the resulting policy.
sub language_save {
    onpc_progress::operation('Changing language while preserving the saved policy');
    my ($journey, $prefix) = @_;
    die 'parent:language-save-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && $prefix =~ /^[a-z][a-z0-9-]*$/;
    language_selection($journey, $prefix);
    $journey->consume_observation("$prefix-$_", $journey->seen("$prefix-$_")) for ('save', 'state');
}

sub qualify_rtl {
    onpc_progress::operation('Qualifying Parent Hebrew public text and saved language');
    my ($exchange) = @_;
    die 'parent:rtl-arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    require onpc_journey;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'parent-rtl', review => 0);
    my $desktop = login_functional($journey);
    $journey->consume_observation('initial-language', launch($journey, $desktop, 'initial-language'));
    $journey->consume_observation($_, $journey->seen($_)) for qw(initial-save initial-state);
    for my $prefix ('english-entry', 'hebrew', 'english-return') {
        language_presentation_roundtrip($journey, $prefix);
    }
    $journey->finish();
}

sub qualify_dialog_language {
    onpc_progress::operation('Qualifying inherited Parent dialog language and retained draft');
    my ($exchange) = @_;
    die 'parent:dialog-language-arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    require onpc_journey;
    require onpc_text;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'parent-dialog-language', review => 0);
    my $desktop = login_functional($journey);
    $journey->consume_observation('initial-language', launch($journey, $desktop, 'initial-language'));
    $journey->consume_observation($_, $journey->seen($_)) for
        qw(initial-save initial-state about-refused feedback-refused feedback-empty);
    onpc_text::replace_text($journey, $_) for qw(body-rtl reply-rtl);
    $journey->consume_observation('draft-seeded', $journey->seen('draft-seeded'));
    dialog_close($journey, 'draft');
    for my $language ('english', 'hebrew', 'restored') {
        language_selection($journey, $language);
        $journey->consume_observation($_, $journey->seen($_)) for ("$language-save", "$language-state");
        for my $surface ('about', 'feedback') {
            my $prefix = "$language-$surface-first";
            dialog_visit($journey, $prefix,
                $language eq 'hebrew' && $surface eq 'feedback' ? 'rtl' : 'ltr');
            $journey->consume_observation("$prefix-refused", $journey->seen("$prefix-refused"));
        }
    }
    $journey->finish();
}

sub dialog_close {
    onpc_progress::operation('Closing the owned Parent dialog and confirming its absence');
    my ($journey, $prefix) = @_;
    die 'parent:dialog-close-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && $prefix =~ /^[a-z][a-z0-9-]*$/;
    $journey->consume_observation("$prefix-close", $journey->seen("$prefix-close"));
    testapi::send_key('alt-f4');
    $journey->consume_observation("$prefix-closed", $journey->seen("$prefix-closed"));
}

sub dialog_visit {
    onpc_progress::operation('Reading inherited Parent dialog text and retained draft');
    my ($journey, $prefix, $direction) = @_;
    die 'parent:dialog-visit-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $prefix =~ /^[a-z][a-z0-9-]*$/ && $direction =~ /^(ltr|rtl)$/;
    $journey->consume_observation("$prefix-open", $journey->seen("$prefix-open"));
    $journey->consume_observation("$prefix-read", $journey->seen("$prefix-read"));
    dialog_close($journey, $prefix);
}

# Opening the dialog already reads its public contents. A fresh close proof
# still owns Alt-F4; no second content-only checkpoint is needed.
sub dialog_use {
    onpc_progress::operation('Reading the dialog and returning to Parent');
    my ($journey, $prefix) = @_;
    die 'parent:dialog-use-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && $prefix =~ /^[a-z][a-z0-9-]*$/;
    $journey->consume_observation("$prefix-open", $journey->seen("$prefix-open"));
    dialog_close($journey, $prefix);
}

sub qualify_hebrew_policy {
    onpc_progress::operation('Qualifying enabled Parent English Hebrew English policy readback');
    my ($exchange) = @_;
    die 'parent:hebrew-policy-arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    require onpc_journey;
    require onpc_allowance_boundaries;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'parent-hebrew-policy', review => 0);
    my $desktop = login_functional($journey);
    $journey->consume_observation('initial-language', launch($journey, $desktop, 'initial-language'));
    $journey->consume_observation('initial-save', $journey->seen('initial-save'));
    onpc_allowance_boundaries::select_child($journey, 'riley-setup', 'keyboard');
    for my $stage (qw(riley-enabled riley-saved riley-allowance riley-before)) {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    for my $prefix ('english-entry', 'hebrew', 'english-return') {
        language_presentation_roundtrip($journey, $prefix);
    }
    $journey->finish();
}

sub qualify_language_isolation {
    onpc_progress::operation('Qualifying Parent Chinese language across enabled child selection');
    my ($exchange) = @_;
    die 'parent:language-isolation-arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    require onpc_journey;
    require onpc_lifecycle;
    require onpc_allowance_boundaries;
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => 'parent-language-isolation', review => 0);
    my $desktop = login_functional($journey);
    $journey->consume_observation('initial-language', launch($journey, $desktop, 'initial-language'));
    $journey->consume_observation('initial-save', $journey->seen('initial-save'));
    for my $child ('riley', 'jordan') {
        onpc_allowance_boundaries::select_child($journey, "$child-setup", 'keyboard');
        for my $suffix ('enabled', 'saved', 'allowance', 'before') {
            my $stage = "$child-$suffix";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    }
    language_selection($journey, 'chinese');
    $journey->consume_observation('chinese-save', $journey->seen('chinese-save'));
    for my $prefix ('riley', 'jordan', 'riley-return') {
        onpc_allowance_boundaries::select_child($journey, $prefix, 'keyboard');
        for my $suffix ('state', 'choice', 'close') {
            my $stage = "$prefix-$suffix";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    }
    onpc_lifecycle::reopen($journey, 'parent', $journey->seen('prior-window'), 'management');
    for my $prefix ('reopened-riley', 'reopened-jordan', 'reopened-riley-return') {
        onpc_allowance_boundaries::select_child($journey, $prefix, 'keyboard');
        for my $suffix ('state', 'choice', 'close') {
            my $stage = "$prefix-$suffix";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    }
    $journey->finish();
}

# FLOW15's bounded GDM/fresh/Parent/success route. Other routes remain unsupported.
sub enter_desktop {
    onpc_progress::operation('Entering the Parent desktop');
    my ($journey, $source, $account, $entry, $expected) = @_;
    die 'parent:desktop-binding' unless @_ == 5 && $source eq 'gdm' && $account eq 'parent'
        && $entry eq 'fresh' && $expected eq 'success';
    return sign_in($journey, $account, $expected);
}

# FLOW01: fresh greeter or independently observed same-user desktop; new window.
sub open_for_child {
    onpc_progress::operation('Opening Parent for [Child user]');
    my ($journey, $source, $entry, $window, $child) = @_;
    die 'parent:flow-binding' unless @_ == 5 && ref($journey) eq 'onpc_journey'
        && (($source eq 'gdm' && $entry eq 'fresh')
            || ($source eq 'desktop' && $entry eq 'same-user'))
        && $window eq 'new' && ($child eq 'existing' || $child eq 'child');
    my $same = $entry eq 'same-user';
    my $prefix = $same ? 'same-' : '';
    # New means absent before launch, not a relabelled retained window.
    $journey->seen('same-window-absent') if $same;
    my $desktop = $same ? $journey->seen('same-desktop')
        : enter_desktop($journey, $source, 'parent', $entry, 'success');
    launch($journey, $desktop, 'management', $prefix . 'desktop');
    return select_child($journey, $child, $journey->seen($prefix . 'child-picker-opened'),
        $prefix . 'child-picker-opened', $prefix . 'child-choice-highlighted', $prefix . 'parent-selected');
}

# FLOW16's finite qualified bindings. The controller maps each checkpoint to
# FLOW02 with these exact explicit inputs, then independently reads balances.
sub set_allowance {
    onpc_progress::operation('Setting the daily allowance for [Child user]');
    my ($journey, $source, $parent, $entry, $window, $child, $initial, $minutes, $final) = @_;
    die 'parent:allowance-binding' unless @_ == 9 && $parent eq 'parent'
        && $window eq 'new' && $final eq '1'
        && (($child eq 'existing' && $source eq 'gdm' && $entry eq 'fresh'
             && $initial eq '0' && $minutes eq '30')
            || $child eq 'child' && (($source eq 'gdm' && $entry eq 'fresh' && $initial eq '0'
             && ($minutes eq '0' || $minutes eq '30'))
            || ($source eq 'desktop' && $entry eq 'same-user' && $initial eq '1' && $minutes eq '15')));
    my $prefix = $entry eq 'same-user' ? 'same-' : '';
    my $selected = open_for_child($journey, $source, $entry, $window, $child);
    $journey->consume_observation($prefix . 'parent-selected', $selected);
    return $journey->seen($prefix . 'allowance-configured');
}

# PARENT02/UI15: opened public list -> UI14 -> Enter -> independent selection.
# The caller may already hold the opened list at a recorder phase boundary.
sub select_child {
    onpc_progress::operation('Selecting [Child user] from the child selector');
    my ($journey, $child, $opened, $list_stage, $highlight_stage, $selected_stage) = @_;
    my %bindings = (
        child => 'child-picker-opened/child-choice-highlighted/parent-selected',
        existing => 'child-picker-opened/child-choice-highlighted/parent-selected',
        new => 'new-child-visible/new-child-choice-highlighted/new-child-selected',
        returned => 'existing-child-picker-opened/existing-child-choice-highlighted/existing-returned',
    );
    die 'parent:selection-binding' unless @_ == 6 && ref($journey) eq 'onpc_journey'
        && exists($bindings{$child})
        && (join('/', $list_stage, $highlight_stage, $selected_stage) eq $bindings{$child}
            || ($child eq 'child' || $child eq 'existing')
            && join('/', $list_stage, $highlight_stage, $selected_stage)
                eq 'same-child-picker-opened/same-child-choice-highlighted/same-parent-selected');
    my $highlighted = $journey->highlight_choice($opened, $list_stage, $highlight_stage);
    $journey->consume_observation($highlight_stage, $highlighted);
    testapi::send_key('ret');
    return $journey->seen($selected_stage);
}

sub login_standard_functional {
    onpc_progress::operation('Signing in as [Standard user]');
    my ($journey) = @_;
    die 'parent:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_gdm::reattach_functional();
    return sign_in($journey, 'other-child', 'success');
}

# Legacy appearance-based entry stays refused. Shared direct entry above
# requires two fresh recipient proofs before password input.
sub login {
    onpc_progress::operation('Signing in as [Parent user]');
    die 'parent:legacy-login-refused';
}

sub launch_from_app_grid {
    onpc_progress::operation('Launching Parent from the app grid');
    die 'parent:legacy-search-refused';
}

sub open_app_grid {
    onpc_progress::operation('Opening the app grid');
    die 'parent:legacy-search-refused';
}

sub login_standard {
    onpc_progress::operation('Signing in as [Standard user]');
    die 'parent:legacy-login-refused';
}

sub select_existing_child {
    onpc_progress::operation('Selecting [Existing child] from the child selector');
    die 'parent:legacy-picker-refused';
}

1;
