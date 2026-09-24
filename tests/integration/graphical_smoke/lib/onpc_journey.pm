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
    die 'journey:previous-failure' if $self->{invocation_failed};
    delete $self->{last_observation};
    testapi::record_info($self->{prefix} . '-' . $stage, $self->{review}
        ? 'Qualification observation; terminal matching remains required.'
        : 'Installed customer surface observed.');
    my $reply = $self->{exchange}->($stage, undef);
    $self->{last_observation} = {stage => $stage, reply => $reply};
    return $reply;
}

# Opt-in finite public-operation invocations. Legacy authentication continues
# through its existing challenge helpers; repeated operations cannot recycle
# either a stage's reply file or another invocation's result.
sub declare_invocations {
    my ($self, $stages) = @_;
    die 'journey:invocation-plan' if exists($self->{invocations});
    die 'journey:invocation-plan' unless ref($stages) eq 'ARRAY' && @$stages;
    my %unique;
    for my $stage (@$stages) {
        die 'journey:invocation-plan' unless defined($stage)
            && $stage =~ /\A[a-z][a-z0-9-]*\z/ && !$unique{$stage}++;
    }
    $self->{invocations} = [@$stages];
    $self->{invocation_index} = 0;
}

sub invoke {
    my ($self, $stage) = @_;
    die 'journey:previous-failure' if $self->{invocation_failed};
    my $reply;
    my $ok = eval {
        my $index = $self->{invocation_index};
        die 'journey:invocation-order' unless ref($self->{invocations}) eq 'ARRAY'
            && defined($index) && $index < @{$self->{invocations}}
            && defined($stage) && $stage eq $self->{invocations}[$index];
        $reply = $self->seen($stage);
        die 'journey:invocation-reply' unless ref($reply) eq 'HASH'
            && defined($reply->{observed}) && $reply->{observed} eq $stage;
        $self->{invocation_index}++;
        1;
    };
    unless ($ok) {
        $self->{invocation_failed} = 1;
        delete $self->{last_observation};
        die $@;
    }
    return $reply;
}

sub consume_observation {
    my ($self, $stage, $reply) = @_;
    die 'journey:previous-failure' if $self->{invocation_failed};
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
    onpc_progress::operation('Restoring the test guest to its off baseline');
    my ($self) = @_;
    die 'journey:previous-failure' if $self->{invocation_failed};
    if (exists($self->{invocations})
            && $self->{invocation_index} != @{$self->{invocations}}) {
        $self->{invocation_failed} = 1;
        die 'journey:missing-invocations';
    }
    # No explicit captures after authentication. Automatic matcher results stay
    # private and are reconciled by the controller after the off-state restore.
    testapi::console('sut')->disable();
    testapi::power('off');
    die 'journey:shutdown-unverified' unless testapi::check_shutdown(0);
    testapi::record_info('shutdown',
        'Owned guest off-state restoration and verification completed.');
}

sub service_system_prompt {
    die 'journey:prompt-coordinate-route-refused';
}

sub click_target {
    onpc_progress::operation('Clicking the qualified public control');
    die 'journey:id-addressed-action-required';
}

1;
