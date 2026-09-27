package onpc_feedback_states;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();

sub run {
    onpc_progress::operation('Reading feedback validation and Send availability without sending');
    my ($exchange) = @_;
    die 'feedback:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'feedback-states', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('feedback-open', 'feedback-state-empty') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    for my $edit (['body-whitespace', 'feedback-state-whitespace'],
                  ['body-first', 'feedback-state-no-reply'],
                  ['reply-malformed', 'feedback-state-malformed'],
                  ['reply-first', 'feedback-state-valid']) {
        onpc_text::replace_text($journey, $edit->[0]);
        $journey->consume_observation($edit->[1], $journey->seen($edit->[1]));
    }
    for my $stage ('feedback-state-close', 'feedback-state-wrong-entry', 'feedback-state-reopen') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
sub rejection_observe {
    onpc_progress::operation('Observing the declared invalid-only feedback boundary');
    my ($journey, $stage) = @_;
    $journey->consume_observation($stage, $journey->seen($stage));
}

sub run_rejection {
    onpc_progress::operation('Qualifying invalid-only feedback rejection through public editing');
    my ($exchange) = @_;
    die 'rejection:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'feedback-rejection', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    rejection_observe($journey, $_) for ('feedback-open', 'rejection-empty-send', 'rejection-empty-read');
    onpc_text::replace_text($journey, 'body-first');
    rejection_observe($journey, 'rejection-valid-refusal');
    onpc_text::replace_text($journey, 'reply-malformed');
    rejection_observe($journey, $_) for ('rejection-malformed-send', 'rejection-malformed-read');
    onpc_text::replace_text($journey, 'reply-clear');
    input_hidden($journey);
    rejection_observe($journey, $_) for ('rejection-hidden-send', 'rejection-hidden-read');
    input_complex($journey);
    rejection_observe($journey, $_) for ('rejection-complex-send', 'rejection-complex-read',
        'rejection-close', 'rejection-wrong-entry', 'rejection-reopen',
        'rejection-reopened-send', 'rejection-reopened-read');
    $journey->finish();
}

sub input_hidden {
    onpc_progress::operation('Entering and independently reading the fixed hidden character');
    my ($journey) = @_;
    onpc_text::replace_text($journey, 'body-hidden-base');
    rejection_observe($journey, 'rejection-hidden-focus');
    testapi::send_key('ctrl-home');
    testapi::send_key('right');
    rejection_observe($journey, 'rejection-hidden-caret');
    # One normal input-method sequence, never clipboard/DOM injection. Exact
    # public scalar readback must pass before the invalid-only action is offered.
    testapi::send_key('ctrl-shift-u');
    testapi::type_string('0001');
    testapi::send_key('ret');
    rejection_observe($journey, 'rejection-hidden-input-read');
}

sub input_complex {
    onpc_progress::operation('Building and formatting the fixed excessive formatting document');
    my ($journey) = @_;
    onpc_text::replace_text($journey, 'body-complex-75');
    onpc_text::duplicate_text($journey, $_) for (
        'body-complex-150', 'body-complex-300', 'body-complex-600', 'body-complex');
    for my $kind ('bold', 'italic', 'underline', 'strike') {
        rejection_observe($journey, "rejection-format-$kind-focus");
        testapi::send_key('ctrl-a');
        rejection_observe($journey, "rejection-format-$kind-apply");
    }
}

sub run_length {
    onpc_progress::operation('Qualifying ASCII and emoji UTF-16 boundaries with invalid-only Send');
    my ($exchange) = @_;
    die 'length:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'feedback-length', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    rejection_observe($journey, 'feedback-open');
    for my $family ('ascii', 'mixed') {
        for my $units (5000, 5001) {
            my $binding = "body-$family-$units";
            onpc_text::replace_text($journey, $binding . ($family eq 'mixed' ? '-base' : ''));
            onpc_text::append_scalar($journey, $binding) if $family eq 'mixed';
            if ($units == 5000) {
                rejection_observe($journey, $_) for ("length-$family-valid", "length-$family-refusal");
            } else {
                rejection_observe($journey, $_) for ("rejection-$family-send", "rejection-$family-read");
            }
        }
        rejection_observe($journey, $_) for (
            "length-$family-close", "length-$family-wrong-entry", "length-$family-reopen",
            "rejection-$family-reopened-send", "rejection-$family-reopened-read");
        # Validation occurs on Send. Start the next family's edit-only checks
        # in a fresh dialog rather than inheriting the prior rejection status.
        if ($family eq 'ascii') {
            rejection_observe($journey, $_) for ('length-ascii-reset-close', 'length-ascii-reset-open');
        }
    }
    $journey->finish();
}
1;
