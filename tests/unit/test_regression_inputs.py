"""A changed file, mode, or input set invalidates combined execution evidence."""

import subprocess

import pytest

from regression_inputs import identity


def test_input_identity_includes_uncommitted_bytes_modes_and_deletions(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    source = tmp_path / 'source'
    source.write_text('before')
    original = identity(tmp_path)
    source.write_text('after')
    changed = identity(tmp_path)
    source.chmod(0o700)
    executable = identity(tmp_path)
    source.unlink()
    removed = identity(tmp_path)
    assert len({original, changed, executable, removed}) == 4


def test_generated_evidence_is_excluded_and_symlinks_are_refused(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / '.gitignore').write_text('output/\n')
    before = identity(tmp_path)
    output = tmp_path / 'output'
    output.mkdir()
    (output / 'report').write_text('streamed evidence')
    assert identity(tmp_path) == before
    (tmp_path / 'link').symlink_to(output / 'report')
    with pytest.raises(ValueError, match='symlink'):
        identity(tmp_path)
