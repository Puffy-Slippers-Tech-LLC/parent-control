package onpc_text;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

my %values = (
    'catalogue-name' => 'ONPC Allowed Fixture',
    'catalogue-description' => 'Exact native catalogue fixture',
    'catalogue-identifier' => 'com.puffyslippers.ONPCTest.A.desktop',
    'catalogue-absent' => 'ONPC Absent Catalogue Fixture 077b', 'catalogue-clear' => '',
    'body-ascii-5000' => 'x' x 5000,
    'body-ascii-5001' => 'x' x 5001,
    'body-mixed-5000-base' => 'x' x 4998,
    'body-mixed-5001-base' => 'x' x 4999,
    'kiosk-fraction' => '1.25',
    'kiosk-invalid-empty' => '', 'kiosk-invalid-letters' => 'abc',
    'kiosk-invalid-negative' => '-1', 'kiosk-invalid-zero' => '0',
    'kiosk-invalid-below' => '0.09', 'kiosk-invalid-over' => '1440.1',
    'kiosk-invalid-comma' => '1,5',
    'body-first' => 'Synthetic feedback first',
    'body-blocks' => "Heading sample\nSubheading sample\nNumber sample\nBullet sample\nQuote sample\nCode sample\nPlain sample",
    'body-second' => 'Synthetic feedback replacement', 'body-clear' => '',
    'body-whitespace' => '   ',
    'body-hidden-base' => 'ab',
    'body-complex' => join("\n", ('x') x 1200),
    'body-complex-75' => join("\n", ('x') x 75),
    'reply-first' => 'first@example.invalid',
    'reply-second' => 'second@example.invalid', 'reply-clear' => '',
    'reply-malformed' => 'invalid-reply',
    'daily-1' => '1', 'daily-2' => '2', 'daily-3' => '3', 'daily-7' => '7',
    'daily-0' => '0', 'daily-15' => '15', 'daily-1439' => '1439',
    'daily-invalid-empty' => '', 'daily-invalid-letters' => 'abc',
    'daily-invalid-negative' => '-1', 'daily-invalid-fraction' => '0.5',
    'daily-invalid-maximum' => '1440', 'daily-invalid-over' => '1441',
);
my %repetitions;
for my $binding ('body-ascii-5000', 'body-ascii-5001',
                 'body-mixed-5000-base', 'body-mixed-5001-base') {
    my @chain = ("$binding-seed", map { "$binding-double-$_" } 1..4);
    $values{$chain[0]} = substr($values{$binding}, 0, int(length($values{$binding}) / 16));
    $repetitions{$binding} = \@chain;
}

# UI16: every keyboard batch consumes a new focused-recipient proof. An
# exception stops this composite; no input retry or repair is permitted.
sub replace_text {
    onpc_progress::operation('Replacing one declared nonsecret field value');
    my ($journey, $binding, $prefix) = @_;
    die 'text:binding' unless (@_ == 2 || @_ == 3) && ref($journey) eq 'onpc_journey'
        && defined($binding) && exists($values{$binding});
    $prefix //= "text-$binding";
    die 'text:prefix' unless $prefix =~ /\A[a-z][a-z0-9-]*\z/;
    if (exists($repetitions{$binding})) {
        die 'text:repeat-prefix' unless $prefix eq "text-$binding";
        return repeat_text($journey, $binding);
    }
    if ($binding =~ /^reply-/) {
        # GTK's native entry has no Component.GrabFocus implementation. Use
        # the declared keyboard route, then independently prove reply focus.
        my $anchor = "$prefix-anchor";
        $journey->consume_observation($anchor, $journey->seen($anchor));
        testapi::send_key('ctrl-tab');
    }
    my $stage = "$prefix-focus";
    $journey->consume_observation($stage, $journey->seen($stage));
    testapi::send_key('ctrl-a');
    $stage = "$prefix-selected";
    $journey->consume_observation($stage, $journey->seen($stage));
    if (length($values{$binding})) {
        # A declared custom commit is part of this single bounded keyboard
        # batch. An intervening controller round trip would let debounce save
        # and disable the editor before Return/Tab can reach it. os-autoinst
        # maps newline and tab to ordinary Return and Tab key events.
        my $suffix = $binding eq 'daily-2' ? "\n" : $binding eq 'daily-3' ? "\t" : '';
        testapi::type_string($values{$binding} . $suffix,
            max_interval => $binding eq 'body-complex-75' ? 250 : 20);
    } else {
        testapi::send_key('backspace');
    }
    $stage = "$prefix-read";
    my $result = $journey->seen($stage);
    $journey->consume_observation($stage, $result);
    return $result;
}

