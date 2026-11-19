package onpc_app_launch;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_desktop_session ();
use onpc_app_rows ();

sub use_app {
    my ($activity, $route, $child, $kind) = @_;
    my $role = $kind eq 'native' ? undef : 'A';
    onpc_app_rows::native_usable_app($activity, $route, $activity->seen('desktop'),
                                   $child, $role, $kind);
}

sub use_command_after_grid {
    my ($journey, $prefix, $child, $kind) = @_;
    onpc_app_rows::native_finish_app($journey->scope("$prefix-use"));
    use_app($journey->scope("$prefix-command"), 'command', $child, $kind);
}

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
        && ($route eq 'command' || ($route eq 'grid' && $control eq 'enabled')
            || $route eq 'files' && $control eq 'enabled'
                && $kind eq 'native'
            || $route eq 'desktop' && $control eq 'enabled'
                && $kind eq 'native')
        && ($policy eq 'allowed' || $policy eq 'hard-blocked' || $policy eq 'soft-blocked')
        && ($kind eq 'native' || $kind eq 'snap' && $policy eq 'allowed'
            || $kind eq 'flatpak');
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
        onpc_app_rows::access_choice($journey, "$rule-save", "$rule-row");
    } else {
        onpc_app_rows::edit_policy($journey, onpc_app_rows::fixture_app('A'),
            'match-precise', $access, $rule, []);
    }
    $journey->seen('parent-logout');
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'other-child', 'fresh', 'success', 'jordan-entry');
    my $jordan = $journey->scope($policy eq 'allowed' ? 'jordan-use' : 'jordan-denied');
    $jordan->seen('place') if $route eq 'desktop';
    if ($policy eq 'allowed') {
        use_app($jordan, $route, 'other-child', $kind);
    } elsif ($kind eq 'flatpak') {
        onpc_app_rows::flatpak_blocked_app($jordan, 'A', $route, 'command');
    } else {
        onpc_app_rows::native_blocked_app($jordan, 'A', $route);
    }
    use_command_after_grid($journey, 'jordan', 'other-child', $kind)
        if $route eq 'grid' && $policy eq 'allowed';
    $jordan->seen('dismiss') if $route eq 'files';
    if ($route eq 'desktop') {
        onpc_app_rows::native_finish_app($jordan) if $policy eq 'allowed';
        $jordan->seen('cleanup');
    }
    $journey->seen('jordan-logout');
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'child', 'fresh', 'success', 'riley-entry');
    my $riley = $journey->scope('riley-use');
    $riley->seen('place') if $route eq 'desktop';
    use_app($riley, $route, 'child', $kind);
    use_command_after_grid($journey, 'riley', 'child', $kind)
        if $route eq 'grid' && $policy eq 'allowed';
    $riley->seen('dismiss') if $route eq 'files';
    if ($route eq 'desktop') {
        onpc_app_rows::native_finish_app($riley);
        $riley->seen('cleanup');
    }
    $journey->finish();
}
1;
