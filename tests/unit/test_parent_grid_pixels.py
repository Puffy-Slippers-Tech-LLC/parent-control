"""App-grid readiness uses reviewed Shell controls, independent of app tiles."""

import json

from PIL import Image, ImageDraw
import pytest

from tests.support.needle_matcher import NEEDLES, match_image


@pytest.mark.parametrize('missing', [None, 0, 1, 2])
def test_grid_requires_all_controls_while_tiles_can_change(tmp_path, missing):
    tag = 'onpc-parent-app-grid'
    areas = json.loads((NEEDLES / (tag + '.json')).read_bytes())['area']
    with Image.open(NEEDLES / (tag + '.png')) as source:
        image = source.convert('RGB')
    draw = ImageDraw.Draw(image)
    # Synthetic regression pixels stand in for changed app tiles, never live
    # acceptance evidence. None of the matched controls overlaps this region.
    draw.rectangle((60, 250, 950, 690), fill='purple')
    if missing is not None:
        area = areas[missing]
        x, y = area['xpos'], area['ypos']
        draw.rectangle((x-16, y-16, x+area['width']+16, y+area['height']+16), fill='black')
    path = tmp_path / 'grid.png'
    image.save(path)
    result = match_image(path, tag)
    assert bool(result['ok']) == (missing is None), result
    if missing is None:
        assert all(area['similarity'] == 1 for area in result['area']), result


@pytest.mark.parametrize('screen', ['onpc-parent-desktop', 'onpc-gdm-parent-account',
                                   'onpc-gdm-parent-masked-password'])
def test_grid_refuses_desktop_and_login_controls(screen):
    result = match_image(NEEDLES / (screen + '.png'), 'onpc-parent-app-grid')
    assert not result['ok'], result
