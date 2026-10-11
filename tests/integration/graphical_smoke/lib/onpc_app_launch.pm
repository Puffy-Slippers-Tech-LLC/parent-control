package onpc_app_launch;
use strict;
use warnings;
use Digest::SHA qw(sha256_hex);
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_desktop_session ();
use onpc_app_rows ();

sub run {
    onpc_progress::operation('Using the allowed native command independently as both children');
    my ($exchange, $declared, $challenges, $control) = @_;
    $control = 'enabled' unless defined($control);
    die 'app-launch:arguments' unless (@_ == 3 || @_ == 4) && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && ($control eq 'enabled' || $control eq 'disabled');
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'native-command-allowed', review => 0);
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
    my $app = 'parent-app-' . substr(sha256_hex('com.puffyslippers.ONPCTest.A.desktop'), 0, 16);
    onpc_app_rows::edit_policy($journey, $app,
        'match-precise', 'allowed', 'allowed', []);
    $journey->seen('parent-logout');
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'other-child', 'fresh', 'success', 'jordan-entry');
    my $jordan = $journey->scope('jordan-use');
    onpc_app_rows::native_usable_app($jordan, 'command', $jordan->seen('desktop'));
    $journey->seen('jordan-logout');
    onpc_desktop_session::enter_desktop(
        $journey, 'gdm', 'child', 'fresh', 'success', 'riley-entry');
    my $riley = $journey->scope('riley-use');
    onpc_app_rows::native_usable_app($riley, 'command', $riley->seen('desktop'));
    $journey->finish();
}
1;
