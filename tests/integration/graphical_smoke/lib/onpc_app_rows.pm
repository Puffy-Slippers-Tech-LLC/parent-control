package onpc_app_rows;
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);
use JSON::PP ();
use testapi ();
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();
use onpc_feedback_privacy ();

my %policy_apps = map { $_ => 'parent-app-' . substr(sha256_hex(
    'com.puffyslippers.ONPCTest.' . $_ . '.desktop'), 0, 16) } qw(A H S Alias);
my $policy_app = $policy_apps{A};

# Keep fixture identity mechanics here; callers own their rules and edit order.
sub fixture_app {
    my ($role) = @_;
    die 'policy:fixture-role' unless @_ == 1 && defined($role) && exists($policy_apps{$role});
    return $policy_apps{$role};
}

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

sub flatpak_fixtures {
    onpc_progress::operation('Reading prepared Flatpak apps and their public Parent defaults');
    my ($exchange) = @_;
    die 'flatpak:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'flatpak-fixtures', review => 0);
    native_entry($journey);
    read_rows($journey, $_) for ('apps-page', 'app-rows', 'reopened-rows');
    $journey->finish();
}

# PARENT10 composes the qualified text replacement and complete row read.
# Caller-owned invocation names allow independent reuse without hidden reopen.
sub search {
    onpc_progress::operation('Replacing a declared search query and independently reading catalogue rows');
    my ($journey, $binding, $stage) = @_;
    die 'catalogue:arguments' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && $binding =~ /\Acatalogue-(?:name|description|identifier|hard|soft|alias|absent|clear)\z/
        && $stage =~ /\A[a-z][a-z0-9-]*\z/;
    onpc_text::replace_text($journey, $binding);
    return $journey->consume_observation($stage, $journey->seen($stage));
}

# PARENT11: caller-owned stages; no qualification lifecycle or hidden row read.
sub filter {
    onpc_progress::operation('Setting a catalogue filter');
    my ($journey, $kind, $mask, $prefix) = @_;
    my %options = ('match-rule' => ['pattern', 'precise'],
                   'access-rule' => ['allowed', 'conditional', 'permanent']);
    die 'catalogue:filter' unless @_ == 4 && ref($journey) eq 'onpc_journey'
        && exists($options{$kind}) && $mask =~ /\A[0-7]\z/
        && $mask < (1 << @{$options{$kind}}) && $prefix =~ /\A[a-z][a-z0-9-]*\z/;
    for my $action ('open', @{$options{$kind}}) {
        my $stage = "$prefix-$action";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
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
        && defined($draft) && $draft =~ /\Amatch-(?:(?:precise|wildcard)(?:-basename)?|wildcard-appimages|rejected-directory|hard-precise|alias-precise|soft-(?:wildcard|precise|rejected-directory))\z/;
    die 'match:edit-stages' unless !grep { !defined($_) || !/\A[a-z][a-z0-9-]*\z/ }
        ($prefix, $open, $read);
    die 'match:edit-result' unless $draft =~ /\Amatch-(?:soft-)?rejected-directory\z/
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
    my ($journey, $app, $draft, $access, $prefix, $filters, $setup) = @_;
    $setup //= 0;
    die 'policy:binding' unless (@_ == 6 || @_ == 7) && ref($journey) eq 'onpc_journey'
        && ($setup eq '0' || $setup eq '1')
        && (($app eq $policy_app && $draft =~ /\Amatch-(?:(?:precise|wildcard)(?:-basename)?|wildcard-appimages)\z/)
            || ($app eq $policy_apps{H} && $draft eq 'match-hard-precise')
            || ($app eq $policy_apps{Alias} && $draft eq 'match-alias-precise')
            || ($app eq $policy_apps{S} && $draft =~ /\Amatch-soft-(?:wildcard|precise)\z/))
        && $access =~ /\A(?:allowed|permanent|conditional)\z/
        && $prefix =~ /\A[a-z][a-z0-9-]*\z/ && ref($filters) eq 'ARRAY' && @$filters <= 2;
    my %used;
    for my $filter (@$filters) {
        die 'policy:filters' unless ref($filter) eq 'ARRAY' && @$filter == 2
            && $filter->[0] =~ /\A(?:match-rule|access-rule)\z/ && !$used{$filter->[0]}++
            && $filter->[1] =~ /\A[0-7]\z/
            && ($filter->[0] ne 'match-rule' || $filter->[1] < 4);
    }
    my $query = $app eq $policy_apps{H} ? 'catalogue-hard'
              : $app eq $policy_apps{S} ? 'catalogue-soft'
              : $app eq $policy_apps{Alias} ? 'catalogue-alias' : 'catalogue-identifier';
    onpc_text::replace_text($journey, $query, "$prefix-search");
    filter($journey, $_->[0], $_->[1], "$prefix-$_->[0]") for @$filters;
    if ($setup) {
        # The caller independently checks the complete saved policy after
        # preparation. Keep every guarded input, without redundant row reads.
        $journey->consume_observation("$prefix-open", $journey->seen("$prefix-open"));
        onpc_text::replace_text($journey, $draft, "$prefix-draft");
        $journey->consume_observation("$prefix-save", $journey->seen("$prefix-save"));
        return $journey->consume_observation("$prefix-access-save", $journey->seen("$prefix-access-save"));
    }
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

# FLOW19: explicit entry and finite app list. Caller owns the current ledger,
# independent return and exact saved-row comparisons on the controller.
sub named_app_set {
    onpc_progress::operation('Saving the declared app rules for [Child user]');
    my ($journey, $source, $entry, $window, $child, $apps, $prefix) = @_;
    die 'app-set:binding' unless @_ == 7 && ref($journey) eq 'onpc_journey'
        && ($child eq 'child' || $child eq 'existing')
        && (($source eq 'gdm' && $entry eq 'fresh' && $window eq 'new')
            || ($source eq 'desktop' && $entry eq 'same-user'
                && $window eq 'retained'))
        && ref($apps) eq 'ARRAY' && @$apps && @$apps <= 4;
    my %used;
    for my $app (@$apps) {
        die 'app-set:apps' unless ref($app) eq 'ARRAY' && @$app == 3
            && exists($policy_apps{$app->[0]}) && !$used{$app->[0]}++
            && (($app->[0] eq 'A' && $app->[1] =~ /\Amatch-(?:(?:precise|wildcard)(?:-basename)?|wildcard-appimages)\z/)
                || ($app->[0] eq 'H' && $app->[1] eq 'match-hard-precise')
                || ($app->[0] eq 'S' && $app->[1] =~ /\Amatch-soft-(?:wildcard|precise)\z/)
                || ($app->[0] eq 'Alias' && $app->[1] eq 'match-alias-precise'))
            && $app->[2] =~ /\A(?:allowed|permanent|conditional)\z/;
    }
    my $section = $journey->scope($prefix);
    my $stage = $entry eq 'fresh' ? 'parent-selected' : 'entry-parent-retained';
    if ($entry eq 'fresh') {
        $journey->consume_observation('parent-selected',
            onpc_parent::open_for_child($journey, $source, $entry, $window, $child));
    } else {
        $section->consume_observation($stage,
            onpc_parent::open_for_child($section, $source, $entry, $window, $child, 'entry'));
    }
    $section->consume_observation('apps-page', $section->seen('apps-page'));
    for my $index (0 .. $#$apps) {
        my ($role, $draft, $access) = @{$apps->[$index]};
        edit_policy($section, fixture_app($role), $draft, $access, 'edit-' . $index, [], 1);
    }
    onpc_text::replace_text($section, 'catalogue-clear', 'clear');
    saved_rows($section, $apps, 'saved');
    $section->consume_observation($_, $section->seen($_)) for qw(before session);
    # DESK03 keeps the original desktop and independently observes GDM.
    require onpc_desktop_session;
    return onpc_desktop_session::switch_user(
        $section, $section->seen('repeat-desktop'), 'repeat-desktop');
}

sub saved_rows {
    onpc_progress::operation('Comparing every saved app rule');
    my ($journey, $apps, $prefix) = @_;
    die 'app-set:read-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && ref($apps) eq 'ARRAY' && @$apps
        && $prefix =~ /\A[a-z][a-z0-9-]*\z/;
    for my $app (@$apps) {
        my $role = lc($app->[0]);
        for my $kind ('match', 'access') {
            my $stage = "$prefix-$role-$kind";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    }
}

sub daily_soft_profile {
    onpc_progress::operation('Preparing daily time that outlasts the child Soft-app exception');
    my ($exchange, $declared, $challenges, $request) = @_;
    die 'flow18:binding' unless @_ == 4 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ref($request) eq 'ARRAY' && join(',', @$request) eq 'child,parent,6,1';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'daily-soft-profile', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    $journey->{kiosk_request} = $request;
    onpc_gdm::reattach_functional();
    prepare_daily_soft_profile($journey);
    $journey->finish();
}

sub prepare_daily_soft_profile {
    my ($journey) = @_;
    die 'flow18:journey' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    named_app_set($journey, 'gdm', 'fresh', 'new', 'child', [
        ['A', 'match-precise', 'allowed'], ['H', 'match-hard-precise', 'permanent'],
        ['S', 'match-soft-wildcard', 'conditional']], 'apps');
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'parent', 'retained', 'success', 'setup-return');
    onpc_parent::grant_only_time_profile(
        $journey, 'desktop', 'same-user', 'retained', 0, 0, 6, 'observed', 0, 10);
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'child', 'fresh', 'success', 'first-child');
    my $soft = $journey->scope('soft');
    native_usable_app($soft, 'command', $soft->seen('desktop'), 'child', 'S');
    native_read_activity($journey, 'soft-capture');
    onpc_desktop_session::enter_desktop(
        $journey, 'desktop', 'parent', 'retained', 'success', 'away-parent', 'child');
    $journey->consume_observation('away-parent-retained',
        onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'child', 'away', 0));
    # The first read's controller action owns the bounded TIME03 wait. There
    # are no edits or form/settings tours between this read and the return.
    $journey->seen($_) for qw(away-balance return-balance);
    my $leaving = $journey->scope('leave-parent');
    onpc_desktop_session::switch_user($leaving, $leaving->seen('desktop'));
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'child', 'retained', 'success', 'returned-child');
    native_read_activity($journey, 'soft-preserved');
    $journey->seen('positive-child-witness');
}

