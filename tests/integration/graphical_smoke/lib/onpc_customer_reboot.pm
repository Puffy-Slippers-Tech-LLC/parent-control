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
    install_entry($journey);
    return_entry($journey);
    $journey->finish();
}

sub install_entry {
    onpc_progress::operation('Installing the verified release and requesting its declared activation reboot');
    my ($journey) = @_;
    die 'customer-reboot:entry-arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    $journey->seen('wrong-entry');
    onpc_parent::login_functional($journey);
    $journey->seen('command-context');
    $journey->seen('package-submitted');
    $journey->seen('package-result');
    $journey->seen('reboot-requested');
}

sub return_entry {
    onpc_progress::operation('Observing the new greeter and signing in after reboot');
    my ($journey) = @_;
    die 'customer-reboot:return-arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_gdm::sign_in_challenge($journey, 'after-reboot',
        'reboot-installed-greeter', 'reboot-parent-focused', 'reboot-desktop');
}

sub run_upgrade {
    onpc_progress::operation('Installing the authentic old release before the real upgrade');
    my ($exchange, $declared, $challenges) = @_;
    die 'package-upgrade:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && join('/', @$declared) eq
            'reboot-installed-greeter/reboot-parent-focused/reboot-recipient-qualified/reboot-recipient-rechecked/reboot-desktop'
        && ref($challenges) eq 'HASH' && keys(%$challenges) == 1
        && ref($challenges->{'after-reboot'}) eq 'ARRAY'
        && join('/', @{$challenges->{'after-reboot'}}) eq
            'parent/reboot-recipient-qualified/reboot-recipient-rechecked';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'package-upgrade', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_progress::operation('Installing the authentic old release and observing its activation reboot');
    install_entry($journey);
    return_entry($journey);
    onpc_progress::operation('Upgrading once and independently observing completion without another reboot');
    $journey->seen($_) for qw(upgrade-context upgrade-submitted upgrade-result upgrade-reread);
    $journey->finish();
}

1;
