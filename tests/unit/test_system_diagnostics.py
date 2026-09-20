"""Exercise actual diagnostic argument boundaries, filesystem reads and Polkit."""
import json
import os
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from tests.support.paths import ROOT
diag = runpy.run_path(str(ROOT / 'tools/onpc-diagnostics'))


@pytest.mark.parametrize('argv', [
    ['journal', '--vacuum-time=1s'], ['journal', '--rotate'], ['journal', '--flush'],
    ['journal', '--output=/tmp/path'], ['journal', '--lines=-1'],
    ['systemctl', 'restart', 'sshd'], ['systemctl', 'edit', 'sshd'],
    ['systemctl', 'show', '--root=/tmp'], ['systemctl', 'status', '--pager-end'],
    ['systemctl', 'status', '--property=ExecStart'], ['systemctl', 'cat', '/tmp/unit'],
    ['processes', '-e', 'arbitrary'], ['network', 'link', 'delete'], ['packages', '--install'],
    ['applications', '/home/child'], ['applications', '1001', '/etc/shadow'],
    ['applications', '--exec', '1001'], ['applications', '0'],
    ['launcher', '1001', '../secret.desktop'], ['launcher', '1001', '/etc/shadow'],
    ['launcher', '1001', 'app.desktop', '--exec'], ['launcher', '0', 'app.desktop'],
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


@pytest.mark.parametrize('uid,home', [
    (0, '/root'), (999, '/home/service'), (2 ** 32 - 1, '/home/child'),
    (1001, '/etc'), (1001, '/home/..'), (1001, '/home/child/../other'),
    (1001, '/home/child/'), (1001, '/home/child\n'),
])
def test_applications_refuses_unrelated_paths(uid, home, monkeypatch):
    monkeypatch.setattr(diag['pwd'], 'getpwuid',
                        lambda value: SimpleNamespace(pw_uid=value, pw_dir=home))
    with pytest.raises(ValueError):
        diag['application_parts'](uid)


def test_applications_uses_nss_home_and_refuses_unknown_account(monkeypatch):
    lookup = Mock(return_value=SimpleNamespace(pw_uid=1001, pw_dir='/home/child'))
    monkeypatch.setattr(diag['pwd'], 'getpwuid', lookup)
    assert diag['application_parts'](1001) == ['home', 'child', 'Applications']
    lookup.side_effect = KeyError(1001)
    with pytest.raises(ValueError):
        diag['application_parts'](1001)


def test_applications_lists_metadata_without_following_entries(tmp_path, monkeypatch, capsys):
    directory = tmp_path / 'Applications'
    directory.mkdir()
    regular = directory / 'Lunar Client.AppImage'
    regular.write_bytes(b'private contents')
    regular.chmod(0o755)
    (directory / 'folder').mkdir()
    (directory / 'link').symlink_to(tmp_path)
    os.mkfifo(directory / 'fifo')
    reader = diag['read_applications']
    monkeypatch.setitem(reader.__globals__, 'application_parts',
                        lambda uid: directory.parts[1:])
    assert diag['main'](['applications', '1001']) == 0
    entries = json.loads(capsys.readouterr().out)
    assert [entry['name'] for entry in entries] == ['Lunar Client.AppImage', 'fifo', 'folder', 'link']
    assert [entry['kind'] for entry in entries] == ['file', 'special', 'directory', 'symlink']
    assert entries[0]['mode'] == '0o755'
    assert entries[0]['bytes'] == len(b'private contents')


def test_applications_refuses_symlinked_directory_components(tmp_path, monkeypatch):
    actual = tmp_path / 'actual'
    actual.mkdir()
    (actual / 'Applications').mkdir()
    linked = tmp_path / 'linked'
    linked.symlink_to(actual, target_is_directory=True)
    reader = diag['read_applications']
    for path in (linked, linked / 'Applications'):
        monkeypatch.setitem(reader.__globals__, 'application_parts', lambda uid: path.parts[1:])
        with pytest.raises(OSError):
            reader(1001)


def test_applications_refuses_excess_entries_without_partial_output(tmp_path, monkeypatch, capsys):
    reader = diag['read_applications']
    monkeypatch.setitem(reader.__globals__, 'application_parts', lambda uid: tmp_path.parts[1:])
    entry = Mock(name='entry')
    entry.name = 'app'
    entry.stat.return_value = SimpleNamespace(st_mode=0o100755, st_size=1)
    scan = MagicMock()
    scan.__enter__.return_value = iter([entry] * 4097)
    monkeypatch.setattr(diag['os'], 'scandir', lambda fd: scan)
    with pytest.raises(ValueError, match='entry limit'):
        reader(1001)
    assert capsys.readouterr().out == ''


def test_launcher_reports_only_launch_metadata(tmp_path, monkeypatch, capsys):
    reader = diag['read_launcher']
    monkeypatch.setitem(reader.__globals__, 'application_parts',
                        lambda uid: [*tmp_path.parts[1:], 'Applications'])
    directory = tmp_path / '.local/share/applications'
    directory.mkdir(parents=True)
    (directory / 'lunar.desktop').write_text(
        '[Desktop Entry]\nType=Application\nExec=AppImageLauncher /apps/Lunar.AppImage\n'
        'Name=Private label\nX-Unrelated=private value\n'
        '[Desktop Action Other]\nExec=unrelated\n')
    assert diag['main'](['launcher', '1001', 'lunar.desktop']) == 0
    assert json.loads(capsys.readouterr().out) == {
        'Type': 'Application', 'Exec': 'AppImageLauncher /apps/Lunar.AppImage'}


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'fifo', 'oversized', 'invalid', 'parent-link'])
def test_launcher_refuses_unsafe_files(tmp_path, monkeypatch, kind):
    reader = diag['read_launcher']
    monkeypatch.setitem(reader.__globals__, 'application_parts',
                        lambda uid: [*tmp_path.parts[1:], 'Applications'])
    directory = tmp_path / '.local/share/applications'
    directory.mkdir(parents=True)
    source = tmp_path / 'source'
    source.write_text('[Desktop Entry]\nType=Application\n')
    target = directory / 'app.desktop'
    if kind == 'symlink':
        target.symlink_to(source)
    elif kind == 'hardlink':
        os.link(source, target)
    elif kind == 'fifo':
        os.mkfifo(target)
    elif kind == 'oversized':
        target.write_bytes(b'x' * 65537)
    elif kind == 'invalid':
        target.write_bytes(b'\xff')
    else:
        directory.rmdir()
        directory.symlink_to(tmp_path, target_is_directory=True)
        (tmp_path / 'app.desktop').write_text(source.read_text())
    with pytest.raises((ValueError, OSError)):
        reader(1001, 'app.desktop')


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
