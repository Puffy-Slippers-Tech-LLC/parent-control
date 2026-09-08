"""Read-only aliases do not forward tool options that execute or write."""
import runpy
import subprocess
from pathlib import Path

import pytest

reader = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/read-only'))


@pytest.mark.parametrize('args', [
    ['search', '--pre=/tmp/evil', 'needle'], ['sort', '-o', '/tmp/output'],
    ['unique', '--output=/tmp/file'], ['gzip', '--force', 'file'],
    ['slice', '1', '0'], ['slice', '1e', '10'], ['slice', '1', '10', '--expression=e'],
    ['fetch', 'file:///etc/shadow'], ['fetch', 'https://user:password@example.com'],
    ['fetch', 'https://example.com', '--output=/tmp/file'], ['fetch', 'https://example.com', '-XPOST'],
])
def test_mutating_options_refused(args):
    with pytest.raises(ValueError):
        reader['command'](args)


def test_fetch_is_fixed_get_with_no_config_credentials_redirect_protocol_or_output_override():
    command = reader['command'](['fetch', 'https://example.com/?query=x&y=z'])
    assert command[:4] == ['/usr/bin/curl', '--disable', '--globoff', '-fsSL']
    assert command[-2:] == ['--', 'https://example.com/?query=x&y=z']
    assert '--proto-redir' in command


def test_preprocessor_text_is_only_a_search_pattern():
    command = reader['command'](['search', '--', '--pre=/tmp/evil', '.'])
    assert command[-3:] == ['--', '--pre=/tmp/evil', '.']


def test_filter_paths_cannot_be_output_options():
    assert reader['command'](['sort', '--', '-o', 'file'])[-3:] == ['--', '-o', 'file']
    assert reader['command'](['slice', '2', '9', 'file']) == [
        '/usr/bin/sed', '-n', '2,9p', '--', 'file']


@pytest.mark.parametrize('action', ['search', 'files'])
def test_path_globs_select_files_and_directories_without_broadening(tmp_path, monkeypatch, action):
    monkeypatch.chdir(tmp_path)
    for name in ('integration/fixture.py', 'integration/fixture dir/child.py',
                 'fixtures/literal.py', 'unit/test_graphical.py', 'integration/other.py'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('needle\n')
    args = [action, '--path-glob', 'integration/fixture*',
            '--path-glob', 'unit/test_graphical*']
    if action == 'search':
        args.append('needle')
    args.append('fixtures')
    result = subprocess.run(reader['command'](args), capture_output=True, text=True,
                            check=True, timeout=10)
    paths = {line.split(':', 1)[0] for line in result.stdout.splitlines()}
    assert paths == {'integration/fixture.py', 'integration/fixture dir/child.py',
                     'fixtures/literal.py', 'unit/test_graphical.py'}


@pytest.mark.parametrize('action', ['search', 'files'])
def test_unmatched_path_glob_refuses_even_with_literal_paths(tmp_path, monkeypatch, action):
    monkeypatch.chdir(tmp_path)
    args = [action, '--path-glob', 'missing*']
    if action == 'search':
        args.append('needle')
    with pytest.raises(ValueError, match='matched no paths'):
        reader['command']([*args, '.'])


def test_glob_matches_cannot_inject_options_or_shell_commands(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    name = '-e$(touch sentinel)'
    (tmp_path / name).write_text('needle\n')
    result = subprocess.run(reader['command'](['search', '--path-glob=-e*', 'needle']),
                            capture_output=True, text=True, check=True, timeout=10)
    assert 'needle' in result.stdout
    assert not (tmp_path / 'sentinel').exists()


def test_literal_wildcard_path_is_not_implicitly_expanded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'selected.txt').touch()
    assert reader['command'](['search', 'needle', '*.txt'])[-1] == '*.txt'


def test_unmatched_glob_diagnostic_does_not_echo_inputs(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reader['os'], 'geteuid', lambda: 1000)
    assert reader['main'](['search', '--path-glob', 'private-name*', 'private-pattern']) == 2
    captured = capsys.readouterr()
    assert 'filename pattern matched no paths' in captured.err
    assert 'private-' not in captured.err
    assert not captured.out