sub daily_soft_expiry {
    onpc_progress::operation('Keeping child access after extra time expires with daily time left');
    my ($exchange, $declared, $challenges, $request, $restore) = @_;
    $restore //= 'none';
    die 'flow18:binding' unless (@_ == 4 || @_ == 5) && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ref($request) eq 'ARRAY' && join(',', @$request) eq 'child,parent,6,1'
        && ($restore eq 'none' || $restore eq 'unlock' || $restore eq 'fresh-login'
            || $restore eq 'allowance-edit' || $restore eq 'toggle' || $restore eq 'app-save'
            || $restore eq 'revoke');
    # Keep FLOW18's qualified approval scope and exact request binding.
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'daily-soft-profile', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    $journey->{kiosk_request} = $request;
    onpc_gdm::reattach_functional();
    retained_app_activities($journey, [['peer', 'other-child', 'fresh']]);
    prepare_daily_soft_profile($journey);
    if ($restore eq 'unlock') {
        my $allowed = $journey->scope('allowed');
        native_usable_app($allowed, 'command', $allowed->seen('desktop'), 'child');
        native_read_activity($journey, 'allowed-capture');
    } else {
        native_activity_entry($journey, 'allowed', 'command', 'child');
    }
    $journey->seen($_) for qw(expiry-wait-first expiry-wait-last expired-countdown);
    native_activity_resume($journey, 'allowed-return') if $restore eq 'none';
    native_activity_resume($journey, 'expired-soft');
    if ($restore eq 'unlock') {
        onpc_desktop_session::lock($journey, $journey->seen('lock-ready'), 'lock-ready');
        onpc_desktop_session::unlock_success($journey);
        native_read_activity($journey, 'restored-soft-closed');
        native_blocked_app($journey->scope('blocked-hard'), 'H');
        native_blocked_app($journey->scope('blocked-soft'), 'S');
        native_activity_resume($journey, 'allowed-return');
    } elsif ($restore eq 'fresh-login') {
        my $leaving = $journey->scope('expired-child');
        onpc_desktop_session::log_out($leaving, $leaving->seen('desktop'));
        onpc_desktop_session::enter_desktop(
            $journey, 'gdm', 'child', 'fresh', 'success', 'fresh-child');
        native_blocked_app($journey->scope('blocked-hard'), 'H');
        native_blocked_app($journey->scope('blocked-soft'), 'S');
        my $allowed = $journey->scope('new-allowed');
        native_usable_app($allowed, 'command', $allowed->seen('desktop'), 'child', 'A');
    } elsif ($restore eq 'allowance-edit' || $restore eq 'toggle' || $restore eq 'app-save'
            || $restore eq 'revoke') {
        onpc_desktop_session::enter_desktop(
            $journey, 'desktop', 'parent', 'retained', 'success', 'edit-parent', 'child');
        $journey->consume_observation('edit-parent-retained',
            onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'child', 'edit', 0));
        if ($restore eq 'toggle') {
            $journey->seen($_) for qw(limit-off saved-off limit-on saved-on cleared-balance);
        } elsif ($restore eq 'app-save') {
            $journey->seen('app-save-apps');
            match_editor($journey, 'app-save-open', 'app-save-read');
            match_response($journey, 'app-save-save', 'app-save-row');
        } elsif ($restore eq 'revoke') {
            $journey->seen($_) for qw(revoke-before revoke-open revoke-confirm revoke-cleared);
        } else {
            require onpc_allowance_selection;
            onpc_allowance_selection::select($journey, 'raised', [15], 'confirm');
        }
        onpc_desktop_session::enter_desktop(
            $journey, 'desktop', 'child', 'retained', 'success', 'restored-child', 'parent');
        if ($restore eq 'toggle') {
            native_activity_resume($journey, 'restored-soft');
            native_finish_app($journey->scope('restored-soft'));
        } else {
            native_read_activity($journey, 'restored-soft-closed');
        }
        native_blocked_app($journey->scope('blocked-hard'), 'H');
        native_blocked_app($journey->scope('blocked-soft'), 'S');
        native_activity_resume($journey, 'allowed-return');
    } else {
        native_finish_app($journey->scope('expired-soft'));
        my $fresh = $journey->scope('new-soft');
        native_usable_app($fresh, 'command', $fresh->seen('desktop'), 'child', 'S');
    }
    $journey->seen('final-child-countdown');
    retained_app_visit($journey, 'peer-return', 'other-child', 'desktop', 'child');
    $journey->finish();
}

