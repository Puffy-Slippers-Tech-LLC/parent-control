"""Local export qualification only: fake terminal input, no OS authentication.

Copied to a temporary test_authorization.py by the host-safe regression. Import
the real installed fixture so this exercises its JUnit integration, including
when the authentication assertion fails. Never stage this sample in the VM.
"""

import importlib.util
import os

import pytest

import system_caller as caller

spec = importlib.util.spec_from_file_location(
    'installed_authorization', os.environ['ONPC_AUTHORIZATION_SOURCE'])
authorization = importlib.util.module_from_spec(spec)
spec.loader.exec_module(authorization)
authentication_diagnostics = authorization.authentication_diagnostics


@pytest.fixture
def sample_agent(monkeypatch, authentication_diagnostics, surface):
    password = caller.FixturePassword()
    password._value = b'fixture-credential-do-not-export'
    private = b'private-user /home/private-user private@example.invalid ' + password._value
    agent = caller.TextAgent.__new__(caller.TextAgent)
    agent.master = 10
    agent.record_diagnostic = authentication_diagnostics
    agent.pending = (
        b'polkit-agent-helper-1: pam_authenticate failed: ' + private +
        b'\nAUTHENTICATION FAILED\n' +
        (b'polkit-agent-helper-1: error response to PolicyKit daemon: ' + private +
         b'\nAUTHENTICATION FAILED' if surface == 'child1' else
         private + b'\nAUTHENTICATION COMPLETE'))
    monkeypatch.setattr(caller.termios, 'tcgetattr', lambda fd: [0, 0, 0, 0])
    monkeypatch.setattr(caller.os, 'write', lambda fd, data: len(data))
    # Captured output remains private even though the safe categories survive.
    print(private.decode())
    return agent, password


@pytest.mark.parametrize('surface', ('child1', 'kiosk'))
def test_real_selected_parent_authentication(sample_agent, surface):
    agent, password = sample_agent
    agent.authenticate(password, succeeds=False)
    agent.authenticate(password)
