package onpc_text;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

my %values = (
    'body-first' => 'Synthetic feedback first',
    'body-second' => 'Synthetic feedback replacement', 'body-clear' => '',
    'reply-first' => 'first@example.invalid',
    'reply-second' => 'second@example.invalid', 'reply-clear' => '',
);

# UI16: every keyboard input consumes a new focused-recipient proof. An
# exception stops this composite; no input retry or repair is permitted.
sub replace_text {
    onpc_progress::operation('Replacing one declared synthetic feedback value');
    my ($journey, $binding) = @_;
    die 'text:binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($binding) && exists($values{$binding});
    if ($binding =~ /^reply-/) {
        # GTK's native entry has no Component.GrabFocus implementation. Use
        # the declared keyboard route, then independently prove reply focus.
        my $anchor = "text-$binding-anchor";
        $journey->consume_observation($anchor, $journey->seen($anchor));
        testapi::send_key('ctrl-tab');
    }
    my $stage = "text-$binding-focus";
    $journey->consume_observation($stage, $journey->seen($stage));
    testapi::send_key('ctrl-a');
    $stage = "text-$binding-selected";
    $journey->consume_observation($stage, $journey->seen($stage));
    if (length($values{$binding})) {
        testapi::type_string($values{$binding}, max_interval => 20);
    } else {
        testapi::send_key('backspace');
    }
    $stage = "text-$binding-read";
    my $result = $journey->seen($stage);
    $journey->consume_observation($stage, $result);
    return $result;
}

sub run {
    onpc_progress::operation('Qualifying synthetic text replacement without sending');
    my ($exchange) = @_;
    die 'text:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'text', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('text-disabled', 'text-wrong-entry', 'feedback-open') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    replace_text($journey, $_) for ('body-first', 'body-second', 'body-clear');
    for my $stage ('feedback-close', 'feedback-reopen') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    replace_text($journey, $_) for ('reply-first', 'reply-second', 'reply-clear');
    $journey->consume_observation('feedback-finished', $journey->seen('feedback-finished'));
    $journey->finish();
}
1;
