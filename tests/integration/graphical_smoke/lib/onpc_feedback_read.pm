package onpc_feedback_read;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();
use testapi ();

sub activate_existing_window {
    onpc_progress::operation('Activating an existing owned window');
    my ($journey, $stage) = @_;
    die 'switch:binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && $stage =~ /^switch-(parent|viewer|feedback|viewer-again|feedback-again|viewer-close)$/;
    $journey->consume_observation($stage . '-ready', $journey->seen($stage . '-ready'));
    testapi::send_key('alt-tab');
    $journey->consume_observation($stage, $journey->seen($stage));
}

sub run_window_switch {
    onpc_progress::operation('Returning to identified existing windows and comparing the synthetic draft');
    my ($exchange) = @_;
    die 'switch:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'window-switch', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('switch-parent-before', 'switch-viewer-launch') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    activate_existing_window($journey, 'switch-parent');
    $journey->consume_observation('feedback-open', $journey->seen('feedback-open'));
    onpc_text::replace_text($journey, 'body-first');
    onpc_text::replace_text($journey, 'reply-first');
    $journey->consume_observation('switch-draft-before', $journey->seen('switch-draft-before'));
    for my $stage ('switch-viewer', 'switch-feedback',
                   'switch-viewer-again', 'switch-feedback-again', 'switch-viewer-close') {
        activate_existing_window($journey, $stage);
    }
    testapi::send_key('alt-f4');
    $journey->consume_observation('switch-viewer-absent', $journey->seen('switch-viewer-absent'));
    $journey->finish();
}

sub run {
    onpc_progress::operation('Qualifying read-only Parent feedback');
    my ($exchange) = @_;
    die 'feedback-read:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'feedback-read', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('feedback-open', 'feedback-read', 'feedback-close',
                   'feedback-wrong-entry', 'feedback-reopen', 'feedback-reread',
                   'feedback-finished') {
        my $result = $journey->seen($stage);
        $journey->consume_observation($stage, $result);
    }
    $journey->finish();
}

1;
