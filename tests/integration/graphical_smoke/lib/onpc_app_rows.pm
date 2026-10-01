package onpc_app_rows;
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);
use testapi ();
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();
use onpc_feedback_privacy ();

my $policy_app = 'parent-app-' . substr(sha256_hex('com.puffyslippers.ONPCTest.A.desktop'), 0, 16);

sub run {
    onpc_progress::operation('Qualifying complete App Limits row observations');
    my ($exchange) = @_;
    die 'app-rows:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'app-rows', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    read_rows($journey);
    $journey->finish();
}

# PARENT12/UI13 shared finite complete-read, refusals and independent reread.
sub read_rows {
    onpc_progress::operation('Reading complete public App Limits rows');
    my ($journey, $stage) = @_;
    die 'app-rows:arguments' unless (@_ == 1 || @_ == 2) && ref($journey) eq 'onpc_journey'
        && (!defined($stage) || $stage =~ /\A[a-z][a-z0-9-]*\z/);
    for my $stage (defined($stage) ? ($stage) :
                   ('apps-page', 'app-rows', 'wrong-child', 'wrong-page', 'reopened-rows')) {
        my $result = $journey->seen($stage);
        $journey->consume_observation($stage, $result);
    }
}

sub native_fixtures {
    onpc_progress::operation('Verifying baseline native fixtures and observing their public catalogue rows');
    my ($exchange) = @_;
    die 'native:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'native-fixtures', review => 0);
    native_entry($journey);
    read_rows($journey);
    $journey->finish();
}

sub native_entry {
    onpc_progress::operation('Entering Parent and selecting the baseline native fixture child');
    my ($journey) = @_;
    die 'native:entry' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_gdm::reattach_functional();
    my $desktop = onpc_parent::enter_desktop($journey, 'gdm', 'parent', 'fresh', 'success');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'existing',
        $journey->seen('child-picker-opened'), 'child-picker-opened',
        'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
}

# PARENT10 composes the qualified text replacement and complete row read.
# Caller-owned invocation names allow independent reuse without hidden reopen.
sub search {
    onpc_progress::operation('Replacing a declared search query and independently reading catalogue rows');
    my ($journey, $binding, $stage) = @_;
    die 'catalogue:arguments' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $binding =~ /\Acatalogue-(?:name|description|identifier|absent|clear)\z/
        && $stage =~ /\A[a-z][a-z0-9-]*\z/;
    onpc_text::replace_text($journey, $binding);
    return $journey->consume_observation($stage, $journey->seen($stage));
}

