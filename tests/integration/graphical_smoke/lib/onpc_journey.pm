package onpc_journey;
use strict;
use warnings;
use onpc_progress ();
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
    onpc_progress::operation('Waiting for the expected screen');
    die 'journey:image-observation-refused';
}

sub seen {
    my ($self, $stage) = @_;
    delete $self->{last_observation};
    testapi::record_info($self->{prefix} . '-' . $stage, $self->{review}
        ? 'Qualification observation; terminal matching remains required.'
        : 'Installed customer surface observed.');
    my $reply = $self->{exchange}->($stage, undef);
    $self->{last_observation} = {stage => $stage, reply => $reply};
    return $reply;
}

sub consume_observation {
    my ($self, $stage, $reply) = @_;
    my $last = delete $self->{last_observation};
    die 'journey:stale-observation' unless !$self->{review} && ref($last) eq 'HASH'
        && $last->{stage} eq $stage && ref($reply) eq 'HASH'
        && ref($last->{reply}) eq 'HASH' && $last->{reply} == $reply;
    return $reply;
}

sub navigate_choice {
    onpc_progress::operation('Navigating the public list order');
    die 'journey:positional-navigation-refused';
}

# UI14: an explicit fresh list reply drives navigation; its separate checkpoint
# must verify identity and focus before a caller may commit the selection.
sub highlight_choice {
    onpc_progress::operation('Highlighting the intended list choice');
    my ($self, $choice, $list_stage, $focused_stage) = @_;
    die 'journey:focus-stage' unless @_ == 4 && defined($focused_stage)
        && $focused_stage =~ /\A[a-z][a-z0-9-]*\z/;
    $self->consume_observation($list_stage, $choice);
    if ($choice->{ui_focused}) {
        die 'journey:choice-focus' if exists($choice->{ui_keys});
    } else {
        $self->navigate_choice($choice);
    }
    return $self->seen($focused_stage);
}

sub finish {
    onpc_progress::operation('Shutting down the test guest');
    my ($self) = @_;
    # No explicit captures after authentication. Automatic matcher results stay
    # private and are reconciled by the controller after shutdown.
    testapi::console('sut')->disable();
    testapi::power('off');
    die 'journey:shutdown-unverified' unless testapi::check_shutdown(0);
}

sub service_system_prompt {
    die 'journey:prompt-coordinate-route-refused';
}

sub click_target {
    onpc_progress::operation('Clicking the qualified public control');
    die 'journey:id-addressed-action-required';
}

1;
