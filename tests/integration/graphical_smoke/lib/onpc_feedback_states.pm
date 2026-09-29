package onpc_feedback_states;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();

sub stable_trace {
    onpc_progress::operation('Starting and collecting unchanged public feedback samples');
    my ($journey, $entry) = @_;
    die 'trace:arguments' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && ($entry eq 'first' || $entry eq 'second');
    rejection_observe($journey, "trace-$entry-start");
    rejection_observe($journey, "trace-$entry-finish");
}

sub transition_trace {
    onpc_progress::operation('Tracing one caller-owned synthetic text change');
    my ($journey, $entry) = @_;
    die 'trace:arguments' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && ($entry eq 'first' || $entry eq 'second');
    observed_text($journey, $entry, 'body-first');
}

sub observed_text {
    onpc_progress::operation('Observing one explicitly declared caller text input');
    my ($journey, $entry, $binding) = @_;
    die 'trace:arguments' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && defined($entry) && $entry =~ /^[a-z][a-z0-9-]*$/
        && ($binding eq 'body-first' || $binding eq 'body-clear');
    rejection_observe($journey, "trace-$entry-start");
    onpc_text::replace_text($journey, $binding, $entry);
    rejection_observe($journey, "trace-$entry-finish");
}

sub observed_toggle {
    onpc_progress::operation('Observing one explicitly declared accessibility toggle');
    my ($journey, $stage) = @_;
    die 'trace:arguments' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($stage) && $stage =~ /^[a-z][a-z0-9-]*$/;
    rejection_observe($journey, $stage);
}

sub run_accessibility_trace {
    onpc_progress::operation('Qualifying checked-state events during synchronous accessibility input');
    my ($exchange) = @_;
    die 'trace:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'accessibility-trace', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $entry ('first', 'second') {
        rejection_observe($journey, "$entry-$_") for ('disabled', 'wrong-child', 'wrong-surface');
        observed_toggle($journey, "$entry-observed-enable");
        rejection_observe($journey, "$entry-independent-saved");
        rejection_observe($journey, 'restore-disabled') if $entry eq 'first';
    }
    $journey->finish();
}

sub run_composition {
    onpc_progress::operation('Qualifying valid-to-invalid feedback observation and independent readback');
    my ($exchange) = @_;
    die 'trace:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'compose-observation', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    rejection_observe($journey, 'feedback-open');
    for my $entry ('first', 'second') {
        onpc_text::replace_text($journey, 'body-first', "prepare-$entry");
        observed_text($journey, $entry, 'body-clear');
        rejection_observe($journey, "independent-$entry");
        rejection_observe($journey, $_) for ($entry eq 'first'
            ? ('trace-close', 'trace-wrong-entry', 'trace-open-again') : ());
    }
    $journey->finish();
}

sub run_transition {
    onpc_progress::operation('Qualifying public feedback observation during caller input');
    my ($exchange) = @_;
    die 'trace:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'trace-transition', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    rejection_observe($journey, 'feedback-open');
    transition_trace($journey, 'first');
    onpc_text::replace_text($journey, 'body-clear', 'clear');
    rejection_observe($journey, $_) for ('trace-close', 'trace-wrong-entry', 'trace-open-again');
    transition_trace($journey, 'second');
    $journey->finish();
}

sub run_trace {
    onpc_progress::operation('Qualifying unchanged feedback traces and independent entry');
    my ($exchange) = @_;
    die 'trace:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'trace-stable', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    rejection_observe($journey, 'feedback-open');
    stable_trace($journey, 'first');
    rejection_observe($journey, $_) for ('feedback-close', 'feedback-state-wrong-entry', 'feedback-open-again');
    stable_trace($journey, 'second');
    $journey->finish();
}

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
    edit_states($journey);
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

# FEED09 composition for an already open empty Parent feedback dialog.
sub edit_states {
    onpc_progress::operation('Editing feedback fields and independently reading each validation state');
    my ($journey) = @_;
    die 'feedback:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    for my $edit (['body-whitespace', 'feedback-state-whitespace'],
                  ['body-first', 'feedback-state-no-reply'],
                  ['reply-malformed', 'feedback-state-malformed'],
                  ['reply-first', 'feedback-state-valid']) {
        onpc_text::replace_text($journey, $edit->[0]);
        rejection_observe($journey, $edit->[1]);
    }
}

# UI16 + FEED09: retain the empty reply; leave the length rejection showing.
# Dialog reset and independent-entry checks belong to the caller's recipe.
sub length_boundary {
    onpc_progress::operation('Checking one UTF-16 family without submitting its valid draft');
    my ($journey, $family) = @_;
    die 'length:arguments' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($family) && ($family eq 'ascii' || $family eq 'mixed');
    for my $units (5000, 5001) {
        my $binding = "body-$family-$units";
        onpc_text::replace_text($journey, $binding . ($family eq 'mixed' ? '-base' : ''));
        onpc_text::append_scalar($journey, $binding) if $family eq 'mixed';
        rejection_observe($journey, $_) for ($units == 5000
            ? ("length-$family-valid", "length-$family-refusal")
            : ("rejection-$family-send", "rejection-$family-read"));
    }
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
        length_boundary($journey, $family);
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
