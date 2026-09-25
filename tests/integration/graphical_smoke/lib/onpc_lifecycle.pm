package onpc_lifecycle;
use strict;
use warnings;
use onpc_progress ();
use onpc_parent ();
use onpc_window ();

# LIFE01: consume the named prior window, independently guard its active state,
# close normally, prove absence, and use PARENT01 without selecting or editing.
sub reopen {
    onpc_progress::operation('Closing and reopening Parent');
    my ($journey, $window, $prior, $destination) = @_;
    die 'lifecycle:binding' unless @_ == 4 && ref($journey) eq 'onpc_journey'
        && $window eq 'parent' && $destination eq 'management';
    $journey->consume_observation('prior-window', $prior);
    onpc_window::close($journey, $window, $journey->seen('close-ready'));
    onpc_parent::launch($journey, $journey->seen('same-desktop'),
        $destination, 'same-desktop');
    return $journey->seen('initial-selection');
}
1;
