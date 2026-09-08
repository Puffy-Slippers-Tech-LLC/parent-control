package onpc_password;
use strict;
use warnings;
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

sub enter_password {
    my ($role, $surface) = @_;
    die "secret:input-refused\n" if $failed;
    # Latch before any operation that might capture an authentication screen.
    $authentication_started = 1;
    my $ok = eval {
        die "secret:arguments\n" unless @_ == 2 && defined($role) && defined($surface)
          && exists($variables{$role}) && exists($prompts{$surface});
        die "secret:video-policy\n" unless testapi::get_var('NOVIDEO', 0) eq '1';
        my $password = testapi::get_required_var($variables{$role});
        die "secret:value\n" unless defined($password) && !ref($password)
          && $password =~ /\A[\x20-\x7e]{1,256}\z/;
        # One maintained needle must establish the intended fixture identity
        # AND its empty, focused, masked field. A generic password-field match
        # could otherwise accept an unrelated account on this baseline.
        # Missing needles/timeouts fail before typing; no coordinate fallback.
        testapi::assert_screen($prompts{$surface} . '-' . $role . '-masked-password', 30)
          or die "secret:prompt\n";
        # No caller options: type_password permits overriding secret => 1.
        testapi::type_password($password);
        1;
    };
    unless ($ok) {
        $failed = 1;
        die "secret:input-failed\n";  # Never propagate raw API/credential errors.
    }
    # Do not submit, infer authentication success or collect a screen here.
    return 1;
}

sub capture_before_authentication {
    if ($failed || $authentication_started || @_) {
        $failed = 1;
        die "secret:capture-refused\n";
    }
    my $result;
    my $ok = eval {
        $result = testapi::save_screenshot();
        die "secret:capture\n" unless ref($result) eq 'HASH' && $result->{screenshot};
        1;
    };
    unless ($ok) {
        $failed = 1;
        die "secret:capture-failed\n";
    }
    return $result;
}

1;
