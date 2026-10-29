package onpc_active_grant_disable;
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_app_rows ();
use onpc_request_flow ();
use onpc_desktop_session ();
use onpc_text ();

sub run {
    onpc_progress::operation('Qualifying active-grant disable transitions');
    my ($exchange, $declared, $challenges, $binding) = @_;
    die 'active-grant-disable:arguments' unless @_ == 4 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && defined($binding) && ($binding eq 'engineering' || $binding eq 'public');
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => 'active-grant-disable-' . $binding, review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 0, 1));
    $journey->seen('apps-page');
    for my $edit (['H', 'match-hard-precise', 'permanent', 'hard'],
                  ['S', 'match-soft-wildcard', 'conditional', 'soft']) {
        my $app = 'parent-app-' . substr(sha256_hex(
            'com.puffyslippers.ONPCTest.' . $edit->[0] . '.desktop'), 0, 16);
        onpc_app_rows::edit_policy($journey, $app, @$edit[1 .. 3], [], 1);
    }
    onpc_text::replace_text($journey, 'catalogue-clear', 'setup-clear');
    $journey->seen($_) for qw(saved-policy setup-switch setup-greeter);
    onpc_request_flow::obtain_time($journey, 'default', 'fixture-child', 'fixture-parent', 600, 1, 'automatic');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'child-entry');
    $journey->seen('child-countdown');
    onpc_app_rows::native_activity_entry($journey, 'activity', 'command', 'child', 0);
    if ($binding eq 'engineering') {
        $journey->finish();
        return;
    }
    $journey->seen($_) for qw(child-switch child-greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'parent-return');
    $journey->consume_observation('supplied-parent-retained', onpc_parent::open_for_child(
        $journey, 'desktop', 'same-user', 'retained', 'child', 'supplied', 0));
    $journey->seen($_) for qw(granted-policy disabled disabled-saved disabled-policy
        parent-switch disabled-greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'retained', 'success', 'child-return');
    onpc_app_rows::native_activity_resume($journey, 'resumed');
    $journey->finish();
}
1;
