package onpc_fresh_thirty_allowance;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_app_rows ();
use onpc_feedback_privacy ();

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
# Case composition: shared FLOW16, query/filter and complete-row leaves.
sub search_filters {
    onpc_progress::operation('Searching Jordan catalogue and checking unchanged app policies');
    my ($exchange) = @_;
    die 'search-filters:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'search-filters', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    for my $stage ('balance-reread', 'saved-settings', 'apps-page') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
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
