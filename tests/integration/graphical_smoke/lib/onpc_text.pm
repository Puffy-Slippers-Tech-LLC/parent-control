package onpc_text;
use strict;
use warnings;
use utf8;
use testapi ();
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

my %values = (
    'match-wildcard' => '/opt/onpc-test-fixtures/Applications/Exact*.AppImage',
    'match-wildcard-basename' => 'Exact*.AppImage',
    'match-wildcard-appimages' => '/opt/onpc-test-fixtures/Applications/*.AppImage',
    'match-rejected-directory' => '/opt/onpc-test-fixtures/Rejected/*.AppImage',
    'match-precise' => '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage',
    'match-precise-basename' => 'Exact Fixture.AppImage',
    'match-invalid-empty' => '', 'match-invalid-whitespace' => '   ',
    'match-invalid-basename' => 'Unrelated.AppImage',
    'match-invalid-absolute' => '/opt/onpc-test-fixtures/Applications/Unrelated.AppImage',
    'catalogue-name' => 'ONPC Allowed Fixture',
    'catalogue-description' => 'Exact native catalogue fixture',
    'catalogue-identifier' => 'com.puffyslippers.ONPCTest.A.desktop',
    'catalogue-absent' => 'ONPC Absent Catalogue Fixture 077b', 'catalogue-clear' => '',
    'body-ascii-5000' => 'x' x 5000,
    'body-ascii-5001' => 'x' x 5001,
    'body-mixed-5000-base' => 'x' x 4998,
    'body-mixed-5001-base' => 'x' x 4999,
    'kiosk-fraction' => '1.25',
    'chinese-kiosk-fraction' => '1.25',
    'jordan-kiosk-fraction' => '1.25',
    'overlay-fraction' => '1.25',
    'kiosk-invalid-empty' => '', 'kiosk-invalid-letters' => 'abc',
    'kiosk-invalid-negative' => '-1', 'kiosk-invalid-zero' => '0',
    'kiosk-invalid-below' => '0.09', 'kiosk-invalid-over' => '1440.1',
    'kiosk-invalid-comma' => '1,5',
    'body-first' => 'Synthetic feedback first',
    'body-rtl' => 'שלום Alex 75',
    'reply-rtl' => 'rtl-check@example.invalid',
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
    'daily-4' => '4', 'daily-5' => '5',
    'daily-0' => '0', 'daily-15' => '15', 'daily-1439' => '1439',
    'daily-invalid-empty' => '', 'daily-invalid-letters' => 'abc',
    'daily-invalid-negative' => '-1', 'daily-invalid-fraction' => '0.5',
    'daily-invalid-maximum' => '1440', 'daily-invalid-over' => '1441',
);
my %repetitions;
for my $key (grep { /^kiosk-invalid-/ } keys %values) {
    (my $overlay = $key) =~ s/^kiosk-/overlay-/;
    $values{$overlay} = $values{$key};
}
for my $binding ('body-ascii-5000', 'body-ascii-5001',
                 'body-mixed-5000-base', 'body-mixed-5001-base') {
    my @chain = ("$binding-seed", map { "$binding-double-$_" } 1..4);
    $values{$chain[0]} = substr($values{$binding}, 0, int(length($values{$binding}) / 16));
    $repetitions{$binding} = \@chain;
}

# UI16: the shared observer qualifies each logical recipient, applies the
# declared API value once, then independently reads the result.
sub replace_text {
    onpc_progress::operation('Setting a declared field through the Application UI API');
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
        $journey->consume_observation("$prefix-anchor", $journey->seen("$prefix-anchor"));
    }
    for my $stage ("$prefix-focus", "$prefix-selected") {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    my $result = $journey->seen("$prefix-read");
    return $journey->consume_observation("$prefix-read", $result);
}

# The shared API block owns the finite rapid-save values and source binding.
sub observed_custom_edits {
    onpc_progress::operation('Setting two declared custom allowances through the App UI API');
    my ($journey, $stage, $first, $last, $child) = @_;
    $child //= 'child';
    die 'text:rapid-binding' unless (@_ == 4 || @_ == 5) && ref($journey) eq 'onpc_journey'
        && $stage =~ /\A[a-z][a-z0-9-]*\z/ && $first eq '5' && $last eq '6'
        && ($child eq 'child' || $child eq 'existing');
    # The shared Python input block validates the declared child/source and
    # performs each canonical edit once. Its later result reads the saved value.
    my $result = $journey->seen($stage);
    return $journey->consume_observation($stage, $result);
}

sub repeat_text {
    onpc_progress::operation('Composing declared text through shared API stages');
    my ($journey, $binding) = @_;
    die 'text:repeat-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($binding) && exists($repetitions{$binding});
    my ($seed, @copies) = @{$repetitions{$binding}};
    replace_text($journey, $seed);
    duplicate_text($journey, $_) for @copies;
    my $prefix = "text-suffix-$binding";
    for my $phase ('focus', 'caret', 'read') {
        $journey->consume_observation("$prefix-$phase", $journey->seen("$prefix-$phase"));
    }
}

# Shared UI16 composite: exact synthetic source, one canonical text setter,
# then the independently observed doubled result. No input retries.
sub duplicate_text {
    onpc_progress::operation('Setting and independently reading one declared text composition');
    my ($journey, $binding) = @_;
    die 'text:duplicate-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($binding) && ($binding =~ /\Abody-complex(?:-(?:150|300|600))?\z/
            || $binding =~ /\Abody-(?:ascii-500[01]|mixed-500[01]-base)-double-[1-4]\z/);
    my $prefix = "text-duplicate-$binding";
    for my $phase ('focus', 'select', 'selected', 'read') {
        $journey->consume_observation("$prefix-$phase", $journey->seen("$prefix-$phase"));
    }
}

# UI16 finite non-BMP append through the public text API after exact source.
sub append_scalar {
    onpc_progress::operation('Setting declared Unicode text through the Application UI API');
    my ($journey, $binding) = @_;
    die 'text:scalar-binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($binding) && $binding =~ /\A(?:body-mixed-500[01]|body-smoke)\z/;
    my $prefix = "text-scalar-$binding";
    for my $phase ('focus', 'caret', 'read') {
        $journey->consume_observation("$prefix-$phase", $journey->seen("$prefix-$phase"));
    }
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
