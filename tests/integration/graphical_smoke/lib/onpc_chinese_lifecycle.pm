package onpc_chinese_lifecycle;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_customer_reboot ();
use onpc_request_flow ();

sub run {
    onpc_progress::operation('Testing the latest Chinese installation and two fresh native approvals');
    my ($exchange, $invocations, $challenges) = @_;
    die 'chinese-lifecycle:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'chinese-lifecycle', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    onpc_customer_reboot::chinese_current_entry($journey);
    $journey->seen($_) for qw(setup-cancel setup-returned);
    onpc_gdm::sign_in_challenge($journey, 'setup-parent',
        'setup-installed-greeter', 'setup-parent-focused', 'setup-desktop');
    onpc_parent::named_management($journey, 'setup-manage', 'existing');
    $journey->seen($_) for qw(other-enabled other-saved policy-before setup-logout);
    onpc_gdm::enter_station($journey, '');
    $journey->seen($_) for qw(other-first-parent first-language first-checked first-close);
    onpc_request_flow::prepare_chinese($journey, 'first');
    onpc_request_flow::approve_chinese($journey, 'first');
    $journey->seen('first-returned');
    onpc_gdm::sign_in_challenge($journey, 'first-policy-parent',
        'first-policy-installed-greeter', 'first-policy-parent-focused', 'first-policy-desktop');
    onpc_parent::named_management($journey, 'first-manage', 'existing');
    $journey->seen($_) for qw(first-policy first-logout);
    onpc_gdm::enter_station($journey, 'cancel-');
    $journey->seen($_) for qw(second-language second-checked second-close);
    onpc_request_flow::prepare_chinese($journey, 'second');
    onpc_request_flow::approve_chinese($journey, 'second');
    $journey->seen('second-returned');
    onpc_gdm::sign_in_challenge($journey, 'second-policy-parent',
        'second-policy-installed-greeter', 'second-policy-parent-focused', 'second-policy-desktop');
    onpc_parent::named_management($journey, 'second-manage', 'existing');
    $journey->seen('second-policy');
    $journey->finish();
}

1;
