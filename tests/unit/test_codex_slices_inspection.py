"""Preapproved inspection cannot dispatch workers, write state or load injected Python."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / 'tools/codex_slices.py'
SPEC = importlib.util.spec_from_file_location('slice_inspection', LAUNCHER)
loop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(loop)


@pytest.mark.parametrize('args, exit_code', [
    (['--help'], 0), (['-h'], 0), (['--help', 'start'], 0),
    (['--help', '--command', 'arbitrary'], 0),
    (['status'], None), (['status', '--reconciled'], None),
    (['status', '--max-slices', '1', '--max-api-retries', '2'], None),
    (['status', 'start'], 2), (['status', 'run'], 2), (['status', 'stop'], 2),
    (['status', 'kill'], 2), (['status', 'resume'], 2), (['status', 'restart'], 2),
    (['status', '--restart-of', 'old-run', '--request-id', '718e11b8-1c72-471d-9222-fb2b37283ed4'], 2),
    (['status', '-c', 'arbitrary'], 2), (['status', '--command', 'arbitrary'], 2),
    (['status', '--max-sl', '1'], 2),
])
@pytest.mark.parametrize('saved', [False, True])
def test_inspection_cannot_mutate_or_dispatch_even_with_trailing_arguments(
        tmp_path, monkeypatch, capsys, args, exit_code, saved):
    state = {'status': 'needs-review', 'reason': 'unconfirmed-handoff'}
    storage = tmp_path / loop.STORAGE
    if saved:
        storage.mkdir(parents=True)
        (storage / 'state.json').write_text(json.dumps(state))
    before = {str(path.relative_to(tmp_path)): path.read_bytes()
              for path in tmp_path.rglob('*') if path.is_file()}

    def refuse(*_args, **_kwargs):
        pytest.fail('inspection attempted a write, worker or control operation')

    for name in ('run', 'wait_for_restart', 'preflight', 'private_directory', 'write_json', 'exclusive'):
        monkeypatch.setattr(loop, name, refuse)
    monkeypatch.setattr(loop.subprocess, 'Popen', refuse)
    if exit_code is None:
        assert loop.main(args, root=tmp_path) == 0
        assert json.loads(capsys.readouterr().out) == (state if saved else {'status': 'not-started'})
    else:
        with pytest.raises(SystemExit) as error:
            loop.main(args, root=tmp_path)
        assert error.value.code == exit_code
    after = {str(path.relative_to(tmp_path)): path.read_bytes()
             for path in tmp_path.rglob('*') if path.is_file()}
    assert before == after
    assert storage.exists() == saved


@pytest.mark.parametrize('help_flag', ['--help', '-h'])
def test_executable_help_ignores_python_environment_and_stdin(tmp_path, help_flag):
    # The direct executable is the policy boundary. Exercise its actual shebang,
    # without a test interpreter that would conceal missing isolation flags.
    injected = tmp_path / 'argparse.py'
    injected.write_text("raise RuntimeError('injected-python-module')\n")
    env = {**os.environ, 'PYTHONPATH': str(tmp_path), 'PYTHONHOME': str(tmp_path),
           'PYTHONINSPECT': '1'}
    result = subprocess.run([str(LAUNCHER), help_flag], cwd=tmp_path, env=env,
                            input="raise RuntimeError('injected-stdin')\n",
                            text=True, capture_output=True, check=True, timeout=10)
    assert 'usage:' in result.stdout
    assert not result.stderr
    assert not (tmp_path / loop.STORAGE).exists()
    assert not (tmp_path / '__pycache__').exists()


def test_status_highlights_top_level_status_on_tty(tmp_path, monkeypatch, capsys):
    storage = tmp_path / loop.STORAGE
    storage.mkdir(parents=True)
    state = {'attempt': 'slice-1', 'reason': 'slice', 'status': 'running'}
    (storage / 'state.json').write_text(json.dumps(state))
    monkeypatch.setattr(loop, 'status_inspect_color', lambda: True)

    assert loop.main(['status'], root=tmp_path) == 0
    output = capsys.readouterr().out.rstrip('\n')
    color = loop.STATUS_COLORS['running']
    assert f'{color}  "status": "running"{loop.STATUS_RESET}' in output
    assert '  "attempt": "slice-1"' in output
    stripped = output.replace(f'{color}', '').replace(loop.STATUS_RESET, '')
    assert json.loads(stripped) == state


def test_status_skips_highlight_without_tty(monkeypatch):
    monkeypatch.setattr(loop.sys.stdout, 'isatty', lambda: False)
    monkeypatch.setenv('TERM', 'xterm')
    monkeypatch.delenv('NO_COLOR', raising=False)
    report = loop.format_status_report({'status': 'blocked', 'reason': 'approval'})
    assert report == '{\n  "reason": "approval",\n  "status": "blocked"\n}'
    assert loop.STATUS_RESET not in report
