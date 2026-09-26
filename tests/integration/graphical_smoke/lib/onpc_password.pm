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
my %challenges_used;
my $active_challenge;

# Explicit UI19/GDM05 binding for subsequent authentications. A used identity
# is never cleared, and any uncertainty poisons every later secret route.
sub enter_gdm_challenge {
    onpc_progress::operation('Qualifying and consuming the declared password challenge');
    my ($journey, $id) = @_;
    die "secret:input-refused\n" if $failed;
    my $ok = eval {
        die 'secret:challenge' unless @_ == 2 && ref($journey) eq 'onpc_journey'
            && !$journey->{review} && defined($id) && !$challenges_used{$id}
            && ref($journey->{challenges}) eq 'HASH'
            && ref($journey->{challenges}{$id}) eq 'ARRAY';
        $challenges_used{$id} = 1;
        # The compatibility route has no explicit identity and may never be
        # used to obtain another authentication after an explicit challenge.
        $functional_started = 1;
        $functional_input_started = 1;
        my ($role, $first, $second) = @{$journey->{challenges}{$id}};
        $authentication_started = 1;
        die 'secret:console' unless testapi::current_console() eq 'sut';
        die 'secret:video-policy' unless testapi::get_var('NOVIDEO', 0) eq '1';
        my $proof;
        for my $entry ([$first, 'qualified'], [$second, 'rechecked']) {
            my ($stage, $check) = @$entry;
            $proof = $journey->invoke($stage);
            my $context = $proof->{challenge};
            die 'secret:recipient' unless keys(%$proof) == 2
                && ref($context) eq 'HASH' && keys(%$context) == 4
                && ($context->{id} // '') eq $id && ($context->{role} // '') eq $role
                && ($context->{surface} // '') eq 'gdm' && ($context->{check} // '') eq $check;
        }
        $active_challenge = {journey => $journey, id => $id, role => $role,
                             stage => $second, proof => $proof};
        type_fixture_secret($role, $journey, $proof, $id);
        1;
    };
    unless ($ok) {
        $failed = 1;
        undef $active_challenge;
        die "secret:input-failed\n";
    }
    return 1;
}

sub enter_parent_gdm_password {
    onpc_progress::operation('Qualifying the Parent password recipient');
    return _enter_functional_gdm_password('parent', @_);
}

# Fixed MATE binding: controller checks opaque same-challenge identity and the
# exact administrator/child/request at both durable checkpoints. Any failure
# poisons all subsequent secret routes, including uncertain type_password.
sub enter_kiosk_mate_password {
    onpc_progress::operation('Qualifying the kiosk approval password recipient');
    my ($journey, $wrong) = @_;
    die "secret:input-refused\n" if $failed;
    my $ok = eval {
        my $reject = @_ == 2 && defined($wrong) && $wrong eq 'wrong';
        my $binding = $reject ? 'rejection' : 'approval';
        my $id = 'kiosk-mate-' . $binding;
        die 'secret:challenge' unless (@_ == 1 || $reject) && ref($journey) eq 'onpc_journey'
            && ($journey->{prefix} // '') eq 'kiosk-' . $binding
            && !$journey->{review} && !$challenges_used{$id};
        $challenges_used{$id} = 1;
        $authentication_started = 1;
        $functional_started = 1;
        $functional_input_started = 1;
        die 'secret:console' unless testapi::current_console() eq 'sut';
        die 'secret:video-policy' unless testapi::get_var('NOVIDEO', 0) eq '1';
        my $proof;
        for my $stage ($binding . '-qualified', $binding . '-rechecked') {
            $proof = $journey->seen($stage);
            die 'secret:recipient' unless ref($proof) eq 'HASH' && keys(%$proof) == 1
                && ($proof->{observed} // '') eq $stage;
        }
        $active_challenge = {journey => $journey, id => $id, role => 'parent',
                             stage => $binding . '-rechecked', proof => $proof, wrong => $reject};
        type_fixture_secret('parent', $journey, $proof, $id);
        1;
    };
    unless ($ok) {
        $failed = 1;
        undef $active_challenge;
        die "secret:input-failed\n";
    }
    return 1;
}

sub enter_standard_gdm_password {
    onpc_progress::operation('Qualifying the standard-account password recipient');
    return _enter_functional_gdm_password('other-child', @_);
}

sub _enter_functional_gdm_password {
    my ($role, $journey) = @_;
    if ($failed || $functional_started) {
        $failed = 1;
        die "secret:input-refused\n";
    }
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
    my ($role, $journey, $proof, $challenge) = @_;
    if ($failed || (!defined($challenge) && $functional_input_started)) {
        $failed = 1;
        die "secret:input-refused\n";
    }
    $authentication_started = 1;
    $functional_input_started = 1 unless defined($challenge);
    my $ok = eval {
        die "secret:arguments\n" unless (@_ == 3 || @_ == 4) && ($role eq 'parent' || $role eq 'other-child')
            && ref($journey) eq 'onpc_journey' && !$journey->{review};
        my $stage;
        my $wrong = 0;
        if (defined($challenge)) {
            my $active = $active_challenge;
            undef $active_challenge; # Consume before accessing the secret API.
            die 'secret:challenge' unless ref($active) eq 'HASH'
                && $active->{journey} == $journey && $active->{id} eq $challenge
                && $active->{role} eq $role && ref($proof) eq 'HASH'
                && $active->{proof} == $proof;
            $stage = $active->{stage};
            $wrong = $active->{wrong} // 0;
        } else {
            $stage = ($role eq 'parent' ? '' : 'standard-') . 'recipient-rechecked';
            die "secret:recipient\n" unless ref($proof) eq 'HASH' && keys(%$proof) == 1
                && ($proof->{observed} // '') eq $stage;
        }
        $journey->consume_observation($stage, $proof);
        die "secret:console\n" unless testapi::current_console() eq 'sut';
        die "secret:video-policy\n" unless testapi::get_var('NOVIDEO', 0) eq '1';
        my $password = testapi::get_required_var($variables{$role});
        die "secret:value\n" unless defined($password) && !ref($password)
            && $password =~ /\A[\x20-\x7e]{1,256}\z/;
        # Fixed public negative fixture, guaranteed different from the frozen
        # credential; no derived secret bytes enter diagnostics or evidence.
        if ($wrong) {
            $password = $password eq 'onpc-wrong-fixture-password'
                ? 'onpc-other-wrong-fixture-password' : 'onpc-wrong-fixture-password';
        }
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
