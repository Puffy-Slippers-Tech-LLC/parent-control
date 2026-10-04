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

sub run_chinese {
    onpc_progress::operation('Qualifying the continuous Chinese upgrade and first kiosk presentation');
    my ($exchange, $declared, $challenges) = @_;
    die 'chinese-kiosk:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && keys(%$challenges) == 4;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'chinese-kiosk', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    install_entry($journey);
    return_entry($journey);
    $journey->seen($_) for qw(upgrade-context language-setting language-parent-logout);
    chinese_desktop_renewal($journey, 'upgrade-', 'upgrade-parent');
    $journey->seen($_) for qw(upgrade-ready upgrade-submitted upgrade-result upgrade-reread upgrade-switch);
    chinese_initial_notice($journey);
    $journey->seen($_) for qw(second-reboot-requested second-reboot-greeter);
    chinese_initial_form($journey);
    $journey->finish();
}

sub chinese_desktop_renewal {
    onpc_progress::operation('Renewing the Chinese child desktop and returning to the administrator');
    my ($journey, $prefix, $challenge) = @_;
    die 'chinese-renewal:arguments' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && (($prefix eq 'upgrade-' && $challenge eq 'upgrade-parent')
            || ($prefix eq 'install-' && $challenge eq 'install-parent'));
    onpc_gdm::sign_in_challenge($journey, 'chinese-child',
        'language-installed-greeter', 'language-standard-focused', 'language-desktop');
    $journey->seen('language-child-logout');
    onpc_gdm::sign_in_challenge($journey, $challenge,
        $prefix . 'installed-greeter', $prefix . 'parent-focused', $prefix . 'desktop');
}

sub chinese_initial_notice {
    onpc_progress::operation('Reading the untouched Chinese restart notice and returning normally');
    my ($journey) = @_;
    die 'chinese-notice:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_gdm::enter_station($journey, 'initial-');
    $journey->seen($_) for qw(initial-notice initial-notice-close initial-notice-return);
    onpc_gdm::sign_in_challenge($journey, 'return-parent',
        'return-installed-greeter', 'return-parent-focused', 'return-desktop');
}

sub chinese_initial_form {
    onpc_progress::operation('Reading the untouched Chinese chooser and cancelling without saving');
    my ($journey) = @_;
    die 'chinese-form:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    onpc_gdm::enter_station($journey, 'renewed-');
    $journey->seen($_) for qw(initial-language initial-language-cancel initial-form);
}

sub run_chinese_current {
    onpc_progress::operation('Qualifying the latest installation and untouched Chinese first presentations');
    my ($exchange, $declared, $challenges) = @_;
    die 'chinese-current-install:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH'
        && keys(%$challenges) == 3;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'chinese-current-install', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    $journey->seen('wrong-entry');
    onpc_parent::login_functional($journey);
    $journey->seen($_) for qw(command-context language-setting language-parent-logout);
    chinese_desktop_renewal($journey, 'install-', 'install-parent');
    $journey->seen($_) for qw(install-ready package-submitted package-result package-reread install-switch);
    chinese_initial_notice($journey);
    $journey->seen($_) for qw(reboot-requested reboot-greeter);
    chinese_initial_form($journey);
    $journey->finish();
}

1;