sub qualify_named_app_set {
    onpc_progress::operation('Checking saved child app rules after Parent returns');
    my ($exchange, $declared, $challenges) = @_;
    die 'app-set:qualification' unless @_ == 3 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'named-app-set', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    my $apps = [['A', 'match-precise', 'allowed'], ['H', 'match-hard-precise', 'permanent'],
                ['S', 'match-soft-wildcard', 'conditional']];
    my $smaller = [['A', 'match-precise', 'conditional'], ['S', 'match-soft-precise', 'allowed']];
    require onpc_desktop_session;
    onpc_gdm::reattach_functional();
    named_app_set($journey, 'gdm', 'fresh', 'new', 'child', $apps, 'first');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'return');
    $journey->consume_observation('returned-session', $journey->seen('returned-session'));
    $journey->consume_observation('returned-parent-retained',
        onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'child', 'returned'));
    $journey->consume_observation('returned-apps', $journey->seen('returned-apps'));
    saved_rows($journey, $apps, 'returned');
    named_app_set($journey, 'desktop', 'same-user', 'retained', 'child', $smaller, 'smaller');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'final-return');
    $journey->consume_observation('final-session', $journey->seen('final-session'));
    $journey->consume_observation('final-parent-retained',
        onpc_parent::open_for_child($journey, 'desktop', 'same-user', 'retained', 'child', 'final'));
    $journey->consume_observation('final-apps', $journey->seen('final-apps'));
    saved_rows($journey, $smaller, 'final');
    $journey->finish();
}

# APP01's graphical exception: one declared query, then one launch commit.
sub native_search {
    onpc_progress::operation('Finding the declared native fixture in public app search');
    my ($journey, $desktop, $result_stage, $role, $kind) = @_;
    $result_stage //= 'app-grid';
    $role //= 'A';
    $kind //= 'native';
    die 'native:search-binding' unless (@_ >= 2 && @_ <= 5)
        && ref($journey) eq 'onpc_journey'
        && ($kind eq 'native' && $role =~ /\A(?:A|Alias|H|S)\z/
            || ($kind eq 'snap' || $kind eq 'flatpak') && $role =~ /\A(?:A|H|S)\z/)
        && ($result_stage eq 'app-grid' || $result_stage eq 'refusals');
    my %snap = (A => 'Allowed', H => 'Hard', S => 'Soft');
    return onpc_parent::search_whole_query(
        $journey, $desktop, $kind ne 'native' ? 'ONPC ' . ($kind eq 'flatpak' ? 'Flatpak' : 'Snap') . ' ' . $snap{$role} . ' Fixture'
            : $role eq 'Alias' ? 'ONPC Shared Target Fixture' : 'ONPC ' . $snap{$role} . ' Fixture', $result_stage);
}

sub native_launch_grid {
    onpc_progress::operation('Launching the declared native fixture from the app grid');
    my ($journey, $entry, $gesture) = @_;
    $gesture //= 'ret';
    die 'native:launch-binding' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey'
        && ($gesture eq 'ret' || $gesture eq 'ctrl-ret');
    $journey->consume_observation('app-grid', $entry);
    testapi::send_key($gesture);
    return $journey->seen('opened');
}

sub native_open_grid {
    onpc_progress::operation('Finding and launching the native fixture from the app grid');
    my ($journey, $desktop, $role) = @_;
    die 'native:launch-binding' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey';
    return native_launch_grid($journey, native_search($journey, $desktop, 'app-grid', $role));
}

