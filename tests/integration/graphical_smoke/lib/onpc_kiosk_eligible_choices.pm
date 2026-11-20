package onpc_kiosk_eligible_choices;
use strict;
use warnings;
use onpc_progress ();
use onpc_desktop_session ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying eligible request station account choices');
    my ($exchange, $engineering, $invocations, $challenges) = @_;
    die 'kiosk-choices:arguments' unless (@_ == 1 || defined($engineering) && (
        @_ == 2 && $engineering == 2 || @_ == 4 && $engineering == 1
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH'))
        && ref($exchange) eq 'CODE';
    my $feedback = $engineering && $engineering == 1;
    my $journey = onpc_journey->new(
        exchange => $exchange,
        prefix => $feedback ? 'kiosk-feedback-confinement' : 'kiosk-eligible-choices', review => 0);
    if ($feedback) {
        $journey->declare_invocations($invocations);
        $journey->declare_challenges($challenges);
    }
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    my @allowance = $feedback ? qw(allowance-15-select allowance-15-read time-explanation-read) : ();
    for my $stage ('wrong-entry', 'limit-enabled', 'save-enabled', @allowance,
                   'switch-user', 'gdm-switched') {
        my $result = $journey->seen($stage);
        $journey->consume_observation($stage, $result);
    }
    if ($feedback) {
        my $desktop = onpc_desktop_session::enter_desktop($journey, 'gdm', 'child',
            'fresh', 'success', 'fixture-child');
        $journey->consume_observation('fixture-child-desktop', $desktop);
        $journey->seen($_) for qw(child-countdown child-switch child-greeter);
    }
    onpc_gdm::enter_station($journey, '');
    for my $stage ('request-form', 'wrong-choices', 'child-selected',
                   'approver-selected', 'selections-read') {
        my $result = $journey->seen($stage);
        $journey->consume_observation($stage, $result);
    }
    if ($feedback) {
        for my $stage ('kiosk-diagnostic-error', 'kiosk-diagnostic-report', 'kiosk-diagnostic-editor',
                      'kiosk-diagnostic-privacy') {
            my $result = $journey->seen($stage);
            $journey->consume_observation($stage, $result);
        }
    }
    if ($engineering && $engineering == 2) {
        for my $stage ('kiosk-reminder-preview', 'kiosk-reminder-preview-cancel') {
            my $result = $journey->seen($stage);
            $journey->consume_observation($stage, $result);
        }
    }
    $journey->finish();
}

1;
