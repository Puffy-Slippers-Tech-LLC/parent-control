"""Protected evidence links preserve guarded reader and target identity boundaries."""
from tests.support.modules import load_module
import errno
import os
import subprocess
from types import SimpleNamespace

import pytest


from tests.support.paths import ROOT
checks = load_module('onpc_test_document_checks', ROOT / 'tools/document_checks.py')


@pytest.mark.parametrize('outcome', ['verified', 'refused', 'malformed', 'timeout', 'unavailable'])
def test_explicit_protected_link_inspection_uses_only_the_guarded_metadata_reader(
        tmp_path, monkeypatch, outcome):
    from evidence_policy import Condition
    root = tmp_path / 'checkout'
    (root / 'docs').mkdir(parents=True)
    source = root / 'docs/guide.md'
    source.write_text('[private prose](../output/test-runs/private-result.json)\n')
    target = root / 'output/test-runs/private-result.json'
    original = type(target).stat
    calls = []

    def denied(path, *args, **kwargs):
        if checks.Path(os.path.abspath(path)) == target:
            raise PermissionError(errno.EACCES, 'private access details', str(target))
        return original(path, *args, **kwargs)

    def metadata_reader(argv, **kwargs):
        calls.append(argv)
        assert argv == ['/usr/bin/pkexec', '--keep-cwd',
                        '/usr/local/libexec/onpc-test-artifacts', 'stat', str(target)]
        assert kwargs == dict(cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True, check=False, timeout=15)
        if outcome == 'timeout':
            raise subprocess.TimeoutExpired(argv, 15)
        if outcome == 'unavailable':
            raise FileNotFoundError('private helper details')
        return SimpleNamespace(returncode=2 if outcome == 'refused' else 0,
                               stdout='{"kind":"file"}' if outcome != 'malformed' else 'true')

    monkeypatch.setattr(checks, 'ROOT', root)
    monkeypatch.setattr(type(target), 'stat', denied)
    monkeypatch.setattr(checks.subprocess, 'run', metadata_reader)
    text = source.read_text()
    link = next(checks.references(text))
    assert checks.link_condition(source, text, link) == (None if outcome == 'verified' else Condition.DENIED)
    assert len(calls) == 1


def test_parent_steps_through_symlinks_cannot_verify_an_unrelated_artifact(
        tmp_path, monkeypatch):
    from evidence_policy import Condition
    root = tmp_path / 'checkout'
    evidence = root / 'output/test-runs'
    evidence.mkdir(parents=True)
    (evidence / 'result.json').touch()
    private = tmp_path / 'elsewhere/private'
    private.mkdir(parents=True)
    (evidence / 'jump').symlink_to(private, target_is_directory=True)
    source = root / 'guide.md'
    source.write_text('[private prose](output/test-runs/jump/../result.json)\n')
    target = evidence / 'jump/../result.json'
    original = type(target).stat

    def denied(path, *args, **kwargs):
        if path == target:
            raise PermissionError(errno.EACCES, 'private access details', str(target))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(checks, 'ROOT', root)
    monkeypatch.setattr(type(target), 'stat', denied)
    monkeypatch.setattr(checks.subprocess, 'run', lambda *args, **kwargs:
                        pytest.fail('a different normalized target must not reach the reader'))
    text = source.read_text()
    assert checks.link_condition(source, text, next(checks.references(text))) == Condition.DENIED