# APP01's direct command route. The controller binds the active child session;
# APP02 reads the actual public window separately from command submission.
sub native_open_command {
    onpc_progress::operation('Launching the declared native fixture as [Child user]');
    my ($journey, $desktop) = @_;
    die 'native:launch-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    # With no supplied observation, the command's controller operation still
    # acquires both fresh session/desktop/prompt preflights before launch.
    $journey->consume_observation('desktop', $desktop) if defined($desktop);
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
    my ($journey, $route, $desktop, $child, $role, $kind, $gesture) = @_;
    $child //= 'other-child';
    $kind //= 'native';
    $gesture //= 'ret';
    die 'native:usable-binding' unless (@_ >= 3 && @_ <= 7) && ref($journey) eq 'onpc_journey'
        && defined($route) && ($route eq 'command' || $route eq 'grid' || $route eq 'files' || $route eq 'desktop')
        && (defined($desktop) || $route eq 'command')
        && ($child eq 'child' || $child eq 'other-child' || $child eq 'parent' && $route eq 'command')
        && ($gesture eq 'ret' || ($kind eq 'snap' || $kind eq 'flatpak') && $route eq 'grid' && $gesture eq 'ctrl-ret')
        && ($kind eq 'flatpak' && defined($role)
            && ($child eq 'other-child' && $role =~ /\A(?:A|H|S)\z/
                || $child eq 'child' && $role eq 'A' && $gesture eq 'ret')
            || $kind eq 'snap' && defined($role)
            && ($child eq 'other-child' && $role =~ /\A(?:A|H|S)\z/
                || $child eq 'child' && $role eq 'A' && $gesture eq 'ret')
            || $kind eq 'native' && (!defined($role) || $role eq 'Alias' && $route eq 'grid' && $child eq 'other-child'
            || $role eq 'S' && $child eq 'other-child'
            || $route eq 'command' &&
            ($role =~ /\A(?:A|S)\z/ && $child eq 'child'
                || $role =~ /\A(?:N|unmatched-soft|SpaceCopy|CommaCopy|VersionNext|VersionNonmatch|VersionExisting)\z/ && $child eq 'other-child')));
    die 'native:files-binding' if $route eq 'files' &&
        !($kind eq 'native' && ($child eq 'other-child' && (!defined($role) || $role eq 'S')
            || $child eq 'child' && !defined($role)));
    my $opened;
    if ($route eq 'desktop') {
        die 'native:desktop-binding' unless $kind eq 'native'
            && ($child eq 'other-child' || $child eq 'child') && !defined($role);
        $journey->consume_observation('desktop', $desktop);
        my $icon = $journey->consume_observation('icon', $journey->seen('icon'));
        die 'native:desktop-selection' unless exists($icon->{desktop_icon_selected});
        # Accessibility focus does not set DING's internal keyboard selection,
        # which Ctrl+Space requires. The icon proof admits one ordinary entry;
        # independently verify its sole selection before sending Enter.
        testapi::send_key('ctrl-a') unless $icon->{desktop_icon_selected};
        $journey->consume_observation('selected', $journey->seen('selected'));
        testapi::send_key('ret');
        $opened = $journey->seen('opened');
    } elsif ($route eq 'files') {
        $journey->consume_observation('desktop', $desktop);
        $journey->consume_observation('files', $journey->seen('files'));
        testapi::send_key('ret');
        $opened = $journey->seen('opened');
    } else {
        $opened = $route eq 'command' ? native_open_command($journey, $desktop)
        : $kind ne 'native' ? native_launch_grid($journey,
            native_search($journey, $desktop, 'app-grid', $role, $kind), $gesture)
                                   : native_open_grid($journey, $desktop, $role);
    }
    return native_use_app($journey, $opened);
}

# FLOW08: hidden Flatpak grid entry, then an independent command denial.
sub flatpak_blocked_app {
    onpc_progress::operation('Checking that the child cannot open the blocked Flatpak app');
    my ($journey, $role, $route, $command_stage) = @_;
    $command_stage //= 'denied';
    die 'flatpak:denial-binding' unless (@_ == 3 || @_ == 4)
        && ref($journey) eq 'onpc_journey' && $role =~ /\A(?:A|H|S)\z/
        && ($route eq 'command' || $route eq 'grid')
        && ($command_stage eq 'denied' || $command_stage eq 'command');
    # The hidden-grid observation sends no Enter. Command denial is a separate
    # result, not a fallback launch after uncertain input.
    native_search($journey, $journey->seen('desktop'), 'app-grid', $role, 'flatpak')
        if $route eq 'grid';
    return $journey->seen($command_stage);
}

# FLOW08: exact command denial, or the declared grid attempt/result operation.
sub native_blocked_app {
    onpc_progress::operation('Checking that the child cannot open the blocked app');
    my ($journey, $role, $route) = @_;
    $route //= 'command';
    die 'native:denial-binding' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey'
        && ($route eq 'command' && $role =~ /\A(?:A|H|S|Alias|C|SpaceCopy|CommaCopy|VersionNext)\z/
            || $route eq 'grid' && $role =~ /\A(?:A|Alias|H|S)\z/
            || $route eq 'files' && $role =~ /\A(?:A|H|S)\z/);
    if ($route eq 'files') {
        $journey->consume_observation('files', $journey->seen('files'));
        testapi::send_key('ret');
        return $journey->seen('denied');
    }
    if ($route eq 'grid') {
        my $entry = native_search($journey, $journey->seen('desktop'), 'app-grid', $role);
        $journey->consume_observation('app-grid', $entry);
        die 'native:denial-entry' unless JSON::PP::is_bool($entry->{grid_launch_required});
        testapi::send_key('ret') if $entry->{grid_launch_required};
        return $journey->seen('denied');
    }
    return $journey->seen('command');
}

sub shared_target_launchers {
    onpc_progress::operation('Checking that the child can use both allowed launchers for one app');
    my ($exchange, $declared, $challenges) = @_;
    die 'native:alias-arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'shared-target-launchers', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    $journey->seen('saved-settings');
    $journey->seen('apps-page');
    $journey->seen('initial-rows');
    $journey->seen('parent-logout');
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'other-child', 'fresh', 'success', 'child-entry');
    for my $role ('A', 'Alias') {
        my $app = $journey->scope($role eq 'A' ? 'original' : 'alias');
        native_usable_app($app, 'grid', $app->seen('desktop'), 'other-child',
                          $role eq 'Alias' ? $role : undef);
        native_finish_app($app);
    }
    $journey->seen('child-logout');
    $journey->finish();
}

