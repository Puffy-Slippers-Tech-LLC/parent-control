package onpc_customer_reboot;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();

sub run {
    onpc_progress::operation('Installing the product before the planned customer reboot');
    my ($exchange, $declared, $challenges) = @_;
    my @stages = qw(reboot-installed-greeter reboot-parent-focused
        reboot-recipient-qualified reboot-recipient-rechecked reboot-desktop);
    die 'customer-reboot:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq join('/', @stages)
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 1
        && ref($challenges->{'after-reboot'}) eq 'ARRAY'
        && join('/', @{$challenges->{'after-reboot'}}) eq
            'parent/reboot-recipient-qualified/reboot-recipient-rechecked';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'customer-reboot', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    $journey->seen('wrong-entry');
    onpc_parent::login_functional($journey);
    $journey->seen('command-context');
    $journey->seen('package-submitted');
    $journey->seen('package-result');
    $journey->seen('reboot-requested');
    onpc_progress::operation('Observing the new greeter and signing in after reboot');
    onpc_gdm::sign_in_challenge($journey, 'after-reboot',
        'reboot-installed-greeter', 'reboot-parent-focused', 'reboot-desktop');
    $journey->finish();
}

1;
