package onpc_journey;
use strict;
use warnings;
use testapi ();

sub new {
    my ($class, %args) = @_;
    die 'journey:arguments' unless keys(%args) == 3 && ref($args{exchange}) eq 'CODE'
        && defined($args{prefix}) && $args{prefix} =~ /\A[a-z][a-z0-9-]*\z/
        && defined($args{review}) && ($args{review} eq '0' || $args{review} eq '1');
    return bless \%args, $class;
}

# Only nonsecret app observations may use review acquisition. Input, password
# recipient, desktop and app-grid helpers always call their own strict matches.
# Review never awards acceptance: the controller still reconciles every match.
sub observe {
    my ($self, $tag, $timeout) = @_;
    return $self->{review} ? testapi::check_screen($tag, 5) : testapi::assert_screen($tag, $timeout);
}

sub seen {
    my ($self, $stage) = @_;
    testapi::record_info($self->{prefix} . '-' . $stage, $self->{review}
        ? 'Qualification observation; terminal matching remains required.'
        : 'Installed customer surface observed.');
    $self->{exchange}->($stage, undef);
}

sub finish {
    my ($self) = @_;
    # No explicit captures after authentication. Automatic matcher results stay
    # private and are reconciled by the controller after shutdown.
    testapi::console('sut')->disable();
    testapi::power('off');
    die 'journey:shutdown-unverified' unless testapi::check_shutdown(0);
}

1;
