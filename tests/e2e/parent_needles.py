"""Bounded preparation of reviewed pixels, never generated UI evidence."""

import io
import json
import os
from pathlib import Path
import re
import stat

from PIL import Image

# GDM can use either of these already reviewed label renderings after setup.
# Fixed aliases preserve the semantic tag without weakening pixel thresholds
# or allowing arbitrary account/password variants.
GDM_RENDERINGS = {
    'onpc-gdm-parent-baseline-installed-account':
        ('onpc-gdm-parent-installed-account', 365, False),
    'onpc-gdm-parent-baseline-installed-input-account':
        ('onpc-gdm-parent-installed-input-account', 365, True),
    'onpc-gdm-other-parent-baseline-installed-input-account':
        ('onpc-gdm-other-parent-installed-input-account', 275, True),
}
PARENT_RENDERINGS = {
    'onpc-parent-child-choice-two-children': 'onpc-parent-child-choice',
}


def semantic_tag(name):
    return GDM_RENDERINGS[name][0] if name in GDM_RENDERINGS else PARENT_RENDERINGS.get(name, name)


TAGS = tuple(GDM_RENDERINGS) + tuple(PARENT_RENDERINGS) + ('onpc-gdm-other-parent-installed-input-account',
        'onpc-gdm-standard-installed-input-account',
        'onpc-gdm-standard-selected-account',
        'onpc-gdm-other-child-masked-password',
        'onpc-parent-desktop', 'onpc-parent-app-grid',
        'onpc-parent-standard-unavailable',
        'onpc-parent-child-picker', 'onpc-parent-child-choice', 'onpc-parent-child-selected',
        'onpc-parent-new-child-choice', 'onpc-parent-new-child-selected',
        'onpc-parent-empty',
        'onpc-parent-menu', 'onpc-parent-about-item', 'onpc-parent-about',
        'onpc-parent-about-legal', 'onpc-parent-license-link', 'onpc-parent-license')
CLICK_TAGS = (frozenset(name for name, (_, _, click) in GDM_RENDERINGS.items() if click)
             | frozenset(PARENT_RENDERINGS) | frozenset(('onpc-gdm-other-parent-installed-input-account',
    'onpc-gdm-standard-installed-input-account',
    'onpc-parent-child-picker', 'onpc-parent-child-choice', 'onpc-parent-menu',
    'onpc-parent-new-child-choice',
    'onpc-parent-about-item', 'onpc-parent-license-link')))


def prepare(root, source, tag, regions, *, click=False, replace=False):
    if (tag not in TAGS or (click and tag not in CLICK_TAGS)
            or not 1 <= len(regions) <= 8):
        raise ValueError('invalid fixed tag or region count')
    if tag in GDM_RENDERINGS:
        _, y, expected_click = GDM_RENDERINGS[tag]
        if regions != [f'442,{y},118,32'] or click != expected_click:
            raise ValueError('invalid fixed GDM rendering region or click')
    if tag in PARENT_RENDERINGS and (regions != ['188,272,121,36'] or not click):
        raise ValueError('invalid fixed child-choice rendering region or click')
    source = Path(source)
    if source.parent != Path('/tmp') or not re.fullmatch(r'onpc-[A-Za-z0-9_-]+\.png', source.name):
        raise ValueError('source must be an exported onpc PNG directly in /tmp')
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1 or not 24 <= metadata.st_size <= 32 * 1024 * 1024):
            raise ValueError('source ownership or file type')
        raw = stream.read()
    with Image.open(io.BytesIO(raw)) as original:
        if original.format != 'PNG' or original.size != (1024, 768):
            raise ValueError('expected 1024x768 worker PNG')
        original.load()
        original = original.convert('RGB')
    canvas = Image.new('RGB', original.size)
    areas = []
    for region in regions:
        if not re.fullmatch(r'[0-9]+,[0-9]+,[0-9]+,[0-9]+', region):
            raise ValueError('area must contain four unsigned integers')
        x, y, width, height = map(int, region.split(','))
        if not (0 <= x < 1024 and 0 <= y < 768 and 1 <= width <= 1024-x and 1 <= height <= 768-y):
            raise ValueError('area outside screenshot')
        # os-autoinst's matcher blurs edges. Preserve its context without
        # retaining unrelated accounts, clocks or other screen contents.
        box = (max(0, x-16), max(0, y-16), min(1024, x+width+16), min(768, y+height+16))
        canvas.paste(original.crop(box), box[:2])
        areas.append(dict(xpos=x, ypos=y, width=width, height=height, type='match', match=100))
    if click:
        if areas[-1]['width'] < 3 or areas[-1]['height'] < 3:
            raise ValueError('click region too small')
        areas[-1]['click_point'] = {'xpos': areas[-1]['width']//2, 'ypos': areas[-1]['height']//2}
    destination = Path(root) / 'tests/integration/graphical_smoke/needles'
    if destination.resolve() != destination or not destination.is_dir():
        raise ValueError('unsafe needle directory')
    targets = [destination / (tag + suffix) for suffix in ('.png', '.json')]
    for target in targets:
        if os.path.lexists(target):
            metadata = target.lstat()
            if (not replace or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                    or metadata.st_uid != os.getuid()):
                raise ValueError('existing needle requires explicit safe replacement')
    image = io.BytesIO()
    canvas.save(image, format='PNG')
    payloads = [image.getvalue(), (json.dumps({'tags': [semantic_tag(tag)], 'area': areas}, indent=2)+'\n').encode()]
    for target, payload in zip(targets, payloads):
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_TRUNC if replace else os.O_EXCL)
        with os.fdopen(os.open(target, flags, 0o644), 'wb') as stream:
            stream.write(payload)
