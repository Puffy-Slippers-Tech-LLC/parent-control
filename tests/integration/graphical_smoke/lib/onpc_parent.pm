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

# UI21: a fresh public target routes one click; a separate read proves focus.
sub focus_search {
    onpc_progress::operation('Focusing the app search field');
    my ($journey, $field, $surface) = @_;
    die 'parent:search-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $surface eq 'overview';
    $journey->consume_observation('app-grid', $field);
    $journey->click_target($field);
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
    testapi::type_string($product);
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
    my ($journey, $functional) = @_;
    onpc_gdm::reattach_after_setup();
    $journey->seen('installed-greeter');
    die 'parent:list-is-password' if testapi::check_screen('onpc-gdm-parent-masked-password', 0);
    onpc_pointer::click('onpc-gdm-other-parent-installed-input-account', 30);
    testapi::wait_still_screen(1, 10);
    die 'parent:other-prompt-is-list' if testapi::check_screen('onpc-gdm-parent-installed-account', 0);
    die 'parent:wrong-password-recipient' if testapi::check_screen('onpc-gdm-parent-masked-password', 0);
    testapi::send_key('esc');
    onpc_pointer::click('onpc-gdm-parent-installed-input-account', 30);
    die 'parent:list-still-visible' if testapi::check_screen('onpc-gdm-parent-installed-account', 0);
    testapi::assert_screen('onpc-gdm-parent-masked-password', 30);
    $journey->seen('recipient-qualified');
    onpc_password::enter_password('parent', 'gdm');
    testapi::send_key('ret');
    testapi::assert_screen('onpc-parent-desktop', 90) unless $functional;
    $journey->seen('desktop');
}

sub launch_from_app_grid {
    onpc_progress::operation('Launching Parent from the app grid');
    my ($journey) = @_;
    open_app_grid($journey);
    testapi::type_string('Oh No! Parent Control');
    testapi::wait_still_screen(1, 10);
    testapi::send_key('ret');
}

sub open_app_grid {
    onpc_progress::operation('Opening the app grid');
    my ($journey) = @_;
    testapi::send_key('super-a');
    testapi::assert_screen('onpc-parent-app-grid', 30);
    $journey->seen('app-grid');
}

sub login_standard {
    onpc_progress::operation('Signing in as [Standard user]');
    my ($journey) = @_;
    onpc_gdm::reattach_after_setup();
    $journey->seen('installed-greeter');
    die 'parent-access:list-is-password'
        if testapi::check_screen('onpc-gdm-other-child-masked-password', 0);
    onpc_gdm::inspect_installed_standard(sub {
        die 'parent-access:parent-matches-standard'
            if testapi::check_screen('onpc-gdm-other-child-masked-password', 0);
    });
    die 'parent-access:list-still-visible'
        if testapi::check_screen('onpc-gdm-parent-installed-account', 0);
    die 'parent-access:wrong-password-recipient'
        if testapi::check_screen('onpc-gdm-parent-masked-password', 0);
    testapi::assert_screen('onpc-gdm-other-child-masked-password', 30);
    $journey->seen('recipient-qualified');
    onpc_password::enter_password('other-child', 'gdm');
    testapi::send_key('ret');
    testapi::assert_screen('onpc-parent-desktop', 90);
    $journey->seen('desktop');
}

sub select_existing_child {
    onpc_progress::operation('Selecting [Existing child] from the child selector');
    my ($journey) = @_;
    onpc_pointer::click('onpc-parent-child-picker', 90);
    # Choose the reviewed existing fixture through the ordinary dropdown.
    onpc_pointer::click('onpc-parent-child-choice', 30);
    $journey->observe('onpc-parent-child-selected', 30);
    $journey->seen('parent-selected');
}

1;
