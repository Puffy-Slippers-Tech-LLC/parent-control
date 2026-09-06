use strict;
use warnings;
use autotest 'loadtest';
use testapi;
use distribution;

testapi::set_distribution(distribution->new());
loadtest('tests/smoke.pm');
1;