# PARENT11: caller-owned stages; no qualification lifecycle or hidden row read.
sub filter {
    onpc_progress::operation('Setting a catalogue filter and independently checking every option');
    my ($journey, $kind, $mask, $prefix) = @_;
    my %options = ('match-rule' => ['pattern', 'precise'],
                   'access-rule' => ['allowed', 'conditional', 'permanent']);
    die 'catalogue:filter' unless @_ == 4 && ref($journey) eq 'onpc_journey'
        && exists($options{$kind}) && $mask =~ /\A[0-7]\z/
        && $mask < (1 << @{$options{$kind}}) && $prefix =~ /\A[a-z][a-z0-9-]*\z/;
    for my $action ('open', @{$options{$kind}}, 'read') {
        my $stage = "$prefix-$action";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    testapi::send_key('esc');
    my $stage = "$prefix-closed";
    return $journey->consume_observation($stage, $journey->seen($stage));
}

sub catalogue_search {
    onpc_progress::operation('Qualifying exact public catalogue search results');
    my ($exchange) = @_;
    die 'catalogue:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'catalogue-search', review => 0);
    native_entry($journey);
    for my $stage ('apps-page', 'initial-rows', 'wrong-child', 'wrong-page', 'independent-entry') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    search($journey, 'catalogue-name', 'name-rows');
    for my $stage ('incomplete-result', 'reopened-name') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    search($journey, 'catalogue-absent', 'absent-rows');
    $journey->consume_observation('reopened-absent', $journey->seen('reopened-absent'));
    search($journey, 'catalogue-clear', 'cleared-rows');
    $journey->finish();
}

sub catalogue_filters {
    onpc_progress::operation('Qualifying public catalogue filters and unchanged policy');
    my ($exchange) = @_;
    die 'catalogue:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'catalogue', review => 0);
    native_entry($journey);
    for my $stage ('apps-page', 'initial-rows', 'wrong-child', 'wrong-page', 'independent-entry') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    search($journey, 'catalogue-name', 'name-rows');
    filter($journey, 'match-rule', 2, 'precise');
    filter($journey, 'access-rule', 1, 'allowed');
    for my $stage ('filtered-rows', 'reopened-entry') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    filter($journey, 'match-rule', 2, 'independent-precise');
    filter($journey, 'access-rule', 1, 'independent-allowed');
    $journey->consume_observation('independent-filtered-rows', $journey->seen('independent-filtered-rows'));
    filter($journey, 'match-rule', 3, 'restore-match');
    filter($journey, 'access-rule', 7, 'restore-access');
    search($journey, 'catalogue-clear', 'cleared-rows');
    $journey->finish();
}

# UI04/UI03 caller-owned stages, reusable from an independently open legend.
sub legend {
    onpc_progress::operation('Reading the public app access and match-rule explanations');
    my ($journey, $expanded, $read) = @_;
    die 'legend:arguments' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && (!defined($expanded) || $expanded =~ /\A[a-z][a-z0-9-]*\z/)
        && $read =~ /\A[a-z][a-z0-9-]*\z/;
    $journey->consume_observation($expanded, $journey->seen($expanded)) if defined($expanded);
    return $journey->consume_observation($read, $journey->seen($read));
}

sub policy_legend {
    onpc_progress::operation('Qualifying the complete public legend without changing app policy');
    my ($exchange) = @_;
    die 'legend:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'policy-legend', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    for my $stage ('balance-reread', 'apps-page', 'initial-rows', 'wrong-child',
                   'wrong-page', 'independent-entry') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    legend($journey, 'legend-expanded', 'legend-read');
    legend($journey, undef, 'independent-open-read');
    $journey->consume_observation('final-rows', $journey->seen('final-rows'));
    $journey->finish();
}

# Shared PARENT13/15 stages; independently open editors may omit the open stage.
sub match_editor {
    onpc_progress::operation('Reading the owned app match editor from an explicit entry');
    my ($journey, $open, $read) = @_;
    die 'match:arguments' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && (!defined($open) || $open =~ /\A[a-z][a-z0-9-]*\z/)
        && $read =~ /\A[a-z][a-z0-9-]*\z/;
    $journey->consume_observation($open, $journey->seen($open)) if defined($open);
    return $journey->consume_observation($read, $journey->seen($read));
}

sub match_response {
    onpc_progress::operation('Applying the declared editor response and reading the independent app row');
    my ($journey, $response, $row) = @_;
    die 'match:arguments' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $response =~ /\A[a-z][a-z0-9-]*\z/ && $row =~ /\A[a-z][a-z0-9-]*\z/;
    $journey->consume_observation($response, $journey->seen($response));
    return $journey->consume_observation($row, $journey->seen($row));
}