sub native_denial {
    onpc_progress::operation('Checking the parent blocks apps before the child opens them');
    my ($exchange, $declared, $challenges) = @_;
    die 'native:denial-arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'native-denial', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    $journey->seen('saved-settings');
    $journey->seen('apps-page');
    $journey->seen('initial-rows');
    for my $edit (['A', 'match-precise', 'allowed', 'allowed'],
                  ['H', 'match-hard-precise', 'permanent', 'hard'],
                  ['S', 'match-soft-wildcard', 'conditional', 'soft']) {
        my ($role, $draft, $access, $prefix) = @$edit;
        edit_policy($journey, fixture_app($role), $draft, $access, $prefix, []);
    }
    $journey->seen('parent-logout');
    for my $entry ('first', 'independent') {
        onpc_desktop_session::enter_desktop(
            $journey, 'gdm', 'other-child', 'fresh', 'success', $entry . '-entry');
        for my $role ('H', 'S') {
            my $name = $role eq 'H' ? 'hard' : 'soft';
            native_blocked_app($journey->scope($entry . '-' . $name), $role);
        }
        my $allowed = $journey->scope($entry . '-allowed');
        native_usable_app($allowed, 'grid', $allowed->seen('desktop'), 'other-child');
        native_finish_app($allowed);
        my $other = $journey->scope($entry . '-nonmatching');
        native_usable_app($other, 'command', $other->seen('desktop'), 'other-child', 'N');
        native_finish_app($other);
        $journey->seen($entry . '-logout');
    }
    $journey->finish();
}

sub native_policy_closure {
    onpc_progress::operation('Checking that a parent block closes the child original app');
    my ($exchange, $declared, $challenges, $route) = @_;
    $route //= 'original';
    die 'native:closure-arguments' unless (@_ == 3 || @_ == 4) && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ($route eq 'original' || $route eq 'files');
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $route eq 'files' ? 'native-files-routes' : 'native-policy-closure', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    $journey->seen($_) for qw(saved-settings apps-page initial-rows);
    for my $name ('hard', 'soft') {
        if ($name eq 'soft') {
            onpc_desktop_session::enter_desktop(
                $journey, 'gdm', 'parent', 'retained', 'success', 'restore-parent');
            $journey->seen('restore-apps');
            edit_policy($journey, fixture_app('A'), 'match-precise', 'allowed', 'restore', []);
        }
        my $leaving = $journey->scope($name . '-leave-parent');
        onpc_desktop_session::switch_user($leaving, $leaving->seen('desktop'));
        onpc_desktop_session::enter_desktop(
            $journey, 'gdm', 'other-child', 'fresh', 'success', $name . '-fresh');
        my $activity = $journey->scope($name . '-activity');
        native_usable_app($activity, $route eq 'files' ? 'files' : $name eq 'hard' ? 'grid' : 'command',
                          $activity->seen('desktop'), 'other-child');
        $activity->seen('dismiss') if $route eq 'files';
        native_read_activity($journey, $name . '-capture');
        onpc_desktop_session::enter_desktop(
            $journey, 'desktop', 'parent', 'retained', 'success', $name . '-parent', 'other-child');
        $journey->seen($name . '-apps');
        edit_policy($journey, fixture_app('A'), 'match-precise',
                    $name eq 'hard' ? 'permanent' : 'conditional', $name . '-block', []);
        onpc_desktop_session::enter_desktop(
            $journey, 'desktop', 'other-child', 'retained', 'success', $name . '-return', 'parent');
        # Compare the original capture before any new launch can conceal closure.
        native_read_activity($journey, $name . '-closed');
        my $denied = $journey->scope($name . '-denied');
        native_blocked_app($denied, 'A', $route eq 'files' ? 'files' : 'command');
        $denied->seen('dismiss') if $route eq 'files';
        my $other = $journey->scope($name . '-unaffected');
        native_usable_app($other, 'command', $other->seen('desktop'), 'other-child', 'N');
        native_finish_app($other);
        $journey->seen($name . '-logout');
    }
    $journey->finish();
}

# FLOW08: public policy saves followed by original closure and command denial.
sub flatpak_retained_work {
    onpc_progress::operation('Checking that Jordan keeps allowed work while Parent blocks another app');
    my ($exchange, $declared, $challenges) = @_;
    die 'flatpak:retained-arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'flatpak-retained-work', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    $journey->seen($_) for qw(saved-settings apps-page allowed-save allowed-row hard-save hard-row soft-save soft-row);
    my $leaving = $journey->scope('leave-parent');
    onpc_desktop_session::switch_user($leaving, $leaving->seen('desktop'));
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'other-child', 'fresh', 'success', 'fresh');
    for my $name ('allowed', 'soft') {
        my $activity = $journey->scope($name);
        native_usable_app($activity, 'command', $activity->seen('desktop'), 'other-child',
                          $name eq 'allowed' ? 'A' : 'S', 'flatpak');
        native_read_activity($journey, $name . '-capture');
    }
    $journey->seen('hard-denied');
    native_read_activity($journey, $_) for qw(allowed-after-denial soft-after-denial);
    onpc_desktop_session::enter_desktop(
        $journey, 'desktop', 'parent', 'retained', 'success', 'parent-return', 'other-child');
    $journey->seen($_) for qw(return-apps soft-block-save soft-block-row);
    onpc_desktop_session::enter_desktop(
        $journey, 'desktop', 'other-child', 'retained', 'success', 'child-return', 'parent');
    native_read_activity($journey, 'soft-closed');
    $journey->seen('soft-denied');
    native_read_activity($journey, 'allowed-preserved');
    $journey->seen($_) for qw(allowed-resubmit allowed-submitted-again);
    native_read_activity($journey, 'allowed-still-original');
    native_finish_app($journey->scope('allowed'));
    $journey->finish();
}

sub flatpak_policy_closure {
    onpc_progress::operation('Checking that Parent blocks close the child apps and preserve allowed use');
    my ($exchange, $declared, $challenges) = @_;
    die 'flatpak:closure-arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'flatpak-policy-closure', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    $journey->seen($_) for qw(saved-settings apps-page);
    for my $name ('hard', 'soft') {
        onpc_desktop_session::enter_desktop(
            $journey, 'gdm', 'parent', 'retained', 'success', 'next-parent') if $name eq 'soft';
        my $leaving = $journey->scope($name . '-leave-parent');
        onpc_desktop_session::switch_user($leaving, $leaving->seen('desktop'));
        onpc_desktop_session::enter_desktop(
            $journey, 'gdm', 'other-child', 'fresh', 'success', $name . '-fresh');
        my $activity = $journey->scope($name . '-activity');
        native_usable_app($activity, 'command', $activity->seen('desktop'), 'other-child',
                          $name eq 'hard' ? 'H' : 'S', 'flatpak');
        native_read_activity($journey, $name . '-capture');
        onpc_desktop_session::enter_desktop(
            $journey, 'desktop', 'parent', 'retained', 'success', $name . '-parent', 'other-child');
        $journey->seen($name . '-apps');
        $journey->seen($name . '-block-' . $_) for qw(save row);
        onpc_desktop_session::enter_desktop(
            $journey, 'desktop', 'other-child', 'retained', 'success', $name . '-return', 'parent');
        native_read_activity($journey, $name . '-closed');
        $journey->seen($name . '-denied');
        my $allowed = $journey->scope($name . '-unaffected');
        native_usable_app($allowed, 'command', $allowed->seen('desktop'), 'other-child', 'A', 'flatpak');
        native_finish_app($allowed);
        $journey->seen($name . '-logout');
    }
    $journey->finish();
}

