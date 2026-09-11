"""Use the installed os-autoinst matcher; synthetic variants are regression only."""

import json

from tests.support.paths import ROOT
from tests.support.perl import run_perl


NEEDLES = ROOT / 'tests/integration/graphical_smoke/needles'
MATCH = r'''
use strict;
use warnings;
use lib '/usr/lib/os-autoinst';
use cv;
BEGIN { cv::init(); }
use tinycv;
use needle;
use JSON::PP;
needle::init(shift);
my $image = tinycv::read(shift) or die 'image unreadable';
my $tag = shift;
my ($match, $candidates) = $image->search(needle::tags($tag));
my $result = $match // $candidates->[0];
print encode_json({ok => $match ? 1 : 0, area => $result->{area}});
'''


def match_image(path, tag='onpc-gdm-parent-account'):
    return json.loads(run_perl(MATCH, str(NEEDLES), str(path), tag).stdout)
