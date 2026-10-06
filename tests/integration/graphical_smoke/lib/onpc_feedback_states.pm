package onpc_feedback_states;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();
use onpc_allowance_boundaries ();
use onpc_lifecycle ();
use onpc_allowance_selection ();

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
    return run_control_trace($exchange, 'accessibility-trace');
}

sub observed_collection {
    onpc_progress::operation('Waiting for finished diagnostics and available Download');
    my ($journey, $stage) = @_;
    die 'collection:arguments' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($stage) && $stage =~ /\A[a-z][a-z0-9-]*\z/;
    rejection_observe($journey, $stage);
}

sub run_collection {
    onpc_progress::operation('Qualifying collection and usable Download across independent entries');
    my ($exchange) = @_;
    die 'collection:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'feedback-collection', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('parent-selected',
        onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child'));
    for my $entry ('first', 'second') {
        rejection_observe($journey, "$entry-open");
        observed_collection($journey, "$entry-collection");
        rejection_observe($journey, "$entry-$_") for ('independent', 'refused', 'close');
    }
    $journey->finish();
}

sub run_parent_save_trace {
    onpc_progress::operation('Qualifying one Parent input and its settled saved result');
    my ($exchange) = @_;
    die 'trace:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    return run_control_trace($exchange, 'parent-save-trace');
}

sub custom_save_entry {
    onpc_progress::operation('Saving and independently reloading the named custom allowance');
    my ($journey, $entry, $child, $first, $last) = @_;
    die 'trace:custom-entry' unless @_ == 5 && ref($journey) eq 'onpc_journey'
        && $entry =~ /\A[a-z][a-z0-9-]*\z/ && ($child eq 'child' || $child eq 'existing')
        && $first eq '5' && $last eq '6';
    onpc_allowance_selection::select($journey, "$entry-choice", ['custom'], 'confirm');
    rejection_observe($journey, "$entry-$_") for ('open', 'focus', 'wrong-child', 'wrong-surface');
    onpc_text::observed_custom_edits($journey, "$entry-rapid", $first, $last, $child);
    rejection_observe($journey, "$entry-saved");
    onpc_allowance_boundaries::reload_child($journey, $entry);
    rejection_observe($journey, "$entry-reopened");
}

sub ordinary_custom_save {
    onpc_progress::operation('Selecting a child and saving the declared custom allowance');
    my ($journey, $entry, $value) = @_;
    die 'save:ordinary-custom' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && defined($entry) && $entry =~ /\A[a-z][a-z0-9-]*\z/
        && defined($value) && $value eq '7';
    onpc_allowance_boundaries::select_child($journey, $entry);
    rejection_observe($journey, "$entry-setup");
    onpc_allowance_selection::select($journey, "$entry-choice", ['custom'], 'confirm');
    rejection_observe($journey, "$entry-$_") for ('editor', 'wrong-child');
    onpc_text::replace_text($journey, "daily-$value", "$entry-text");
    rejection_observe($journey, "$entry-saved");
}

sub run_named_child_custom_saves {
    onpc_progress::operation('Qualifying independent named-child custom saves');
    my ($exchange) = @_;
    die 'trace:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'named-child-custom-saves', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'existing');
    $journey->consume_observation('parent-selected', $selected);
    rejection_observe($journey, $_) for ('disabled-refused', 'setup');
    custom_save_entry($journey, $_, 'existing', 5, 6) for ('first', 'second');
    ordinary_custom_save($journey, 'riley', 7);
    onpc_allowance_boundaries::select_child($journey, 'final-away');
    rejection_observe($journey, 'jordan-final');
    onpc_allowance_boundaries::select_child($journey, 'final-back');
    rejection_observe($journey, 'riley-final');
    $journey->finish();
}

sub run_save_order {
    onpc_progress::operation('Checking save order and both named child allowances');
    my ($exchange) = @_;
    die 'save-order:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'save-order', review => 0);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('parent-selected',
        onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'existing'));
    rejection_observe($journey, $_) for ('disabled-refused', 'setup');
    onpc_allowance_selection::select($journey, 'jordan-preset', [15], 'confirm');
    custom_save_entry($journey, 'jordan', 'existing', 5, 6);
    ordinary_custom_save($journey, 'riley', 7);
    onpc_allowance_boundaries::select_child($journey, 'final-away');
    rejection_observe($journey, 'jordan-final-read');
    onpc_allowance_boundaries::select_child($journey, 'final-back');
    rejection_observe($journey, 'riley-final');
    onpc_lifecycle::reopen($journey, 'parent', $journey->seen('prior-window'), 'management');
    onpc_allowance_boundaries::select_child($journey, 'reopen-jordan');
    rejection_observe($journey, 'jordan-after-restart');
    onpc_allowance_boundaries::select_child($journey, 'reopen-riley');
    rejection_observe($journey, 'riley-reopened');
    $journey->finish();
}

sub run_custom_save_trace {
    onpc_progress::operation('Qualifying rapid custom saving and independent reloaded results');
    my ($exchange) = @_;
    die 'trace:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'custom-save-trace', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    rejection_observe($journey, $_) for ('disabled-refused', 'enable', 'enabled');
    for my $entry ('first', 'second') {
        onpc_allowance_selection::select($journey, "$entry-preset", [15], 'confirm');
        custom_save_entry($journey, $entry, 'child', 5, 6);
    }
    $journey->finish();
}

sub run_control_trace {
    onpc_progress::operation('Running the declared Parent control trace sequence');
    my ($exchange, $prefix) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => $prefix, review => 0);
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
    rejection_observe($journey, 'rejection-hidden-caret');
    # One normal input-method sequence, never clipboard/DOM injection. Exact
    # public scalar readback must pass before the invalid-only action is offered.
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