# PARENT13/15: reusable Save composition from a caller-owned App Limits entry.
# Validate every binding before touching the editor. Rejected Save ends at the
# automatic report; callers choose review/close and independently read the row.
sub match_edit {
    onpc_progress::operation('Editing the declared match draft and independently observing Save');
    my ($journey, $draft, $prefix, $open, $read, $row) = @_;
    die 'match:edit-binding' unless @_ == 6 && ref($journey) eq 'onpc_journey'
        && defined($draft) && $draft =~ /\Amatch-(?:(?:precise|wildcard)(?:-basename)?|wildcard-appimages|rejected-directory)\z/;
    die 'match:edit-stages' unless !grep { !defined($_) || !/\A[a-z][a-z0-9-]*\z/ }
        ($prefix, $open, $read);
    die 'match:edit-result' unless $draft eq 'match-rejected-directory'
        ? !defined($row) : defined($row) && $row =~ /\A[a-z][a-z0-9-]*\z/;
    my %used;
    die 'match:edit-stages' if grep { $used{$_}++ }
        ($open, $read, "$prefix-draft-focus", "$prefix-draft-selected",
         "$prefix-draft-read", "$prefix-save", defined($row) ? ($row) : ());
    match_editor($journey, $open, $read);
    onpc_text::replace_text($journey, $draft, "$prefix-draft");
    return match_response($journey, "$prefix-save", $row) if defined($row);
    return $journey->consume_observation("$prefix-save", $journey->seen("$prefix-save"));
}

sub match_editor_validation {
    onpc_progress::operation('Qualifying local invalid refusal, saved wildcard and immediate Reset');
    my ($exchange) = @_;
    die 'match:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'match-editor', review => 0);
    native_entry($journey);
    for my $stage ('apps-page', 'initial-rule') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    match_editor($journey, 'editor-open', 'editor-read');
    for my $stage ('wrong-app', 'ambiguous') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_text::replace_text($journey, 'match-invalid-empty', 'invalid-draft');
    $journey->consume_observation('invalid', $journey->seen('invalid'));
    match_response($journey, 'invalid-cancel', 'unchanged-rule');
    match_editor($journey, 'valid-open', 'valid-read');
    onpc_text::replace_text($journey, 'match-wildcard', 'save-draft');
    match_response($journey, 'save', 'saved-rule');
    match_editor($journey, 'independent-open', 'independent-read');
    match_response($journey, 'reset', 'reset-rule');
    match_editor($journey, 'reset-reopen', 'reset-read');
    match_response($journey, 'cancel', 'final-rule');
    $journey->finish();
}

sub rejected_parent_rule {
    onpc_progress::operation('Qualifying a rejected Parent wildcard and last-confirmed policy restoration');
    my ($exchange) = @_;
    die 'report:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'rejected-parent-rule', review => 0);
    native_entry($journey);
    for my $stage ('apps-page', 'initial-rule', 'report-wrong-entry') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    match_edit($journey, 'match-wildcard', 'confirmed',
        'confirmed-open', 'confirmed-read', 'confirmed-rule');
    match_edit($journey, 'match-rejected-directory', 'rejected',
        'editor-open', 'editor-read', undef);
    onpc_feedback_privacy::review_parent_report($journey, 'review');
    $journey->consume_observation('restored-rule', $journey->seen('restored-rule'));
    # Second public error supplies independent valid report entry; no hidden
    # report launch or prior attempt state supplies this prerequisite.
    match_edit($journey, 'match-rejected-directory', 'independent',
        'independent-open', 'independent-read', undef);
    onpc_feedback_privacy::review_parent_report($journey, 'independent');
    $journey->consume_observation('final-rule', $journey->seen('final-rule'));
    $journey->finish();
}

sub match_save_cancel {
    onpc_progress::operation('Qualifying match-rule Cancel preservation and real saved wildcard');
    my ($exchange) = @_;
    die 'match:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'match-save-cancel', review => 0);
    native_entry($journey);
    for my $stage ('apps-page', 'initial-rule') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    match_editor($journey, 'editor-open', 'editor-read');
    for my $stage ('wrong-app', 'ambiguous') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_text::replace_text($journey, 'match-wildcard', 'cancel-draft');
    match_response($journey, 'cancel', 'cancelled-rule');
    # Independent customer entry is supplied before invoking the reader.
    $journey->consume_observation('independent-open', $journey->seen('independent-open'));
    match_editor($journey, undef, 'independent-read');
    onpc_text::replace_text($journey, 'match-wildcard', 'save-draft');
    match_response($journey, 'save', 'saved-rule');
    $journey->finish();
}

