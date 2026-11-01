"""Finite source inputs and evidence doubles for launcher orchestration tests."""

import hashlib

import pytest
import package_inputs
from tools import package_inputs as packaged_inputs


@pytest.fixture
def synthetic_package_identity(monkeypatch, tmp_path):
    # Keep named_input's real option/prefix selection. Dispatch tests do not
    # need to launch Make and hash the product for every selector spelling.
    # test_test_storage_cleanup_safety owns real byte-change/refusal checks.
    # Launchers use standalone imports; some callers use the tools package.
    source = tmp_path / 'product.py'
    source.write_text('pass\n')
    for module in (package_inputs, packaged_inputs):
        monkeypatch.setattr(module, 'paths', lambda _: [source])
        monkeypatch.setattr(module, 'digest', lambda _, paths: hashlib.sha256(
            '\0'.join(path.as_posix() for path in paths).encode()).hexdigest())
