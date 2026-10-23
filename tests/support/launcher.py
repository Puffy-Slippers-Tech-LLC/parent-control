"""Finite source inputs and evidence doubles for launcher orchestration tests."""

import hashlib
import json
from pathlib import Path

import pytest
import package_inputs
from tools import package_inputs as packaged_inputs


@pytest.fixture
def synthetic_report_evidence(monkeypatch):
    """Keep real report files and counts without unrelated custody archives."""
    import runner_evidence

    class Evidence:
        def __init__(self, root, directory, *, workflow):
            self.directory = directory
            self.commands = []
            self.finalizations = []

        def command(self, record):
            self.commands.append(json.loads(json.dumps(record)))

        def finalize(self, **fields):
            self.finalizations.append(fields)
            return dict(receipt=None, records=[], references=[], capture_ids=[])

    monkeypatch.setattr(runner_evidence, 'ReportEvidence', Evidence)


@pytest.fixture
def synthetic_package_identity(monkeypatch):
    # Keep named_input's real option/prefix selection. Dispatch tests do not
    # need to launch Make and hash the product for every selector spelling.
    # test_test_storage_cleanup_safety owns real byte-change/refusal checks.
    # Launchers use standalone imports; some callers use the tools package.
    for module in (package_inputs, packaged_inputs):
        monkeypatch.setattr(module, 'paths', lambda _: [Path('product.py')])
        monkeypatch.setattr(module, 'digest', lambda _, paths: hashlib.sha256(
            '\0'.join(path.as_posix() for path in paths).encode()).hexdigest())
