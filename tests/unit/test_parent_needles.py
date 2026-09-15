"""Reviewed fixture preparation cannot retain unrelated pixels or write elsewhere."""

import tempfile
from pathlib import Path

from PIL import Image
import pytest

import parent_needles


def test_preparation_retains_only_reviewed_regions_and_matcher_border(tmp_path):
    destination = tmp_path / 'tests/integration/graphical_smoke/needles'
    destination.mkdir(parents=True)
    with tempfile.NamedTemporaryFile(prefix='onpc-needle-unit-', suffix='.png', dir='/tmp') as source:
        Image.new('RGB', (1024, 768), 'white').save(source.name)
        parent_needles.prepare(tmp_path, Path(source.name), 'onpc-parent-menu', ['100,100,20,24'], click=True)
        with Image.open(destination / 'onpc-parent-menu.png') as retained:
            assert retained.getbbox() == (84, 84, 136, 140)
        with pytest.raises(ValueError, match='replacement'):
            parent_needles.prepare(tmp_path, Path(source.name), 'onpc-parent-menu', ['100,100,20,24'])


@pytest.mark.parametrize('tag,regions,click', [
    ('../../outside', ['100,100,20,24'], False),
    ('onpc-gdm-parent-masked-password', ['100,100,20,24'], True),
    ('onpc-parent-license', ['100,100,20,24'], True),
    ('onpc-parent-menu', [], True),
])
def test_invalid_destination_or_secret_tag_refuses_before_read(tmp_path, tag, regions, click):
    with pytest.raises(ValueError):
        parent_needles.prepare(tmp_path, Path('/tmp/onpc-no-such-input.png'), tag, regions, click=click)


def test_reader_rejects_unapproved_source_path(tmp_path):
    with pytest.raises(ValueError, match='directly in /tmp'):
        parent_needles.prepare(tmp_path, tmp_path / 'onpc-export.png', 'onpc-parent-menu', ['1,1,4,4'])
