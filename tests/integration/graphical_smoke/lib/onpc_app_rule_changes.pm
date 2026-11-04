package onpc_app_rule_changes;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_app_rows ();
use onpc_desktop_session ();
use onpc_request_flow ();
use onpc_lifecycle ();

# Case-owned finite ordering; all input and result mechanics stay shared.
sub run {
    onpc_progress::operation('Checking app rule changes while both children keep using their own apps');
    my ($exchange, $declared, $challenges, $request, $match, $disabled) = @_;
    $match //= 'precise';
    $disabled //= 0;
    die 'app-transitions:binding' unless (@_ == 4 || @_ == 5 || @_ == 6) && ref($exchange) eq 'CODE'
        && ($match eq 'precise' || $match eq 'pattern')
        && ($disabled eq '0' || $disabled eq '1')
        && ref($request) eq 'ARRAY' && join(',', @$request) eq 'other-child,parent,75,1';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'app-rule-changes', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
    $journey->seen('saved-settings');
    if ($disabled) {
        $journey->seen($_) for qw(limits-off-page limits-off-save limits-off-settings);
    }
    $journey->seen($_) for qw(apps-page initial-rows);
    onpc_app_rows::named_app_set($journey, 'desktop', 'same-user', 'retained', 'existing',
        [['A', $match eq 'pattern' ? 'match-wildcard-appimages' : 'match-precise', 'allowed'],
         ['S', 'match-soft-precise', 'allowed']], 'setup-rules');
    onpc_app_rows::retained_app_activities($journey, [['riley', 'child', 'fresh']]);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'fresh', 'success', 'jordan');
    onpc_app_rows::native_activity_entry($journey, 'initial-matching', 'command', 'other-child', 1, 'policy');
    onpc_app_rows::native_activity_entry($journey, 'initial-nonmatching', 'command', 'other-child', 1, 'unmatched-soft');
    $journey->seen('jordan-session');
    onpc_desktop_session::enter_desktop($journey, 'desktop', 'parent', 'retained', 'success',
                                      'prepared-parent', 'other-child');
    $journey->seen('prepared-apps');
    for my $round (['allowed-soft', 'conditional'], ['soft-hard', 'permanent'],
                   ['hard-soft', 'conditional'], ['soft-allowed', 'allowed'],
                   ['allowed-hard', 'permanent'], ['hard-allowed', 'allowed']) {
        my ($name, $access) = @$round;
        if ($name eq 'soft-hard' || $name eq 'allowed-hard') {
            if ($name eq 'soft-hard') {
                if ($disabled) {
                    $journey->seen($_) for qw(soft-opening-settings soft-opening-enable soft-opening-enabled);
                }
                $journey->seen($_) for qw(soft-opening-balance soft-opening-desktop
                                        soft-opening-switch soft-opening-greeter);
                my $approval = $journey->scope('soft-opening');
                $approval->{kiosk_request} = $request;
                onpc_request_flow::obtain_time($approval, 'observed',
                    'existing-fixture-child', 'fixture-parent', 75, 1, 'automatic');
            }
            if ($name eq 'soft-hard') {
                onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'retained', 'success',
                                                  $name . '-prepare');
            } else {
                onpc_desktop_session::enter_desktop($journey, 'desktop', 'other-child', 'retained', 'success',
                                                  $name . '-prepare', 'parent');
            }
            onpc_app_rows::native_activity_entry($journey, $name . '-opening', 'command', 'other-child', 1, 'policy');
            onpc_desktop_session::enter_desktop($journey, 'desktop', 'parent', 'retained', 'success',
                                              $name . '-save-parent', 'other-child');
            if ($disabled && $name eq 'soft-hard') {
                $journey->seen($_) for qw(soft-opening-disable-page soft-opening-disable);
                onpc_desktop_session::enter_desktop($journey, 'desktop', 'other-child', 'retained', 'success',
                                                  'soft-opening-disabled-child', 'parent');
                onpc_app_rows::native_read_activity($journey, 'soft-opening-preserved');
                onpc_desktop_session::enter_desktop($journey, 'desktop', 'parent', 'retained', 'success',
                                                  'soft-opening-disabled-parent', 'other-child');
            }
        }
        $journey->seen($name . '-' . $_) for qw(settings apps);
        onpc_app_rows::access_choice($journey, $name . '-save', $name . '-access');
        $journey->seen($name . '-match');
        onpc_desktop_session::enter_desktop($journey, 'desktop', 'other-child', 'retained', 'success',
                                          $name . '-result', 'parent');
        my $matching = $journey->scope($name . '-matching');
        if ($access ne 'allowed') {
            onpc_app_rows::native_read_activity($journey, $name . '-closed');
            onpc_app_rows::native_blocked_app($matching, 'A');
        } else {
            onpc_app_rows::native_usable_app($matching, 'command', $matching->seen('desktop'), 'other-child');
            onpc_app_rows::native_finish_app($matching);
        }
        onpc_app_rows::native_read_activity($journey, $name . '-nonmatching-retained');
        $journey->seen($name . '-nonmatching-' . $_) for qw(resubmit submitted close closed);
        onpc_app_rows::native_activity_entry($journey, $name . '-nonmatching-new', 'command', 'other-child', 1, 'unmatched-soft');
        onpc_app_rows::retained_app_visit($journey, $name . '-riley', 'child', 'desktop', 'other-child');
        onpc_app_rows::native_read_activity($journey, $name . '-riley-usable');
        onpc_desktop_session::enter_desktop($journey, 'desktop', 'parent', 'retained', 'success',
                                          $name . '-parent', 'child');
    }
    my $final = $journey->scope('final-reopen');
    $final->consume_observation('initial-selection', onpc_lifecycle::reopen(
        $final, 'parent', $final->seen('prior-window'), 'management'));
    my $child = $journey->scope('final-child');
    $child->consume_observation('parent-selected', onpc_parent::select_child(
        $child, 'existing', $child->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected'));
    $journey->seen($_) for qw(final-apps final-match final-access);
    $journey->finish();
}

1;