# APP04: no hidden launch/input; the plan owns capture and compare endpoints.
sub native_read_activity {
    onpc_progress::operation('Independently reading the owned native activity');
    my ($journey, $stage) = @_;
    die 'native:activity-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($stage) && $stage =~ /\A[a-z][a-z0-9-]*\z/;
    return $journey->consume_observation($stage, $journey->seen($stage));
}

# Caller-owned activity namespace; no VM, window or cleanup lifetime is added.
# Keep marker titles identical to the mapped controller checkpoints.
sub _native_activity_scope {
    my ($journey, $prefix) = @_;
    die 'native:activity-scope' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($prefix) && $prefix =~ /\A[a-z][a-z0-9-]*\z/;
    die 'journey:previous-failure' if $journey->{invocation_failed};
    return onpc_journey->new(
        exchange => sub { $journey->{exchange}->($prefix . '-' . $_[0], $_[1]) },
        prefix => $journey->{prefix} . '-' . $prefix, review => 0);
}

# FLOW08 + APP04: establish one usable activity and capture it before a caller's
# transition. Return the same scope for independent reread and normal closure.
sub native_activity_entry {
    onpc_progress::operation('Establishing and capturing the original native activity');
    my ($journey, $prefix, $route, $account, $desktop_observation, $binding) = @_;
    $account //= 'other-child';
    $binding //= 'activity';
    $desktop_observation = 1 if @_ < 5;
    die 'native:activity-entry' unless (@_ == 3 || @_ == 4 || @_ == 5 || @_ == 6) && defined($route)
        && ($route eq 'command' || $route eq 'grid')
        && defined($desktop_observation) && $desktop_observation =~ /\A[01]\z/
        && ($desktop_observation || $route eq 'command')
        && ($account eq 'child' || $account eq 'other-child' || $account eq 'parent' && $route eq 'command');
    die 'native:activity-binding' unless $binding eq 'activity'
        || ($binding eq 'policy' || $binding eq 'unmatched-soft')
            && $account eq 'other-child' && $route eq 'command';
    my $activity = _native_activity_scope($journey, $prefix);
    native_usable_app($activity, $route,
        $desktop_observation ? $activity->seen('desktop') : undef, $account,
        $binding eq 'unmatched-soft' ? 'unmatched-soft' : undef);
    native_read_activity($activity, 'capture');
    return $activity;
}

# APP03: resume an already observed original window without launching it again.
# The controller compares the caller-declared immutable activity before Submit.
sub native_activity_resume {
    onpc_progress::operation('Resuming the independently observed original native activity');
    my ($journey, $prefix) = @_;
    die 'native:activity-resume' unless @_ == 2;
    my $activity = _native_activity_scope($journey, $prefix);
    return native_use_app($activity, $activity->seen('opened'));
}

# FLOW09 consumes only the caller's ledger and current surface, never a qualifier.
sub retained_app_visit {
    onpc_progress::operation('Returning legitimately to the original usable app activity');
    my ($journey, $prefix, $account, $source, $source_account) = @_;
    die 'native:retained-visit' unless (@_ == 4 || @_ == 5)
        && ref($journey) eq 'onpc_journey';
    onpc_desktop_session::enter_desktop($journey, $source, $account, 'retained', 'success',
                                      $prefix, $source_account);
    return native_activity_resume($journey, $prefix . '-activity');
}

# FLOW14 starts/ends at GDM; one existing or fresh desktop per distinct user.
sub retained_app_activities {
    onpc_progress::operation('Capturing distinct user activities and preserving their desktops');
    my ($journey, $users) = @_;
    die 'native:activity-users' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && ref($users) eq 'ARRAY' && @$users;
    my (%accounts, %prefixes);
    for my $user (@$users) {
        die 'native:activity-users' unless ref($user) eq 'ARRAY' && @$user == 3;
        my ($prefix, $account, $entry) = @$user;
        die 'native:activity-users' unless defined($prefix) && $prefix =~ /\A[a-z][a-z0-9-]*\z/
            && defined($account) && ($account eq 'parent' || $account eq 'child' || $account eq 'other-child')
            && defined($entry) && ($entry eq 'fresh' || $entry eq 'retained')
            && !$accounts{$account}++ && !$prefixes{$prefix}++;
    }
    for my $user (@$users) {
        my ($prefix, $account, $entry) = @$user;
        onpc_desktop_session::enter_desktop($journey, 'gdm', $account, $entry, 'success', $prefix);
        native_activity_entry($journey, $prefix . '-activity', 'command', $account);
        my $section = $journey->scope($prefix);
        $section->seen('desktop-identity');
        $section->consume_observation('switch-ready', $section->seen('switch-ready'));
        $section->seen($_) for qw(switch greeter);
    }
}

sub retained_app_visits {
    onpc_progress::operation('Qualifying distinct retained user app visits');
    my ($exchange, $declared, $challenges) = @_;
    die 'native:retained-visits' unless @_ == 3 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'retained-app-visits', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'initial',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen('allowance-configured');
    $journey->consume_observation('setup-switch-ready', $journey->seen('setup-switch-ready'));
    $journey->seen($_) for qw(setup-switch setup-greeter);
    retained_app_activities($journey, [['jamie', 'parent', 'retained'], ['riley', 'child', 'fresh']]);
    retained_app_visit($journey, 'parent-return', 'parent', 'gdm');
    $journey->seen('parent-usable-activity');
    retained_app_visit($journey, 'child-return', 'child', 'desktop', 'parent');
    $journey->seen('child-usable-activity');
    $journey->seen('wrong-mode-refused');
    retained_app_visit($journey, 'independent-return', 'parent', 'desktop', 'child');
    $journey->seen('independent-usable-activity');
    $journey->finish();
}