# PARENT16: caller supplies entry, choice/save stage and independent row stage.
sub access_choice {
    onpc_progress::operation('Saving the declared app access choice and reading its public row');
    my ($journey, $save, $row) = @_;
    die 'access:arguments' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $save =~ /\A[a-z][a-z0-9-]*\z/ && $row =~ /\A[a-z][a-z0-9-]*\z/;
    $journey->consume_observation($save, $journey->seen($save));
    return $journey->consume_observation($row, $journey->seen($row));
}

sub access_choices {
    onpc_progress::operation('Qualifying Allowed, Hard and Soft access saves from two entries');
    my ($exchange) = @_;
    die 'access:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'access-choices', review => 0);
    native_entry($journey);
    for my $stage ('apps-page', 'initial-row', 'wrong-row', 'editor-open', 'disabled', 'editor-cancel') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    for my $choice ('allowed', 'permanent', 'conditional') {
        access_choice($journey, "$choice-save", "$choice-row");
    }
    # Entry is supplied separately; access_choice never opens a page implicitly.
    for my $stage ('independent-screen', 'independent-entry') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    for my $choice ('allowed', 'permanent', 'conditional') {
        access_choice($journey, "independent-$choice-save", "independent-$choice-row");
    }
    $journey->finish();
}

# FLOW03: caller owns the App Limits entry and all invocation names. Validate
# the entire finite binding before any search/input; never reopen implicitly.
sub edit_policy {
    onpc_progress::operation('Editing one declared app match and access rule through Parent');
    my ($journey, $app, $draft, $access, $prefix, $filters) = @_;
    die 'policy:binding' unless @_ == 6 && ref($journey) eq 'onpc_journey'
        && $app eq $policy_app
        && $draft =~ /\Amatch-(?:(?:precise|wildcard)(?:-basename)?|wildcard-appimages)\z/
        && $access =~ /\A(?:allowed|permanent|conditional)\z/
        && $prefix =~ /\A[a-z][a-z0-9-]*\z/ && ref($filters) eq 'ARRAY' && @$filters <= 2;
    my %used;
    for my $filter (@$filters) {
        die 'policy:filters' unless ref($filter) eq 'ARRAY' && @$filter == 2
            && $filter->[0] =~ /\A(?:match-rule|access-rule)\z/ && !$used{$filter->[0]}++
            && $filter->[1] =~ /\A[0-7]\z/
            && ($filter->[0] ne 'match-rule' || $filter->[1] < 4);
    }
    onpc_text::replace_text($journey, 'catalogue-identifier', "$prefix-search");
    filter($journey, $_->[0], $_->[1], "$prefix-$_->[0]") for @$filters;
    $journey->consume_observation("$prefix-found", $journey->seen("$prefix-found"));
    match_edit($journey, $draft, $prefix, "$prefix-open", "$prefix-old", "$prefix-match");
    access_choice($journey, "$prefix-access-save", "$prefix-access");
    return $journey->consume_observation("$prefix-final-match", $journey->seen("$prefix-final-match"));
}

sub policy_edit {
    onpc_progress::operation('Qualifying full match/access edits with optional filters and independent entry');
    my ($exchange) = @_;
    die 'policy:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'policy', review => 0);
    native_entry($journey);
    for my $stage ('apps-page', 'initial-match', 'initial-access', 'wrong-row',
                   'wrong-child', 'wrong-page', 'restored-entry') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    edit_policy($journey, $policy_app, 'match-wildcard-appimages', 'permanent',
                'filtered', [['match-rule', 3], ['access-rule', 7]]);
    access_choice($journey, 'soft-save', 'soft-row');
    access_choice($journey, 'allowed-save', 'allowed-row');
    for my $stage ('independent-screen', 'independent-entry', 'reread-match', 'reread-access') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    edit_policy($journey, $policy_app, 'match-precise', 'conditional',
                'independent', []);
    for my $stage ('final-screen', 'final-entry', 'final-match', 'final-access') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}

