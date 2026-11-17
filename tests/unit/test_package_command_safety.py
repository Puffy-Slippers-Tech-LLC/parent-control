"""Protect the finite administrator package input and uncertain replay boundary.

Only process-local doubles and private input paths; no guest or host mutation.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import build_test_artifacts
from package_command import PackageCommand


def boundary(monkeypatch, package_format):
    identity = {'name': 'onpc-catalogue-fixture',
                'version': '0:2.0-1' if package_format == 'rpm' else '2.0',
                'architecture': 'x86_64' if package_format == 'rpm' else 'amd64', 'sha256': 'a' * 64}
    transport = SimpleNamespace(config={'run': 'one'}, package_attempts=set(),
                                guard=Mock(), call=Mock())
    verified = SimpleNamespace(recheck=Mock(), assets=Path('/verified'), inputs={'package_sha256': 'b' * 64},
        asset_files={'package.' + package_format: 'b' * 64,
                     'catalogue-new.' + package_format: identity['sha256']})
    monkeypatch.setattr(build_test_artifacts, 'package_identity', Mock(return_value=identity))
    return PackageCommand(transport, verified), identity


@pytest.mark.parametrize('fault,reason', [
    ('attempt', 'wrong-attempt'), ('replay', 'replay'),
    ('missing', 'catalogue-input-required'), ('digest', 'wrong-artifact')])
@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_fixture_input_refuses_before_administrator_or_command_access(monkeypatch, fault, reason, package_format):
    command, identity = boundary(monkeypatch, package_format)
    if fault == 'attempt': command.transport.config = {'run': 'other'}
    if fault == 'replay': command.transport.package_attempts.add('update-catalogue-new')
    if fault == 'missing': command.verified.asset_files.pop('catalogue-new.' + package_format)
    if fault == 'digest': identity['sha256'] = 'c' * 64
    with pytest.raises(ValueError, match='package:' + reason):
        command.submit_fixture('update-catalogue-new')
    command.transport.call.assert_not_called()


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_uncertain_fixture_submission_cannot_be_replayed_by_a_new_command(monkeypatch, package_format):
    import package_command
    from contextlib import nullcontext
    command, _identity = boundary(monkeypatch, package_format)
    monkeypatch.setattr(package_command.session_control, 'observe',
                        Mock(return_value={'package_sha256': 'b' * 64}))
    monkeypatch.setattr(package_command, 'guest_source', lambda: b'fixed source')
    monkeypatch.setattr(package_command, 'package_operation', lambda *args, **kwargs: nullcontext())
    command.transport.call.side_effect = OSError('uncertain reply')
    with pytest.raises(OSError, match='uncertain reply'):
        command.submit_fixture('update-catalogue-new')
    another = PackageCommand(command.transport, command.verified)
    with pytest.raises(ValueError, match='package:replay'):
        another.submit_fixture('update-catalogue-new')
    assert command.transport.call.call_count == 1
