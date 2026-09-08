use strict;
use warnings;
use autotest 'loadtest';
use testapi;
use distribution;

testapi::set_distribution(distribution->new());
if (get_var('ONPC_SERIAL_SMOKE', 0)) {
    # Public console type, with documented .in/.out pipe transport. No backend
    # internals or QEMU device paths are exposed to the distribution.
    $testapi::distri->add_console('onpc-serial', 'virtio-terminal',
        {socked_path => './serial-console'});
}
loadtest('tests/smoke.pm');
1;