sub switch_user_expiry_parent {
    onpc_progress::operation('Keeping parent work usable while child time expires');
    my ($exchange, $declared, $challenges) = @_;
    die 'switch-expiry:arguments' unless @_ == 3 && ref($exchange) eq 'CODE';
    require onpc_desktop_session;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'switch-user-expiry-parent', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_parent::grant_only_time_profile($journey, 'gdm', 'fresh', 'new', 0, 0, 600, 'default', 0);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'child-start');
    $journey->seen('initial-countdown');
    onpc_desktop_session::enter_desktop($journey, 'desktop', 'parent', 'retained', 'success',
                                      'parent-work', 'child');
    native_activity_entry($journey, 'parent-activity', 'command', 'parent');
    for my $number (1 .. 4) {
        native_activity_resume($journey, 'work-' . $number);
        $journey->seen('work-' . $number . '-wait');
    }
    $journey->seen('original-interval-passed');
    onpc_desktop_session::enter_desktop($journey, 'desktop', 'child', 'retained', 'time-denied',
                                      'child-return', 'parent');
    onpc_gdm::return_from_time_denial($journey,
        'denied-return-ready', 'denied-return-state', 'denied-returned');
    retained_app_visit($journey, 'parent-return', 'parent', 'gdm');
    $journey->seen('parent-usable-activity');
    $journey->finish();
}

sub switch_user_expiry_other_child {
    onpc_progress::operation('Keeping the other child working while the original child time expires');
    my ($exchange, $declared, $challenges) = @_;
    die 'switch-expiry:arguments' unless @_ == 3 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'switch-user-expiry-other-child', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    retained_app_activities($journey, [['other-setup', 'other-child', 'fresh']]);
    onpc_parent::grant_only_time_profile($journey, 'gdm', 'fresh', 'new', 0, 0, 600, 'default', 0);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'child-start');
    $journey->seen('initial-countdown');
    retained_app_visit($journey, 'other-work', 'other-child', 'desktop', 'child');
    $journey->seen('other-child-active');
    for my $number (1 .. 4) {
        native_activity_resume($journey, 'work-' . $number);
        $journey->seen('work-' . $number . '-wait');
    }
    $journey->seen('original-interval-passed');
    onpc_desktop_session::enter_desktop($journey, 'desktop', 'child', 'retained', 'time-denied',
                                      'child-return', 'other-child');
    onpc_gdm::return_from_time_denial($journey,
        'denied-return-ready', 'denied-return-state', 'denied-returned');
    retained_app_visit($journey, 'other-return', 'other-child', 'gdm');
    $journey->seen('other-usable-activity');
    $journey->finish();
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