# APP01's graphical exception: one declared query, then one launch commit.
sub native_search {
    onpc_progress::operation('Finding the declared native fixture in public app search');
    my ($journey, $desktop, $result_stage) = @_;
    $result_stage //= 'app-grid';
    die 'native:search-binding' unless (@_ == 2 || @_ == 3)
        && ref($journey) eq 'onpc_journey'
        && ($result_stage eq 'app-grid' || $result_stage eq 'refusals');
    return onpc_parent::search_whole_query(
        $journey, $desktop, 'ONPC Allowed Fixture', $result_stage);
}

sub native_launch_grid {
    onpc_progress::operation('Launching the declared native fixture from the app grid');
    my ($journey, $entry) = @_;
    die 'native:launch-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('app-grid', $entry);
    testapi::send_key('ret');
    return $journey->seen('opened');
}

sub native_open_grid {
    onpc_progress::operation('Finding and launching the native fixture from the app grid');
    my ($journey, $desktop) = @_;
    die 'native:launch-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    return native_launch_grid($journey, native_search($journey, $desktop));
}

# APP01's direct command route. The controller binds the active child session;
# APP02 reads the actual public window separately from command submission.
sub native_open_command {
    onpc_progress::operation('Launching the declared native fixture as [Child user]');
    my ($journey, $desktop) = @_;
    die 'native:launch-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('desktop', $desktop);
    $journey->seen('command');
    return $journey->seen('opened');
}

# APP03: caller holds a fresh owned-window proof. Controller performs the
# public Submit action; a separate observation reads its customer-visible effect.
sub native_use_app {
    onpc_progress::operation('Submitting the native fixture draft and reading its public result');
    my ($journey, $opened) = @_;
    die 'native:use-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('opened', $opened);
    $journey->seen('submit');
    return $journey->seen('submitted');
}

# FLOW08: explicitly qualified native usable routes, no denial fallback.
sub native_usable_app {
    onpc_progress::operation('Launching and using the declared native app route');
    my ($journey, $route, $desktop) = @_;
    die 'native:usable-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && defined($route) && ($route eq 'command' || $route eq 'grid');
    my $opened = $route eq 'command' ? native_open_command($journey, $desktop)
                                   : native_open_grid($journey, $desktop);
    return native_use_app($journey, $opened);
}

# APP04: no hidden launch/input; the plan owns capture and compare endpoints.
sub native_read_activity {
    onpc_progress::operation('Independently reading the owned native activity');
    my ($journey, $stage) = @_;
    die 'native:activity-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($stage) && $stage =~ /\A[a-z][a-z0-9-]*\z/;
    return $journey->consume_observation($stage, $journey->seen($stage));
}

sub native_close_app {
    onpc_progress::operation('Closing the owned native fixture and observing desktop return');
    my ($journey, $submitted) = @_;
    die 'native:close-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('submitted', $submitted);
    return native_finish_app($journey);
}

sub native_finish_app {
    onpc_progress::operation('Reacquiring and normally closing the owned native app');
    my ($journey) = @_;
    die 'native:close-binding' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    $journey->seen('close');
    return $journey->seen('closed');
}

sub native_grid_usable {
    onpc_progress::operation('Qualifying native app-grid launch and ordinary use');
    my ($exchange) = @_;
    die 'native:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'native-grid-usable', review => 0);
    onpc_gdm::reattach_functional();
    onpc_parent::sign_in($journey, 'other-child', 'success');
    $journey->seen('wrong-entry');
    my $first = onpc_journey->new(
        exchange => sub { $exchange->('first-' . $_[0], $_[1]) },
        prefix => 'native-grid-usable-first', review => 0);
    my $opened = native_open_grid($first, $first->seen('desktop'));
    native_close_app($first, native_use_app($first, $opened));

    my $repeat = onpc_journey->new(
        exchange => sub { $exchange->('repeat-' . $_[0], $_[1]) },
        prefix => 'native-grid-usable-repeat', review => 0);
    my $wrong = $repeat->seen('wrong-entry');
    my $accepted = eval { native_launch_grid($repeat, $wrong); 1; };
    die 'native:wrong-entry-accepted' if $accepted;
    die 'native:wrong-refusal' unless $@ =~ /journey:stale-observation/;
    native_search($repeat, $repeat->seen('desktop'), 'refusals');
    # The refusal checkpoint is followed by a fresh supplied grid proof,
    # under the original operation's single-use observation identity.
    my $grid = $repeat->seen('app-grid');
    $opened = native_launch_grid($repeat, $grid);
    native_close_app($repeat, native_use_app($repeat, $opened));
    $journey->finish();
}

