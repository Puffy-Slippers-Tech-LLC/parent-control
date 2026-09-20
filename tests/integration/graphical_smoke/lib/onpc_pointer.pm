package onpc_pointer;
use strict;
use warnings;
use onpc_progress ();

# Retained entry point for legacy callers. Image matches and framebuffer
# geometry can never identify an automation target; callers must use an
# ID-addressed accessibility action instead.
sub click {
    onpc_progress::operation('Clicking the matched control');
    die 'pointer:id-addressed-action-required';
}

1;
