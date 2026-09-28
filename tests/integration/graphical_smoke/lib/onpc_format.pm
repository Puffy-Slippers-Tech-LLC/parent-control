package onpc_format;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();

sub apply_bold {
    onpc_progress::operation('Formatting the declared synthetic range and reading public text attributes');
    my ($journey) = @_;
    die 'format:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('format-focus', $journey->seen('format-focus'));
    testapi::send_key('ctrl-home');
    $journey->consume_observation('format-home', $journey->seen('format-home'));
    testapi::send_key('shift-right') for 1 .. 9;
    for my $stage ('format-selected', 'format-read') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

sub apply_block {
    onpc_progress::operation('Applying a declared feedback block and reading its public meaning');
    my ($journey, $kind) = @_;
    my %ranges = ('heading-1' => [0, 14], 'heading-2' => [15, 32],
        ordered => [33, 46], bulleted => [47, 60], quote => [61, 73], code => [74, 85]);
    die 'blocks:arguments' unless @_ == 2 && ref($journey) eq 'onpc_journey' && exists $ranges{$kind};
    my $prefix = "block-$kind";
    $journey->consume_observation("$prefix-focus", $journey->seen("$prefix-focus"));
    testapi::send_key('ctrl-home');
    $journey->consume_observation("$prefix-home", $journey->seen("$prefix-home"));
    my ($start, $end) = @{$ranges{$kind}};
    testapi::send_key('right') for 1 .. $start;
    testapi::send_key('shift-right') for 1 .. ($end - $start);
    $journey->consume_observation("$prefix-selected", $journey->seen("$prefix-selected"));
    $journey->consume_observation("$prefix-read", $journey->seen("$prefix-read"));
}

sub apply_inline {
    onpc_progress::operation('Applying a bounded inline format or removing all formatting');
    my ($journey, $kind, $namespace) = @_;
    $namespace //= 'formats';
    die 'formats:arguments' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey'
        && ($namespace eq 'formats' || $namespace eq 'linked')
        && grep { $_ eq $kind } ('bold', 'italic', 'underline', 'strike', 'link', 'clear');
    my $prefix = "$namespace-$kind";
    $journey->consume_observation("$prefix-focus", $journey->seen("$prefix-focus"));
    testapi::send_key('ctrl-home');
    $journey->consume_observation("$prefix-home", $journey->seen("$prefix-home"));
    if ($kind eq 'clear') {
        testapi::send_key('ctrl-shift-end');
    } else {
        testapi::send_key('ctrl-end');
        testapi::send_key('left') for 1 .. 12;
        testapi::send_key('shift-right') for 1 .. 5;
    }
    $journey->consume_observation("$prefix-selected", $journey->seen("$prefix-selected"));
    if ($kind eq 'link') {
        $journey->consume_observation("$namespace-link-target", $journey->seen("$namespace-link-target"));
        testapi::type_string('https://example.com/feedback');
        $journey->consume_observation("$namespace-link-save", $journey->seen("$namespace-link-save"));
    }
    $journey->consume_observation("$prefix-read", $journey->seen("$prefix-read"));
}

sub apply_all {
    onpc_progress::operation('Composing every declared feedback format through shared operations');
    my ($journey) = @_;
    die 'formats:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    apply_block($journey, $_) for ('heading-1', 'heading-2', 'ordered', 'bulleted', 'quote', 'code');
    apply_inline($journey, $_) for ('bold', 'italic', 'underline', 'strike', 'link');
}

sub run_formats {
    onpc_progress::operation('Qualifying complete feedback formatting and removal without sending');
    my ($exchange) = @_;
    die 'formats:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'formats', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->consume_observation('feedback-open', $journey->seen('feedback-open'));
    onpc_text::replace_text($journey, 'body-blocks');
    $journey->consume_observation('formats-before', $journey->seen('formats-before'));
    apply_all($journey);
    for my $stage ('formats-kept-close', 'formats-kept-wrong-entry', 'formats-kept-reopen') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    apply_inline($journey, 'clear');
    for my $stage ('formats-cleared-close', 'formats-cleared-wrong-entry', 'formats-cleared-reopen') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}

sub run_links {
    onpc_progress::operation('Qualifying linked inline meaning without sending or navigating');
    my ($exchange) = @_;
    die 'linked:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'linked', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->consume_observation('feedback-open', $journey->seen('feedback-open'));
    onpc_text::replace_text($journey, 'body-blocks');
    $journey->consume_observation('linked-before', $journey->seen('linked-before'));
    apply_inline($journey, $_, 'linked') for ('bold', 'italic', 'underline', 'strike', 'link');
    for my $stage ('linked-kept-close', 'linked-kept-wrong-entry', 'linked-kept-reopen') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}

sub run_blocks {
    onpc_progress::operation('Qualifying independent feedback block observations without sending');
    my ($exchange) = @_;
    die 'blocks:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'blocks', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->consume_observation('feedback-open', $journey->seen('feedback-open'));
    onpc_text::replace_text($journey, 'body-blocks');
    $journey->consume_observation('block-before', $journey->seen('block-before'));
    apply_block($journey, $_) for ('heading-1', 'heading-2', 'ordered', 'bulleted', 'quote', 'code');
    for my $stage ('block-close', 'block-wrong-entry', 'block-reopen') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}

sub run {
    onpc_progress::operation('Qualifying feedback formatting without sending');
    my ($exchange) = @_;
    die 'format:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'format', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->consume_observation('feedback-open', $journey->seen('feedback-open'));
    onpc_text::replace_text($journey, 'body-first');
    $journey->consume_observation('format-before', $journey->seen('format-before'));
    apply_bold($journey);
    for my $stage ('format-close', 'format-wrong-entry', 'format-reopen') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
