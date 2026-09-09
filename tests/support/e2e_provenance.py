"""Real source/artifact files with a simulated held lease, for host-only tests."""

import copy
import hashlib
import json
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import provenance
from tests.support.paths import ROOT


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def lease():
    state = {'phase': 'finalized', 'proof': {'disk': 'retained-proof'},
             'guest': {'ubuntu_version': '26.04', 'accounts': 'private-fixture-account'}}
    capture = SimpleNamespace(state=state, read_state=lambda: copy.deepcopy(state),
                              verify_snapshot=lambda: copy.deepcopy(state['proof']))
    return SimpleNamespace(fd=42, guard=Mock(), capture=capture,
                           state={'baseline_sha256': provenance.digest(state)})


@pytest.fixture
def source(tmp_path):
    root = tmp_path / 'checkout'
    root.mkdir()
    git(root, 'init', '-q')
    for name in ('tests/e2e/scenarios.json', 'tests/e2e/runner.py', 'tests/requirements.json',
                 'docs/TestAutomation/E2E-Coverage.md',
                 'tests/integration/graphical_smoke/main.pm',
                 'tests/integration/graphical_smoke/tests/smoke.pm'):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    (root / '.codex').mkdir()
    (root / '.codex/rules').write_text('fixture input\n')
    (root / '.codex-staged').write_text('sibling input\n')
    git(root, 'add', '.')
    # Include a real untracked input and a real uncommitted tracked edit.
    (root / 'local-change.py').write_text('current input\n')
    with (root / 'tests/e2e/runner.py').open('a') as stream:
        stream.write('\n# local change\n')
    return root


@pytest.fixture
def assets(tmp_path, source):
    root = tmp_path / 'assets'
    root.mkdir(mode=0o700)
    (root / 'package.deb').write_bytes(b'test package bytes')
    fixtures = root / 'fixtures'
    fixtures.mkdir()
    (fixtures / 'payload').write_bytes(b'fixture payload')
    (fixtures / 'onpc-test-application.flatpak').write_bytes(b'flatpak container')
    files = {'payload': hashlib.sha256(b'fixture payload').hexdigest()}
    (fixtures / 'SHA256SUMS.json').write_text(json.dumps({'algorithm': 'sha256', 'files': files}))
    manifest = {
        'schema_version': 1,
        'source': {'digest_sha256': provenance.snapshot(source, source=True)['sha256']},
        'artifacts': {
            'package': {'path': 'package.deb', 'sha256': hashlib.sha256(b'test package bytes').hexdigest()},
            'fixtures': {'path': 'fixtures', 'sha256': hashlib.sha256(
                json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()},
        },
    }
    (root / 'artifact-manifest.json').write_text(json.dumps(manifest))
    return root
