"""Exercise GDM fixture matching with the installed os-autoinst pixel matcher."""

import pytest
from PIL import Image

from tests.support.needle_matcher import NEEDLES, match_image


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
