"""Host-only preflight refuses broken tooling before any graphical attempt."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

DIRECTORY = Path(__file__).resolve().parents[1] / 'integration'
import graphical_backend as backend


def successful_commands():
    pins = backend.package_pins()
    commands = Mock()
    commands.run.side_effect = [
        *(f'install ok installed\n{pins[name]}\n'.encode() for name in backend.PACKAGES),
        b'Current version is unknown [interface v48]\n', b'syntax OK\n',
    ]
    return commands


def test_tooling_success_cannot_claim_graphical_compatibility():
    commands = successful_commands()
    with patch.object(Path, 'read_bytes', return_value=b'reviewed tool'):
        result = backend.check(commands)
    assert result['scope'] == 'tooling-only'
    assert result['graphical_smoke'] == 'not-run'
    assert result['vm_access'] is False
    assert result['test_api'] == 48
    assert len(result['files_sha256']) == 2
    assert [call.args[0][0] for call in commands.run.call_args_list] == [
        '/usr/bin/dpkg-query', '/usr/bin/dpkg-query', '/usr/bin/isotovideo', '/usr/bin/perl']
    assert all(call.kwargs == {'timeout': 30} for call in commands.run.call_args_list)


@pytest.mark.parametrize('status', ['deinstall ok config-files', 'install ok unpacked'])
def test_incomplete_package_install_refuses_before_entrypoint(status):
    commands = Mock()
    commands.run.return_value = f'{status}\n{backend.package_pins()["os-autoinst"]}\n'.encode()
    with pytest.raises(backend.PreflightError, match='tools:package-mismatch:os-autoinst'):
        backend.check(commands)
    assert commands.run.call_count == 1


def test_wrong_package_version_refuses_before_entrypoint():
    commands = Mock()
    commands.run.return_value = b'install ok installed\n0.0\n'
    with pytest.raises(backend.PreflightError, match='tools:package-mismatch:os-autoinst'):
        backend.check(commands)
    assert commands.run.call_count == 1


@pytest.mark.parametrize(('index', 'category'), [
    (0, 'tools:package-unavailable:os-autoinst'),
    (1, 'tools:package-unavailable:libfeature-compat-try-perl'),
    (2, 'tools:entrypoint-failed'), (3, 'tools:generalhw-load-failed'),
])
def test_failed_probe_is_redacted_and_stops_later_work(index, category, capsys):
    commands = successful_commands()
    outputs = list(commands.run.side_effect)
    outputs[index] = RuntimeError('sensitive child output')
    commands.run.side_effect = outputs
    with patch.object(backend, 'Commands', return_value=commands):
        assert backend.main([]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['category'] == category
    assert 'sensitive' not in json.dumps(result)
    assert commands.run.call_count == index + 1


def test_changed_public_api_refuses_backend_loading():
    commands = successful_commands()
    outputs = list(commands.run.side_effect)
    outputs[2] = b'Current version is unknown [interface v49]\n'
    commands.run.side_effect = outputs
    with pytest.raises(backend.PreflightError, match='tools:unexpected-test-api'):
        backend.check(commands)
    assert commands.run.call_count == 3


@pytest.mark.parametrize('contents', [
    '', 'os-autoinst=1\nos-autoinst=2\nlibfeature-compat-try-perl=1\n',
    'os-autoinst=bad value\nlibfeature-compat-try-perl=1\n',
])
def test_invalid_pins_fail_before_commands(tmp_path, contents):
    path = tmp_path / 'pins'
    path.write_text(contents)
    with pytest.raises(backend.PreflightError, match='tools:.*package-pin'):
        backend.package_pins(path)
