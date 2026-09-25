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

# SEARCH03: two paced inputs, each independently read, without input repair.
sub enter_search_query {
    onpc_progress::operation('Entering the Parent app search query');
    my ($journey, $focused, $product) = @_;
    die 'parent:search-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $product eq 'Oh No! Parent Control';
    $journey->consume_observation('search-focused', $focused);
    testapi::type_string(substr($product, 0, 1), max_interval => 20);
    my $started = $journey->seen('search-started');
    $journey->consume_observation('search-started', $started);
    testapi::type_string(substr($product, 1), max_interval => 20);
    return $journey->seen('search-entered');
}

# SEARCH06: explicit observed desktop; stop at the launchable result, before Enter.
sub search_whole_query {
    onpc_progress::operation('Finding Parent through public app search');
    my ($journey, $desktop, $product, $result_stage) = @_;
    die 'parent:search-binding' unless @_ == 4 && ref($journey) eq 'onpc_journey'
        && $product eq 'Oh No! Parent Control' && $result_stage eq 'app-grid';
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
            || $desktop_stage eq 'same-desktop')
        && ($expected eq 'management' || $expected eq 'denied');
    $journey->consume_observation($desktop_stage, $desktop);
    # The controller executes the installed command once as this desktop user.
    # A transport failure is uncertain input; no terminal/search fallback.
    my $prefix = $desktop_stage eq 'same-desktop' ? 'same-' : '';
    $journey->seen($prefix . 'parent-command');
    return $journey->seen($prefix . ($expected eq 'management' ? 'parent-window' : 'management-denied'));
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
        && $child eq 'child' && $window eq 'new' && $final eq '1'
        && (($source eq 'gdm' && $entry eq 'fresh' && $initial eq '0' && $minutes eq '0')
            || ($source eq 'desktop' && $entry eq 'same-user' && $initial eq '1' && $minutes eq '15'));
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
