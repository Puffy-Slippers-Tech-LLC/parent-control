package onpc_password;
use strict;
use warnings;
use onpc_progress ();
use testapi ();

# Only public testapi entry points. The controller pins this source and keeps
# ALL automatic backend screenshots/logs private. NOVIDEO is not a screenshot
# switch; this helper cannot prevent os-autoinst's automatic failure captures.
my %variables = (
    parent => '_SECRET_ONPC_PARENT_PASSWORD',
    child => '_SECRET_ONPC_CHILD_PASSWORD',
    'other-parent' => '_SECRET_ONPC_OTHER_PARENT_PASSWORD',
    'other-child' => '_SECRET_ONPC_OTHER_CHILD_PASSWORD',
);
my %prompts = (
    gdm => 'onpc-gdm',
    polkit => 'onpc-polkit',
    lock => 'onpc-lock',
);
my $failed = 0;
my $authentication_started = 0;
my $functional_started = 0;
my $functional_input_started = 0;

sub enter_parent_gdm_password {
    onpc_progress::operation('Qualifying the Parent password recipient');
    return _enter_functional_gdm_password('parent', @_);
}

sub enter_standard_gdm_password {
    onpc_progress::operation('Qualifying the standard-account password recipient');
    return _enter_functional_gdm_password('other-child', @_);
}

sub _enter_functional_gdm_password {
    my ($role, $journey) = @_;
    die "secret:input-refused\n" if $failed || $functional_started;
    $authentication_started = 1;
    $functional_started = 1;
    my $ok = eval {
        die "secret:arguments\n" unless @_ == 2 && ($role eq 'parent' || $role eq 'other-child')
            && ref($journey) eq 'onpc_journey'
            && !$journey->{review};
        die "secret:console\n" unless testapi::current_console() eq 'sut';
        die "secret:video-policy\n" unless testapi::get_var('NOVIDEO', 0) eq '1';
        # Each fixed controller checkpoint freshly requires the intended
        # identity and sole empty, masked, showing, enabled, focused field.
        # Wrong-recipient rejection is tested separately by harness qualification.
        # No input, action replay or capture occurs between these checks.
        my $prefix = $role eq 'parent' ? '' : 'standard-';
        my $proof;
        for my $stage ($prefix . 'recipient-qualified', $prefix . 'recipient-rechecked') {
            my $reply = $journey->seen($stage);
            die "secret:recipient\n" unless ref($reply) eq 'HASH' && keys(%$reply) == 1
                && defined($reply->{observed}) && $reply->{observed} eq $stage;
            $proof = $reply;
        }
        type_fixture_secret($role, $journey, $proof);
        1;
    };
    unless ($ok) {
        $failed = 1;
        die "secret:input-failed\n";
    }
    return 1;
}

# UI19: consume one explicit fresh recipient proof and type once. The GDM05
# caller owns its two checks; the controller owns their recipient/order
# qualification. This leaf neither submits nor infers authentication success.
sub type_fixture_secret {
    onpc_progress::operation('Entering the protected fixture credential');
    my ($role, $journey, $proof) = @_;
    die "secret:input-refused\n" if $failed || $functional_input_started;
    $authentication_started = 1;
    $functional_input_started = 1;
    my $ok = eval {
        die "secret:arguments\n" unless @_ == 3 && ($role eq 'parent' || $role eq 'other-child')
            && ref($journey) eq 'onpc_journey' && !$journey->{review};
        my $stage = ($role eq 'parent' ? '' : 'standard-') . 'recipient-rechecked';
        die "secret:recipient\n" unless ref($proof) eq 'HASH' && keys(%$proof) == 1
            && ($proof->{observed} // '') eq $stage;
        $journey->consume_observation($stage, $proof);
        die "secret:console\n" unless testapi::current_console() eq 'sut';
        die "secret:video-policy\n" unless testapi::get_var('NOVIDEO', 0) eq '1';
        my $password = testapi::get_required_var($variables{$role});
        die "secret:value\n" unless defined($password) && !ref($password)
            && $password =~ /\A[\x20-\x7e]{1,256}\z/;
        testapi::type_password($password);
        1;
    };
    unless ($ok) {
        $failed = 1;
        die "secret:input-failed\n";
    }
    return 1;
}

sub enter_password {
    onpc_progress::operation('Checking the password recipient before secret input');
    $authentication_started = 1;
    $failed = 1;
    die "secret:public-recipient-id-required\n";
}

sub capture_before_authentication {
    onpc_progress::operation('Capturing the unauthenticated screen');
    $failed = 1;
    die "secret:image-capture-refused\n";
}

sub seal_capture {
    $authentication_started = 1;
}

1;
