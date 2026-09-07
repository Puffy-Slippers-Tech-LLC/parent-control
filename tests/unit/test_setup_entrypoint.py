"""Exercise the real master in a disposable checkout with harmless modules."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / 'checkout with spaces'
    for name in ('tools', 'child', 'tests/integration', 'bin'):
        (root / name).mkdir(parents=True)
    shutil.copy2(ROOT / 'setup.sh', root / 'setup.sh')
    (root / 'Makefile').touch()
    (root / 'child/preview').touch(mode=0o755)
    stub = '''import json, os, pathlib, sys
name = pathlib.Path(__file__).name
with open(os.environ['ONPC_SETUP_TRACE'], 'a') as stream:
    stream.write(json.dumps([name, sys.argv[1:], os.getcwd()]) + '\\n')
sys.exit(7 if os.environ.get('ONPC_SETUP_FAIL') == name else 0)
'''
    for name in ('install_test_runner.py', 'install_graphical_test_policy.py', 'install_codex_rules.py'):
        (root / 'tools' / name).write_text(stub)
    (root / 'tests/integration/prepare_host.py').write_text(stub)
    for name in ('tools/setup_dependencies.sh', 'tests/integration/prepare-vm'):
        (root / name).write_text(
            '#!/bin/bash\n'
            '/usr/bin/python3 -B "$(dirname -- "${BASH_SOURCE[0]}")/record.py"\n')
        (root / name).with_name('record.py').write_text(stub)
    # Privilege dispatch is exercised, but this fixture never elevates privileges.
    pkexec = root / 'bin/pkexec'
    pkexec.write_text('#!/bin/sh\n[ "$1" = "--keep-cwd" ] || exit 9\nshift\nexec "$@"\n')
    pkexec.chmod(0o755)
    make = root / 'bin/make'
    make.write_text('#!/usr/bin/python3\n' + stub)
    make.chmod(0o755)
    return root


def run_setup(root, *args, failure=''):
    trace = root / 'trace.jsonl'
    trace.write_text('')
    result = subprocess.run(
        ['/bin/bash', str(root / 'setup.sh'), *args], cwd=root.parent,
        env={**os.environ, 'PATH': f'{root / "bin"}:{os.environ["PATH"]}',
             'ONPC_SETUP_TRACE': str(trace), 'ONPC_SETUP_FAIL': failure},
        capture_output=True, text=True, timeout=10,
    )
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    assert all(event[2] == str(root) for event in events)
    return result, [(name, args) for name, args, _cwd in events]


RULES = [('install_codex_rules.py', ['--system']), ('install_codex_rules.py', [])]
TOOLS = [('install_test_runner.py', []), ('install_graphical_test_policy.py', []), *RULES]


@pytest.mark.parametrize('mode,expected', [
    ([], [('record.py', []), *TOOLS]),
    (['--dependencies-only'], [('record.py', [])]),
    (['--test-tools-only'], TOOLS),
    (['--codex-rules-only'], RULES),
    (['--prepare-host'], [('prepare_host.py', []), *TOOLS]),
    (['--prepare-vm'], [('record.py', [])]),
    (['--install-extension'], [('make', ['--no-print-directory', '_install-development-extension'])]),
])
def test_modes_repeat_complete_scope_from_any_working_directory(checkout, mode, expected):
    for _ in range(2):
        result, events = run_setup(checkout, *mode)
        assert result.returncode == 0, result.stderr
        assert events == expected


@pytest.mark.parametrize('mode,failure,expected', [
    (['--prepare-host'], 'prepare_host.py', [('prepare_host.py', [])]),
    ([], 'record.py', [('record.py', [])]),
    (['--test-tools-only'], 'install_test_runner.py', [('install_test_runner.py', [])]),
    (['--test-tools-only'], 'install_graphical_test_policy.py', TOOLS[:2]),
    (['--codex-rules-only'], 'install_codex_rules.py', RULES[:1]),
])
def test_failure_stops_dependent_setup_and_can_be_retried(checkout, mode, failure, expected):
    result, events = run_setup(checkout, *mode, failure=failure)
    assert result.returncode == 7
    assert events == expected
    assert 'completed successfully' not in result.stdout
    result, _events = run_setup(checkout, *mode)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('args,code', [
    (['--help'], 0), (['--unknown'], 2), (['--test-tools-only', '--prepare-host'], 2),
])
def test_help_and_invalid_selection_have_no_setup_side_effects(checkout, args, code):
    result, events = run_setup(checkout, *args)
    assert result.returncode == code
    assert not events


@pytest.mark.parametrize('target,mode', [
    ('prep-host', '--prepare-host'), ('prep-vm', '--prepare-vm'),
    ('install-extension', '--install-extension'),
])
def test_make_setup_aliases_only_delegate_to_master(checkout, target, mode):
    shutil.copy2(ROOT / 'Makefile', checkout / 'Makefile')
    (checkout / 'setup.sh').write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    result = subprocess.run(['make', '--no-print-directory', target], cwd=checkout,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == mode
