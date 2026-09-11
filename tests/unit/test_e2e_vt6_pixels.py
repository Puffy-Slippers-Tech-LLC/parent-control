"""Reviewed native VT6 pixels and real matcher refusals, without secret input."""

import hashlib
import io

import pytest
from PIL import Image, ImageDraw

from tests.support.needle_matcher import NEEDLES, match_image
from vt6_prompt_pixels import verify_prompt_pixels


TAG = 'onpc-vt6-parent-password'
SOURCE = NEEDLES / (TAG + '.png')


def test_vt6_source_is_the_reviewed_native_credential_free_capture():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == (
        '63f310dff9a066270e8888af30ade4c65fc5e02af2604dc3bba53defff243f47')
    with Image.open(SOURCE) as image:
        assert image.size == (1024, 768)
    result = match_image(SOURCE, TAG)
    assert result['ok'] and result['area'][0]['similarity'] == 1, result
    assert verify_prompt_pixels(SOURCE.read_bytes(), SOURCE.read_bytes()) == {
        'vt6_prompt_pixels_verified': True}


@pytest.mark.parametrize('cursor', ['underline', 'block'])
def test_vt6_password_cursor_may_blink(tmp_path, cursor):
    with Image.open(SOURCE) as source:
        image = source.convert('RGB')
    ImageDraw.Draw(image).rectangle((60, 78 if cursor == 'underline' else 64, 65, 79), fill='white')
    path = tmp_path / 'cursor.png'
    image.save(path)
    result = match_image(path, TAG)
    assert result['ok'] and result['area'][0]['similarity'] == 1, result
    assert verify_prompt_pixels(path.read_bytes(), SOURCE.read_bytes())


@pytest.mark.parametrize('fault', [
    'wrong-account', 'account-suffix', 'missing-password', 'missing-account',
    'extra-input', 'stale-output', 'moved-challenge', 'wrong-vt', 'resized',
])
def test_vt6_prompt_refuses_wrong_identity_or_stale_screen(tmp_path, fault):
    with Image.open(SOURCE) as source:
        image = source.convert('RGB')
    draw = ImageDraw.Draw(image)
    if fault == 'wrong-account':
        # Replace the last fixture glyph with a different actual terminal glyph.
        image.paste(image.crop((102, 48, 108, 64)), (204, 48))
    elif fault == 'account-suffix':
        image.paste(image.crop((102, 48, 108, 64)), (210, 48))
    elif fault == 'missing-password':
        draw.rectangle((0, 64, 59, 79), fill='black')
    elif fault == 'missing-account':
        draw.rectangle((102, 48, 215, 63), fill='black')
    elif fault == 'extra-input':
        image.paste(image.crop((102, 48, 108, 64)), (66, 64))
    elif fault == 'stale-output':
        image.paste(image.crop((0, 64, 60, 80)), (0, 96))
    elif fault == 'moved-challenge':
        prompt = image.crop((0, 64, 60, 80))
        draw.rectangle((0, 64, 59, 79), fill='black')
        image.paste(prompt, (0, 80))
    elif fault == 'wrong-vt':
        draw.rectangle((216, 16, 221, 31), fill='black')
    elif fault == 'resized':
        image = image.resize((1280, 800))
    path = tmp_path / 'refused.png'
    image.save(path)
    result = match_image(path, TAG)
    assert not result['ok'], result
    with pytest.raises(RuntimeError, match='^vt6-pixels:refused$'):
        verify_prompt_pixels(path.read_bytes(), SOURCE.read_bytes())


@pytest.mark.parametrize('point', [(0, 0), (1023, 767), (500, 400), (59, 70),
                                  (66, 70), (62, 63), (62, 80)])
def test_exact_gate_refuses_single_changed_pixel_outside_cursor(point):
    with Image.open(SOURCE) as source:
        image = source.convert('RGB')
    old = image.getpixel(point)
    image.putpixel(point, ((old[0] + 1) % 256, old[1], old[2]))
    out = io.BytesIO()
    image.save(out, format='PNG')
    with pytest.raises(RuntimeError, match='^vt6-pixels:refused$'):
        verify_prompt_pixels(out.getvalue(), SOURCE.read_bytes())


def test_needle_similarity_cannot_replace_exact_blank_screen_gate(tmp_path):
    with Image.open(SOURCE) as source:
        image = source.convert('RGB')
    image.paste(image.crop((102, 48, 108, 64)), (500, 400))
    path = tmp_path / 'small-extra-glyph.png'
    image.save(path)
    # The installed matcher rounds this sparse change to a passing similarity.
    # Retain the counterexample: the controller MUST also run the exact gate.
    assert match_image(path, TAG)['ok']
    with pytest.raises(RuntimeError, match='^vt6-pixels:refused$'):
        verify_prompt_pixels(path.read_bytes(), SOURCE.read_bytes())


@pytest.mark.parametrize('fault', ['invalid', 'truncated', 'dimensions', 'oversize',
                                  'alpha', 'reference', 'reference-type', 'screen-type'])
def test_exact_gate_refuses_invalid_images_with_fixed_error(fault):
    screen = reference = SOURCE.read_bytes()
    if fault == 'invalid':
        screen = b'private-canary'
    elif fault == 'truncated':
        screen = screen[:64]
    elif fault == 'dimensions':
        screen = screen[:16] + b'\xff' * 8 + screen[24:]
    elif fault == 'oversize':
        screen += b'\x00' * (8 * 1024 * 1024)
    elif fault == 'alpha':
        with Image.open(SOURCE) as source:
            out = io.BytesIO()
            source.convert('RGBA').save(out, format='PNG')
            screen = out.getvalue()
    elif fault == 'reference':
        reference += b'changed'
    elif fault == 'reference-type':
        reference = None
    elif fault == 'screen-type':
        screen = None
    with pytest.raises(RuntimeError, match='^vt6-pixels:refused$'):
        verify_prompt_pixels(screen, reference)
