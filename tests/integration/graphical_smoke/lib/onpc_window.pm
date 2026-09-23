package onpc_window;
use strict;
use warnings;
use onpc_progress ();
use testapi ();

# UI18: only registered active-window proofs can authorize Alt-F4. The result
# checkpoint independently observes absence and the expected underlying surface.
sub close {
    onpc_progress::operation('Closing the current window');
    my ($journey, $window, $proof) = @_;
    my %stages = (
        license => ['license', 'license-closed'],
        'license-qualified' => ['license-provider-refusals', 'license-closed'],
        'license-unrelated-fixture' => ['license-unrelated-ready', 'license-unrelated-closed'],
        'license-empty-fixture' => ['license-empty-ready', 'license-empty-closed'],
        'license-ambiguous-fixture' => ['license-ambiguous-ready', 'license-ambiguous-closed'],
        about => ['about-returned', 'parent-returned'],
        'management-denied' => ['management-denied', 'denial-closed'],
        parent => ['close-ready', 'closed'],
    );
    die 'window:close-binding' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && defined($window) && exists($stages{$window});
    my ($before, $after) = @{$stages{$window}};
    $journey->consume_observation($before, $proof);
    testapi::send_key('alt-f4');
    return $journey->seen($after);
}

1;
