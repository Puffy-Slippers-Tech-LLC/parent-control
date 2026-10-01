package onpc_app_rows;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();

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
    my ($journey) = @_;
    die 'app-rows:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    for my $stage ('apps-page', 'app-rows', 'wrong-child', 'wrong-page', 'reopened-rows') {
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

1;
