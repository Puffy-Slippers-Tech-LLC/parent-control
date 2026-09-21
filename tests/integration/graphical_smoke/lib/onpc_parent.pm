package onpc_parent;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_gdm ();
use onpc_password ();
use onpc_pointer ();

sub login_functional {
    onpc_progress::operation('Signing in as [Parent user]');
    my ($journey) = @_;
    die 'parent:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_gdm::reattach_functional();
    return sign_in($journey, 'parent', 'other-parent', 'success');
}

# GDM07: registered fresh accounts; setup reattachment belongs to the envelope.
sub sign_in {
    onpc_progress::operation('Signing in through the greeter');
    my ($journey, $account, $wrong_account, $expected) = @_;
    die 'parent:entry-binding' unless @_ == 4 && ref($journey) eq 'onpc_journey'
        && ($account eq 'parent' || $account eq 'other-child')
        && $wrong_account eq 'other-parent' && $expected eq 'success';
    my $list = onpc_gdm::refuse_wrong_recipient($journey, $wrong_account, $account);
    my $prefix = $account eq 'parent' ? 'parent' : 'standard';
    onpc_gdm::choose_account($journey, $account, $list, "$prefix-list", "$prefix-focused");
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
    # A login-keyring modal can consume Super-A. Dismiss it before the single
    # opening gesture, rather than repairing an Overview that never opened.
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

# SEARCH05/PARENT01, only the registered Parent/whole-query/new-window binding.
sub open_management {
    onpc_progress::operation('Opening Parent');
    my ($journey, $desktop, $route) = @_;
    die 'parent:launch-binding' unless @_ == 3 && $route eq 'whole-query';
    my $result = search_whole_query($journey, $desktop, 'Oh No! Parent Control', 'app-grid');
    $journey->consume_observation('app-grid', $result);
    testapi::send_key('ret');
    return $journey->seen('parent-window');
}

# FLOW15's bounded GDM/fresh/Parent/success route. Other routes remain unsupported.
sub enter_desktop {
    onpc_progress::operation('Entering the Parent desktop');
    my ($journey, $source, $account, $entry, $expected) = @_;
    die 'parent:desktop-binding' unless @_ == 5 && $source eq 'gdm' && $account eq 'parent'
        && $entry eq 'fresh' && $expected eq 'success';
    return sign_in($journey, $account, 'other-parent', $expected);
}

# FLOW01: independently supplied greeter, new Parent window, explicit child.
sub open_for_child {
    onpc_progress::operation('Opening Parent for [Child user]');
    my ($journey, $source, $entry, $window, $child) = @_;
    die 'parent:flow-binding' unless @_ == 5 && $source eq 'gdm' && $entry eq 'fresh'
        && $window eq 'new' && ($child eq 'existing' || $child eq 'child');
    my $desktop = enter_desktop($journey, $source, 'parent', $entry, 'success');
    open_management($journey, $desktop, 'whole-query');
    return select_child($journey, $child, $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
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
        && join('/', $list_stage, $highlight_stage, $selected_stage) eq $bindings{$child};
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
    return sign_in($journey, 'other-child', 'other-parent', 'success');
}

# Installed account pixels and negative recipient qualification are shared by
# Parent customers. An observation tag alone never authorizes password input.
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
