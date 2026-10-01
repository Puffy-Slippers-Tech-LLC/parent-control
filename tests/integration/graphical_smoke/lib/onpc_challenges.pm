package onpc_challenges;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_journey ();
use onpc_gdm ();
use onpc_desktop_session ();
use onpc_parent ();
use onpc_request_flow ();

sub shell_panel {
    onpc_progress::operation('Qualifying direct and normal panel overlay entry');
    my ($exchange, $declared, $challenges) = @_;
    my @stages = qw(installed-greeter parent-focused recipient-qualified recipient-rechecked desktop
        fresh-installed-greeter fresh-child-focused fresh-child-recipient-qualified
        fresh-child-recipient-rechecked fresh-desktop direct-launch direct-form direct-cancel
        independent-desktop independent-launch independent-form independent-cancel
        panel-desktop panel-panel panel-launch panel-form singleton-reveal singleton-panel singleton-launch
        singleton-overview singleton-form panel-cancel closed-desktop);
    die 'shell-panel:plan' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 2
        && ref($challenges->{'parent-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'parent-login'}}) eq 'parent/recipient-qualified/recipient-rechecked'
        && ref($challenges->{'child-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'child-login'}}) eq
            'child/fresh-child-recipient-qualified/fresh-child-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'shell-panel', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen('allowance-configured');
    $journey->seen('wrong-account-refused');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    onpc_request_flow::overlay_entry($journey, 'direct', 'command');
    $journey->invoke('direct-cancel');
    $journey->invoke('independent-desktop');
    onpc_request_flow::overlay_entry($journey, 'independent', 'command');
    $journey->invoke('independent-cancel');
    $journey->invoke('panel-desktop');
    onpc_request_flow::overlay_entry($journey, 'panel', 'panel');
    onpc_request_flow::overlay_entry($journey, 'singleton', 'panel-reopen');
    $journey->invoke('panel-cancel');
    $journey->invoke('closed-desktop');
    $journey->finish();
}

sub countdown {
    onpc_progress::operation('Qualifying the child desktop countdown');
    my ($present, $exchange, $declared, $challenges) = @_;
    my @stages = qw(installed-greeter parent-focused recipient-qualified recipient-rechecked desktop
        fresh-installed-greeter fresh-child-focused fresh-child-recipient-qualified
        fresh-child-recipient-rechecked fresh-desktop countdown independent-countdown);
    die 'countdown:plan' unless @_ == 4 && ($present eq '0' || $present eq '1')
        && ref($exchange) eq 'CODE' && ref($declared) eq 'ARRAY'
        && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 2
        && ref($challenges->{'parent-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'parent-login'}}) eq 'parent/recipient-qualified/recipient-rechecked'
        && ref($challenges->{'child-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'child-login'}}) eq
            'child/fresh-child-recipient-qualified/fresh-child-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $present ? 'countdown-enabled' : 'countdown-off', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen('allowance-configured');
    $journey->seen('limits-disabled') unless $present;
    $journey->seen('wrong-account-refused');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    $journey->invoke('countdown');
    $journey->invoke('independent-countdown');
    $journey->finish();
}

sub fresh_child_allowed {
    onpc_progress::operation('Qualifying fresh child login with saved daily time');
    my $ok = eval { _fresh_child_allowed(@_); 1 };
    die "fresh-child:failed\n" unless $ok;
}

sub _fresh_child_allowed {
    return _fresh_child_entry('success', @_);
}

sub fresh_child_denied {
    onpc_progress::operation('Qualifying fresh child time denial and normal return');
    my $ok = eval { _fresh_child_entry('time-denied', @_); 1 };
    die "fresh-child:failed\n" unless $ok;
}

sub _fresh_child_entry {
    onpc_progress::operation('Qualifying fresh child login with saved daily time');
    my ($expected, $exchange, $declared, $challenges) = @_;
    die 'fresh-child:result' unless $expected eq 'success' || $expected eq 'time-denied';
    my $result_stage = $expected eq 'success' ? 'fresh-desktop' : 'fresh-denied';
    my @stages = qw(installed-greeter parent-focused recipient-qualified recipient-rechecked desktop
        wrong-list wrong-focused wrong-refused wrong-returned
        fresh-installed-greeter fresh-child-focused fresh-child-recipient-qualified
        fresh-child-recipient-rechecked);
    push @stages, $result_stage;
    push @stages, qw(denied-return-ready denied-returned) if $expected eq 'time-denied';
    die 'fresh-child:plan' unless @_ == 4 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 2
        && ref($challenges->{'parent-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'parent-login'}}) eq 'parent/recipient-qualified/recipient-rechecked'
        && ref($challenges->{'child-login'}) eq 'ARRAY'
        && join('/', @{$challenges->{'child-login'}}) eq
            'child/fresh-child-recipient-qualified/fresh-child-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange,
        prefix => $expected eq 'success' ? 'fresh-child-allowed' : 'fresh-child-denied', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child', $journey->seen('child-picker-opened'),
        'child-picker-opened', 'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen('allowance-configured');
    onpc_desktop_session::switch_user($journey, $journey->seen('repeat-desktop'), 'repeat-desktop');
    my $list = $journey->invoke('wrong-list');
    my $focus = $journey->highlight_choice($list, 'wrong-list', 'wrong-focused');
    $journey->consume_observation('wrong-focused', $focus);
    testapi::send_key('ret');
    my $refused = $journey->invoke('wrong-refused');
    $journey->consume_observation('wrong-refused', $refused);
    testapi::send_key('esc');
    $journey->invoke('wrong-returned');
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', $result_stage);
    onpc_gdm::return_from_time_denial($journey, 'denied-return-ready', 'denied-returned')
        if $expected eq 'time-denied';
    $journey->finish();
}

sub run {
    onpc_progress::operation('Qualifying distinct graphical authentication challenges');
    my ($exchange, $declared, $challenges) = @_;
    my @stages = qw(wrong-list wrong-focused wrong-refused wrong-returned
        installed-greeter parent-focused recipient-qualified recipient-rechecked desktop
        second-installed-greeter second-parent-focused second-recipient-qualified
        second-recipient-rechecked second-desktop);
    die 'challenges:plan' unless ref($declared) eq 'ARRAY'
        && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 2;
    for my $id ('first-login', 'second-login') {
        my $prefix = $id eq 'first-login' ? '' : 'second-';
        die 'challenges:plan' unless ref($challenges->{$id}) eq 'ARRAY'
            && join('/', @{$challenges->{$id}}) eq
                "parent/${prefix}recipient-qualified/${prefix}recipient-rechecked";
    }
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'challenges', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $list = $journey->invoke('wrong-list');
    my $focus = $journey->highlight_choice($list, 'wrong-list', 'wrong-focused');
    $journey->consume_observation('wrong-focused', $focus);
    testapi::send_key('ret');
    my $refusal = $journey->invoke('wrong-refused');
    $journey->consume_observation('wrong-refused', $refusal);
    testapi::send_key('esc');
    $journey->invoke('wrong-returned');
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'first-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_desktop_session::log_out($journey, $desktop);
    onpc_gdm::sign_in_challenge($journey, 'second-login',
        'second-installed-greeter', 'second-parent-focused', 'second-desktop');
    $journey->finish();
}

1;
