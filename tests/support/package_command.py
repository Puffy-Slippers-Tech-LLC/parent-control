"""Shared package command fixture for authority and install cases."""

from types import SimpleNamespace
from unittest.mock import Mock

import package_command as command


DIGEST = 'a' * 64


def boundary(monkeypatch):
    transport = SimpleNamespace(config={'run': 'attempt', 'domain_uuid': 'vm'},
        commands=SimpleNamespace(last_returncode=0), guard=Mock(),
        call=Mock(return_value=(command.COMPLETE + '\n' + command.NOTICE + '\n').encode()))
    verified = SimpleNamespace(inputs={'package_sha256': DIGEST}, recheck=Mock())
    monkeypatch.setattr(command.session_control, 'observe',
                        Mock(return_value={'package_sha256': DIGEST}))
    return command.PackageCommand(transport, verified)
