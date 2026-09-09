"""Exercise GDM fixture matching with the installed os-autoinst pixel matcher."""

import json
from pathlib import Path

import pytest
from PIL import Image

from tests.support.perl import run_perl


NEEDLES = Path(__file__).resolve().parents[1] / 'integration/graphical_smoke/needles'
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


@pytest.mark.parametrize('installed', [False, True])
def test_reviewed_label_matches_after_bounded_layout_movement(tmp_path, installed):
    tag = 'onpc-gdm-parent-' + ('installed-account' if installed else 'account')
    with Image.open(NEEDLES / (tag + '.png')) as source:
        # Exercise the actual matcher's spatial search, including the blur
        # border, rather than comparing the same file against itself.
        shifted = Image.new('RGB', source.size)
        shifted.paste(source, (8, 20))
        path = tmp_path / 'greeter.png'
        shifted.save(path)
    result = match_image(path, tag)
    assert result['ok'] and result['area'][0]['similarity'] == 1, result
    expected_y = 351 if installed else 365
    assert (result['area'][0]['x'], result['area'][0]['y']) == (450, expected_y + 20)


@pytest.mark.parametrize('image', ['onpc-gdm-parent-account',
    'onpc-gdm-other-parent-account', 'onpc-gdm-parent-masked-password'])
def test_installed_label_refuses_other_rendering_identity_and_password_screen(image):
    result = match_image(NEEDLES / (image + '.png'), 'onpc-gdm-parent-installed-account')
    assert not result['ok'], result


def test_old_label_reproduces_post_reboot_pixel_mismatch():
    result = match_image(NEEDLES / 'onpc-gdm-parent-installed-account.png')
    assert not result['ok'] and result['area'][0]['similarity'] < 0.9, result


def test_installed_fixture_contains_only_reviewed_label_and_blur_border():
    with Image.open(NEEDLES / 'onpc-gdm-parent-installed-account.png') as image:
        assert image.size == (1024, 768) and image.mode == 'RGB'
        # This is the reviewed fixture-label crop from the retained failed
        # return, with a 16-pixel matcher border. No other account or clock.
        assert image.getbbox() == (426, 335, 576, 399)
