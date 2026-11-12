package onpc_homework_game;
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
use onpc_lifecycle ();
use onpc_progress ();

sub entry {
    my ($journey, $prefix, $account, $retained, $expected) = @_;
    onpc_desktop_session::enter_desktop($journey, 'gdm', $account,
        $retained ? 'retained' : 'fresh', $expected // 'success', $prefix);
}

sub leave {
    my ($journey, $prefix) = @_;
    $journey->seen("$prefix-$_") for qw(leave switch gdm);
}

sub parent_return {
    my ($journey, $prefix) = @_;
    entry($journey, $prefix, 'parent', 1);
    $journey->seen("$prefix-retained");
}

sub work {
    my ($journey, $prefix, @actions) = @_;
    $journey->seen("$prefix-$_") for @actions;
}

sub countdown {
    my ($journey, $stage) = @_;
    $journey->seen("$stage-panel") if $stage =~ /\Acycle-2-/;
    $journey->seen($stage);
    $journey->seen("$stage-game") if $stage =~ /\Acycle-2-/;
}

sub approval {
    my ($journey, $prefix, $surface, $parent, $seconds, $soft) = @_;
    my $request = $journey->scope($prefix);
    my $binding = ['other-child', $parent, $seconds, $soft];
    my $approver = $parent eq 'parent' ? 'fixture-parent' : 'other-fixture-parent';
    if ($surface eq 'overlay') {
        $request->{overlay_request} = $binding;
        onpc_request_flow::overlay_entry($request, 'request', 'panel');
        $request->seen('remembered');
        onpc_request_flow::prepare($request, 'new', 'open', 'observed',
            'existing-fixture-child', $approver, $seconds, $soft, 'overlay');
        onpc_request_flow::overlay_approve($request, 'automatic');
    } else {
        $request->{kiosk_request} = $binding;
        onpc_gdm::enter_station($request, 'cancel-');
        $request->seen($_) for qw(remembered-child remembered);
        onpc_request_flow::prepare($request, 'new', 'open', 'observed',
            'existing-fixture-child', $approver, $seconds, $soft, 'kiosk');
        onpc_request_flow::approve($request, 'existing-fixture-child', $approver, $seconds, $soft, 'automatic');
        my $retained = !$journey->{fresh_departure} || $prefix =~ /-recovery\z/;
        entry($journey, "$prefix-" . ($retained ? 'retained' : 'fresh'), 'other-child', $retained);
    }
    countdown($journey, "$prefix-countdown");
}

sub riley_visit {
    my ($journey, $prefix) = @_;
    entry($journey, $prefix, 'child', 1);
    work($journey, "$prefix-work", qw(capture resubmit submitted));
}

sub run {
    onpc_progress::operation('Keeping Jordan’s homework while parents alternate game time');
    my ($exchange, $declared, $challenges, $fresh) = @_;
    die 'homework-game:arguments' unless @_ == 4 && defined($fresh) && ($fresh == 0 || $fresh == 1);
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'homework-game', review => 0);
    $journey->{fresh_departure} = $fresh;
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('parent-selected',
        onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'existing'));
    $journey->seen($_) for qw(initial-balance initial-settings apps-page);
    my $apps = [['A', 'match-precise', 'allowed'], ['H', 'match-hard-precise', 'permanent'],
                ['Game', 'match-game-precise', 'conditional']];
    for my $index (0 .. $#$apps) {
        my ($role, $draft, $access) = @{$apps->[$index]};
        onpc_app_rows::edit_policy($journey, onpc_app_rows::fixture_app($role),
            $draft, $access, 'policy-' . $index, [], 1);
    }
    onpc_text::replace_text($journey, 'catalogue-clear', 'clear');
    onpc_app_rows::saved_rows($journey, $apps, 'saved');
    leave($journey, 'setup');
    entry($journey, 'riley-initial', 'child', 0);
    work($journey, 'riley-work', qw(open opened edit save saved submit submitted capture));
    leave($journey, 'riley-initial');
    for my $cycle (1, 2) {
        my $root = "cycle-$cycle";
        my $mode = $cycle == 1 ? 'windowed' : 'fullscreen';
        my ($first, $second) = $cycle == 1 ? ('parent', 'other-parent') : ('other-parent', 'parent');
        parent_return($journey, "$root-daily-parent");
        onpc_allowance_selection::select($journey, "$root-daily", [60 * $cycle], 'confirm');
        $journey->seen("$root-$_") for qw(daily-settings daily-balance);
        leave($journey, "$root-daily-parent");
        entry($journey, "$root-entry", 'other-child', $cycle == 2 && !$fresh);
        work($journey, "$root-reopened", qw(open opened submit submitted capture)) if $fresh && $cycle == 2;
        work($journey, "$root-homework", ($cycle == 1 ? qw(open opened) : ()),
             qw(edit save saved submit submitted capture));
        $journey->seen("$root-$_") for qw(daily-game-denied daily-hard-denied);
        countdown($journey, "$root-earn-before");
        approval($journey, "$root-earn", 'overlay', $first, 60, 1);
        onpc_app_rows::game_usable_app($journey->scope("$root-first-game"), $mode);
        $journey->seen("$root-first-game-capture");
        work($journey, "$root-earned-work", 'capture');
        countdown($journey, "$root-more-before");
        leave($journey, "$root-more");
        parent_return($journey, "$root-more-balance-parent");
        $journey->seen("$root-more-balance");
        leave($journey, "$root-more-balance-parent");
        approval($journey, "$root-more", 'kiosk', $second, 30, 1);
        if ($fresh) {
            work($journey, "$root-more-reopened", qw(open opened submit submitted capture));
            onpc_app_rows::game_usable_app($journey->scope("$root-more-new-game"), $mode);
            $journey->seen("$root-more-new-game-capture");
        } else {
            $journey->seen("$root-$_") for qw(more-game more-move more-played);
        }
        work($journey, "$root-more-work", 'capture');
        $journey->seen("$root-more-hard-denied");
        countdown($journey, "$root-home-before");
        approval($journey, "$root-home", 'overlay', $first, 30, 0);
        $journey->seen("$root-$_") for qw(home-closed home-denied);
        work($journey, "$root-again", qw(edit save saved submit submitted capture));
        countdown($journey, "$root-break-before");
        leave($journey, "$root-break");
        parent_return($journey, "$root-break-balance-parent");
        $journey->seen("$root-break-balance");
        leave($journey, "$root-break-balance-parent");
        approval($journey, "$root-break", 'kiosk', $second, 30, 1);
        work($journey, "$root-break-reopened", qw(open opened submit submitted capture)) if $fresh;
        onpc_app_rows::game_usable_app($journey->scope("$root-break-game"), $mode);
        $journey->seen("$root-break-game-capture");
        for my $name ('positive', 'zero') {
            my $prefix = "$root-$name";
            leave($journey, $prefix);
            parent_return($journey, "$prefix-parent");
            $journey->seen("$root-original-grant") if $name eq 'positive';
            if ($name eq 'positive') {
                $journey->seen("$prefix-daily-open");
                onpc_text::replace_text($journey, 'daily-' . (60 * $cycle + 1), "$prefix-daily-text");
                $journey->seen("$prefix-daily-saved");
            } else {
                onpc_allowance_selection::select($journey, "$prefix-daily", [0], 'confirm');
            }
            $journey->seen("$prefix-$_") for qw(settings balance);
            leave($journey, "$prefix-parent");
            entry($journey, "$prefix-child", 'other-child', !$fresh);
            if ($fresh) {
                work($journey, "$prefix-reopened", qw(open opened submit submitted capture));
                $journey->seen("$prefix-$_") for qw(denied hard);
            } else {
                $journey->seen("$prefix-$_") for qw(game denied original hard);
            }
            work($journey, "$prefix-work", qw(capture resubmit submitted));
        }
        leave($journey, "$root-off");
        parent_return($journey, "$root-off-parent");
        $journey->seen("$root-$_") for qw(off-toggle off-settings);
        leave($journey, "$root-off-parent");
        entry($journey, "$root-off-child", 'other-child', !$fresh);
        work($journey, "$root-off-reopened", qw(open opened submit submitted capture)) if $fresh;
        countdown($journey, "$root-off-countdown");
        $journey->seen("$root-$_") for qw(off-hard off-game-denied);
        unless ($fresh) {
            $journey->seen("$root-$_") for qw(off-game-close off-game-closed);
        }
        leave($journey, "$root-on");
        parent_return($journey, "$root-on-parent");
        $journey->seen("$root-$_") for qw(on-toggle on-settings on-balance);
        leave($journey, "$root-on-parent");
        entry($journey, "$root-denied", 'other-child', !$fresh, 'time-denied');
        onpc_gdm::return_from_time_denial($journey, map { "$root-entry-$_" }
            qw(denied-return-ready denied-return-state denied-returned));
        approval($journey, "$root-visit", 'kiosk', $first, 600, $cycle == 1 ? 1 : 0);
        work($journey, "$root-visit-reopened", qw(open opened submit submitted capture)) if $fresh;
        work($journey, "$root-visit-work", qw(capture resubmit submitted));
        if ($cycle == 1) {
            onpc_app_rows::game_usable_app($journey->scope("$root-visit-game"), $mode);
            $journey->seen("$root-visit-game-capture");
        } else {
            $journey->seen("$root-visit-game-denied");
        }
        $journey->invoke("$root-natural-expiry");
        onpc_desktop_session::verify_locked_input($journey, "$root-lock-input-ready", "$root-lock-result");
        my $locked = $journey->scope($root);
        $locked->consume_observation('time-denied',
            onpc_desktop_session::reveal_lock($locked, 'time-denied'));
        $journey->seen("$root-$_") for qw(return-greeter denied-returned);
        approval($journey, "$root-recovery", 'kiosk', $second, 1200, $cycle == 2 ? 1 : 0);
        work($journey, "$root-recovered-work", qw(capture resubmit submitted));
        if ($cycle == 1) {
            $journey->seen("$root-$_") for qw(recovery-closed recovery-game-denied);
        } else {
            onpc_app_rows::game_usable_app($journey->scope("$root-recovery-game"), $mode);
            $journey->seen("$root-recovery-game-capture");
        }
        $journey->seen("$root-recovery-hard");
        work($journey, "$root-final-work", 'capture');
        leave($journey, "$root-revoke");
        parent_return($journey, "$root-revoke-parent");
        $journey->seen("$root-$_") for qw(revoke-open revoke-warning revoke-confirm revoked-settings revoked-balance);
        leave($journey, "$root-revoke-parent");
        entry($journey, "$root-revoked", 'other-child', !$fresh, 'time-denied');
        onpc_gdm::return_from_time_denial($journey, map { "$root-revoked-$_" }
            qw(denied-return-ready denied-return-state denied-returned));
        riley_visit($journey, "$root-riley");
        leave($journey, "$root-riley");
    }
    parent_return($journey, 'final-parent');
    my $reopen = $journey->scope('reopen');
    onpc_lifecycle::reopen($reopen, 'parent', $reopen->seen('prior-window'), 'management');
    my $final = $journey->scope('final');
    onpc_parent::select_child($final, 'existing', $final->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->seen($_) for qw(final-settings final-balance final-apps);
    onpc_app_rows::saved_rows($journey, $apps, 'final');
    leave($journey, 'final-parent');
    riley_visit($journey, 'final-riley');
    $journey->seen('cleanup');
    $journey->finish();
}

1;
