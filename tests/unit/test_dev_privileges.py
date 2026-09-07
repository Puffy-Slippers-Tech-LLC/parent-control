"""Routine launchers never ask Polkit to open an authentication dialog."""
import os
import json
from pathlib import Path
import runpy
import stat
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

privileges = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/dev_privileges.py'))
PROGRAM = '/usr/local/libexec/onpc-test-runner'


@pytest.mark.parametrize('name', ['test-runner', 'setup', 'diagnostics', 'test-artifacts', 'export-screenshot'])
@pytest.mark.parametrize('returncode', [0, 1, 2, 127])
def test_noninteractive_permission_preflight_gates_pkexec(monkeypatch, returncode, name):
    program = '/usr/local/libexec/onpc-' + name
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(Path, 'lstat', lambda _: SimpleNamespace(st_mode=stat.S_IFREG | 0o755, st_uid=0))
    check = Mock(return_value=SimpleNamespace(returncode=returncode))
    execute = Mock()
    monkeypatch.setattr(privileges['subprocess'], 'run', check)
    monkeypatch.setattr(os, 'execve', execute)
    if returncode:
        with pytest.raises(ValueError, match='noninteractive'):
            privileges['launch'](program, ['vm', 'status'])
        execute.assert_not_called()
    else:
        privileges['launch'](program, ['vm', 'status'])
        assert execute.call_args.args[1] == ['/usr/bin/pkexec', program, 'vm', 'status']
    command = check.call_args.args[0]
    assert '--allow-user-interaction' not in command
    assert '--enable-internal-agent' not in command
    assert command[command.index('--process') + 1].count(',') == 2
    assert '--detail' not in command
    assert command[2] == 'com.puffyslippers.onpc.development.' + name


def test_arbitrary_program_refused_without_authority_request(monkeypatch):
    check = Mock()
    monkeypatch.setattr(privileges['subprocess'], 'run', check)
    with pytest.raises(ValueError):
        privileges['check']('/usr/bin/python3')
    check.assert_not_called()


@pytest.mark.parametrize('filename,name', [
    ('50-onpc-test-runner.rules', 'test-runner'),
    ('50-onpc-diagnostics.rules', 'diagnostics'),
    ('50-onpc-test-artifacts.rules', 'test-artifacts'),
    ('50-onpc-screenshot-export.rules', 'export-screenshot'),
    ('50-onpc-setup.rules', 'setup'),
])
@pytest.mark.parametrize('override,expected', [
    ({}, 'yes'), ({'user': None, 'program': None}, 'yes'),
    ({'user': None}, 'no'), ({'program': '/usr/bin/python3'}, 'no'),
    ({'active': False}, 'no'), ({'local': False}, 'no'), ({'admin': False}, 'no'),
    ({'id': 'org.freedesktop.policykit.exec'}, 'abstain'),
])
def test_installed_actions_allow_detail_free_checks_and_deny_excluded_callers(filename, name, override, expected):
    request = dict(id='com.puffyslippers.onpc.development.' + name,
                   program='/usr/local/libexec/onpc-' + name,
                   user='root', local=True, active=True, admin=True)
    request.update(override)
    script = '''const fs=require('fs'), vm=require('vm');
const r=JSON.parse(process.argv[1]); let rule;
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), {
polkit:{addRule:f=>rule=f, Result:{YES:'yes',NO:'no'}}});
const result=rule({id:r.id,lookup:k=>r[k]}, {
local:r.local,active:r.active,isInGroup:g=>g==='sudo' && r.admin});
process.stdout.write(result || 'abstain');'''
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(['/usr/bin/node', '-e', script, json.dumps(request), str(root / 'config' / filename)],
                            text=True, capture_output=True, check=True)
    assert result.stdout == expected
