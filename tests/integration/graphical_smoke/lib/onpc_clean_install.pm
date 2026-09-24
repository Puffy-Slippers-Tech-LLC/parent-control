package onpc_clean_install;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();
use onpc_request_exit ();

sub run {
    onpc_progress::operation('Installing and rebooting before first product use');
    my ($exchange, $declared, $challenges) = @_;
    die 'clean-install:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'clean-install', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_parent::login_functional($journey);
    for my $stage ('command-context', 'package-submitted', 'package-result', 'reboot-requested') {
        $journey->seen($stage);
    }
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'after-reboot',
        'reboot-installed-greeter', 'reboot-parent-focused', 'reboot-desktop');
    onpc_parent::launch($journey, $desktop, 'management', 'reboot-desktop');
    my $selected = onpc_parent::select_child($journey, 'child',
        $journey->seen('child-picker-opened'), 'child-picker-opened',
        'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    onpc_progress::operation('Reading fresh defaults and entering the request station');
    for my $stage ('apps-page', 'app-rows', 'switch-user', 'gdm-switched') {
        $journey->seen($stage);
    }
    onpc_request_exit::enter_station($journey, 'cancel');
    $journey->seen('cancel-action');
    $journey->seen('cancel-returned');
    $journey->finish();
}

1;
