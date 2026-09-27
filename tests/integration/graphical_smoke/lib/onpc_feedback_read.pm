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

sub chooser_handoff {
    onpc_progress::operation('Supplying the exact prepared files and observing feedback');
    my ($journey, $items) = @_;
    die 'chooser:binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && ($items == 0 || $items == 1 || $items == 2 || $items == 3);
    for my $stage ('feedback-open', 'chooser-wrong-entry', 'chooser-open',
                   'chooser-location', 'chooser-files',
                   'chooser-accept', 'chooser-attachments', 'chooser-reopen',
                   'chooser-cancel', 'chooser-preserved') {
        $journey->consume_observation($stage, $journey->seen($stage));
        if ($items && $stage eq 'feedback-open') {
            $journey->consume_observation('attachment-wrong-entry', $journey->seen('attachment-wrong-entry'));
        }
        if ($stage eq 'chooser-open') {
            testapi::send_key('ctrl-l');
        } elsif ($stage eq 'chooser-location') {
            testapi::send_key('ret');
        }
    }
    if ($items) {
        for my $stage ('attachment-details', ($items >= 2
                ? ('attachment-preview', 'attachment-preview-return')
                : ('attachment-remove', 'attachment-remaining'))) {
            $journey->consume_observation($stage, $journey->seen($stage));
        }
    }
}

sub boundary_batch {
    onpc_progress::operation('Checking a finite attachment boundary and independently preserved list');
    my ($journey, $batch) = @_;
    die 'attachment:batch' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && $batch =~ /^(count|sixth|maximum|oversized|total|overflow)$/;
    for my $step ('before', 'open', 'location', 'files', 'accept', 'result', 'preserved') {
        my $stage = "boundary-$batch-$step";
        $journey->consume_observation($stage, $journey->seen($stage));
        testapi::send_key('ctrl-l') if $step eq 'open';
        testapi::send_key('ret') if $step eq 'location';
    }
}

sub run_file_chooser {
    onpc_progress::operation('Selecting synthetic feedback files and checking public attachment results');
    my ($exchange, $items) = @_;
    die 'chooser:arguments' unless (@_ == 1 || (@_ == 2 && ($items == 1 || $items == 2 || $items == 3)))
        && ref($exchange) eq 'CODE';
    $items ||= 0;
    my @prefixes = ('file-chooser', 'attachment-items', 'attachment-preview', 'attachment-boundaries');
    my $journey = onpc_journey->new(exchange => $exchange, prefix => $prefixes[$items], review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    chooser_handoff($journey, $items);
    if ($items == 3) {
        for my $stage ('attachment-remove', 'attachment-remaining', 'boundary-clear-small') {
            $journey->consume_observation($stage, $journey->seen($stage));
        }
        boundary_batch($journey, 'count');
        boundary_batch($journey, 'sixth');
        for my $stage ('boundary-clear-count', 'boundary-exclude-logs') {
            $journey->consume_observation($stage, $journey->seen($stage));
        }
        boundary_batch($journey, 'maximum');
        boundary_batch($journey, 'oversized');
        boundary_batch($journey, 'total');
        my $stage = 'boundary-remove-total';
        $journey->consume_observation($stage, $journey->seen($stage));
        boundary_batch($journey, 'overflow');
    }
    $journey->finish();
}

1;
