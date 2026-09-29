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
use onpc_format ();

# FEED10(app-exit): consume a fresh nonempty draft proof, close feedback,
# compose LIFE01, and compare the reopened draft before any field input.
sub app_exit {
    onpc_progress::operation('Reopening Parent and observing the empty feedback draft');
    my ($journey, $before, $invocation) = @_;
    $invocation //= '';
    die 'feedback-reset:arguments' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey'
        && $invocation =~ /\A(?:[a-z][a-z0-9-]*-)?\z/;
    my $closed = onpc_window::close($journey, 'feedback', $before, $invocation);
    $journey->consume_observation($invocation . 'feedback-draft-closed', $closed);
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

sub review_privacy {
    onpc_progress::operation('Reading Privacy and independently comparing the returned draft');
    my ($journey, $invocation) = @_;
    $invocation //= '';
    die 'feedback:arguments' unless (@_ == 1 || @_ == 2) && ref($journey) eq 'onpc_journey'
        && $invocation =~ /\A(?:[a-z][a-z0-9-]*-)?\z/;
    my $returned = onpc_window::close($journey, 'feedback-privacy',
        $journey->seen($invocation . 'feedback-privacy-open'), $invocation);
    $journey->consume_observation($invocation . 'feedback-privacy-returned', $returned);
    return $returned;
}

sub run {
    onpc_progress::operation('Reviewing local feedback through the declared composition');
    my ($exchange, $flow) = @_;
    die 'feedback:arguments' unless ref($exchange) eq 'CODE'
        && (@_ == 1 || @_ == 2 && defined($flow) && ($flow eq 'validation' || $flow eq 'draft' || $flow eq 'attachments' || $flow eq 'export'));
    return _diagnostic_export($exchange) if defined($flow) && $flow eq 'export';
    return _attachments($exchange) if defined($flow) && $flow eq 'attachments';
    return _validation($exchange) if defined($flow) && $flow eq 'validation';
    return _draft($exchange) if defined($flow) && $flow eq 'draft';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'feedback-privacy', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->consume_observation('feedback-close-refused', $journey->seen('feedback-close-refused'));
    $journey->consume_observation('feedback-open', $journey->seen('feedback-open'));
    onpc_text::replace_text($journey, $_) for ('body-first', 'reply-first');
    $journey->consume_observation('feedback-draft', $journey->seen('feedback-draft'));
    review_privacy($journey);
    preserve_dialog($journey, $journey->seen('feedback-draft-reread'));
    my $returned = onpc_window::close($journey, 'feedback-privacy-independent', $journey->seen('privacy-independent'));
    $journey->consume_observation('privacy-independent-returned', $returned);
    $journey->finish();
}

sub _draft {
    onpc_progress::operation('Reviewing a formatted one-file draft and its complete preservation and reset history');
    my ($exchange) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'feedback-draft', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    onpc_feedback_read::prepare_window_switch($journey);
    $journey->consume_observation('feedback-open', $journey->seen('feedback-open'));
    onpc_text::replace_text($journey, 'body-first');
    $journey->consume_observation('format-before', $journey->seen('format-before'));
    onpc_format::apply_bold($journey);
    onpc_text::append_scalar($journey, 'body-smoke');
    onpc_text::replace_text($journey, 'reply-first');
    onpc_feedback_read::supply_files($journey, 'draft-chooser');
    for my $stage ('feedback-draft', 'switch-draft-before') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_feedback_read::activate_existing_window($journey, $_) for ('switch-viewer', 'switch-feedback');
    review_privacy($journey);
    preserve_dialog($journey, $journey->seen('feedback-draft-reread'));
    app_exit($journey, $journey->seen('reset-feedback-draft-reread'), 'reset-');
    $journey->seen('feedback-reread');
    $journey->finish();
}

sub _attachments {
    onpc_progress::operation('Checking installed attachment handoff, Cancel and removal');
    my ($exchange) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'feedback-attachments', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->consume_observation('feedback-open', $journey->seen('feedback-open'));
    onpc_feedback_read::supply_files($journey, 'chooser');
    onpc_feedback_read::chooser_preservation($journey);
    $journey->consume_observation('attachment-details', $journey->seen('attachment-details'));
    onpc_feedback_read::attachment_removal($journey);
    $journey->finish();
}

sub _diagnostic_export {
    onpc_progress::operation('Checking diagnostic Save cancellation, failure, recovery and Privacy');
    my ($exchange) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'parent-diagnostic-export', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->consume_observation('collection', $journey->seen('collection'));
    onpc_text::replace_text($journey, $_) for ('body-first', 'reply-first');
    $journey->consume_observation('cancel-capture', $journey->seen('cancel-capture'));
    onpc_feedback_read::save_cancellation($journey, 'cancel');
    $journey->consume_observation('cancel-return', $journey->seen('cancel-return'));
    $journey->consume_observation('denied-capture', $journey->seen('denied-capture'));
    onpc_feedback_read::save_handoff($journey, 'denied');
    $journey->consume_observation('denied-return', $journey->seen('denied-return'));
    $journey->consume_observation('export-capture', $journey->seen('export-capture'));
    onpc_feedback_read::diagnostic_export($journey, 'export');
    $journey->consume_observation('privacy-capture', $journey->seen('privacy-capture'));
    review_privacy($journey);
    $journey->consume_observation('privacy-return', $journey->seen('privacy-return'));
    my $proof = $journey->seen('feedback-draft-reread');
    my $closed = onpc_window::close($journey, 'feedback', $proof);
    $journey->consume_observation('feedback-draft-closed', $closed);
    $journey->finish();
}

sub _validation {
    onpc_progress::operation('Checking installed empty-message rejection and editing recovery');
    my ($exchange) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'feedback-validation', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    onpc_feedback_states::rejection_observe($journey, $_) for ('feedback-open', 'feedback-state-empty');
    onpc_feedback_states::rejection_observe($journey, $_) for ('rejection-empty-send', 'rejection-empty-read');
    onpc_text::replace_text($journey, $_) for ('body-first', 'reply-first');
    onpc_feedback_states::rejection_observe($journey, $_) for (
        'recovery-close', 'recovery-reopen', 'review-valid', 'feedback-state-close');
    $journey->finish();
}
1;
