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
    my ($exchange, $declared, $challenges, $request, $disabled) = @_;
    die 'app-transitions:binding' unless @_ == 5 && ref($exchange) eq 'CODE'
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
        [['A', $disabled ? 'match-wildcard-appimages' : 'match-precise', 'allowed'],
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
        my $carry_matching = $name eq 'soft-allowed';
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
            onpc_desktop_session::enter_desktop($journey, 'gdm', 'other-child', 'retained', 'success',
                                              $name . '-prepare');
            onpc_app_rows::native_activity_entry($journey, $name . '-opening', 'command', 'other-child', 1, 'policy');
            onpc_desktop_session::enter_desktop($journey, 'desktop', 'parent', 'retained', 'success',
                                              $name . '-save-parent', 'other-child');
            if ($disabled) {
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
        visit_riley($journey, $name, 'parent') if $carry_matching;
        onpc_desktop_session::enter_desktop($journey, 'desktop', 'other-child', 'retained', 'success',
                                          $name . '-result', $carry_matching ? 'child' : 'parent');
        my $matching = $journey->scope($name . '-matching');
        if ($access ne 'allowed') {
            onpc_app_rows::native_read_activity($journey, $name . '-closed');
            onpc_app_rows::native_blocked_app($matching, 'A');
        } elsif ($carry_matching) {
            onpc_app_rows::native_activity_entry($journey, $name . '-matching', 'command', 'other-child', 1, 'policy');
        } else {
            onpc_app_rows::native_usable_app($matching, 'command', $matching->seen('desktop'), 'other-child');
            onpc_app_rows::native_finish_app($matching);
        }
        onpc_app_rows::native_read_activity($journey, $name . '-nonmatching-retained');
        $journey->seen($name . '-nonmatching-' . $_) for qw(resubmit submitted close closed);
        onpc_app_rows::native_activity_entry($journey, $name . '-nonmatching-new', 'command', 'other-child', 1, 'unmatched-soft');
        onpc_app_rows::native_read_activity($journey, $name . '-matching-retained') if $carry_matching;
        visit_riley($journey, $name, 'other-child') unless $carry_matching;
        onpc_desktop_session::enter_desktop($journey, 'desktop', 'parent', 'retained', 'success',
                                          $name . '-parent', $carry_matching ? 'other-child' : 'child');
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

sub visit_riley {
    my ($journey, $name, $source) = @_;
    onpc_app_rows::retained_app_visit($journey, $name . '-riley', 'child', 'desktop', $source);
    onpc_app_rows::native_read_activity($journey, $name . '-riley-usable');
}

1;
