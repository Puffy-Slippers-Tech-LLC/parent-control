package onpc_feedback_read;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();
use onpc_window ();
use testapi ();

sub activate_existing_window {
    onpc_progress::operation('Activating an existing owned window');
    my ($journey, $stage, $invocation) = @_;
    $invocation //= '';
    die 'switch:binding' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey'
        && $stage =~ /^switch-(parent|viewer|feedback|viewer-again|feedback-again|viewer-close)$/
        && $invocation =~ /\A(?:[a-z][a-z0-9-]*-)?\z/;
    $stage = $invocation . $stage;
    $journey->consume_observation($stage . '-ready', $journey->seen($stage . '-ready'));
    testapi::send_key('alt-tab');
    $journey->consume_observation($stage, $journey->seen($stage));
}

sub prepare_window_switch {
    onpc_progress::operation('Preparing an observed secondary window and returning to Parent');
    my ($journey, $invocation) = @_;
    $invocation //= '';
    die 'switch:arguments' unless (@_ == 1 || @_ == 2) && ref($journey) eq 'onpc_journey'
        && $invocation =~ /\A(?:[a-z][a-z0-9-]*-)?\z/;
    for my $name ('switch-parent-before', 'switch-viewer-launch') {
        my $stage = $invocation . $name;
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    activate_existing_window($journey, 'switch-parent', $invocation);
}

sub run_window_switch {
    onpc_progress::operation('Returning to identified existing windows and comparing the synthetic draft');
    my ($exchange) = @_;
    die 'switch:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'window-switch', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    prepare_window_switch($journey);
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

# FILE03: the same guarded handoff for ordinary files and finite boundary sets.
# Callers own entry/refusal checks, independent result expectations and Cancel.
sub supply_files {
    onpc_progress::operation('Supplying a declared file set through the owned chooser');
    my ($journey, $prefix) = @_;
    die 'chooser:binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && $prefix =~ /^(chooser|draft-chooser|boundary-(count|sixth|maximum|oversized|total|overflow|name180|name181|hidden|mixed|single|changed))$/;
    for my $step ('open', 'location', 'files', 'accept') {
        my $stage = "$prefix-$step";
        $journey->consume_observation($stage, $journey->seen($stage));
        testapi::send_key('ctrl-l') if $step eq 'open';
        testapi::send_key('ret') if $step eq 'location';
    }
}

sub chooser_preservation {
    onpc_progress::operation('Checking accepted files and preservation after chooser Cancel');
    my ($journey, $invocation) = @_;
    $invocation //= '';
    die 'chooser:invocation' unless (@_ == 1 || @_ == 2) && ref($journey) eq 'onpc_journey'
        && $invocation =~ /\A(?:[a-z][a-z0-9-]*-)?\z/;
    for my $step ('attachments', 'reopen', 'cancel', 'preserved') {
        my $stage = $invocation . 'chooser-' . $step;
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

sub attachment_removal {
    onpc_progress::operation('Removing one declared attachment and independently reading the result');
    my ($journey, $invocation) = @_;
    $invocation //= '';
    die 'attachment:invocation' unless (@_ == 1 || @_ == 2) && ref($journey) eq 'onpc_journey'
        && $invocation =~ /\A(?:[a-z][a-z0-9-]*-)?\z/;
    for my $step ('remove', 'remaining') {
        my $stage = $invocation . 'attachment-' . $step;
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

sub boundary_batch {
    onpc_progress::operation('Checking a finite attachment boundary and independently preserved list');
    my ($journey, $batch) = @_;
    die 'attachment:batch' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && $batch =~ /^(count|sixth|maximum|oversized|total|overflow|name180|name181|hidden|mixed|single|changed)$/;
    my $prefix = "boundary-$batch";
    $journey->consume_observation("$prefix-before", $journey->seen("$prefix-before"));
    supply_files($journey, $prefix);
    for my $step ('result', 'preserved') {
        my $stage = "$prefix-$step";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

sub attachment_limits {
    onpc_progress::operation('Checking the full count and size attachment table');
    my ($journey) = @_;
    die 'attachment:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    attachment_removal($journey);
    $journey->consume_observation('boundary-clear-small', $journey->seen('boundary-clear-small'));
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

sub save_handoff {
    onpc_progress::operation('Saving to the declared destination and checking the public result');
    my ($journey, $entry) = @_;
    die 'save:binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($entry) && $entry =~ /\A[a-z][a-z0-9-]*\z/;
    for my $step ('open', 'name', 'location', 'navigated', 'destination', 'restored', 'accept', 'result') {
        my $stage = "$entry-$step";
        $journey->consume_observation($stage, $journey->seen($stage));
        testapi::send_key('ctrl-l') if $step eq 'name';
        testapi::send_key('ret') if $step eq 'location';
        testapi::send_key('ctrl-l') if $step eq 'navigated';
        testapi::send_key('esc') if $step eq 'destination';
    }
}

sub save_cancellation {
    onpc_progress::operation('Cancelling a fresh chooser and checking unchanged saved output');
    my ($journey, $entry) = @_;
    die 'save:binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($entry) && $entry =~ /\A[a-z][a-z0-9-]*\z/;
    for my $step ('reopen', 'cancel-name', 'cancel', 'preserved') {
        my $stage = "$entry-$step";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

sub diagnostic_export {
    onpc_progress::operation('Saving diagnostics, inspecting the exported ZIP and rereading the draft');
    my ($journey, $entry) = @_;
    save_handoff($journey, $entry);
    for my $step ('inspect', 'return') {
        my $stage = "$entry-$step";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

sub run_diagnostic_export {
    onpc_progress::operation('Qualifying two independent diagnostic export entries');
    my ($exchange) = @_;
    die 'export:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'diagnostic-export', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $entry ('first', 'second') {
        for my $step ('feedback', 'collection') {
            my $stage = "$entry-$step";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
        onpc_text::replace_text($journey, $_, "$entry-text-$_") for ('body-first', 'reply-first');
        for my $step ('capture', 'refused') {
            my $stage = "$entry-$step";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
        diagnostic_export($journey, $entry);
        my $proof = $journey->seen("$entry-feedback-draft-reread");
        my $closed = onpc_window::close($journey, 'feedback', $proof, "$entry-");
        $journey->consume_observation("$entry-feedback-draft-closed", $closed);
    }
    $journey->finish();
}

sub run_save_chooser {
    onpc_progress::operation('Qualifying two independent diagnostic Save entries');
    my ($exchange) = @_;
    die 'save:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'save-chooser', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $entry ('first', 'second') {
        for my $step ('feedback', 'collection', 'refused') {
            my $stage = "$entry-$step";
            $journey->consume_observation($stage, $journey->seen($stage));
        }
        save_handoff($journey, $entry);
        save_cancellation($journey, $entry);
        my $stage = "$entry-close";
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
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
    for my $stage ('feedback-open', ($items ? ('attachment-wrong-entry') : ()),
                   'chooser-wrong-entry') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    supply_files($journey, 'chooser');
    chooser_preservation($journey);
    if ($items) {
        for my $stage ('attachment-details', ($items >= 2
                ? ('attachment-preview', 'attachment-preview-return') : ())) {
            $journey->consume_observation($stage, $journey->seen($stage));
        }
        attachment_removal($journey) if $items == 1;
    }
    if ($items == 3) {
        attachment_limits($journey);
    }
    $journey->finish();
}

1;