# The same finite seed/doubling/remainder recipe as the public adapter. Never
# fall back to full typing after an uncertain or mismatching clipboard result.
sub observed_custom_edits {
    onpc_progress::operation('Typing two declared custom allowances while observing saves');
    my ($journey, $stage, $first, $last, $child) = @_;
    $child //= 'child';
    die 'text:rapid-binding' unless (@_ == 4 || @_ == 5) && ref($journey) eq 'onpc_journey'
        && $stage =~ /\A[a-z][a-z0-9-]*\z/ && $first eq '5' && $last eq '6'
        && ($child eq 'child' || $child eq 'existing');
    my $used = 0;
    my $result = $journey->seen($stage, sub {
        my ($proof) = @_;
        die 'text:rapid-proof' unless !$used && $proof->{binding} eq 'custom-rapid'
            && defined($proof->{child}) && $proof->{child} eq $child
            && ref($proof->{values}) eq 'ARRAY' && @{$proof->{values}} == 2
            && $proof->{values}[0] == $first && $proof->{values}[1] == $last;
        $used = 1;
        # Focus/owner/child proof is fresh and the recorder is already armed.
        # One bounded keyboard batch, with no settled-save round trip between
        # the two commits. Return starts the first save before the next edit.
        testapi::send_key('ctrl-a');
        testapi::type_string($first . "\n", max_interval => 20);
        testapi::send_key('ctrl-a');
        testapi::type_string($last . "\n", max_interval => 20);
    });
    die 'text:rapid-missing' unless $used;
    return $journey->consume_observation($stage, $result);
}

sub repeat_text {
    onpc_progress::operation('Building synthetic text with a short seed and clipboard doubles');
    my ($journey, $binding) = @_;
    die 'text:repeat-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($binding) && exists($repetitions{$binding});
    my ($seed, @copies) = @{$repetitions{$binding}};
    replace_text($journey, $seed);
    duplicate_text($journey, $_) for @copies;
    onpc_progress::operation('Finishing clipboard-built text with its short typed remainder');
    my $prefix = "text-suffix-$binding";
    $journey->consume_observation("$prefix-focus", $journey->seen("$prefix-focus"));
    testapi::send_key('ctrl-end');
    $journey->consume_observation("$prefix-caret", $journey->seen("$prefix-caret"));
    my $suffix = substr($values{$binding}, length($values{$seed}) * 16);
    testapi::type_string($suffix, max_interval => 20) if length($suffix);
    my $result = $journey->seen("$prefix-read");
    $journey->consume_observation("$prefix-read", $result);
    return $result;
}

# Shared UI16 composite: exact synthetic source -> public selection -> one
# copy/append/plain-text paste batch -> exact doubled result. No input retries.
sub duplicate_text {
    onpc_progress::operation('Doubling synthetic text with one ordinary copy and paste');
    my ($journey, $binding) = @_;
    die 'text:duplicate-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($binding) && ($binding =~ /\Abody-complex(?:-(?:150|300|600))?\z/
            || $binding =~ /\Abody-(?:ascii-500[01]|mixed-500[01]-base)-double-[1-4]\z/);
    my $prefix = "text-duplicate-$binding";
    $journey->consume_observation("$prefix-focus", $journey->seen("$prefix-focus"));
    testapi::send_key('ctrl-a');
    $journey->consume_observation("$prefix-select", $journey->seen("$prefix-select"));
    $journey->consume_observation("$prefix-selected", $journey->seen("$prefix-selected"));
    testapi::send_key('ctrl-c');
    testapi::send_key('ctrl-end');
    testapi::send_key('ret') if $binding =~ /\Abody-complex/;
    testapi::send_key('ctrl-shift-v');
    my $result = $journey->seen("$prefix-read");
    $journey->consume_observation("$prefix-read", $result);
    return $result;
}

# UI16 finite non-BMP append: normal input-method keys after exact source,
# focus and public character-caret proofs. No clipboard or private assignment.
sub append_scalar {
    onpc_progress::operation('Appending one declared emoji through ordinary Unicode input');
    my ($journey, $binding) = @_;
    die 'text:scalar-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($binding) && $binding =~ /\A(?:body-mixed-500[01]|body-smoke)\z/;
    my $prefix = "text-scalar-$binding";
    $journey->consume_observation("$prefix-focus", $journey->seen("$prefix-focus"));
    testapi::send_key('ctrl-end');
    $journey->consume_observation("$prefix-caret", $journey->seen("$prefix-caret"));
    testapi::send_key('ctrl-shift-u');
    testapi::type_string('1f600');
    testapi::send_key('ret');
    my $result = $journey->seen("$prefix-read");
    $journey->consume_observation("$prefix-read", $result);
    return $result;
}

sub run {
    onpc_progress::operation('Qualifying synthetic text replacement without sending');
    my ($exchange) = @_;
    die 'text:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'text', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    for my $stage ('text-disabled', 'text-wrong-entry', 'feedback-open') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    replace_text($journey, $_) for ('body-first', 'body-second', 'body-clear');
    for my $stage ('feedback-close', 'feedback-reopen') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    replace_text($journey, $_) for ('reply-first', 'reply-second', 'reply-clear');
    $journey->consume_observation('feedback-finished', $journey->seen('feedback-finished'));
    $journey->finish();
}
1;