sub native_child_entry {
    onpc_progress::operation('Entering the prepared native fixture child desktop');
    my ($exchange, $declared, $challenges, $prefix) = @_;
    my @stages = qw(installed-greeter parent-focused recipient-qualified recipient-rechecked desktop
        child-installed-greeter child-standard-focused child-standard-recipient-qualified
        child-standard-recipient-rechecked child-desktop);
    die 'native:arguments' unless @_ == 4 && ref($exchange) eq 'CODE'
        && defined($prefix) && $prefix =~ /\A[a-z][a-z0-9-]*\z/
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 2
        && ref($challenges->{'parent-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'parent-login'}}) eq 'parent/recipient-qualified/recipient-rechecked'
        && ref($challenges->{'native-child-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'native-child-login'}}) eq
            'other-child/child-standard-recipient-qualified/child-standard-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => $prefix, review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    $journey->seen('logout');
    onpc_gdm::sign_in_challenge($journey, 'native-child-login',
        'child-installed-greeter', 'child-standard-focused', 'child-desktop');
    return $journey;
}

sub native_app {
    onpc_progress::operation('Qualifying guarded native command launch and ordinary use');
    my ($exchange, $declared, $challenges) = @_;
    die 'native:arguments' unless @_ == 3;
    my $journey = native_child_entry($exchange, $declared, $challenges, 'native-app');
    $journey->seen('wrong-entry');
    my $first = onpc_journey->new(
        exchange => sub { $exchange->('first-' . $_[0], $_[1]) },
        prefix => 'native-app-first', review => 0);
    my $opened = native_open_command($first, $first->seen('desktop'));
    native_close_app($first, native_use_app($first, $opened));
    my $repeat = onpc_journey->new(
        exchange => sub { $exchange->('repeat-' . $_[0], $_[1]) },
        prefix => 'native-app-repeat', review => 0);
    my $wrong = $repeat->seen('wrong-entry');
    my $accepted = eval { native_open_command($repeat, $wrong); 1; };
    die 'native:wrong-entry-accepted' if $accepted;
    die 'native:wrong-refusal' unless $@ =~ /journey:stale-observation/;
    $repeat->seen('refusals');
    $opened = native_open_command($repeat, $repeat->seen('desktop'));
    native_close_app($repeat, native_use_app($repeat, $opened));
    $journey->finish();
}

sub app_activity {
    onpc_progress::operation('Qualifying native usable flows and same-window activity comparisons');
    my ($exchange, $declared, $challenges) = @_;
    die 'native:arguments' unless @_ == 3;
    my $journey = native_child_entry($exchange, $declared, $challenges, 'app-activity');
    $journey->seen('wrong-entry');
    for my $route ('command', 'grid') {
        $journey->seen('repeat-wrong-entry') if $route eq 'grid';
        my $flow = onpc_journey->new(
            exchange => sub { $exchange->($route . '-' . $_[0], $_[1]) },
            prefix => 'app-activity-' . $route, review => 0);
        native_usable_app($flow, $route, $flow->seen('desktop'));
        native_read_activity($flow, 'replacement-refused') if $route eq 'grid';
        native_read_activity($flow, 'capture');
        native_read_activity($flow, 'reread');
        # Reacquire the input precondition after observation, rather than
        # reusing the stale submitted reply from before the activity reads.
        native_finish_app($flow);
    }
    $journey->finish();
}


1;