sub riley_native_grid {
    onpc_progress::operation('Qualifying Riley same-target native grid access');
    my ($exchange, $declared, $challenges) = @_;
    die 'native:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'riley-native-grid', review => 0);
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
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-parent-desktop'),
                                      'repeat-parent-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    my $first = _native_activity_scope($journey, 'first');
    native_close_app($first, native_usable_app($first, 'grid', $first->seen('desktop'), 'child'));

    # Independent valid entry, plus a mismatched result proof and focused
    # controller refusals. A refused/uncertain grid never falls back to command.
    my $repeat = _native_activity_scope($journey, 'repeat');
    my $grid = native_search($repeat, $repeat->seen('desktop'), 'refusals');
    my $accepted = eval { native_launch_grid($repeat, $grid); 1; };
    die 'native:wrong-result-accepted' if $accepted;
    die 'native:wrong-refusal' unless $@ =~ /journey:stale-observation/;
    my $opened = native_launch_grid($repeat, $repeat->seen('app-grid'));
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

sub native_space_path {
    my ($exchange, $declared, $challenges, $profile) = @_;
    $profile //= 'space';
    die 'native:space-arguments' unless (@_ == 3 || @_ == 4) && $profile =~ /\A(?:space|comma)\z/;
    onpc_progress::operation('Checking the child can copy and use an app with ' . $profile . ' characters in its name');
    my $journey = native_child_entry($exchange, $declared, $challenges, 'native-' . $profile . '-path');
    for my $entry ($profile eq 'space' ? ('first', 'independent') : ('first')) {
        $journey->seen($entry . '-copy');
        my $app = $journey->scope($entry . '-app');
        native_usable_app($app, 'command', $app->seen('desktop'), 'other-child',
            $profile eq 'space' ? 'SpaceCopy' : 'CommaCopy');
        native_finish_app($app);
        $journey->seen($entry . '-cleanup');
    }
    $journey->seen('child-logout');
    $journey->finish();
}

sub versioned_appimage_assets {
    my ($exchange, $declared, $challenges) = @_;
    die 'native:arguments' unless @_ == 3;
    onpc_progress::operation('Checking the child can copy and use the new app files');
    my $journey = native_child_entry($exchange, $declared, $challenges, 'versioned-appimage-assets');
    for my $entry ('first', 'independent') {
        $journey->seen($entry . '-next-copy');
        $journey->seen($entry . '-nonmatch-copy');
        for my $binding (['next', 'VersionNext'], ['existing', 'VersionExisting'], ['nonmatch', 'VersionNonmatch']) {
            my $app = $journey->scope($entry . '-' . $binding->[0]);
            native_usable_app($app, 'command', $app->seen('desktop'), 'other-child', $binding->[1]);
            native_finish_app($app);
        }
        $journey->seen($entry . '-cleanup');
    }
    $journey->seen('child-logout');
    $journey->finish();
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

sub snap_command_usable {
    onpc_progress::operation('Checking the child can use each Snap app and keep work in two S windows');
    _packaged_command_usable('snap-command-usable', @_);
}

sub flatpak_command_usable {
    onpc_progress::operation('Checking Jordan can use each Flatpak app and keep work in two separate windows');
    _packaged_command_usable('flatpak-command-usable', @_);
}

sub _packaged_command_usable {
    my $prefix = shift;
    my ($exchange, $declared, $challenges) = @_;
    die 'packaged:arguments' unless @_ == 3;
    my $journey = native_child_entry($exchange, $declared, $challenges, $prefix);
    $journey->seen('refusals');
    for my $name ('allowed', 'hard', 'soft', 'soft-second') {
        my $flow = _native_activity_scope($journey, $name);
        if ($prefix eq 'flatpak-command-usable') {
            my $role = $name eq 'allowed' ? 'A' : $name eq 'hard' ? 'H' : 'S';
            native_usable_app($flow, 'command', $flow->seen('desktop'), 'other-child', $role, 'flatpak');
        } else {
            native_usable_app($flow, 'command', $flow->seen('desktop'));
        }
        native_read_activity($flow, 'capture');
        native_read_activity($journey, 'soft-reread') if $name eq 'soft-second';
        native_finish_app($flow) unless $name eq 'soft';
    }
    native_finish_app(_native_activity_scope($journey, 'soft'));
    $journey->finish();
}

sub flatpak_grid {
    onpc_progress::operation('Checking that Parent blocks and restores the child app-grid entry without losing other work');
    my ($exchange, $declared, $challenges) = @_;
    die 'flatpak:grid-arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'flatpak-grid', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    $journey->seen($_) for qw(saved-settings apps-page);
    my $leaving = $journey->scope('leave-parent');
    onpc_desktop_session::switch_user($leaving, $leaving->seen('desktop'));
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'other-child', 'fresh', 'success', 'fresh');
    for my $binding (['allowed', 'A'], ['hard', 'H'], ['soft', 'S']) {
        my ($name, $role) = @$binding;
        my $flow = $journey->scope($name);
        native_usable_app($flow, 'grid', $flow->seen('desktop'), 'other-child', $role, 'flatpak');
        if ($role eq 'A') {
            native_read_activity($journey, 'allowed-capture');
        } else {
            native_finish_app($flow);
        }
    }
    onpc_desktop_session::enter_desktop(
        $journey, 'desktop', 'parent', 'retained', 'success', 'block-parent', 'other-child');
    $journey->seen($_) for qw(block-apps block-save block-row);
    onpc_desktop_session::enter_desktop(
        $journey, 'desktop', 'other-child', 'retained', 'success', 'blocked-child', 'parent');
    flatpak_blocked_app($journey->scope('blocked'), 'S', 'grid');
    native_read_activity($journey, 'allowed-after-block');
    onpc_desktop_session::enter_desktop(
        $journey, 'desktop', 'parent', 'retained', 'success', 'restore-parent', 'other-child');
    $journey->seen($_) for qw(restore-apps restore-save restore-row);
    onpc_desktop_session::enter_desktop(
        $journey, 'desktop', 'other-child', 'retained', 'success', 'restored-child', 'parent');
    my $earlier = $journey->scope('earlier');
    native_usable_app($earlier, 'command', $earlier->seen('desktop'), 'other-child', 'S', 'flatpak');
    native_read_activity($journey, 'earlier-capture');
    my $restored = $journey->scope('restored');
    # Shell Ctrl+Enter requests a new window; Enter could activate S/secondary
    # and conceal a failed launch. Both original activities must remain intact.
    native_usable_app($restored, 'grid', $restored->seen('desktop'), 'other-child', 'S', 'flatpak', 'ctrl-ret');
    native_read_activity($journey, $_) for qw(restored-capture earlier-reread allowed-preserved);
    native_finish_app($restored);
    native_finish_app($earlier);
    native_finish_app($journey->scope('allowed'));
    $journey->finish();
}

sub snap_grid {
    onpc_progress::operation('Checking allowed Snap grid launches and preserving the child\'s earlier work');
    my ($exchange, $declared, $challenges) = @_;
    die 'snap:arguments' unless @_ == 3 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'snap-grid', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    $journey->consume_observation('parent-selected', onpc_parent::select_child(
        $journey, 'existing', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected'));
    read_rows($journey, 'apps-page');
    read_rows($journey, 'app-rows');
    $journey->seen('logout');
    onpc_gdm::sign_in_challenge($journey, 'native-child-login',
        'child-installed-greeter', 'child-standard-focused', 'child-desktop');
    for my $binding (['allowed', 'A'], ['hard', 'H'], ['soft', 'S']) {
        my ($name, $role) = @$binding;
        if ($role eq 'S') {
            my $earlier = _native_activity_scope($journey, 'earlier');
            native_usable_app($earlier, 'command', $earlier->seen('desktop'), 'other-child', 'S', 'snap');
            native_read_activity($earlier, 'capture');
        }
        my $flow = _native_activity_scope($journey, $name);
        # GNOME Shell Ctrl+Enter requests a new window rather than activating
        # the already-running app. The command-opened S/secondary stays open.
        native_usable_app($flow, 'grid', $flow->seen('desktop'), 'other-child', $role, 'snap',
            $role eq 'S' ? 'ctrl-ret' : 'ret');
        native_read_activity($flow, 'capture');
        $journey->seen('refusals') if $role eq 'A';
        native_read_activity($journey, 'earlier-reread') if $role eq 'S';
        native_finish_app($flow);
    }
    native_finish_app(_native_activity_scope($journey, 'earlier'));
    $journey->finish();
}

sub native_desktop_usable {
    onpc_progress::operation('Checking the child can open and use an app from its desktop icon');
    my ($exchange, $declared, $challenges) = @_;
    die 'native:arguments' unless @_ == 3;
    my $journey = native_child_entry($exchange, $declared, $challenges, 'native-desktop-usable');
    for my $entry ('first', 'independent') {
        my $flow = $journey->scope($entry);
        $flow->seen('place');
        native_usable_app($flow, 'desktop', $flow->seen('desktop'));
        native_finish_app($flow);
        $flow->seen('cleanup');
    }
    $journey->seen('child-logout');
    $journey->finish();
}

sub native_files_usable {
    onpc_progress::operation('Checking the child can launch from Files and keep work in a separate window');
    my ($exchange, $declared, $challenges) = @_;
    die 'native:arguments' unless @_ == 3;
    my $journey = native_child_entry($exchange, $declared, $challenges, 'native-files-usable');
    my $first = $journey->scope('first');
    native_usable_app($first, 'files', $first->seen('desktop'));
    $first->seen('dismiss');
    native_finish_app($first);
    my $earlier = $journey->scope('earlier');
    native_usable_app($earlier, 'command', $earlier->seen('desktop'), 'other-child', 'S');
    native_read_activity($earlier, 'capture');
    my $second = $journey->scope('second');
    native_usable_app($second, 'files', $second->seen('desktop'), 'other-child', 'S');
    $second->seen('dismiss');
    native_read_activity($second, 'capture');
    native_read_activity($earlier, 'reread');
    native_finish_app($second);
    native_finish_app($earlier);
    $journey->seen('child-logout');
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
