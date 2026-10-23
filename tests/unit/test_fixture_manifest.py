"""The fixture writer refuses symlinked output ancestors before writing."""

import pytest

from tools import fixture_manifest as codec


def test_directory_ancestor_symlink_refused(tmp_path):
    original, alias = tmp_path / 'original', tmp_path / 'alias'
    original.mkdir()
    alias.symlink_to(original, target_is_directory=True)
    with pytest.raises(ValueError, match='fixture:directory-symlink'):
        codec._directory(alias)
