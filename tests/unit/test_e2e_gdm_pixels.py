"""Exercise GDM fixture matching with the installed os-autoinst pixel matcher."""

import pytest

from tests.support.needle_matcher import NEEDLES, match_image


@pytest.mark.parametrize('image', [
    'onpc-gdm-other-parent-account', 'onpc-gdm-parent-masked-password'])
def test_installed_label_refuses_other_identity_and_password_screen(image):
    result = match_image(NEEDLES / (image + '.png'), 'onpc-gdm-parent-installed-account')
    assert not result['ok'], result


@pytest.mark.parametrize('role', ['parent', 'other-parent'])
@pytest.mark.parametrize('baseline', [False, True])
def test_installed_input_accepts_both_reviewed_renderings_and_refuses_other_role(role, baseline):
    tag = f'onpc-gdm-{role}-installed-input-account'
    image = f'onpc-gdm-{role}-account' if baseline else tag
    result = match_image(NEEDLES / (image + '.png'), tag)
    assert result['ok'] and result['area'][0]['similarity'] == 1, result
    assert result['area'][0]['click_point'] == {'xpos': 59, 'ypos': 16}
    other = 'other-parent' if role == 'parent' else 'parent'
    result = match_image(NEEDLES / (image + '.png'), f'onpc-gdm-{other}-installed-input-account')
    assert not result['ok'], result


def test_installed_readiness_accepts_baseline_rendering_without_click_authority():
    result = match_image(NEEDLES / 'onpc-gdm-parent-account.png',
                         'onpc-gdm-parent-installed-account')
    assert result['ok'] and result['area'][0]['similarity'] == 1, result
    assert 'click_point' not in result['area'][0]
