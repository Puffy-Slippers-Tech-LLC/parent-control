package onpc_feedback_states;
use strict;
use warnings;
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
1;
