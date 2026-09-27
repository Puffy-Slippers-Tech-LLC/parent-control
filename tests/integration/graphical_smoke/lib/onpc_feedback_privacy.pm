package onpc_feedback_privacy;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();
use onpc_window ();
use onpc_feedback_states ();
use onpc_feedback_read ();
use onpc_lifecycle ();

# FEED10(app-exit): consume a fresh nonempty draft proof, close feedback,
# compose LIFE01, and compare the reopened draft before any field input.
sub app_exit {
    onpc_progress::operation('Reopening Parent and observing the empty feedback draft');
    my ($journey, $before) = @_;
    die 'feedback-reset:arguments' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    my $closed = onpc_window::close($journey, 'feedback', $before);
    $journey->consume_observation('feedback-draft-closed', $closed);
    onpc_lifecycle::reopen($journey, 'parent', $journey->seen('prior-window'), 'management');
    $journey->seen('feedback-wrong-entry');
    return $journey->seen('feedback-reopen');
}

sub run_reset {
    onpc_progress::operation('Qualifying feedback draft reset after Parent exits');
    my ($exchange) = @_;
    die 'feedback-reset:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'feedback-reset', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->seen('feedback-close-refused');
    $journey->seen('feedback-open');
    onpc_text::replace_text($journey, $_) for ('body-first', 'reply-first');
    $journey->seen('feedback-draft');
    app_exit($journey, $journey->seen('feedback-draft-reread'));
    $journey->seen('feedback-reread');
    $journey->finish();
}

# FEED10(dialog): the supplied before proof and the reopen observation are
# compared by the controller before this composite returns or any new input.
sub preserve_dialog {
    onpc_progress::operation('Closing and reopening feedback to compare the supplied draft');
    my ($journey, $before) = @_;
    die 'feedback:arguments' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    my $closed = onpc_window::close($journey, 'feedback', $before);
    $journey->consume_observation('feedback-draft-closed', $closed);
    my $reopened = $journey->seen('feedback-draft-reopen');
    $journey->consume_observation('feedback-draft-reopen', $reopened);
    return $reopened;
}

sub run {
    onpc_progress::operation('Reviewing local feedback through the declared composition');
    my ($exchange, $flow) = @_;
    die 'feedback:arguments' unless ref($exchange) eq 'CODE'
        && (@_ == 1 || @_ == 2 && defined($flow) && $flow eq 'validation');
    return _validation($exchange) if defined($flow);
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'feedback-privacy', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->consume_observation('feedback-close-refused', $journey->seen('feedback-close-refused'));
    $journey->consume_observation('feedback-open', $journey->seen('feedback-open'));
    onpc_text::replace_text($journey, $_) for ('body-first', 'reply-first');
    $journey->consume_observation('feedback-draft', $journey->seen('feedback-draft'));
    my $returned = onpc_window::close($journey, 'feedback-privacy', $journey->seen('feedback-privacy-open'));
    $journey->consume_observation('feedback-privacy-returned', $returned);
    preserve_dialog($journey, $journey->seen('feedback-draft-reread'));
    $returned = onpc_window::close($journey, 'feedback-privacy-independent', $journey->seen('privacy-independent'));
    $journey->consume_observation('privacy-independent-returned', $returned);
    $journey->finish();
}

sub _validation {
    onpc_progress::operation('Checking the complete local feedback validation matrix without valid submission');
    my ($exchange) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'feedback-validation', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    onpc_feedback_states::rejection_observe($journey, $_) for ('switch-parent-before', 'switch-viewer-launch');
    onpc_feedback_read::activate_existing_window($journey, 'switch-parent');
    onpc_feedback_states::rejection_observe($journey, $_) for ('feedback-open', 'feedback-state-empty');
    onpc_feedback_states::edit_states($journey);
    onpc_text::replace_text($journey, 'reply-clear', 'length-reply-clear');
    for my $family ('ascii', 'mixed') {
        onpc_feedback_states::length_boundary($journey, $family);
        # Clear the previous public status through the qualified dialog route.
        onpc_feedback_states::rejection_observe($journey, $_) for (
            "length-$family-close", "length-$family-reopen");
    }
    onpc_text::replace_text($journey, 'body-clear');
    onpc_feedback_states::rejection_observe($journey, $_) for ('rejection-empty-send', 'rejection-empty-read');
    onpc_text::replace_text($journey, 'body-first', 'invalid-body-first');
    onpc_feedback_states::rejection_observe($journey, 'rejection-valid-refusal');
    onpc_text::replace_text($journey, 'reply-malformed', 'invalid-reply-malformed');
    onpc_feedback_states::rejection_observe($journey, $_) for ('rejection-malformed-send', 'rejection-malformed-read');
    onpc_text::replace_text($journey, 'reply-clear');
    onpc_feedback_states::input_hidden($journey);
    onpc_feedback_states::rejection_observe($journey, $_) for ('rejection-hidden-send', 'rejection-hidden-read');
    onpc_feedback_states::input_complex($journey);
    onpc_feedback_states::rejection_observe($journey, $_) for (
        'rejection-complex-send', 'rejection-complex-read',
        'rejection-close', 'rejection-wrong-entry', 'rejection-reopen',
        'rejection-reopened-send', 'rejection-reopened-read',
        'review-reset-close', 'review-reset-open');
    onpc_text::replace_text($journey, 'body-first', 'review-body-first');
    onpc_text::replace_text($journey, 'reply-first', 'review-reply-first');
    onpc_feedback_states::rejection_observe($journey, $_) for ('review-valid', 'switch-draft-before');
    onpc_feedback_read::activate_existing_window($journey, $_) for ('switch-viewer', 'switch-feedback');
    onpc_feedback_states::rejection_observe($journey, 'feedback-draft');
    my $returned = onpc_window::close($journey, 'feedback-privacy', $journey->seen('feedback-privacy-open'));
    $journey->consume_observation('feedback-privacy-returned', $returned);
    preserve_dialog($journey, $journey->seen('feedback-draft-reread'));
    $journey->finish();
}
1;
