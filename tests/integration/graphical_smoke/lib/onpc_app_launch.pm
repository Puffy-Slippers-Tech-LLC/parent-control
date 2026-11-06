package onpc_app_launch;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_desktop_session ();
use onpc_app_rows ();

sub run {
    onpc_progress::operation('Checking the parent rule and independent app access for both children');
    my ($exchange, $declared, $challenges, $control, $route, $policy, $kind) = @_;
    $control = 'enabled' unless defined($control);
    $route = 'command' unless defined($route);
    $policy //= 'allowed';
    $kind //= 'native';
    die 'app-launch:arguments' unless (@_ >= 3 && @_ <= 7) && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ($control eq 'enabled' || $control eq 'disabled')
        && ($route eq 'command' || ($route eq 'grid' && $control eq 'enabled'))
        && ($policy eq 'allowed' || $policy eq 'hard-blocked' || $policy eq 'soft-blocked')
        && ($kind eq 'native' || $kind eq 'snap' && $policy eq 'allowed'
            || $kind eq 'flatpak' && $policy eq 'allowed' && $route eq 'command');
    my $rule = $policy eq 'allowed' ? 'allowed' : $policy eq 'hard-blocked' ? 'hard' : 'soft';
    my $access = $rule eq 'allowed' ? 'allowed' : $rule eq 'hard' ? 'permanent' : 'conditional';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => "$kind-$route-$policy", review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    if ($control eq 'enabled') {
        $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
            $journey, 'gdm', 'parent', 'fresh', 'new', 'existing', 0, 30, 1));
        $journey->seen('saved-settings');
    } else {
        # The independent Parent read proves the clean child's disabled limits
        # and zero allowance before any policy edit or child input.
        $journey->consume_observation('parent-selected', onpc_parent::open_for_child(
            $journey, 'gdm', 'fresh', 'new', 'existing'));
    }
    $journey->seen('apps-page');
    if ($kind eq 'snap' || $kind eq 'flatpak') {
        onpc_app_rows::access_choice($journey, 'allowed-save', 'allowed-row');
    } else {
        onpc_app_rows::edit_policy($journey, onpc_app_rows::fixture_app('A'),
            'match-precise', $access, $rule, []);
    }
    $journey->seen('parent-logout');
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'other-child', 'fresh', 'success', 'jordan-entry');
    my $jordan = $journey->scope($policy eq 'allowed' ? 'jordan-use' : 'jordan-denied');
    if ($policy eq 'allowed') {
        onpc_app_rows::native_usable_app($jordan, $route, $jordan->seen('desktop'), 'other-child',
                                       $kind ne 'native' ? 'A' : undef, $kind);
    } else {
        onpc_app_rows::native_blocked_app($jordan, 'A', $route);
    }
    if ($kind eq 'native' && $route eq 'grid' && $policy eq 'allowed') {
        onpc_app_rows::native_finish_app($jordan);
        my $command = $journey->scope('jordan-command');
        onpc_app_rows::native_usable_app($command, 'command', $command->seen('desktop'), 'other-child');
    }
    $journey->seen('jordan-logout');
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'child', 'fresh', 'success', 'riley-entry');
    my $riley = $journey->scope('riley-use');
    onpc_app_rows::native_usable_app($riley, $route, $riley->seen('desktop'), 'child',
                                   $kind ne 'native' ? 'A' : undef, $kind);
    if ($kind eq 'native' && $route eq 'grid' && $policy eq 'allowed') {
        onpc_app_rows::native_finish_app($riley);
        my $command = $journey->scope('riley-command');
        onpc_app_rows::native_usable_app($command, 'command', $command->seen('desktop'), 'child');
    }
    $journey->finish();
}
1;
