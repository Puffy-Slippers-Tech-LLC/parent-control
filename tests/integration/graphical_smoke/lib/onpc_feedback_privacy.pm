package onpc_feedback_privacy;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();
use onpc_window ();

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
    onpc_progress::operation('Reading Privacy and preserving a synthetic draft; Send untouched');
    my ($exchange) = @_;
    die 'feedback:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
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
1;
