package onpc_journey;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use JSON::PP ();
use Fcntl qw(O_WRONLY O_CREAT O_EXCL);

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
    my ($self, $tag, $timeout) = @_;
    return $self->{review} ? testapi::check_screen($tag, 5) : testapi::assert_screen($tag, $timeout);
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
    my ($self, $choice) = @_;
    my $keys = $choice->{ui_keys};
    die 'journey:choice-navigation' unless ref($keys) eq 'ARRAY' && @$keys >= 1
        && @$keys <= 32 && $keys->[0] eq 'home'
        && !grep { $_ ne 'down' } @$keys[1 .. $#$keys];
    testapi::send_key($_) for @$keys;
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
    my ($stage, $sequence) = @_;
    die 'journey:prompt-stage' unless defined($stage) && $stage =~ /\A[a-z][a-z0-9-]*\z/
        && defined($sequence) && $sequence =~ /\A[1-3]\z/;
    my $stem = "$stage.prompt-$sequence";
    return 0 unless -f "$stem.request.json";
    die 'journey:prompt-replay' if -e "$stem.reply.json" || -e "$stem.reply.tmp"
        || -e "$stem.input-started";
    die 'journey:prompt-request' if -l "$stem.request.json" || -s "$stem.request.json" > 1024;
    open(my $request, '<', "$stem.request.json") or die 'journey:prompt-request';
    my $value = do { local $/; JSON::PP::decode_json(<$request>) };
    close($request) or die 'journey:prompt-request-close';
    die 'journey:prompt-schema' unless ref($value) eq 'HASH' && keys(%$value) == 4
        && ($value->{stage} // '') eq $stage && ($value->{sequence} // 0) == $sequence
        && ($value->{kind} // '') eq 'login-keyring';
    # Reuse the same bounded public-coordinate pointer as customer controls.
    # An uncertain click throws before acknowledgement and is never repeated.
    sysopen(my $started, "$stem.input-started", O_WRONLY | O_CREAT | O_EXCL, 0600)
        or die 'journey:prompt-input-replay';
    close($started) or die 'journey:prompt-input-record';
    my $journey = __PACKAGE__->new(exchange => sub {}, prefix => 'system-prompt', review => 0);
    $journey->click_target($value);
    open(my $reply, '>', "$stem.reply.tmp") or die 'journey:prompt-reply';
    print {$reply} JSON::PP::encode_json({stage => $stage, sequence => $sequence,
        action => 'cancel-click', outcome => 'sent'});
    close($reply) or die 'journey:prompt-reply-close';
    rename("$stem.reply.tmp", "$stem.reply.json") or die 'journey:prompt-reply-publish';
    return 1;
}

sub click_target {
    onpc_progress::operation('Clicking the qualified public control');
    my ($self, $reply) = @_;
    die 'journey:pointer-console' unless testapi::current_console() eq 'sut';
    my $point = $reply->{ui_pointer};
    die 'journey:pointer-response' unless ref($point) eq 'HASH' && keys(%$point) == 2
        && defined($point->{x}) && defined($point->{y})
        && $point->{x} =~ /\A[0-9]+\z/ && $point->{y} =~ /\A[0-9]+\z/;
    my $console = testapi::console('sut');
    my ($width, $height) = ($console->mouse_width(), $console->mouse_height());
    die 'journey:pointer-bounds' unless defined($width) && defined($height)
        && $width > 0 && $height > 0 && $point->{x} < $width && $point->{y} < $height;
    # AT-SPI SCREEN and the console pointer both use current framebuffer
    # coordinates. No screenshot normalization or fixed resolution is involved.
    testapi::mouse_set($point->{x}, $point->{y});
    testapi::mouse_click('left');
}

1;
