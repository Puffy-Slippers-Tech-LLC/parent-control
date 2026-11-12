package onpc_family_routines;
use strict;
use warnings;
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_app_rows ();
use onpc_text ();
use onpc_request_flow ();
use onpc_desktop_session ();
use onpc_allowance_selection ();
use onpc_progress ();

my $apps = [['A', 'match-precise', 'allowed'], ['H', 'match-hard-precise', 'permanent'],
            ['Game', 'match-game-precise', 'conditional']];
my %roles = (jordan => 'other-child', riley => 'child');
my %opened;

sub entry {
    my ($journey, $prefix, $account, $retained, $expected) = @_;
    return onpc_desktop_session::enter_desktop($journey, 'gdm', $account,
        $retained ? 'retained' : 'fresh', $expected // 'success', $prefix);
}

sub leave {
    my ($journey, $prefix) = @_;
    $journey->seen("$prefix-$_") for qw(leave switch gdm);
}

sub select_child {
    my ($journey, $prefix, $who) = @_;
    my $section = $journey->scope($prefix);
    $section->consume_observation('parent-selected', onpc_parent::select_child($section,
        $who eq 'jordan' ? 'existing' : 'child', $section->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected'));
}

sub management {
    my ($journey, $prefix, $parent, $who) = @_;
    my $retained = $opened{$parent};
    entry($journey, "$prefix-entry", $parent, $retained);
    $journey->consume_observation("$prefix-parent-retained",
        onpc_parent::open_for_child($journey, 'desktop', 'same-user', $retained ? 'retained' : 'new',
            $who eq 'jordan' ? 'existing' : 'child', $prefix, 1, $parent));
    $journey->seen("$prefix-session");
    $opened{$parent} = 1;
}

sub rows {
    my ($journey, $prefix) = @_;
    $journey->seen("$prefix-apps");
    onpc_app_rows::saved_rows($journey->scope($prefix), $apps, 'rows');
}

sub peer_parent {
    my ($journey, $prefix, $who) = @_;
    select_child($journey, $prefix, $who);
    $journey->seen("$prefix-balance");
    rows($journey, $prefix);
}

sub profile {
    my ($journey, $prefix, $minutes) = @_;
    onpc_allowance_selection::select($journey, "$prefix-daily", [$minutes], 'confirm');
    $journey->seen("$prefix-$_") for qw(off on settings balance);
}

sub work {
    my ($journey, $prefix, @actions) = @_;
    $journey->seen("$prefix-$_") for @actions;
}

sub choices {
    my ($journey, $prefix, $seed) = @_;
    $journey->invoke("$prefix-launch");
    $journey->seen("$prefix-select") if $seed;
    $journey->seen("$prefix-$_") for qw(read cancel returned);
}

sub peer_work {
    my ($journey, $prefix, $who) = @_;
    entry($journey, $prefix, $roles{$who}, 1);
    work($journey, "$prefix-work", qw(capture resubmit submitted));
    choices($journey, "$prefix-choices", 0);
    leave($journey, $prefix);
}

sub approval {
    my ($journey, $prefix, $who, $surface, $seconds, $soft) = @_;
    my $request = $journey->scope($prefix);
    my $parent = $surface eq 'overlay' ? 'other-parent' : 'parent';
    my $binding = [$roles{$who}, $parent, $seconds, $soft];
    my $child = $who eq 'jordan' ? 'existing-fixture-child' : 'fixture-child';
    my $approver = $surface eq 'overlay' ? 'other-fixture-parent' : 'fixture-parent';
    $request->{$surface . '_request'} = $binding;
    onpc_request_flow::prepare($request, 'new', 'new', 'observed', $child, $approver,
                               $seconds, $soft, $surface);
    if ($surface eq 'overlay') {
        onpc_request_flow::overlay_approve($request, 'automatic');
    } else {
        onpc_request_flow::approve($request, $child, $approver, $seconds, $soft, 'automatic');
        entry($journey, "$prefix-retained", $roles{$who}, 1);
    }
    $journey->seen("$prefix-countdown");
}

sub run {
    onpc_progress::operation('Keeping both children’s work, time and choices separate');
    my ($exchange, $declared, $challenges) = @_;
    die 'family-routines:arguments' unless @_ == 3 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'family-routines', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = entry($journey, 'initial', 'parent', 0);
    $journey->consume_observation('initial-desktop', $desktop);
    $journey->seen($_) for qw(initial-parent-command initial-parent-window);
    select_child($journey, 'initial', 'jordan');
    for my $who (qw(jordan riley)) {
        select_child($journey, 'setup-riley', 'riley') if $who eq 'riley';
        $journey->seen("setup-$who-enable");
        onpc_allowance_selection::select($journey, "setup-$who-daily", [120], 'confirm');
        $journey->seen("setup-$who-$_") for qw(balance apps);
        for my $index (0 .. $#$apps) {
            my ($role, $draft, $access) = @{$apps->[$index]};
            onpc_app_rows::edit_policy($journey->scope("setup-$who"), onpc_app_rows::fixture_app($role),
                $draft, $access, "policy-$index", [], 1);
        }
        onpc_text::replace_text($journey->scope("setup-$who"), 'catalogue-clear', 'clear');
        onpc_app_rows::saved_rows($journey->scope("setup-$who"), $apps, 'rows');
    }
    $journey->seen('setup-window');
    $opened{parent} = 1;
    leave($journey, 'setup');
    for my $who (qw(jordan riley)) {
        entry($journey, "initial-$who", $roles{$who}, 0);
        work($journey, "initial-$who-work", qw(open opened edit save saved submit submitted capture));
        choices($journey, "initial-$who-choices", 1);
        leave($journey, "initial-$who");
        onpc_gdm::enter_station($journey->scope("seed-$who"), '');
        $journey->seen("seed-$who-$_") for qw(select read cancel returned);
    }
    my @visits = (['jordan', 60, 'overlay', 75, 1], ['riley', 0, 'kiosk', 7200, 1],
                  ['riley', 120, 'overlay', 150, 0], ['jordan', 0, 'kiosk', 7200, 0]);
    for my $index (0 .. $#visits) {
        my ($who, $minutes, $surface, $seconds, $soft) = @{$visits[$index]};
        my $root = 'visit-' . ($index + 1);
        my $parent = $index % 2 ? 'second-parent' : 'parent';
        my $peer = $who eq 'jordan' ? 'riley' : 'jordan';
        management($journey, "$root-before", $parent, $peer);
        peer_parent($journey, "$root-peer-before", $peer);
        leave($journey, "$root-before");
        peer_work($journey, "$root-peer-before-child", $peer);
        management($journey, "$root-edit", $parent, $who);
        peer_parent($journey, "$root-selected-before", $who);
        select_child($journey, "$root-selected-current", $who);
        profile($journey, "$root-profile", $minutes);
        leave($journey, "$root-edit");
        if ($surface eq 'overlay') {
            entry($journey, "$root-child", $roles{$who}, 1);
            $journey->seen("$root-before-countdown");
        }
        approval($journey, "$root-request", $who, $surface, $seconds, $soft);
        work($journey, "$root-work", qw(edit save saved submit submitted capture));
        if ($soft) {
            onpc_app_rows::game_usable_app($journey->scope("$root-game"), 'windowed');
            $journey->seen("$root-game-capture");
            $journey->seen("$root-game-$_") for $who eq 'jordan' ? qw(resume resumed progress) : ();
        } else {
            $journey->seen("$root-game-$_") for qw(closed denied);
        }
        $journey->seen("$root-hard-denied");
        choices($journey, "$root-choices", 1);
        leave($journey, "$root-child-done");
        management($journey, "$root-after", $parent, $peer);
        peer_parent($journey, "$root-peer-after", $peer);
        leave($journey, "$root-after");
        peer_work($journey, "$root-peer-after-child", $peer);
    }
    management($journey, 'daily-before', 'parent', 'jordan');
    peer_parent($journey, 'daily-jordan-before', 'jordan');
    select_child($journey, 'daily-riley', 'riley');
    profile($journey, 'daily-riley', 120);
    peer_parent($journey, 'daily-jordan-after', 'jordan');
    leave($journey, 'daily-parent');
    peer_work($journey, 'daily-jordan', 'jordan');
    entry($journey, 'daily-riley', 'child', 1);
    work($journey, 'daily-riley-work', qw(capture resubmit submitted));
    choices($journey, 'daily-riley-choices', 0);
    $journey->seen("daily-riley-$_") for qw(game-denied hard-denied);
    leave($journey, 'daily-riley');
    management($journey, 'revoke-parent', 'second-parent', 'riley');
    peer_parent($journey, 'revoke-riley-before', 'riley');
    select_child($journey, 'revoke-jordan', 'jordan');
    $journey->seen("revoke-jordan-$_") for qw(open warning confirm balance);
    peer_parent($journey, 'revoke-riley-after', 'riley');
    rows($journey, 'final-riley');
    select_child($journey, 'final-jordan', 'jordan');
    rows($journey, 'final-jordan');
    leave($journey, 'revoke-parent');
    entry($journey, 'revoked-jordan', 'other-child', 1, 'time-denied');
    onpc_gdm::return_from_time_denial($journey, map { "revoked-jordan-$_" }
        qw(denied-return-ready denied-return-state denied-returned));
    onpc_gdm::enter_station($journey->scope('final-station'), '');
    $journey->seen("final-$_-child"), $journey->seen("final-$_-choices") for qw(jordan riley);
    $journey->seen("final-station-$_") for qw(cancel returned);
    entry($journey, 'final-riley', 'child', 1);
    work($journey, 'final-riley-work', qw(capture resubmit submitted));
    $journey->seen("final-riley-$_") for qw(game-denied hard-denied);
    work($journey, 'final-riley-work', qw(close closed));
    $journey->seen('cleanup');
    $journey->finish();
}

1;
