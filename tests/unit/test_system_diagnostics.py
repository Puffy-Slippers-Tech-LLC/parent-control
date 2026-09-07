"""Exercise actual diagnostic argument boundaries, filesystem reads and Polkit."""
import json
import os
from pathlib import Path
import runpy
import subprocess
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
diag = runpy.run_path(str(ROOT / 'tools/onpc-diagnostics'))


@pytest.mark.parametrize('argv', [
    ['journal', '--vacuum-time=1s'], ['journal', '--rotate'], ['journal', '--flush'],
    ['journal', '--output=/tmp/path'], ['journal', '--lines=-1'],
    ['systemctl', 'restart', 'sshd'], ['systemctl', 'edit', 'sshd'],
    ['systemctl', 'show', '--root=/tmp'], ['systemctl', 'status', '--pager-end'],
    ['systemctl', 'status', '--property=ExecStart'], ['systemctl', 'cat', '/tmp/unit'],
    ['processes', '-e', 'arbitrary'], ['network', 'link', 'delete'], ['packages', '--install'],
])
def test_write_exec_and_option_injection_rejected(argv, monkeypatch):
    execute = Mock()
    monkeypatch.setattr(diag['subprocess'], 'run', execute)
    assert diag['main'](argv) == 2
    execute.assert_not_called()


def test_journal_patterns_and_times_are_literal_options():
    args = diag['arguments'](['journal', '--unit', 'oh-no-*', '--since', '1 hour ago',
                              '--boot=-1', '--lines=600'])
    selected = diag['command'](args)
    assert '--unit=oh-no-*' in selected
    assert '--since=1 hour ago' in selected
    assert '--boot=-1' in selected
    assert '--no-pager' in selected


def test_diagnostics_never_inherit_pager_or_injection(monkeypatch):
    monkeypatch.setenv('SYSTEMD_PAGER', '/tmp/evil')
    monkeypatch.setenv('LD_PRELOAD', '/tmp/evil')
    execute = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(diag['subprocess'], 'run', execute)
    assert diag['main'](['systemctl', 'status', 'sshd.service']) == 0
    args = execute.call_args
    assert '/tmp/evil' not in args.kwargs['env'].values()
    assert '--no-ask-password' in args.args[0]
    assert args.kwargs['timeout'] == 60


@pytest.mark.parametrize('path', ['/etc/shadow', '/dev/sda', '/proc/1/mem',
                                  '/var/log/../secret', '/var/log//file', 'relative'])
def test_unrelated_and_special_paths_not_approved(path):
    with pytest.raises(ValueError):
        diag['file_parts'](path)


def test_open_refuses_symlinks_hardlinks_and_fifo(tmp_path, monkeypatch):
    reader = diag['read_file']
    monkeypatch.setitem(reader.__globals__, 'file_parts', lambda path: Path(path).parts[1:])
    regular = tmp_path / 'source'
    regular.write_text('diagnostic')
    link = tmp_path / 'link'
    link.symlink_to(regular)
    fifo = tmp_path / 'fifo'
    os.mkfifo(fifo)
    hard = tmp_path / 'hard'
    os.link(regular, hard)
    for path in (link, fifo, hard):
        with pytest.raises((ValueError, OSError)):
            reader(diag['arguments'](['read', str(path)]))


@pytest.mark.parametrize('override,allowed', [
    ({}, True), ({'program': '/usr/bin/journalctl'}, False),
    ({'program': '/tmp/onpc-diagnostics'}, False), ({'user': 'other'}, False),
    ({'local': False}, False), ({'active': False}, False), ({'admin': False}, False),
])
def test_diagnostic_polkit_scope(override, allowed):
    request = dict(id='com.puffyslippers.onpc.development.diagnostics', program='/usr/local/libexec/onpc-diagnostics',
                   user='root', local=True, active=True, admin=True)
    request.update(override)
    script = '''const fs = require('fs'), vm = require('vm');
const r = JSON.parse(process.argv[1]); let rule;
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), {
polkit: {addRule: f => rule = f, Result: {YES: 'yes'}}});
process.stdout.write(rule({id:r.id, lookup:k=>r[k]}, {
local:r.local, active:r.active, isInGroup:g=>g==='sudo' && r.admin}) === 'yes' ? 'yes' : 'no');'''
    result = subprocess.run(['/usr/bin/node', '-e', script, json.dumps(request),
                             str(ROOT / 'config/50-onpc-diagnostics.rules')],
                            text=True, capture_output=True, check=True)
    assert result.stdout == ('yes' if allowed else 'no')
