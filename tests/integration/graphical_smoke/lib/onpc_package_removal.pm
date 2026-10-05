package onpc_package_removal;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();
use onpc_request_flow ();
use onpc_text ();

sub scope {
    my ($journey, $prefix) = @_;
    die 'package-removal:scope' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && $prefix =~ /\A[a-z][a-z0-9-]*\z/;
    return onpc_journey->new(exchange => sub {
        $journey->{exchange}->($prefix . '-' . $_[0], $_[1]);
    }, prefix => 'package-removal-' . $prefix, review => 0);
}

sub login {
    my ($journey, $prefix, $role) = @_;
    die 'package-removal:login' unless @_ == 3 && ($role eq 'parent' || $role eq 'child');
    my $focused = $role eq 'parent' ? 'parent-focused' : 'child-focused';
    my $desktop = onpc_gdm::sign_in_challenge($journey, $prefix,
        "$prefix-installed-greeter", "$prefix-$focused", "$prefix-desktop");
    $journey->consume_observation("$prefix-desktop", $desktop);
}

sub management {
    my ($journey, $prefix) = @_;
    my $section = scope($journey, $prefix);
    $section->seen($_) for qw(parent-command parent-window);
    my $selected = onpc_parent::select_child($section, 'child',
        $section->seen('child-picker-opened'), 'child-picker-opened',
        'child-choice-highlighted', 'parent-selected');
    $section->consume_observation('parent-selected', $selected);
}

sub station {
    my ($journey, $prefix) = @_;
    return onpc_gdm::enter_station(scope($journey, $prefix), '');
}

sub allowance {
    my ($journey, $prefix, $minutes) = @_;
    $journey->seen("$prefix-open");
    onpc_text::replace_text($journey, "daily-$minutes", "$prefix-text");
    $journey->seen("$prefix-saved");
}

sub run {
    onpc_progress::operation('Following one continuous removal, retention and purge history');
    my ($exchange, $declared, $challenges) = @_;
    die 'package-removal:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'package-removal', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_parent::login_functional($journey);
    $journey->seen($_) for qw(command-context package-submitted package-result activated-reboot-requested);
    login($journey, 'activated', 'parent');
    management($journey, 'initial');
    $journey->seen($_) for qw(initial-apps initial-rows initial-screen limit-enabled save-enabled);
    allowance($journey, 'initial-allowance', 4);
    $journey->seen($_) for qw(initial-apps-again initial-block
        initial-block-read initial-policy switch-user gdm-switched);
    onpc_gdm::enter_station($journey, '');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default', 'fixture-child', 'fixture-parent', 75, 1);
    $journey->seen($_) for qw(open-cancel open-returned);
    login($journey, 'restricted-child', 'child');
    $journey->seen($_) for qw(blocked-before-remove overlay-launch overlay-choices overlay-cancel restricted-logout);
    onpc_request_flow::obtain_time($journey, 'selected', 'fixture-child', 'fixture-parent', 75, 1, 'automatic');
    login($journey, 'remove-parent', 'parent');
    management($journey, 'before-remove');
    $journey->seen($_) for qw(active-grant remove-submitted remove-result removed-reboot-requested);
    login($journey, 'removed', 'parent');
    $journey->seen('removed-parent-logout');
    login($journey, 'healthy-child', 'child');
    $journey->seen($_) for qw(healthy-command healthy-opened healthy-submit healthy-submitted
        healthy-close healthy-closed healthy-child-logout);
    login($journey, 'reinstall-parent', 'parent');
    $journey->seen($_) for qw(reinstall-submitted reinstall-result retained-reboot-requested);
    login($journey, 'retained', 'parent');
    management($journey, 'retained');
    $journey->seen($_) for qw(retained-policy retained-switch retained-greeter);
    station($journey, 'retained');
    $journey->seen($_) for qw(retained-request retained-cancel retained-returned);
    login($journey, 'reapply-parent', 'parent');
    management($journey, 'reapply');
    allowance($journey, 'reapply-allowance', 5);
    $journey->seen($_) for qw(reapply-apps reapply-allowed reapply-allowed-read reapply-block
        reapply-block-read reapply-policy reapply-switch reapply-greeter);
    login($journey, 'reblocked-child', 'child');
    $journey->seen($_) for qw(blocked-after-reinstall reblocked-logout);
    login($journey, 'purge-parent', 'parent');
    $journey->seen($_) for qw(purge-submitted purge-result purged-reboot-requested);
    login($journey, 'purged', 'parent');
    $journey->seen($_) for qw(fresh-submitted fresh-result fresh-reboot-requested);
    login($journey, 'fresh', 'parent');
    management($journey, 'fresh');
    $journey->seen($_) for qw(fresh-apps fresh-rows fresh-switch fresh-greeter);
    station($journey, 'fresh');
    $journey->seen($_) for qw(fresh-request fresh-cancel fresh-returned);
    $journey->finish();
}

1;
