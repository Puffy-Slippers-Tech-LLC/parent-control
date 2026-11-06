"""Protect the new privileged Flatpak scope and unowned-package boundary.

Only process-local doubles and pytest-private files; no VM, package manager,
subprocess, bus, display, shared cache or significant resource demand.
"""
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.modules import load_module
from tests.support.paths import ROOT

flatpaks = load_module('baseline_flatpak_safety', ROOT / 'tests/integration/baseline_flatpaks.py')


def manifest():
    return {ref: {'bundle': bundle, 'commit': str(index) * 64,
                  'metadata': hashlib.sha256(flatpaks.assets.metadata(ref.split('/')[1]).encode()).hexdigest()}
            for index, (ref, bundle) in enumerate(flatpaks.assets.declarations().items(), 1)}


def test_wrong_manifest_refuses_before_any_package_command(monkeypatch):
    monkeypatch.setattr(flatpaks, 'read', lambda path: b'{"foreign": {}}')
    command = Mock()
    monkeypatch.setattr(flatpaks, 'run', command)
    runner = SimpleNamespace(run=Mock())
    with pytest.raises(ValueError, match='flatpak-fixtures:manifest'):
        flatpaks.reconcile('a' * 64, runner=runner)
    command.assert_not_called()
    runner.run.assert_not_called()


def test_unowned_installed_identity_refuses_before_any_write(monkeypatch):
    expected = manifest()
    packages = {name: name.encode() for name in flatpaks.assets.declarations().values()}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in packages.items()}
    monkeypatch.setattr(flatpaks, 'read', lambda path, **kwargs:
        json.dumps(expected).encode() if path.name == flatpaks.assets.MANIFEST else
        json.dumps(hashes).encode() if path.name == 'SHA256SUMS.json' else packages[path.name])
    monkeypatch.setattr(flatpaks.os.path, 'lexists', lambda path: False)
    monkeypatch.setattr(flatpaks, 'installed', lambda: {next(iter(expected))})
    writer = Mock()
    monkeypatch.setattr(flatpaks, 'publish', writer)
    runner = SimpleNamespace(run=Mock())
    with pytest.raises(ValueError, match='flatpak-fixtures:foreign-package'):
        flatpaks.reconcile('a' * 64, runner=runner)
    writer.assert_not_called()
    runner.run.assert_not_called()


def test_user_scope_response_refuses_before_deployment_reads(monkeypatch):
    expected = manifest()
    ref = next(iter(expected))
    command = Mock(side_effect=[SimpleNamespace(stdout=ref),
        SimpleNamespace(stdout=expected[ref]['commit']),
        SimpleNamespace(stdout='/home/child/.local/share/flatpak/' + ref)])
    monkeypatch.setattr(flatpaks, 'run', command)
    reader = Mock()
    monkeypatch.setattr(flatpaks, 'read_deployed', reader)
    with pytest.raises(ValueError, match='flatpak-fixtures:installed-scope'):
        flatpaks.readback(ref, expected[ref])
    reader.assert_not_called()
    assert all('--system' in call.args[0] for call in command.call_args_list)


def test_unknown_recipient_refuses_before_commands(monkeypatch):
    command = Mock()
    monkeypatch.setattr(flatpaks, 'run', command)
    with pytest.raises(ValueError, match='flatpak-fixtures:recipient'):
        flatpaks.readback('app/foreign/x86_64/stable', {})
    command.assert_not_called()


def test_deployment_reader_preserves_foreign_bytes(tmp_path, monkeypatch):
    path = tmp_path / 'metadata'
    path.write_bytes(b'keep foreign bytes')
    monkeypatch.setattr(flatpaks, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='flatpak-fixtures:deployment-owner|flatpak-fixtures:deployment-file'):
        flatpaks.read_deployed(path)
    assert path.read_bytes() == b'keep foreign bytes'
