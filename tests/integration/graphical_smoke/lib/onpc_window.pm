package onpc_window;
use strict;
use warnings;
use onpc_progress ();
use testapi ();

# UI18: only registered active-window proofs can authorize Alt-F4. The result
# checkpoint independently observes absence and the expected underlying surface.
sub close {
    onpc_progress::operation('Closing the current window');
    my ($journey, $window, $proof, $invocation) = @_;
    $invocation //= '';
    my %stages = (
        license => ['license', 'license-closed'],
        about => ['about-returned', 'parent-returned'],
        'station-about' => ['about-close-ready', 'about-closed'],
        'overlay-about' => ['about-close-ready', 'about-closed'],
        'management-denied' => ['management-denied', 'denial-closed'],
        parent => ['close-ready', 'closed'],
        feedback => ['feedback-draft-reread', 'feedback-draft-closed'],
        'parent-report' => ['report', 'feedback-draft-closed'],
        'feedback-privacy' => ['feedback-privacy-open', 'feedback-privacy-returned'],
        'feedback-privacy-independent' => ['privacy-independent', 'privacy-independent-returned'],
    );
    die 'window:close-binding' unless (@_ == 3 || @_ == 4) && ref($journey) eq 'onpc_journey'
        && defined($window) && exists($stages{$window})
        && $invocation =~ /\A(?:[a-z][a-z0-9-]*-)?\z/;
    my ($before, $after) = @{$stages{$window}};
    $before = $invocation . $before;
    $after = $invocation . $after;
    $journey->consume_observation($before, $proof);
    testapi::send_key('alt-f4');
    return $journey->seen($after);
}

1;
