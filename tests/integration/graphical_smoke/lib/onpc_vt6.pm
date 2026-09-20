package onpc_vt6;
use strict;
use warnings;
use onpc_progress ();
use onpc_password ();

my $attempted = 0;

# A VT console can prove its process and serial lineage to the controller, but
# it exposes no public automation identity for the graphical input recipient.
# Keep both retained entry points bounded and single-use, and refuse before
# console selection, image acquisition, credential access or input. The serial
# authentication route remains separate in onpc_serial.
sub authenticate {
    onpc_progress::operation('Authenticating at the fixture terminal');
    die "vt6:already-attempted\n" if $attempted++;
    onpc_password::seal_capture();
    die "vt6:public-recipient-id-required\n";
}

sub inspect_prompt {
    onpc_progress::operation('Inspecting the terminal login prompt');
    die "vt6:already-attempted\n" if $attempted++;
    onpc_password::seal_capture();
    die "vt6:public-recipient-id-required\n";
}

1;
