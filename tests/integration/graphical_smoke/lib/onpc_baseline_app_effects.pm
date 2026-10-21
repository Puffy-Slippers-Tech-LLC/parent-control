package onpc_baseline_app_effects;
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_app_rows ();
use onpc_text ();
use onpc_request_flow ();
use onpc_desktop_session ();

sub run {
    onpc_progress::operation('Qualifying granted app use and restored time and app restrictions');
    my ($exchange, $declared, $challenges) = @_;
    die 'baseline-app-effects:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'baseline-app-effects', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 0, 1));
    $journey->seen($_) for qw(saved-settings apps-page);
    my %apps = map { $_ => 'parent-app-' . substr(sha256_hex(
        "com.puffyslippers.ONPCTest.$_.desktop"), 0, 16) } qw(A H S);
    for my $edit (['A', 'match-precise', 'allowed', 'allowed'],
                  ['H', 'match-hard-precise', 'permanent', 'hard'],
                  ['S', 'match-soft-wildcard', 'conditional', 'soft']) {
        onpc_app_rows::edit_policy($journey, $apps{$edit->[0]}, @$edit[1 .. 3], []);
    }
    onpc_text::replace_text($journey, 'catalogue-clear', 'setup-clear');
    $journey->seen($_) for qw(saved-policy switch-ready switch-user gdm-switched);
    onpc_request_flow::obtain_time($journey, 'default', 'fixture-child', 'fixture-parent', 600, 1, 'automatic');
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'child', 'fresh', 'success', 'child-entry');
    $journey->seen('child-countdown');
    for my $binding (['allowed-use', 'A'], ['soft-use', 'S']) {
        my $section = $journey->scope($binding->[0]);
        onpc_app_rows::native_usable_app($section, 'command', $section->seen('desktop'), 'child', $binding->[1]);
    }
    $journey->seen($_) for qw(soft-close soft-closed allowed-close allowed-closed hard-denied
        remaining-countdown child-switch-ready child-switch child-greeter);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'parent-return');
    $journey->consume_observation('supplied-parent-retained', onpc_parent::open_for_child(
        $journey, 'desktop', 'same-user', 'retained', 'child', 'supplied'));
    $journey->seen($_) for qw(granted-policy revoke-open revoke-warning revoke-confirm revoked-policy
        parent-switch-ready parent-switch revoked-greeter enter-locked);
    $journey->consume_observation('time-denied', onpc_desktop_session::reveal_lock($journey, 'time-denied'));
    $journey->seen($_) for qw(soft-denied return-greeter denied-returned);
    onpc_desktop_session::enter_desktop($journey, 'gdm', 'parent', 'retained', 'success', 'restore-return');
    $journey->consume_observation('restored-parent-retained', onpc_parent::open_for_child(
        $journey, 'desktop', 'same-user', 'retained', 'child', 'restored'));
    $journey->seen('restore-apps');
    for my $edit (['H', 'match-hard-precise', 'restore-hard'], ['S', 'match-soft-wildcard', 'restore-soft']) {
        onpc_app_rows::edit_policy($journey, $apps{$edit->[0]}, $edit->[1], 'allowed', $edit->[2], []);
    }
    onpc_text::replace_text($journey, 'catalogue-clear', 'restore-clear');
    $journey->seen($_) for qw(restore-screen restore-disabled restore-saved restore-settings restore-balance);
    $journey->finish();
}
1;
